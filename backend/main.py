import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from neo4j import AsyncGraphDatabase

from database import conn_manager
from models import CypherQuery, GraphResponse, NodeDTO, RelationshipDTO, PresetCreate, PresetUpdate, PresetResponse, AnalyzeRequest, AnalyzeResponse, SettingsUpdate, NlQueryRequest, NlQueryResponse, Nl2CypherRequest, Nl2CypherResponse, HistoryAddRequest, SemanticQueryRequest, SemanticNLQueryRequest, SemanticNLQueryResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await conn_manager.close_all()


app = FastAPI(title="GraphVI API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def strip_prefix_middleware(request, call_next):
    """Strip deployment subpath prefix from API requests.

    When Nginx proxies /<prefix>/api/xxx to the backend, the path arrives
    as /<prefix>/api/xxx, which doesn't match any API route. This middleware
    rewrites /<prefix>/api/xxx → /api/xxx before routing.
    """
    path = request.url.path
    if path.count("/") >= 3 and "/api/" in path:
        api_idx = path.index("/api/")
        if api_idx > 0:
            request.scope["path"] = path[api_idx:]
            request.scope["root_path"] = ""
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize_props(props: dict) -> dict:
    """Convert Neo4j temporal/spatial types to strings for JSON serialization."""
    result = {}
    for k, v in props.items():
        if isinstance(v, (list, tuple)):
            result[k] = [str(i) for i in v]
        elif isinstance(v, dict):
            result[k] = _serialize_props(v)
        elif type(v).__module__.startswith("neo4j."):
            result[k] = str(v)
        else:
            result[k] = v
    return result


def _extract_node(node) -> NodeDTO:
    labels = list(node.labels) if hasattr(node, "labels") else (node.get("labels") or [])
    props = _serialize_props(dict(node))
    props.pop("elementId", None)
    props.pop("embedding", None)
    node_id = str(node.element_id) if hasattr(node, "element_id") else str(id(node))
    caption = props.get("name") or props.get("title") or (list(props.values())[0] if props else "")
    return NodeDTO(id=node_id, labels=labels, properties=props, caption=str(caption))


def _extract_relationship(rel) -> RelationshipDTO:
    props = _serialize_props(dict(rel))
    props.pop("elementId", None)
    rel_id = str(rel.element_id) if hasattr(rel, "element_id") else str(id(rel))
    source_id = str(rel.start_node.element_id) if hasattr(rel, "start_node") else str(rel.get("start_node"))
    target_id = str(rel.end_node.element_id) if hasattr(rel, "end_node") else str(rel.get("end_node"))
    return RelationshipDTO(
        id=rel_id,
        type=rel.type,
        source=source_id,
        target=target_id,
        properties=props,
    )


def _parse_graph_data(records: list) -> GraphResponse:
    nodes_map: dict[str, NodeDTO] = {}
    rels_map: dict[str, RelationshipDTO] = {}

    def walk(value):
        if value is None:
            return
        if hasattr(value, "labels") and hasattr(value, "element_id"):
            node = _extract_node(value)
            if node.id not in nodes_map:
                nodes_map[node.id] = node
            return
        if hasattr(value, "type") and hasattr(value, "start_node") and hasattr(value, "end_node"):
            rel = _extract_relationship(value)
            if rel.id not in rels_map:
                rels_map[rel.id] = rel
                walk(value.start_node)
                walk(value.end_node)
            return
        # Handle Neo4j Path object (variable-length relationships)
        if hasattr(value, "nodes") and hasattr(value, "relationships"):
            for node in value.nodes:
                walk(node)
            for rel in value.relationships:
                walk(rel)
            return
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)
        elif hasattr(value, "values"):
            for v in value.values():
                walk(v)

    for record in records:
        for v in record.values():
            walk(v)

    return GraphResponse(nodes=list(nodes_map.values()), relationships=list(rels_map.values()))


# ─── Presets API ─────────────────────────────────────────────────────────────
from presets_db import init_db, get_all, create, update as update_preset, delete as delete_preset
from settings_db import init_settings_table, get_all_settings, set_multiple_settings
from history_db import init_history_table, add_history, get_history, delete_history, clear_history

init_db()
init_settings_table()
init_history_table()


@app.get("/api/presets", response_model=list[PresetResponse])
async def list_presets():
    return get_all()


@app.post("/api/presets", response_model=PresetResponse, status_code=201)
async def create_preset(body: PresetCreate):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return create(body.question.strip(), body.cypher)


@app.put("/api/presets/{preset_id}", response_model=PresetResponse)
async def update_preset_endpoint(preset_id: int, body: PresetUpdate):
    result = update_preset(preset_id, body.question, body.cypher)
    if not result:
        raise HTTPException(status_code=404, detail="Preset not found")
    return result


@app.delete("/api/presets/{preset_id}", status_code=204)
async def delete_preset_endpoint(preset_id: int):
    delete_preset(preset_id)


# ─── AI Analyse API ──────────────────────────────────────────────────────────
from llm_service import call_llm_stream, test_llm_connection


@app.post("/api/analyze/test")
async def analyze_test(body: dict | None = None):
    """Test LLM connection with a simple prompt"""
    try:
        overrides = body or {}
        reply = await test_llm_connection(overrides or None)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"LLM test failed: {e}")


@app.post("/api/analyze/stream")
async def analyze_graph_stream(body: AnalyzeRequest):
    if not body.nodes and not body.relationships:
        raise HTTPException(status_code=400, detail="No graph data to analyze")
    try:
        return StreamingResponse(
            call_llm_stream(body.nodes, body.relationships, body.custom_prompt),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.warning("AI analyse failed: %s", e)
        raise HTTPException(status_code=500, detail=f"AI analyse error: {e}")


# ─── History API ─────────────────────────────────────────────────────────────
@app.get("/api/history")
async def list_history(limit: int = 50):
    from settings_db import get_all_settings
    s = get_all_settings()
    uri = s.get("neo4j_uri", "")
    db = s.get("neo4j_database", "")
    return get_history(uri, db, limit)


@app.post("/api/history")
async def save_history(body: HistoryAddRequest):
    from settings_db import get_all_settings
    s = get_all_settings()
    uri = s.get("neo4j_uri", "")
    db = s.get("neo4j_database", "")
    add_history(body.question, body.cypher, body.type, uri, db)
    return {"status": "ok"}


@app.delete("/api/history/{history_id}")
async def delete_history_item(history_id: int):
    delete_history(history_id)
    return {"status": "ok"}


@app.delete("/api/history")
async def clear_history_all():
    from settings_db import get_all_settings
    s = get_all_settings()
    uri = s.get("neo4j_uri", "")
    db = s.get("neo4j_database", "")
    clear_history(uri, db)
    return {"status": "ok"}


# ─── Settings API ────────────────────────────────────────────────────────────
@app.get("/api/settings")
async def list_settings():
    return get_all_settings()


@app.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    set_multiple_settings(body.settings)
    return {"status": "ok"}


@app.post("/api/query/nl", response_model=NlQueryResponse)
async def execute_nl_query(body: NlQueryRequest):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    from nl2cypher import nl2cypher
    try:
        result = await nl2cypher(body.question.strip())
        graph = _parse_graph_data(result["records"])
        return NlQueryResponse(
            nodes=[n.model_dump() for n in graph.nodes],
            relationships=[r.model_dump() for r in graph.relationships],
            generated_cypher=result["generated_cypher"],
        )
    except Exception as e:
        logger.warning("NL query failed: %s", e)
        raise HTTPException(status_code=500, detail=f"NL query error: {e}")


@app.post("/api/nl2cypher", response_model=Nl2CypherResponse)
def nl2cypher_api(body: Nl2CypherRequest):
    """Generate Cypher from natural language, return only the Cypher statement."""
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    from nl2cypher import generate_cypher_only
    try:
        cypher = generate_cypher_only(body.question.strip())
        return Nl2CypherResponse(cypher=cypher)
    except Exception as e:
        logger.warning("NL2Cypher failed: %s", e)
        raise HTTPException(status_code=500, detail=f"NL2Cypher error: {e}")


@app.post("/api/query", response_model=GraphResponse)
async def execute_query(body: CypherQuery):
    if not body.cypher or not body.cypher.strip():
        raise HTTPException(status_code=400, detail="Cypher query cannot be empty")
    try:
        records, summary = await conn_manager.run_query(cypher=body.cypher)
        if records:
            return _parse_graph_data(records)
        return GraphResponse(nodes=[], relationships=[])
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Query failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Query error: {e}")


@app.post("/api/query/semantic", response_model=GraphResponse)
async def semantic_query(body: SemanticQueryRequest):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        from semantic_search import semantic_search
        return await semantic_search(body.question.strip(), body.top_k)
    except Exception as e:
        logger.warning("Semantic query failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Semantic query error: {e}")


@app.post("/api/query/semantic/test")
async def semantic_test(body: dict | None = None):
    """Test embedding API connectivity. Checks: API reachable + model exists."""
    try:
        overrides = body or {}
        from settings_db import get_all_settings
        endpoint = overrides.get("embedding_endpoint") or get_all_settings().get("embedding_endpoint", "https://api.openai.com/v1")
        api_key = overrides.get("embedding_api_key") or get_all_settings().get("embedding_api_key", "")
        model = overrides.get("embedding_model") or get_all_settings().get("embedding_model", "text-embedding-3-small")
        vector_index = overrides.get("vector_index_name") or get_all_settings().get("vector_index_name", "entity_vector")

        if not api_key:
            raise ValueError("API Key 未配置")

        # 1. Test embedding API with a simple call
        from openai import OpenAI as OpenAIClient
        client = OpenAIClient(api_key=api_key, base_url=endpoint.rstrip("/") + "/")
        resp = client.embeddings.create(model=model, input="test")
        dims = len(resp.data[0].embedding)

        # 2. Check if vector index exists in Neo4j
        from database import conn_manager as cm
        index_ok = False
        try:
            records, _ = await cm.run_query(
                "SHOW VECTOR INDEXES WHERE name = $name",
                parameters={"name": vector_index},
            )
            index_ok = len(records) > 0
        except Exception:
            pass

        parts = [f"Embedding API 连接成功，模型 {model}，维度 {dims}"]
        if index_ok:
            parts.append(f"向量索引「{vector_index}」存在")
        else:
            parts.append(f"向量索引「{vector_index}」不存在，请在 Neo4j 中手动创建")

        return {"status": "ok", "detail": "；".join(parts), "dimensions": dims, "index_exists": index_ok}
    except Exception as e:
        msg = str(e)
        if "401" in msg or "unauthorized" in msg.lower() or "auth" in msg.lower():
            msg = "API Key 无效或权限不足"
        elif "404" in msg or "not found" in msg.lower():
            msg = f"模型不存在或 API 地址错误"
        elif "connect" in msg.lower() or "timeout" in msg.lower():
            msg = f"无法连接到 API 地址，请检查网络"
        raise HTTPException(status_code=400, detail=f"语义检索测试失败: {msg}")


@app.post("/api/query/semantic-nl", response_model=SemanticNLQueryResponse)
async def semantic_nl_query(body: SemanticNLQueryRequest):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        from semantic_search import semantic_nl_search
        graph, cypher = await semantic_nl_search(body.question.strip(), body.top_k)
        return SemanticNLQueryResponse(
            nodes=[n.model_dump() for n in graph.nodes],
            relationships=[r.model_dump() for r in graph.relationships],
            generated_cypher=cypher,
        )
    except Exception as e:
        logger.warning("Semantic NL query failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Semantic NL query error: {e}")


class ConnectBody(BaseModel):
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"


@app.post("/api/connect")
async def test_connect(body: ConnectBody, save: bool = False):
    """Test Neo4j connection. If save=True, persist config and reconnect."""
    try:
        driver = AsyncGraphDatabase.driver(
            body.uri,
            auth=(body.username, body.password),
            max_connection_lifetime=3600,
            max_connection_pool_size=10,
        )
        async with driver.session(database=body.database) as session:
            await session.run("RETURN 1 AS ok")
        await driver.close()

        if save:
            set_multiple_settings({
                "neo4j_uri": body.uri,
                "neo4j_username": body.username,
                "neo4j_password": body.password,
                "neo4j_database": body.database,
            })
            from nl2cypher import invalidate_schema_cache
            await conn_manager.reconnect()
            invalidate_schema_cache()

        return {"status": "connected", "message": "Neo4j 连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {e}")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files with SPA fallback for Vue Router routes.
# Must be defined AFTER all API routes so they take precedence.
# Catch-all route: serve matching file, or index.html for SPA routing.
dist_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist_path.exists():
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        # Try direct path, then strip subpath prefixes (for /graphvi/assets/xxx → /assets/xxx)
        target = dist_path / full_path if full_path else dist_path
        if target.is_file():
            return FileResponse(target)
        slash = full_path.find("/")
        if slash > 0:
            alt = dist_path / full_path[slash + 1:]
            if alt.is_file():
                return FileResponse(alt)
        return FileResponse(dist_path / "index.html")

    logger.info("Serving frontend from %s", dist_path)
else:
    logger.warning("Frontend dist not found at %s — API only", dist_path)

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from neo4j import AsyncGraphDatabase

from backend.database import conn_manager
from backend.models import CypherQuery, GraphResponse, NodeDTO, RelationshipDTO, PresetCreate, PresetUpdate, PresetResponse, AnalyzeRequest, AnalyzeResponse, SettingsUpdate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await conn_manager.close_all()


app = FastAPI(title="GraphVI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_node(node) -> NodeDTO:
    labels = list(node.labels) if hasattr(node, "labels") else (node.get("labels") or [])
    props = dict(node)
    props.pop("elementId", None)
    node_id = str(node.element_id) if hasattr(node, "element_id") else str(id(node))
    caption = props.get("name") or props.get("title") or (list(props.values())[0] if props else "")
    return NodeDTO(id=node_id, labels=labels, properties=props, caption=str(caption))


def _extract_relationship(rel) -> RelationshipDTO:
    props = dict(rel)
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
from backend.presets_db import init_db, get_all, create, update as update_preset, delete as delete_preset
from backend.settings_db import init_settings_table, get_all_settings, set_multiple_settings

init_db()
init_settings_table()


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
from backend.llm_service import call_llm_stream, test_llm_connection


@app.post("/api/analyze/test")
async def analyze_test():
    try:
        reply = await test_llm_connection()
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


# ─── Settings API ────────────────────────────────────────────────────────────
@app.get("/api/settings")
async def list_settings():
    return get_all_settings()


@app.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    set_multiple_settings(body.settings)
    return {"status": "ok"}


@app.post("/api/query", response_model=GraphResponse)
async def execute_query(body: CypherQuery):
    if not body.cypher or not body.cypher.strip():
        raise HTTPException(status_code=400, detail="Cypher query cannot be empty")
    try:
        records, summary = await conn_manager.run_query(cypher=body.cypher)
    except Exception as e:
        logger.warning("Query failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Query error: {e}")

    if not records:
        return GraphResponse(nodes=[], relationships=[])

    return _parse_graph_data(records)


class ConnectBody(BaseModel):
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"


@app.post("/api/connect")
async def test_connect(body: ConnectBody, save: bool = False):
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
            from backend.settings_db import set_multiple_settings
            set_multiple_settings({
                "neo4j_uri": body.uri,
                "neo4j_username": body.username,
                "neo4j_password": body.password,
                "neo4j_database": body.database,
            })
            await conn_manager.reconnect()

        return {"status": "connected", "message": "Neo4j 连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {e}")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Mount frontend static files AFTER all API routes (routes take precedence)
dist_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="frontend")
    logger.info("Serving frontend from %s", dist_path)
else:
    logger.warning("Frontend dist not found at %s — API only", dist_path)

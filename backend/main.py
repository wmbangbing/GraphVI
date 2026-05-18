import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Body

from database import conn_manager
from models import CypherQuery, ConnectConfig, GraphResponse, NodeDTO, RelationshipDTO

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


@app.post("/api/query", response_model=GraphResponse)
async def execute_query(body: CypherQuery):
    if not body.cypher or not body.cypher.strip():
        raise HTTPException(status_code=400, detail="Cypher query cannot be empty")
    try:
        records, summary = await conn_manager.run_query(
            cypher=body.cypher,
            uri=body.uri,
            username=body.username,
            password=body.password,
            database=body.database,
        )
    except Exception as e:
        logger.warning("Query failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Query error: {e}")

    if not records:
        return GraphResponse(nodes=[], relationships=[])

    return _parse_graph_data(records)


@app.post("/api/connect")
async def test_connect(body: ConnectConfig):
    try:
        records, _ = await conn_manager.run_query(
            cypher="RETURN 1 AS ok",
            uri=body.uri,
            username=body.username,
            password=body.password,
            database=body.database,
        )
        return {"status": "connected", "message": "Neo4j 连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {e}")


@app.get("/api/health")
async def health():
    return {"status": "ok"}

from pydantic import BaseModel


class CypherQuery(BaseModel):
    cypher: str
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"


class ConnectConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"


class NodeDTO(BaseModel):
    id: str
    labels: list[str]
    properties: dict
    caption: str = ""


class RelationshipDTO(BaseModel):
    id: str
    type: str
    source: str
    target: str
    properties: dict


class GraphResponse(BaseModel):
    nodes: list[NodeDTO]
    relationships: list[RelationshipDTO]


class ErrorResponse(BaseModel):
    detail: str

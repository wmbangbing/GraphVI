from pydantic import BaseModel


class CypherQuery(BaseModel):
    cypher: str


class ConnectConfig(BaseModel):
    pass


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


class PresetCreate(BaseModel):
    question: str
    cypher: str | None = None


class PresetUpdate(BaseModel):
    question: str | None = None
    cypher: str | None = None


class PresetResponse(BaseModel):
    id: int
    question: str
    cypher: str | None = None
    created_at: str
    updated_at: str


class AnalyzeRequest(BaseModel):
    nodes: list[dict] = []
    relationships: list[dict] = []
    custom_prompt: str | None = None


class AnalyzeResponse(BaseModel):
    summary: str


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


class NlQueryRequest(BaseModel):
    question: str


class NlQueryResponse(BaseModel):
    nodes: list[dict]
    relationships: list[dict]
    generated_cypher: str


class HistoryAddRequest(BaseModel):
    question: str | None = None
    cypher: str
    type: str


class HistoryResponse(BaseModel):
    id: int
    question: str | None = None
    cypher: str
    type: str
    db_uri: str
    db_name: str
    created_at: str


class Nl2CypherRequest(BaseModel):
    question: str


class Nl2CypherResponse(BaseModel):
    cypher: str


class ErrorResponse(BaseModel):
    detail: str

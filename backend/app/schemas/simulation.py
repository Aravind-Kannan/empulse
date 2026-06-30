from pydantic import BaseModel, Field


class NotionSimulationRequest(BaseModel):
    notion_integration_token: str = ""
    notion_database_id: str = ""
    ollama_model: str = "llama3.2"


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class SimulationStep(BaseModel):
    message: str
    status: str = "info"


class NotionSimulationResponse(BaseModel):
    success: bool
    steps: list[SimulationStep]
    documents_generated: int
    notion_pages_written: int
    cognee_dataset: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]

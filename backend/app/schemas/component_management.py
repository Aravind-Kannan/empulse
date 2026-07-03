from pydantic import BaseModel, Field


class ComponentUpdateRequest(BaseModel):
    name: str | None = None
    tags: str | None = None
    criticality: str | None = None
    description: str | None = None


class ComponentUpdateResponse(BaseModel):
    component_id: str
    cognee_dataset: str
    graph_nodes_created: int
    graph_edges_created: int


class ComponentDeleteResponse(BaseModel):
    component_id: str
    cognee_dataset: str
    graph_nodes_created: int
    graph_edges_created: int

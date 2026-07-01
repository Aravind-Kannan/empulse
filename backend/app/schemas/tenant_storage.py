import uuid

from pydantic import BaseModel, Field


class Neo4jAccessDetails(BaseModel):
    browser_url: str
    bolt_url: str
    username: str
    password: str
    database: str
    dedicated_database: bool
    browser_instructions: str
    startup_commands: list[str] = Field(default_factory=list)
    sample_cypher: list[str] = Field(default_factory=list)


class VectorStoreDetails(BaseModel):
    provider: str
    path: str | None = None
    isolated_per_tenant: bool
    note: str


class CogneeMetadataDbDetails(BaseModel):
    provider: str
    path: str
    isolated_per_tenant: bool
    note: str


class TenantCogneeStorageAccess(BaseModel):
    tenant_id: uuid.UUID
    cognee_dataset_name: str
    cognee_dataset_id: uuid.UUID
    isolation_mode: str
    backend_access_control_enabled: bool
    neo4j: Neo4jAccessDetails
    vector_store: VectorStoreDetails
    cognee_metadata_db: CogneeMetadataDbDetails

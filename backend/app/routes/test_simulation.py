import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.simulation import NotionSimulationRequest, NotionSimulationResponse, SimulationStep
from app.services.notion_simulation import run_notion_simulation, stream_notion_simulation

router = APIRouter(prefix="/api/test", tags=["test"])


@router.post("/run-simulation", response_model=NotionSimulationResponse)
async def run_simulation(payload: NotionSimulationRequest) -> NotionSimulationResponse:
    steps: list[SimulationStep] = []

    def log(message: str, status: str = "info") -> None:
        steps.append(SimulationStep(message=message, status=status))

    result = await run_notion_simulation(
        notion_token=payload.notion_integration_token,
        notion_database_id=payload.notion_database_id,
        ollama_model=payload.ollama_model,
        log=log,
    )

    return NotionSimulationResponse(
        success=bool(result.get("success")),
        steps=steps,
        documents_generated=int(result.get("documents_generated", 0)),
        notion_pages_written=int(result.get("notion_pages_written", 0)),
        cognee_dataset=str(result.get("cognee_dataset", "")),
        nodes=result.get("nodes", []),
        edges=result.get("edges", []),
    )


@router.post("/run-simulation/stream")
async def run_simulation_stream(payload: NotionSimulationRequest) -> StreamingResponse:
    generator = stream_notion_simulation(
        notion_token=payload.notion_integration_token,
        notion_database_id=payload.notion_database_id,
        ollama_model=payload.ollama_model,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

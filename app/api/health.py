from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    from app.config import settings
    return HealthResponse(
        status="ok",
        service="rena-rag",
        environment=settings.environment,
    )

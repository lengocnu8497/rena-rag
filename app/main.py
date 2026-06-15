from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health
from app.api import dashboard as dashboard_api
from app.api import inspect as inspect_api
from app.api import ingest_pdf as ingest_pdf_api
from app.config import settings
from app.db.client import init_client
from app.observability.logging import configure_logging
from app.observability.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.log_level)
    await init_client()
    yield


app = FastAPI(
    title="Rena RAG",
    description="Agentic RAG service for Rena iOS — aesthetic procedure research and recovery",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened to specific origins in prod via CloudFront + ALB
    allow_credentials=True,
    allow_methods=["POST", "GET", "DELETE", "PUT"],
    allow_headers=["Authorization", "Content-Type", "apikey"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(inspect_api.router)
app.include_router(dashboard_api.router)
app.include_router(ingest_pdf_api.router)

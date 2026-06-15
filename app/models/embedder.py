from openai import AsyncOpenAI

from app.config import settings

MODEL = "text-embedding-3-small"
DIMENSIONS = 1536

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def embed(text: str) -> list[float]:
    resp = await _get_client().embeddings.create(
        model=MODEL,
        input=text,
        dimensions=DIMENSIONS,
    )
    return resp.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single API call. Results are index-ordered."""
    resp = await _get_client().embeddings.create(
        model=MODEL,
        input=texts,
        dimensions=DIMENSIONS,
    )
    return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]

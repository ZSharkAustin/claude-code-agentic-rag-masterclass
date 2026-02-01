import cohere
from langsmith import traceable

from app.config import settings

_client = None

if settings.cohere_api_key:
    _client = cohere.ClientV2(api_key=settings.cohere_api_key)


def is_reranker_available() -> bool:
    return _client is not None


@traceable(name="rerank_chunks")
def rerank_chunks(query: str, chunks: list[dict], top_n: int = 5) -> list[dict]:
    if not _client or not chunks:
        return chunks[:top_n]

    documents = [chunk.get("content", "") for chunk in chunks]

    response = _client.rerank(
        model=settings.cohere_rerank_model,
        query=query,
        documents=documents,
        top_n=top_n,
    )

    reranked = []
    for result in response.results:
        chunk = {**chunks[result.index], "relevance_score": result.relevance_score}
        reranked.append(chunk)
    return reranked

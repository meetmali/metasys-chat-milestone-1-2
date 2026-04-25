"""
rag.py  —  Metasys-Chat Milestone 1

Per-request query pipeline:
  1. Embed the user question with sentence-transformers (same model as ingest)
  2. Query ChromaDB for the top-k closest API documentation chunks
  3. Inject those chunks as context into a system prompt
  4. Stream the response from Ollama back to the caller as Server-Sent Events
"""

import json
import sys
from pathlib import Path
from typing import AsyncGenerator

import chromadb
import httpx
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    CHROMA_PATH, COLLECTION_NAME, EMBED_MODEL,
    OLLAMA_URL, OLLAMA_MODEL, TOP_K,
)

# ---------------------------------------------------------------------------
# Module-level singletons — loaded on first use, reused across requests
# ---------------------------------------------------------------------------

_embed_model: SentenceTransformer | None = None
_collection = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def _reset_collection_cache():
    """Called after a fresh ingest so the next query picks up the new data."""
    global _collection
    _collection = None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a precise technical assistant for the Metasys REST API by Johnson Controls.
Answer questions about how to use the API: endpoint paths, HTTP methods,
query parameters, request bodies, response schemas, authentication, and error codes.

Rules:
- Base every answer strictly on the documentation excerpts provided below.
- If the excerpts do not cover the question, say so clearly rather than guessing.
- Be concise. Always include the HTTP method and path when referencing an endpoint.
- Format endpoint references as: METHOD /path  (e.g. GET /spaces)

--- Metasys REST API Documentation ---
{context}
--- End of Documentation ---"""


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------

async def query_stream(message: str) -> AsyncGenerator[str, None]:
    """
    Async generator that yields Server-Sent Event frames.
    Each frame is:  data: <json-encoded token>\n\n
    Final frame is: data: [DONE]\n\n

    Tokens are JSON-encoded so that newlines inside a token
    never break the SSE framing.
    """

    # --- Retrieve relevant chunks from ChromaDB ----------------------------
    try:
        collection = _get_collection()
    except Exception:
        yield f"data: {json.dumps('Knowledge base not ready. Run: python backend/ingest.py')}\n\n"
        yield "data: [DONE]\n\n"
        return

    model = _get_embed_model()
    query_embedding = model.encode(message).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        include=["documents", "metadatas"],
    )

    docs    = results.get("documents", [[]])[0]
    context = "\n\n---\n\n".join(docs) if docs else "No relevant documentation found."

    # --- Build messages for Ollama -----------------------------------------
    system_content = SYSTEM_PROMPT.format(context=context)
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user",   "content": message},
    ]

    payload = {
        "model":    OLLAMA_MODEL,
        "messages": messages,
        "stream":   True,
        "options":  {"temperature": 0.1, "num_predict": 1024},
    }

    # --- Stream from Ollama ------------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data  = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield f"data: {json.dumps(token)}\n\n"
                        if data.get("done"):
                            yield "data: [DONE]\n\n"
                            return
                    except json.JSONDecodeError:
                        continue

    except httpx.ConnectError:
        msg = (
            f"Cannot reach Ollama at {OLLAMA_URL}. "
            "Start it with: ollama serve"
        )
        yield f"data: {json.dumps(msg)}\n\n"
        yield "data: [DONE]\n\n"

    except httpx.HTTPStatusError as e:
        msg = f"Ollama returned HTTP {e.response.status_code}: {e.response.text[:200]}"
        yield f"data: {json.dumps(msg)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps(f'Unexpected error: {e}')}\n\n"
        yield "data: [DONE]\n\n"

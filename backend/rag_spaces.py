"""
rag_spaces.py  --  Metasys-Chat Milestone 2

RAG query pipeline for the metasys_spaces ChromaDB collection.
Same pattern as rag.py but tuned for building/space data questions.
"""

import ssl
import os
import urllib3
import requests as _req

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["CURL_CA_BUNDLE"] = ""
urllib3.disable_warnings()
_orig = _req.Session.merge_environment_settings
def _no_ssl(self, url, proxies, stream, verify, cert):
    s = _orig(self, url, proxies, stream, verify, cert)
    s["verify"] = False
    return s
_req.Session.merge_environment_settings = _no_ssl

import json
import sys
from pathlib import Path
from typing import AsyncGenerator

import chromadb
import httpx
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from config import CHROMA_PATH, EMBED_MODEL, OLLAMA_URL, OLLAMA_MODEL, TOP_K

SPACES_COLLECTION = "metasys_spaces"

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_embed_model = None
_collection  = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = client.get_collection(SPACES_COLLECTION)
    return _collection


def reset_collection_cache():
    global _collection
    _collection = None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a building data assistant for a Metasys building automation system.
You have access to data about spaces (rooms, buildings, areas) in the building.

Each space record includes:
- Name and type (room, building, or generic)
- Area in square meters
- Description
- Parent space (the building or area it belongs to)
- Full location path
- Equipment serving the space

Answer questions about spaces clearly and concisely.
When listing spaces, include their name, type, area, and parent building.
If a question asks about size comparisons (e.g. larger than X sq meters),
use the area field to filter and list all matching spaces.
If the data does not contain enough information to answer, say so clearly.

--- Building Space Data ---
{context}
--- End of Data ---"""


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------

async def query_spaces_stream(message: str) -> AsyncGenerator[str, None]:
    """
    Async generator yielding SSE frames for a spaces question.
    """
    # Retrieve relevant space chunks
    try:
        collection = _get_collection()
    except Exception:
        yield f"data: {json.dumps('Spaces knowledge base not ready. Run: python backend/ingest_spaces.py')}\n\n"
        yield "data: [DONE]\n\n"
        return

    model = _get_embed_model()
    query_embedding = model.encode(message).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(TOP_K * 3, 20),   # fetch more for spaces -- better coverage
        include=["documents", "metadatas"],
    )

    docs    = results.get("documents", [[]])[0]
    context = "\n\n---\n\n".join(docs) if docs else "No space data found."

    # Build messages
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

    # Stream from Ollama
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
        yield f"data: {json.dumps(f'Cannot reach Ollama at {OLLAMA_URL}. Run: ollama serve')}\n\n"
        yield "data: [DONE]\n\n"
    except httpx.HTTPStatusError as e:
        yield f"data: {json.dumps(f'Ollama error {e.response.status_code}')}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps(f'Unexpected error: {e}')}\n\n"
        yield "data: [DONE]\n\n"

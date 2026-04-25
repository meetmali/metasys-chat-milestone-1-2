"""
main.py  --  Metasys-Chat  (Milestone 1 + Milestone 2)

Start from project root:
    uvicorn backend.main:app --reload --port 8000

Routes:
    GET  /                  serve the dark chat UI

    -- Milestone 1: API Docs --
    POST /chat              SSE stream -- API docs RAG
    POST /ingest            re-ingest openapi.json

    -- Milestone 2: Spaces --
    POST /chat/spaces       SSE stream -- spaces RAG
    POST /ingest/spaces     fetch live data from MRAM and re-ingest

    -- Shared --
    GET  /health            readiness check for both collections
"""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

from config import CHROMA_PATH, COLLECTION_NAME
from ingest import run_ingest
from rag import query_stream, _reset_collection_cache
from ingest_spaces import run_ingest_spaces
from rag_spaces import query_spaces_stream, reset_collection_cache as reset_spaces_cache

app = FastAPI(title="metasys-chat", docs_url=None, redoc_url=None)

FRONTEND = Path(__file__).parent.parent / "frontend" / "index.html"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_ui():
    if not FRONTEND.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html not found")
    return FileResponse(FRONTEND)


# ---------------------------------------------------------------------------
# Milestone 1 -- API Docs chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is empty")
    return StreamingResponse(
        query_stream(req.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ingest")
async def ingest():
    try:
        result = run_ingest()
        _reset_collection_cache()
        return {
            "status":  "success",
            "message": f"Ingested {result['chunks']} chunks into '{result['collection']}'",
            **result,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Milestone 2 -- Spaces chat
# ---------------------------------------------------------------------------

@app.post("/chat/spaces")
async def chat_spaces(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is empty")
    return StreamingResponse(
        query_spaces_stream(req.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ingest/spaces")
async def ingest_spaces():
    try:
        result = run_ingest_spaces()
        reset_spaces_cache()
        return {
            "status":  "success",
            "message": f"Ingested {result['chunks']} spaces into '{result['collection']}' ({result['errors']} errors)",
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    db_file      = Path(CHROMA_PATH) / "chroma.sqlite3"
    chroma_ready = db_file.exists()
    collections  = []

    if chroma_ready:
        try:
            import chromadb
            client      = chromadb.PersistentClient(path=CHROMA_PATH)
            collections = [c.name for c in client.list_collections()]
        except Exception:
            pass

    return {
        "status":         "ok",
        "chroma_ready":   chroma_ready,
        "api_docs_ready": COLLECTION_NAME in collections,
        "spaces_ready":   "metasys_spaces" in collections,
        "collections":    collections,
    }

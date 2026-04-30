# metasys-assistant

A RAG-based chatbot that wraps the Metasys REST API spec and live building space data behind a natural language interface. The pipeline ingests structured JSON sources, chunks and embeds them into a local ChromaDB vector store, and routes queries through a locally hosted LLM via Ollama. Both the embedding model and inference run entirely on device with no external API calls and no data leaving the machine.

---

## Architecture

### Milestone 1 — API Documentation Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ INGESTION  (run once)                                               │
│                                                                     │
│  openapi.json  ──►  Parse 59 endpoints  ──►  Embed chunks          │
│  (on disk)          into 60 text chunks      (all-MiniLM-L6-v2)    │
│                                                   │                 │
│                                                   ▼                 │
│                                          ChromaDB (metasys_api)     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ CHAT  (per message)                                                 │
│                                                                     │
│  User question                                                      │
│      │                                                              │
│      ▼                                                              │
│  Embed question  ──►  Vector search  ──►  Top 5 chunks             │
│  (all-MiniLM)         (cosine similarity)      │                    │
│                                                ▼                    │
│                                       Build system prompt          │
│                                       (question + context)         │
│                                                │                    │
│                                                ▼                    │
│                                       Ollama (llama3.2:3b)         │
│                                       running locally              │
│                                                │                    │
│                                                ▼                    │
│                                       Stream response to UI        │
└─────────────────────────────────────────────────────────────────────┘
```

### Milestone 2 — Building Spaces Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ INGESTION  (run once, requires MRAM)                                │
│                                                                     │
│  MRAM :4242                                                         │
│      │                                                              │
│      ▼                                                              │
│  GET /api/v6/spaces  ──►  278 space IDs                            │
│                                │                                    │
│                                ▼                                    │
│  GET /api/v6/spaces/{id}  ──►  Rich data per space:                │
│  (278 requests)               name, type, area, description,       │
│                               location hierarchy, equipment        │
│                                │                                    │
│                                ▼                                    │
│  Build 1 text chunk per space  ──►  Embed chunks                   │
│                                      (all-MiniLM-L6-v2)            │
│                                           │                         │
│                                           ▼                         │
│                                  ChromaDB (metasys_spaces)         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ CHAT  (per message)                                                 │
│                                                                     │
│  User question                                                      │
│      │                                                              │
│      ▼                                                              │
│  Embed question  ──►  Vector search  ──►  Top 15 space chunks      │
│  (all-MiniLM)         (cosine similarity)      │                    │
│                                                ▼                    │
│                                       Build system prompt          │
│                                       (question + context)         │
│                                                │                    │
│                                                ▼                    │
│                                       Ollama (llama3.2:3b)         │
│                                       running locally              │
│                                                │                    │
│                                                ▼                    │
│                                       Stream response to UI        │
└─────────────────────────────────────────────────────────────────────┘
```

### Full System Infrastructure

```
                        metasys-assistant
                              │
              ┌───────────────┴───────────────┐
              │                               │
        Milestone 1                     Milestone 2
        API Docs chat                  Spaces chat
              │                               │
        POST /chat                    POST /chat/spaces
        POST /ingest                  POST /ingest/spaces
              │                               │
              └───────────┬───────────────────┘
                          │
                    FastAPI Server
                    (localhost:8000)
                          │
              ┌───────────┼───────────┐
              │           │           │
         ChromaDB      Ollama    sentence-
         (local)     (local LLM) transformers
         data/          :11434   (embeddings)
         chroma_db/
              │
    ┌─────────┴──────────┐
    │                    │
metasys_api        metasys_spaces
(60 chunks)        (278 spaces)
Milestone 1        Milestone 2


                [Milestone 2 only]
                MRAM Mock Server
                localhost:4242
                npx @cp-metasys/rest-api-mock
```

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| LLM | [Ollama](https://ollama.com) — `llama3.2:3b` | Runs entirely on-device. No API keys, no external calls, no data leakage. |
| Embeddings | `sentence-transformers` — `all-MiniLM-L6-v2` | Small (~90MB), fast on CPU, no GPU needed. Downloads once and runs offline. |
| Vector DB | [ChromaDB](https://www.trychroma.com) | Zero infrastructure — persists to a local folder. No server, no Docker. |
| Backend | [FastAPI](https://fastapi.tiangolo.com) + Uvicorn | Async SSE streaming, serves the UI and all API routes from one process. |
| Frontend | Vanilla HTML + JS | Single dark UI file, no build step, no framework. Streams tokens live. |
| Mock API | MRAM (`@cp-metasys/rest-api-mock`) | Simulates a real Metasys system locally at `localhost:4242`. |

---

## Data Privacy

> All LLM inference, embeddings, and vector search run entirely on your machine. No question, no document, no building data, and no response is ever sent to an external server or third-party API.

| Component | How it stays local |
|---|---|
| LLM | Ollama runs the model on your hardware — no call to OpenAI, Anthropic, or any cloud service |
| Embeddings | sentence-transformers runs on CPU after a one-time model download |
| Vector DB | ChromaDB writes to `data/chroma_db/` on disk — never leaves the machine |
| Building data | MRAM is a local mock server — no real Metasys system is exposed |
| API keys | None required |

---

## Project Structure

```
metasys-assistant/
├── backend/
│   ├── config.py             # All settings loaded from .env
│   ├── ingest.py             # M1: parse openapi.json → embed → ChromaDB
│   ├── rag.py                # M1: embed query → search → stream from Ollama
│   ├── ingest_spaces.py      # M2: fetch MRAM spaces → embed → ChromaDB
│   ├── rag_spaces.py         # M2: embed query → search spaces → stream from Ollama
│   └── main.py               # FastAPI app — all routes
├── frontend/
│   └── index.html            # Dark chat UI with API Docs / Spaces toggle
├── data/
│   ├── openapi.json          # Metasys REST API v4 OpenAPI spec
│   └── chroma_db/            # Local vector database (git-ignored)
├── .env                      # Environment config (git-ignored)
├── .gitignore
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.11 or higher
- Node.js (for MRAM — Milestone 2 only)
- [Ollama](https://ollama.com/download) installed

### Step 1 — Pull the LLM model

```bash
ollama pull llama3.2:3b
```

> First run downloads ~2GB. On a low-RAM machine try `ollama pull mistral:7b` as an alternative.

### Step 2 — Create virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Project

### Milestone 1 — API Docs Chat

**1. Run ingestion** (reads `data/openapi.json`, builds vector DB — run once):

```bash
python backend/ingest.py
```

Expected output:
```
[ingest] Loading spec from data/openapi.json ...
[ingest] Built 60 chunks from 52 paths
[ingest] Embedding chunks ...
[ingest] Done. 60 chunks stored in 'metasys_api'.
```

**2. Start the server:**

```bash
uvicorn backend.main:app --reload --port 8000
```

**3. Open in browser:**

```
http://localhost:8000
```

Click the **API Docs** tab. The green dot confirms the knowledge base is ready.

---

### Milestone 2 — Building Spaces Chat

**1. Start MRAM** (in a separate terminal):

```bash
cd path/to/mramTest
npx @cp-metasys/rest-api-mock
```

MRAM serves mock building data at `http://localhost:4242`.

**2. Run spaces ingestion** (fetches all 278 spaces from MRAM — run once):

```bash
python backend/ingest_spaces.py
```

Expected output:
```
[ingest_spaces] Fetching all spaces from http://localhost:4242/api/v6/spaces ...
[ingest_spaces] Got 278 spaces
[ingest_spaces] Fetching details for 278 spaces ...
[ingest_spaces] 50/278 fetched ...
[ingest_spaces] 100/278 fetched ...
[ingest_spaces] Done. 278 spaces stored in 'metasys_spaces'.
```

**3. Start the server:**

```bash
uvicorn backend.main:app --reload --port 8000
```

**4. Open in browser:**

```
http://localhost:8000
```

Click the **Spaces** tab and try asking a question.

---

## API Routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Serve the chat UI |
| `POST` | `/chat` | M1: Stream API docs RAG response |
| `POST` | `/ingest` | M1: Re-ingest `openapi.json` |
| `POST` | `/chat/spaces` | M2: Stream spaces RAG response |
| `POST` | `/ingest/spaces` | M2: Fetch live MRAM data and re-ingest |
| `GET` | `/health` | Readiness check for both ChromaDB collections |

---

## Environment Variables

Stored in `.env` at the project root:

```env
MRAM_URL=http://localhost:4242
SPEC_PATH=data/openapi.json
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
CHROMA_PATH=data/chroma_db
COLLECTION_NAME=metasys_api
TOP_K=5
EMBED_MODEL=all-MiniLM-L6-v2
```

---

## Example Questions

### API Docs mode (Milestone 1)

- What endpoints are available for working with spaces?
- How does pagination work in the Metasys API?
- How do I authenticate with the Metasys REST API?
- What query parameters does `GET /objects` support?

### Spaces mode (Milestone 2)

- What rooms are larger than 300 square meters?
- What buildings have a bedroom? Also provide their IDs.
- Give me all the information about the building named Crystal Cave Dwelling.
- List all buildings in the system.
- What equipment is in the Kitchen?

---

## Re-ingesting Data

**M1** — Re-run if you update `openapi.json`, or click **Re-ingest** in the UI header.

**M2** — Re-run any time you want fresh data from MRAM (e.g. after the mock data changes):

```bash
python backend/ingest_spaces.py
```

Or click **Re-ingest** while in Spaces mode in the UI.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Knowledge base not ready` | Run `python backend/ingest.py` (M1) or `python backend/ingest_spaces.py` (M2) |
| `Cannot reach Ollama` | Run `ollama serve` in a separate terminal |
| `MRAM not reachable` | Run `npx @cp-metasys/rest-api-mock` in a separate terminal |
| `SSL certificate error` during ingest | Add `HF_HUB_DISABLE_SSL_VERIFICATION=1` before running ingest |
| `python not found` on Windows | Disable the Microsoft Store Python alias in App Execution Aliases settings |
| Slow responses | Switch to `llama3.2:3b` in `.env` — faster than `llama3.1:8b` on CPU |

---

*Built by Meet Mali — JCAIL Controls Track Intern — University of Illinois Urbana-Champaign*

# metasys-assistant

A RAG-based chatbot that wraps the Metasys REST API spec and live building space data behind a natural language interface. The pipeline ingests structured JSON sources, chunks and embeds them into a local ChromaDB vector store, and routes queries through a locally hosted LLM via Ollama. Both the embedding model and inference run entirely on device with no external API calls and no data leaving the machine.

---

## Architecture

### Milestone 1 — API Documentation Pipeline

<img width="602" height="650" alt="Screenshot 2026-04-30 at 12 37 32 PM" src="https://github.com/user-attachments/assets/7a70f527-1aa9-48b2-ac16-d1b5f79217fb" />


### Milestone 2 — Building Spaces Pipeline

<img width="602" height="883" alt="Screenshot 2026-04-30 at 12 38 17 PM" src="https://github.com/user-attachments/assets/1c7751a8-dd2b-48ea-95b9-6941825cb7ee" />



### Full System Infrastructure

<img width="597" height="865" alt="Screenshot 2026-04-30 at 12 38 49 PM" src="https://github.com/user-attachments/assets/5d0f8d7b-9f88-40ff-8ffb-1c257f144b8a" />



## Tech Stack

| Component | Technology | Why |
|---|---|---|
| LLM | [Ollama](https://ollama.com) - `llama3.2:3b` | Runs entirely on-device. No API keys, no external calls, no data leakage. |
| Embeddings | `sentence-transformers` - `all-MiniLM-L6-v2` | Small (~90MB), fast on CPU, no GPU needed. Downloads once and runs offline. |
| Vector DB | [ChromaDB](https://www.trychroma.com) | Zero infrastructure, persists to a local folder. No server, no Docker. |
| Backend | [FastAPI](https://fastapi.tiangolo.com) + Uvicorn | Async SSE streaming, serves the UI and all API routes from one process. |
| Frontend | Vanilla HTML + JS | Single dark UI file, no build step, no framework. Streams tokens live. |
| Mock API | MRAM (`@cp-metasys/rest-api-mock`) | Simulates a real Metasys system locally at `localhost:4242`. |

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
- Node.js (for MRAM - Milestone 2 only)
- [Ollama](https://ollama.com/download) installed

### Step 1 — Pull the LLM model

```bash
ollama pull llama3.2:3b
```

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

**1. Run ingestion** (reads `data/openapi.json`, builds vector DB - run once):

```bash
python backend/ingest.py
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

**3. Start the server:**

```bash
uvicorn backend.main:app --reload --port 8000
```

**4. Open in browser:**

```
http://localhost:8000
```

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

*Built by Meet Mali — JCAIL Controls Track Intern — University of Illinois Urbana-Champaign*

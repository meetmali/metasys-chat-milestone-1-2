"""
ingest.py  —  Metasys-Chat Milestone 1

Reads data/openapi.json from disk, parses every endpoint operation into a
text chunk, embeds with sentence-transformers, and stores in ChromaDB.

Run once before starting the server:
    python backend/ingest.py

Re-run any time the spec file changes.  The collection is wiped and rebuilt
fresh on every run so there are no stale chunks.
"""

import json
import os
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from config import SPEC_PATH, CHROMA_PATH, COLLECTION_NAME, EMBED_MODEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_spec(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_ref(spec: dict, ref: str) -> dict:
    """
    Resolve a JSON Reference like '#/components/parameters/pageParam'.
    Walks the spec dict following the path segments after the '#/'.
    Returns an empty dict if any segment is missing.
    """
    if not ref.startswith("#/"):
        return {}
    parts = ref[2:].split("/")
    node = spec
    for part in parts:
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def schema_type_str(spec: dict, schema: dict, depth: int = 0) -> str:
    """Turn a schema object into a short human-readable type string."""
    if not schema:
        return ""
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])
    s_type = schema.get("type", "")
    if s_type == "array":
        items = schema.get("items", {})
        return "array of " + schema_type_str(spec, items, depth + 1)
    if s_type == "object" or "properties" in schema:
        props = list(schema.get("properties", {}).keys())
        if not props:
            return "object"
        if depth >= 1:
            return "object"
        return "object {" + ", ".join(props[:8]) + ("..." if len(props) > 8 else "") + "}"
    return s_type if s_type else "any"


# ---------------------------------------------------------------------------
# Parser — one text chunk per operation
# ---------------------------------------------------------------------------

def build_chunks(spec: dict) -> list[tuple[str, dict]]:
    """
    Return a list of (text, metadata) tuples.
    One chunk for the API overview, one per endpoint+method combination.
    """
    chunks = []

    # --- API overview chunk ------------------------------------------------
    info = spec.get("info", {})
    overview = (
        f"Metasys REST API — {info.get('title', '')} {info.get('version', '')}\n"
        f"{info.get('description', '').strip()}\n"
        "Authentication: JWT bearer token obtained via POST /login.\n"
        "Base path: /api/v6 (MRAM mock) or configured server URL.\n"
        "Pagination: use page and pageSize query parameters.\n"
        "All timestamps are ISO-8601 UTC."
    )
    chunks.append((overview, {
        "type": "overview", "path": "", "method": "", "tags": "", "summary": "API overview"
    }))

    # --- Per-operation chunks ----------------------------------------------
    paths = spec.get("paths", {})

    for api_path, path_item in paths.items():
        if "$ref" in path_item:
            path_item = resolve_ref(spec, path_item["$ref"])

        # Parameters declared at path level (shared by all methods)
        shared_params = path_item.get("parameters", [])

        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            op = path_item.get(method)
            if not op:
                continue

            summary      = op.get("summary", "").strip()
            description  = op.get("description", "").strip()
            tags         = ", ".join(op.get("tags", []))
            operation_id = op.get("operationId", "")

            # ---- Parameters -----------------------------------------------
            all_params = list(shared_params) + list(op.get("parameters", []))
            param_lines = []
            for p in all_params:
                if "$ref" in p:
                    p = resolve_ref(spec, p["$ref"])
                if not p:
                    continue
                p_name     = p.get("name", "")
                p_in       = p.get("in", "")          # query / path / header
                p_required = " *required*" if p.get("required") else ""
                p_desc     = p.get("description", "").replace("\n", " ").strip()
                schema     = p.get("schema", {})
                if isinstance(schema, dict) and "$ref" in schema:
                    p_type = schema["$ref"].split("/")[-1]
                elif isinstance(schema, dict):
                    p_type = schema.get("type", "")
                    enum_vals = schema.get("enum", [])
                    if enum_vals:
                        p_type += " [" + ", ".join(str(v) for v in enum_vals[:6]) + "]"
                else:
                    p_type = ""
                line = f"  - {p_name} ({p_in}{', ' + p_type if p_type else ''}{p_required})"
                if p_desc:
                    line += f": {p_desc[:200]}"
                param_lines.append(line)

            params_block = "\n".join(param_lines) if param_lines else "  none"

            # ---- Request body ---------------------------------------------
            req_body_block = ""
            req_body = op.get("requestBody", {})
            if req_body:
                rb_required = " *required*" if req_body.get("required") else ""
                rb_desc     = req_body.get("description", "").replace("\n", " ").strip()
                content     = req_body.get("content", {})
                schema_str  = ""
                for _, content_val in content.items():
                    s = content_val.get("schema", {})
                    if s:
                        schema_str = schema_type_str(spec, s)
                    break
                req_body_block = (
                    f"\nRequest body{rb_required}"
                    + (f" ({schema_str})" if schema_str else "")
                    + (f": {rb_desc}" if rb_desc else "")
                )

            # ---- Responses ------------------------------------------------
            responses = op.get("responses", {})
            response_lines = []
            for code, resp in list(responses.items())[:8]:
                if "$ref" in resp:
                    resp = resolve_ref(spec, resp["$ref"])
                resp_desc = resp.get("description", "").replace("\n", " ").strip()
                response_lines.append(f"  {code}: {resp_desc}")

            responses_block = "\n".join(response_lines) if response_lines else "  none"

            # ---- Assemble chunk -------------------------------------------
            chunk = "\n".join(filter(None, [
                f"{method.upper()} {api_path}",
                f"Summary: {summary}" if summary else "",
                f"Tags: {tags}" if tags else "",
                f"Operation ID: {operation_id}" if operation_id else "",
                f"Description: {description}" if description else "",
                "Parameters:",
                params_block,
                req_body_block.strip() if req_body_block else "",
                "Responses:",
                responses_block,
            ]))

            chunks.append((chunk, {
                "type":         "operation",
                "path":         api_path,
                "method":       method.upper(),
                "tags":         tags,
                "summary":      summary,
                "operation_id": operation_id,
            }))

    return chunks


# ---------------------------------------------------------------------------
# Main ingestion routine  (also importable by main.py for the /ingest route)
# ---------------------------------------------------------------------------

def run_ingest() -> dict:
    spec_path = Path(SPEC_PATH)
    if not spec_path.exists():
        raise FileNotFoundError(
            f"Spec not found at '{SPEC_PATH}'. "
            "Place openapi.json in the data/ folder."
        )

    print(f"[ingest] Loading spec from {spec_path} ...")
    spec   = load_spec(str(spec_path))
    chunks = build_chunks(spec)
    print(f"[ingest] Built {len(chunks)} chunks from {len(spec.get('paths', {}))} paths")

    print(f"[ingest] Loading embedding model '{EMBED_MODEL}' ...")
    model = SentenceTransformer(EMBED_MODEL)

    texts     = [c[0] for c in chunks]
    metadatas = [c[1] for c in chunks]

    print("[ingest] Embedding chunks ...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)

    print(f"[ingest] Writing to ChromaDB at '{CHROMA_PATH}' ...")
    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
        print("[ingest] Cleared previous collection")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Upsert in batches of 100 to stay well within ChromaDB limits
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        end = i + batch_size
        collection.add(
            documents  = texts[i:end],
            embeddings = embeddings[i:end].tolist(),
            metadatas  = metadatas[i:end],
            ids        = [f"chunk_{j}" for j in range(i, min(end, len(texts)))],
        )

    print(f"[ingest] Done. {len(texts)} chunks stored in '{COLLECTION_NAME}'.")
    return {"chunks": len(texts), "collection": COLLECTION_NAME}


if __name__ == "__main__":
    result = run_ingest()
    print(f"\nIngestion complete — {result['chunks']} chunks in '{result['collection']}'")

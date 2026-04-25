"""
ingest_spaces.py  --  Metasys-Chat Milestone 2

Fetches live building data from MRAM and stores it in ChromaDB.

Strategy:
  1. GET /api/v6/spaces          -- all 278 space IDs in one call
  2. GET /api/v6/spaces/{id}     -- rich data per space (area, description, servedBy)
  3. Build one text chunk per space
  4. Embed + store in 'metasys_spaces' ChromaDB collection

Run once (with MRAM running) before using the spaces chat:
    python backend/ingest_spaces.py

Re-run any time you want fresh data from MRAM.
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

import sys
import json
import time
from pathlib import Path

import httpx
import chromadb
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from config import MRAM_URL, CHROMA_PATH, EMBED_MODEL

SPACES_COLLECTION = "metasys_spaces"


# ---------------------------------------------------------------------------
# MRAM fetching
# ---------------------------------------------------------------------------

def fetch_all_space_ids(base_url: str) -> list[dict]:
    """
    Fetch all spaces from GET /api/v6/spaces.
    Returns list of basic space dicts (id, name, type, parentUrl, itemReference).
    """
    url = f"{base_url}/api/v6/spaces"
    print(f"[ingest_spaces] Fetching all spaces from {url} ...")
    with httpx.Client(timeout=30.0, verify=False) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    spaces = data.get("items", [])
    total  = data.get("total", len(spaces))
    print(f"[ingest_spaces] Got {len(spaces)} spaces (total reported: {total})")
    return spaces


def fetch_space_detail(base_url: str, space_id: str) -> dict:
    """
    Fetch rich detail for one space: area, description, servedBy equipment.
    """
    url = f"{base_url}/api/v6/spaces/{space_id}"
    with httpx.Client(timeout=30.0, verify=False) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Hierarchy parser
# ---------------------------------------------------------------------------

def parse_hierarchy(item_reference: str) -> list[str]:
    """
    Parse itemReference into ordered hierarchy levels.

    Example:
        'Storybook:Snow White/Mystic Realm.Enchanted Forest.Willow Grove.Kitchen'
        ->  ['Mystic Realm', 'Enchanted Forest', 'Willow Grove', 'Kitchen']
    """
    if not item_reference:
        return []
    # Strip the 'Storybook:Snow White/' prefix
    if "/" in item_reference:
        item_reference = item_reference.split("/", 1)[1]
    return [p.strip() for p in item_reference.split(".") if p.strip()]


def hierarchy_path(item_reference: str) -> str:
    parts = parse_hierarchy(item_reference)
    return " > ".join(parts) if parts else ""


def parent_building(item_reference: str) -> str:
    """
    Extract the immediate parent building name from the hierarchy.
    For 'Mystic Realm.Forest.Willow Cottage.Kitchen' -> 'Willow Cottage'
    """
    parts = parse_hierarchy(item_reference)
    # The last part is the space itself; the one before it is the parent
    if len(parts) >= 2:
        return parts[-2]
    return ""


# ---------------------------------------------------------------------------
# Chunk builder
# ---------------------------------------------------------------------------

def clean_type(raw_type: str) -> str:
    """'spaceTypesEnumSet.room' -> 'room'"""
    if "." in raw_type:
        return raw_type.split(".")[-1]
    return raw_type


def build_chunk(detail: dict) -> str:
    """
    Build a rich text chunk for one space from its detail response.
    This is what gets embedded and searched by the RAG pipeline.
    """
    name        = detail.get("name", "")
    space_id    = detail.get("id", "")
    raw_type    = detail.get("type", "")
    space_type  = clean_type(raw_type)
    description = (detail.get("description") or "").strip()
    item_ref    = detail.get("itemReference", "")
    area        = detail.get("area")
    area_units  = detail.get("areaUnits", "")
    served_by   = detail.get("servedBy", []) or []
    parent_url  = detail.get("parentUrl") or ""

    # Area string
    if area is not None:
        area_str = f"{area} square meters"
    else:
        area_str = "not specified"

    # Equipment list (deduplicate by id)
    seen_ids = set()
    equip_names = []
    for eq in served_by:
        eq_id = eq.get("id", "")
        if eq_id not in seen_ids:
            seen_ids.add(eq_id)
            eq_name = eq.get("name", "")
            eq_type = eq.get("type", "")
            if eq_name:
                equip_names.append(f"{eq_name} ({eq_type})" if eq_type else eq_name)

    equip_str = ", ".join(equip_names) if equip_names else "none"

    # Hierarchy
    full_path   = hierarchy_path(item_ref)
    parent_name = parent_building(item_ref)

    # Build chunk text — structured so the LLM can reason about it clearly
    lines = [
        f"Space name: {name}",
        f"Type: {space_type}",
        f"Area: {area_str}",
        f"Description: {description if description else 'none'}",
        f"Parent space: {parent_name if parent_name else 'none'}",
        f"Full path: {full_path if full_path else 'unknown'}",
        f"Equipment served by: {equip_str}",
        f"ID: {space_id}",
        f"Item reference: {item_ref}",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def run_ingest_spaces() -> dict:
    # 1. Fetch all space IDs
    spaces = fetch_all_space_ids(MRAM_URL)
    if not spaces:
        raise RuntimeError("No spaces returned from MRAM. Is MRAM running at " + MRAM_URL + "?")

    # 2. Fetch detail for each space
    print(f"[ingest_spaces] Fetching details for {len(spaces)} spaces ...")
    chunks    = []
    metadatas = []
    ids       = []
    errors    = 0

    for i, space in enumerate(spaces):
        space_id   = space.get("id", "")
        space_name = space.get("name", "")
        raw_type   = space.get("type", "")

        if not space_id:
            continue

        try:
            detail = fetch_space_detail(MRAM_URL, space_id)
            chunk  = build_chunk(detail)
            area   = detail.get("area")

            chunks.append(chunk)
            metadatas.append({
                "id":        space_id,
                "name":      space_name,
                "type":      clean_type(raw_type),
                "area":      str(area) if area is not None else "",
                "item_ref":  detail.get("itemReference", ""),
                "parent":    parent_building(detail.get("itemReference", "")),
            })
            ids.append(f"space_{space_id}")

            if (i + 1) % 50 == 0:
                print(f"[ingest_spaces]   {i + 1}/{len(spaces)} fetched ...")

        except Exception as e:
            errors += 1
            print(f"[ingest_spaces]   ERROR fetching space {space_id} ({space_name}): {e}")
            continue

    print(f"[ingest_spaces] Built {len(chunks)} chunks ({errors} errors)")

    # 3. Embed
    print(f"[ingest_spaces] Loading embedding model '{EMBED_MODEL}' ...")
    model = SentenceTransformer(EMBED_MODEL)

    print("[ingest_spaces] Embedding chunks ...")
    embeddings = model.encode(chunks, show_progress_bar=True, batch_size=32)

    # 4. Store in ChromaDB
    print(f"[ingest_spaces] Writing to ChromaDB at '{CHROMA_PATH}' ...")
    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(SPACES_COLLECTION)
        print("[ingest_spaces] Cleared previous spaces collection")
    except Exception:
        pass

    collection = client.create_collection(
        name=SPACES_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        end = i + batch_size
        collection.add(
            documents  = chunks[i:end],
            embeddings = embeddings[i:end].tolist(),
            metadatas  = metadatas[i:end],
            ids        = ids[i:end],
        )

    print(f"[ingest_spaces] Done. {len(chunks)} spaces stored in '{SPACES_COLLECTION}'.")
    return {"chunks": len(chunks), "collection": SPACES_COLLECTION, "errors": errors}


if __name__ == "__main__":
    result = run_ingest_spaces()
    print(f"\nIngestion complete -- {result['chunks']} spaces in '{result['collection']}' ({result['errors']} errors)")

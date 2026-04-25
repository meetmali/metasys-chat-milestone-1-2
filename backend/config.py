import os
from dotenv import load_dotenv

load_dotenv()

MRAM_URL        = os.getenv("MRAM_URL",         "http://localhost:4242")
SPEC_PATH       = os.getenv("SPEC_PATH",        "data/openapi.json")
OLLAMA_URL      = os.getenv("OLLAMA_URL",       "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",     "llama3.1:8b")
CHROMA_PATH     = os.getenv("CHROMA_PATH",      "data/chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME",  "metasys_api")
TOP_K           = int(os.getenv("TOP_K",        "5"))
EMBED_MODEL     = os.getenv("EMBED_MODEL",      "all-MiniLM-L6-v2")

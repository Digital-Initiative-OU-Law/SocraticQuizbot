import os


def flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# Feature flags
FEATURE_RETRIEVAL = flag("FEATURE_RETRIEVAL", "0")
FEATURE_STREAMING = flag("FEATURE_STREAMING", "1")
FEATURE_ENCRYPT_KEYS = flag("FEATURE_ENCRYPT_KEYS", "1")

# Model/backend
DEFAULT_LLM_BACKEND = os.getenv("DEFAULT_LLM_BACKEND", "openai")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDINGS_MODEL = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Retrieval
USE_PGVECTOR = flag("USE_PGVECTOR", "0")
TOP_K = int(os.getenv("TOP_K", "5"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))


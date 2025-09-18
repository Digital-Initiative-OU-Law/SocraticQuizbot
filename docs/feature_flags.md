Feature flags and configuration

Environment variables
- FEATURE_RETRIEVAL: Enable retrieval and pgvector pipeline (0/1). Requires Postgres with `vector` extension.
- USE_PGVECTOR: Create retrieval schema at init (0/1). Safe to enable; creates tables if missing.
- FEATURE_STREAMING: Enable OpenAI streaming in chat (0/1).
- FEATURE_ENCRYPT_KEYS: Prefer encrypted user key storage (0/1) when `FERNET_KEY_B64` is set.
- DEFAULT_LLM_BACKEND: `openai` (default) or `ollama`.
- OPENAI_MODEL: Chat model, e.g., `gpt-4o-mini`.
- OPENAI_EMBEDDINGS_MODEL: Embeddings model, e.g., `text-embedding-3-small`.
- OLLAMA_HOST: e.g., `http://localhost:11434`.
- OLLAMA_MODEL: Chat model for Ollama, e.g., `mistral`.
- TOP_K: Retrieval top-k (default 5).
- CHUNK_SIZE / CHUNK_OVERLAP: Retrieval chunking params.
- FERNET_KEY_B64: Urlsafe base64 key for Fernet (32-byte). Enables at-rest encryption for user API keys.

Notes
- Set flags in your environment before launching Streamlit.
- Changing `USE_OLLAMA` at runtime toggles backend in the current process.
- With FEATURE_RETRIEVAL=1 and USE_PGVECTOR=1, new PDFs are indexed at quiz start.

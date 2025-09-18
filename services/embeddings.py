from typing import List, Optional
import os
import requests
from services.settings import OPENAI_EMBEDDINGS_MODEL, OLLAMA_HOST

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


class EmbeddingsService:
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key
        if provider == "openai" and OpenAI is not None:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self.provider == "openai" and self.client is not None:
            resp = self.client.embeddings.create(model=OPENAI_EMBEDDINGS_MODEL, input=texts)
            return [d.embedding for d in resp.data]  # type: ignore[attr-defined]
        # Ollama fallback
        vectors: List[List[float]] = []
        for t in texts:
            try:
                r = requests.post(
                    f"{OLLAMA_HOST}/api/embeddings",
                    json={"model": os.getenv("OLLAMA_EMBEDDINGS_MODEL", os.getenv("OLLAMA_MODEL", "mistral")), "prompt": t},
                    timeout=30,
                )
                if r.status_code == 200:
                    data = r.json()
                    vectors.append(data.get("embedding", []))
                else:
                    vectors.append([])
            except Exception:
                vectors.append([])
        return vectors


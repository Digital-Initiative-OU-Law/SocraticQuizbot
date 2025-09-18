from typing import List, Tuple, Optional
from services.settings import USE_PGVECTOR, TOP_K, CHUNK_SIZE, CHUNK_OVERLAP
from database.models import get_db_connection
from services.embeddings import EmbeddingsService


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


def upsert_document(course: Optional[str], week: Optional[str], filename: str, md5: str) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO documents (course, week, filename, md5)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (md5) DO UPDATE SET course = EXCLUDED.course, week = EXCLUDED.week, filename = EXCLUDED.filename
        RETURNING id
        """,
        (course, week, filename, md5),
    )
    doc_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return doc_id


def index_text(md5: str, full_text: str, provider: str = "openai", api_key: Optional[str] = None):
    if not USE_PGVECTOR or not full_text:
        return
    chunks = _chunk_text(full_text)
    if not chunks:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM documents WHERE md5 = %s", (md5,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return
    document_id = row[0]
    # Clear previous chunks
    cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
    # Embed and insert
    embedder = EmbeddingsService(provider=provider, api_key=api_key)
    vectors = embedder.embed(chunks)
    for i, (c, v) in enumerate(zip(chunks, vectors)):
        if not v:
            continue
        cur.execute(
            "INSERT INTO chunks (document_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s)",
            (document_id, i, c, v),
        )
    conn.commit()
    cur.close()
    conn.close()


def search_similar(md5_list: List[str], query: str, k: int = TOP_K) -> List[Tuple[str, float]]:
    if not USE_PGVECTOR or not query or not md5_list:
        return []
    embedder = EmbeddingsService()
    vec = embedder.embed([query])
    if not vec or not vec[0]:
        return []
    v = vec[0]
    conn = get_db_connection()
    cur = conn.cursor()
    # Find chunk content for the selected docs only
    cur.execute(
        "SELECT id FROM documents WHERE md5 = ANY(%s)", (md5_list,),
    )
    doc_ids = [r[0] for r in cur.fetchall()]
    if not doc_ids:
        cur.close()
        conn.close()
        return []
    cur.execute(
        """
        SELECT content, 1 - (embedding <=> %s::vector) AS score
        FROM chunks
        WHERE document_id = ANY(%s)
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s
        """,
        (v, doc_ids, v, k),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [(r[0], float(r[1])) for r in rows]


"""Lưu và tìm vector bằng PostgreSQL + pgvector (exact search, cosine)."""
import json
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .models import Chunk


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL trống — kiểm tra starter/.env")
        if dimensions <= 0:
            raise ValueError("dimensions phải > 0")
        self.url, self.dimensions = database_url, dimensions
        with psycopg.connect(self.url, connect_timeout=5) as conn:   # báo lỗi sớm nếu DB tắt
            conn.execute("SELECT 1")

    def create_schema(self) -> None:
        with psycopg.connect(self.url) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy    text NOT NULL,
                    chunk_id    text NOT NULL,
                    document_id text NOT NULL,
                    source      text NOT NULL,
                    page        int  NOT NULL,
                    metadata    jsonb NOT NULL DEFAULT '{{}}',
                    text        text NOT NULL,
                    embedding   vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id))""")
            dims = conn.execute("SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass "
                                "AND attname = 'embedding'").fetchone()[0]
            if dims != self.dimensions:
                raise ValueError(f"Bảng có vector({dims}) nhưng model có {self.dimensions} chiều")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Số chunk và số vector khác nhau")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError("Vector sai số chiều")
        rows = [(strategy, c.chunk_id, c.document_id, c.source, c.page,
                 json.dumps(c.metadata, ensure_ascii=False), c.text, _vec(v)) for c, v in zip(chunks, vectors)]
        doc_ids = sorted({c.document_id for c in chunks})
        with psycopg.connect(self.url) as conn, conn.cursor() as cur:
            # Tài liệu thay đổi -> xóa chunk cũ không còn tồn tại của chính các tài liệu đó
            cur.execute("DELETE FROM chunks WHERE strategy = %s AND document_id = ANY(%s) "
                        "AND NOT (chunk_id = ANY(%s))", (strategy, doc_ids, [c.chunk_id for c in chunks]))
            cur.executemany("""
                INSERT INTO chunks (strategy, chunk_id, document_id, source, page, metadata, text, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::vector)
                ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                    document_id = EXCLUDED.document_id, source = EXCLUDED.source, page = EXCLUDED.page,
                    metadata = EXCLUDED.metadata, text = EXCLUDED.text, embedding = EXCLUDED.embedding""", rows)

    def count(self, strategy: str) -> int:
        with psycopg.connect(self.url) as conn:
            return conn.execute("SELECT count(*) FROM chunks WHERE strategy = %s", (strategy,)).fetchone()[0]

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        qv = _vec(query_vector)
        sql = ("SELECT chunk_id, document_id, source, page, metadata, text, "
               "1 - (embedding <=> %s::vector) AS score FROM chunks WHERE strategy = %s")
        params: list[Any] = [qv, strategy]
        if filters:
            sql += " AND metadata @> %s::jsonb"            # lọc bằng SQL, có tham số hóa
            params.append(json.dumps(filters))
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params += [qv, top_k]
        with psycopg.connect(self.url) as conn, conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(sql, params).fetchall()

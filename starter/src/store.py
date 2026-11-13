"""Store and search vectors with PostgreSQL + pgvector (exact cosine search, no ANN index)."""
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import Chunk

# Metadata columns allowed in a filter. Column names are interpolated into the SQL text, so only this
# whitelist is accepted; the filter VALUES are always sent as bound parameters.
FILTERABLE = {"section", "kind", "document_id", "page"}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def create_schema(self) -> None:
        """One table for all strategies; (strategy, chunk_id) is the key so strategies never overwrite each other."""
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy    TEXT    NOT NULL,
                    chunk_id    TEXT    NOT NULL,
                    document_id TEXT    NOT NULL,
                    source      TEXT    NOT NULL,
                    page        INTEGER NOT NULL,
                    section     TEXT,
                    kind        TEXT,
                    text        TEXT    NOT NULL,
                    metadata    JSONB   NOT NULL DEFAULT '{{}}',
                    embedding   vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )""")
            conn.execute("CREATE INDEX IF NOT EXISTS chunks_filter_idx ON chunks (strategy, section)")
            existing = conn.execute(
                "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
            ).fetchone()["atttypmod"]
            if existing != self.dimensions:
                raise ValueError(f"table 'chunks' stores {existing}-dim vectors but the model produces {self.dimensions}")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Insert or update by (strategy, chunk_id), then delete this strategy's obsolete chunks of the same documents."""
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"every vector must have {self.dimensions} dimensions")
        if not chunks:
            return
        rows = [
            (strategy, c.chunk_id, c.document_id, c.source, c.page, c.metadata.get("section"), c.metadata.get("kind"),
             c.text, Jsonb(c.metadata), _vector_literal(v))
            for c, v in zip(chunks, vectors)
        ]
        with self._connect() as conn, conn.cursor() as cur:       # one transaction: all or nothing
            cur.executemany("""
                INSERT INTO chunks (strategy, chunk_id, document_id, source, page, section, kind, text, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                    document_id = EXCLUDED.document_id, source = EXCLUDED.source, page = EXCLUDED.page,
                    section = EXCLUDED.section, kind = EXCLUDED.kind, text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding
                """, rows)
            cur.execute(
                "DELETE FROM chunks WHERE strategy = %s AND document_id = ANY(%s) AND chunk_id <> ALL(%s)",
                (strategy, sorted({c.document_id for c in chunks}), [c.chunk_id for c in chunks]),
            )

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Filter in SQL first (exact), then rank the remaining chunks by cosine distance."""
        if len(query_vector) != self.dimensions:
            raise ValueError(f"query vector must have {self.dimensions} dimensions")
        filters = filters or {}
        unknown = set(filters) - FILTERABLE
        if unknown:
            raise ValueError(f"filter on {sorted(unknown)} is not allowed; use {sorted(FILTERABLE)}")

        where, params = ["strategy = %s"], [strategy]
        for column, value in filters.items():
            if isinstance(value, (list, tuple, set)):
                where.append(f"{column} = ANY(%s)")
                params.append(list(value))
            else:
                where.append(f"{column} = %s")
                params.append(value)

        sql = f"""
            SELECT chunk_id, document_id, source, page, section, kind, text, metadata,
                   embedding <=> %s::vector AS distance
            FROM chunks WHERE {' AND '.join(where)}
            ORDER BY distance LIMIT %s"""
        with self._connect() as conn:
            rows = conn.execute(sql, [_vector_literal(query_vector), *params, top_k]).fetchall()
        return [{**row, "score": 1.0 - row["distance"]} for row in rows]     # score = cosine similarity

    def count(self, strategy: str) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT count(*) AS n FROM chunks WHERE strategy = %s", (strategy,)).fetchone()["n"]

    def delete_strategy(self, strategy: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE strategy = %s", (strategy,))

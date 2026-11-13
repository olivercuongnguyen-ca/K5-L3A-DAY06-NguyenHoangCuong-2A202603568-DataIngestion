"""Choose a real embedding provider (API or local) and implement this contract.

Chosen here: local embeddings with fastembed (ONNX, no API key).
"""
from typing import Protocol

from fastembed import TextEmbedding

# BGE retrieval models are trained to embed *queries* with this instruction and documents without it.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """TODO: implement a provider adapter; do not silently fall back to mock vectors.

    Implemented as a fastembed adapter. Fails loudly if the model cannot be loaded; never falls back to mock vectors.
    """

    def __init__(self, model_name: str, query_prefix: str = BGE_QUERY_PREFIX, batch_size: int = 32) -> None:
        # TODO: initialize real embedder and dimensions
        self.model_name = model_name
        self.query_prefix = query_prefix
        self.batch_size = batch_size
        self._model = TextEmbedding(model_name)                    # downloads once, then cached; raises on failure
        self.dimensions = len(next(iter(self._model.embed(["dimension probe"]))))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # TODO: embed_documents
        if not texts:
            return []
        return [v.tolist() for v in self._model.embed(texts, batch_size=self.batch_size)]

    def embed_query(self, question: str) -> list[float]:
        # TODO: embed_query
        return next(iter(self._model.embed([self.query_prefix + question]))).tolist()

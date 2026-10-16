from __future__ import annotations

from typing import Any


class FastEmbedEmbedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        backend: Any | None = None,
    ) -> None:
        self._model_name = model_name
        self._backend = backend

    def _get_backend(self) -> Any:
        if self._backend is None:
            from fastembed import TextEmbedding

            self._backend = TextEmbedding(self._model_name)
        return self._backend

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_backend().embed(texts, batch_size=64)
        return [
            vector.tolist() if hasattr(vector, "tolist") else list(vector)
            for vector in vectors
        ]

    def dimension(self) -> int:
        return len(self.embed(["dimension probe"])[0])

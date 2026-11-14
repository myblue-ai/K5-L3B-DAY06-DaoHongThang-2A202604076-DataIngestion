"""Choose a real embedding provider (API or local) and implement this contract."""
from typing import Protocol


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
    """Sentence Transformers chạy local. Lỗi tải model -> báo lỗi, KHÔNG fallback sang vector giả."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimensions = len(self.model.encode(["probe"])[0])
        self.max_seq_length = self.model.max_seq_length
        # Họ e5 yêu cầu tiền tố khác nhau cho câu hỏi và tài liệu
        self.is_e5 = "e5" in model_name.lower()

    def _doc(self, t: str) -> str:
        return "passage: " + t if self.is_e5 else t

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode([self._doc(t) for t in texts], batch_size=32,
                                 normalize_embeddings=True, show_progress_bar=True)
        return vecs.tolist()

    def embed_query(self, question: str) -> list[float]:
        q = "query: " + question if self.is_e5 else question
        return self.model.encode([q], normalize_embeddings=True)[0].tolist()

    def count_tokens(self, text: str) -> int:
        return len(self.model.tokenizer(self._doc(text))["input_ids"])


from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            local_files_only=True,
        )

    def encode(self, text: str):
        return self.model.encode(text)
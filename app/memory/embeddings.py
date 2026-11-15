from sentence_transformers import SentenceTransformer


class EmbeddingService:
    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self):
        self.model = SentenceTransformer(
            self.MODEL_NAME,
            local_files_only=True,
        )

    def encode(self, text: str):
        if not isinstance(text, str):
            raise TypeError("Embedding input must be a string.")

        text = text.strip()

        if not text:
            raise ValueError("Cannot generate embedding for empty text.")

        return self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
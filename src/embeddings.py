import os

import numpy as np

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingsProvider:
    _model = None

    def __init__(self, mode="test"):
        self.mode = mode
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self._load_model()

    def _load_model(self):
        if EmbeddingsProvider._model is None:
            from sentence_transformers import SentenceTransformer
            EmbeddingsProvider._model = SentenceTransformer(MODEL_NAME)
            print(f"  [CACHE] Modelo cargado: {MODEL_NAME}")

    def embed(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        vecs = EmbeddingsProvider._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        )
        return vecs.tolist()

    def get_tfidf_vectorizer(self):
        return None

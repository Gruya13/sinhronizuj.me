import numpy as np
from typing import List

class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EmbeddingService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @property
    def model(self):
        if self._model is None:
            print("[EMBEDDING] Učitavam višejezični model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2...", flush=True)
            from sentence_transformers import SentenceTransformer
            # paraphrase-multilingual-MiniLM-L12-v2 je lagan (110M parametara), brz i odličan za višejezični alignment (ENG-SRB)
            self._model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
            print("[EMBEDDING] Model uspešno učitan u memoriju.", flush=True)
        return self._model

    def get_embedding(self, text: str) -> List[float]:
        if not text:
            return []
        try:
            # Generišemo embedding i konvertujemo u listu float-ova
            emb = self.model.encode(text, convert_to_numpy=True)
            return emb.tolist()
        except Exception as e:
            print(f"[EMBEDDING ERROR] Greška pri generisanju embeddinga: {e}", flush=True)
            return []

    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return 0.0
        try:
            a = np.array(vec1)
            b = np.array(vec2)
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(dot_product / (norm_a * norm_b))
        except Exception as e:
            print(f"[EMBEDDING ERROR] Greška pri računanju sličnosti: {e}", flush=True)
            return 0.0

embedding_service = EmbeddingService()

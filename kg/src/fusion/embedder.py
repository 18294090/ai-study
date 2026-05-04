try:
    from FlagEmbedding import BGEM3FlagModel
    FLAG_EMBEDDING_AVAILABLE = True
except ImportError:
    FLAG_EMBEDDING_AVAILABLE = False

import numpy as np
from typing import List, Optional


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-m3", use_fp16: bool = True):
        self.model_name = model_name
        if FLAG_EMBEDDING_AVAILABLE:
            self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
        else:
            self.model = None

    def encode(self, texts: List[str], batch_size: int = 64) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("FlagEmbedding not installed. Install with: pip install FlagEmbedding")
        result = self.model.encode(texts, batch_size=batch_size)
        return np.array(result['dense_vecs'])

    @classmethod
    def from_embeddings(cls, embeddings: np.ndarray):
        embedder = cls.__new__(cls)
        embedder.model_name = "mock"
        embedder.model = None
        embedder._mock_embeddings = embeddings
        embedder.encode = lambda texts, batch_size=64: embedder._mock_embeddings[:len(texts)]
        return embedder
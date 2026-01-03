import hashlib
from typing import List, Optional, Union
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)

class EmbeddingService:

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: Optional[Path] = None
    ):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None
        self._dimension: Optional[int] = None

    @property
    def model(self):
        if self._model is None:
            self._load_model()
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load_model()
        return self._dimension

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")

            kwargs = {}
            if self.cache_dir:
                kwargs["cache_folder"] = str(self.cache_dir)

            self._model = SentenceTransformer(self.model_name, **kwargs)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded. Dimension: {self._dimension}")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embeddings. "
                "Install with: pip install sentence-transformers"
            )

    def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True
        )

        return embeddings.tolist()

    def embed_single(self, text: str) -> List[float]:
        result = self.embed([text])
        return result[0] if result else []

    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        import numpy as np
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    def text_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

_default_service: Optional[EmbeddingService] = None

def get_embedding_service(
    model_name: Optional[str] = None,
    cache_dir: Optional[Path] = None
) -> EmbeddingService:
    global _default_service

    if model_name is None:
        from utils.config import config
        model_name = getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')

    if _default_service is None or _default_service.model_name != model_name:
        _default_service = EmbeddingService(model_name, cache_dir)

    return _default_service

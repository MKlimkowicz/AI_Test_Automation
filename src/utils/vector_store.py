import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field

from utils.logger import get_logger
from utils.embeddings import EmbeddingService, get_embedding_service

logger = get_logger(__name__)

@dataclass
class QueryResult:
    id: str
    text: str
    metadata: Dict[str, Any]
    similarity: float
    embedding: Optional[List[float]] = None

@dataclass
class CollectionStats:
    name: str
    count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

class VectorStore:

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        self.persist_dir = persist_dir
        self.embedding_service = embedding_service or get_embedding_service()
        self._client = None
        self._collections: Dict[str, Any] = {}

    @property
    def client(self):
        if self._client is None:
            self._init_client()
        return self._client

    def _init_client(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings

            logger.info(f"Initializing ChromaDB at: {self.persist_dir or 'in-memory'}")

            settings = Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )

            if self.persist_dir:
                self.persist_dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_dir),
                    settings=settings
                )
            else:
                self._client = chromadb.Client(settings=settings)

            logger.info("ChromaDB initialized successfully")
        except ImportError:
            raise ImportError(
                "chromadb is required for vector storage. "
                "Install with: pip install chromadb"
            )

    def get_or_create_collection(self, name: str) -> Any:
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.debug(f"Collection '{name}' ready")
        return self._collections[name]

    def delete_collection(self, name: str) -> bool:
        try:
            self.client.delete_collection(name)
            if name in self._collections:
                del self._collections[name]
            logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete collection {name}: {e}")
            return False

    def list_collections(self) -> List[str]:
        collections = self.client.list_collections()
        return [c.name for c in collections]

    def collection_stats(self, name: str) -> CollectionStats:
        collection = self.get_or_create_collection(name)
        return CollectionStats(
            name=name,
            count=collection.count(),
            metadata=collection.metadata or {}
        )

    def add(
        self,
        collection_name: str,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        if not texts:
            return []

        collection = self.get_or_create_collection(collection_name)

        if ids is None:
            ids = [self.embedding_service.text_hash(t) for t in texts]

        if metadatas is None:
            metadatas = [{} for _ in texts]

        metadatas = [self._sanitize_metadata(m) for m in metadatas]

        embeddings = self.embedding_service.embed(texts)

        existing_ids = set()
        try:
            existing = collection.get(ids=ids)
            existing_ids = set(existing["ids"]) if existing["ids"] else set()
        except Exception:
            pass

        new_indices = [i for i, id_ in enumerate(ids) if id_ not in existing_ids]

        if not new_indices:
            logger.debug(f"All {len(ids)} documents already exist in {collection_name}")
            return ids

        new_ids = [ids[i] for i in new_indices]
        new_texts = [texts[i] for i in new_indices]
        new_embeddings = [embeddings[i] for i in new_indices]
        new_metadatas = [metadatas[i] for i in new_indices]

        collection.add(
            ids=new_ids,
            documents=new_texts,
            embeddings=new_embeddings,
            metadatas=new_metadatas
        )

        logger.debug(f"Added {len(new_ids)} documents to {collection_name}")
        return ids

    def add_single(
        self,
        collection_name: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None
    ) -> str:
        ids = self.add(
            collection_name,
            [text],
            [metadata] if metadata else None,
            [id] if id else None
        )
        return ids[0] if ids else ""

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include_embeddings: bool = False
    ) -> List[QueryResult]:
        collection = self.get_or_create_collection(collection_name)

        if collection.count() == 0:
            return []

        query_embedding = self.embedding_service.embed_single(query_text)

        include = ["documents", "metadatas", "distances"]
        if include_embeddings:
            include.append("embeddings")

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, collection.count()),
                where=where,
                include=include
            )
        except Exception as e:
            logger.warning(f"Query failed: {e}")
            return []

        query_results = []
        if results and results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 - distance

                result = QueryResult(
                    id=id_,
                    text=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    similarity=similarity,
                    embedding=results["embeddings"][0][i] if include_embeddings and results.get("embeddings") else None
                )
                query_results.append(result)

        return query_results

    def query_similar(
        self,
        collection_name: str,
        query_text: str,
        threshold: float = 0.7,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> List[QueryResult]:
        results = self.query(collection_name, query_text, n_results, where)
        return [r for r in results if r.similarity >= threshold]

    def get_by_id(
        self,
        collection_name: str,
        id: str
    ) -> Optional[QueryResult]:
        collection = self.get_or_create_collection(collection_name)

        try:
            result = collection.get(ids=[id], include=["documents", "metadatas"])
            if result["ids"]:
                return QueryResult(
                    id=result["ids"][0],
                    text=result["documents"][0] if result["documents"] else "",
                    metadata=result["metadatas"][0] if result["metadatas"] else {},
                    similarity=1.0
                )
        except Exception:
            pass

        return None

    def update(
        self,
        collection_name: str,
        id: str,
        text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        collection = self.get_or_create_collection(collection_name)

        try:
            update_kwargs: Dict[str, Any] = {"ids": [id]}

            if text is not None:
                update_kwargs["documents"] = [text]
                update_kwargs["embeddings"] = [self.embedding_service.embed_single(text)]

            if metadata is not None:
                update_kwargs["metadatas"] = [self._sanitize_metadata(metadata)]

            collection.update(**update_kwargs)
            return True
        except Exception as e:
            logger.warning(f"Update failed for {id}: {e}")
            return False

    def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None
    ) -> bool:
        collection = self.get_or_create_collection(collection_name)

        try:
            if ids:
                collection.delete(ids=ids)
            elif where:
                collection.delete(where=where)
            else:
                return False
            return True
        except Exception as e:
            logger.warning(f"Delete failed: {e}")
            return False

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (list, dict)):
                sanitized[key] = json.dumps(value)
            else:
                sanitized[key] = str(value)
        return sanitized

    def reset(self) -> None:
        self.client.reset()
        self._collections.clear()
        logger.info("Vector store reset")

_default_store: Optional[VectorStore] = None

def get_vector_store(
    persist_dir: Optional[Path] = None,
    embedding_service: Optional[EmbeddingService] = None
) -> VectorStore:
    global _default_store

    if persist_dir is None:
        from utils.config import config
        persist_dir = config.get_project_root() / getattr(config, 'VECTOR_DB_PATH', '.vector_store')

    if _default_store is None:
        _default_store = VectorStore(persist_dir, embedding_service)

    return _default_store

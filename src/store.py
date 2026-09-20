from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

        try:
            import chromadb  # noqa: F401

            # TODO: initialize chromadb client + collection
            self._use_chroma = True
        except Exception:
            self._use_chroma = False
            self._collection = None

    def _make_record(self, doc: Document) -> dict[str, Any]:
        content = doc.content or ""
        metadata = dict(doc.metadata or {})
        metadata.setdefault("doc_id", doc.id)
        return {
            "id": str(doc.id),
            "content": content,
            "metadata": metadata,
            "embedding": self._embedding_fn(content),
            "doc_id": str(metadata.get("doc_id", doc.id)),
        }

    def _search_records(self, query: str, records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if not records:
            return []

        query_embedding = self._embedding_fn(query)
        scored = []
        for record in records:
            embedding = record.get("embedding") or self._embedding_fn(record.get("content", ""))
            score = _dot(query_embedding, embedding)
            scored.append(
                {
                    "id": record["id"],
                    "content": record["content"],
                    "metadata": record.get("metadata", {}),
                    "score": score,
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: max(0, top_k)]

    def add_documents(self, docs: list[Document]) -> None:
        """
        Embed each document's content and store it.

        For ChromaDB: use collection.add(ids=[...], documents=[...], embeddings=[...])
        For in-memory: append dicts to self._store
        """
        if self._use_chroma and self._collection is not None:
            records = [self._make_record(doc) for doc in docs]
            ids = [record["id"] for record in records]
            contents = [record["content"] for record in records]
            embeddings = [record["embedding"] for record in records]
            metadatas = [record["metadata"] for record in records]
            self._collection.add(ids=ids, documents=contents, embeddings=embeddings, metadatas=metadatas)
            self._store.extend(records)
            self._next_index += len(records)
            return

        for doc in docs:
            record = self._make_record(doc)
            self._store.append(record)
        self._next_index += len(docs)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Find the top_k most similar documents to query.

        For in-memory: compute dot product of query embedding vs all stored embeddings.
        """
        if self._use_chroma and self._collection is not None:
            query_embedding = self._embedding_fn(query)
            results = self._collection.query(query_embeddings=[query_embedding], n_results=max(1, top_k))
            hits = []
            for i, doc_id in enumerate(results.get("ids", [[]])[0]):
                metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                payload = {
                    "id": doc_id,
                    "content": results.get("documents", [[]])[0][i],
                    "metadata": metadata,
                    "score": float(results.get("distances", [[]])[0][i]) if results.get("distances") else 0.0,
                }
                hits.append(payload)
            return hits

        return self._search_records(query, self._store, top_k)

    def get_collection_size(self) -> int:
        """Return the total number of stored chunks."""
        if self._use_chroma and self._collection is not None:
            try:
                return int(self._collection.count())
            except Exception:
                return len(self._store)
        return len(self._store)

    def search_with_filter(self, query: str, top_k: int = 3, metadata_filter: dict = None) -> list[dict]:
        """
        Search with optional metadata pre-filtering.

        First filter stored chunks by metadata_filter, then run similarity search.
        """
        records = list(self._store)
        if metadata_filter:
            records = [
                record
                for record in records
                if all(record.get("metadata", {}).get(key) == value for key, value in metadata_filter.items())
            ]
        return self._search_records(query, records, top_k)

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove all chunks belonging to a document.

        Returns True if any chunks were removed, False otherwise.
        """
        before = len(self._store)
        self._store = [
            record
            for record in self._store
            if record.get("doc_id") != doc_id
            and record.get("id") != doc_id
            and record.get("metadata", {}).get("doc_id") != doc_id
        ]
        if self._use_chroma and self._collection is not None:
            try:
                self._collection.delete(where={"doc_id": doc_id})
            except Exception:
                pass
        return len(self._store) < before

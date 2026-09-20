from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        relevant = self.store.search(question, top_k=top_k)

        if not relevant:
            return "I couldn't find any relevant context in the knowledge base."

        context = "\n\n".join(
            f"[{index}] {entry['content']}" for index, entry in enumerate(relevant, start=1)
        )

        prompt = (
            "Use the following context to answer the question. "
            "If the context does not contain the answer, say so clearly.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        )
        return self.llm_fn(prompt)

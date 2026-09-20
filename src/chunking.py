from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []

        raw_sentences = re.split(r'(?<=[.!?])(?:\s+|\n+)', text.strip())
        sentences = [segment.strip() for segment in raw_sentences if segment and segment.strip()]
        if not sentences:
            return [text.strip()] if text.strip() else []

        chunks: list[str] = []
        for i in range(0, len(sentences), self.max_sentences_per_chunk):
            group = sentences[i : i + self.max_sentences_per_chunk]
            chunk = " ".join(group).strip()
            if chunk:
                chunks.append(chunk)
        return chunks


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = self.DEFAULT_SEPARATORS if separators is None else list(separators)
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        clean_text = text.strip()
        if len(clean_text) <= self.chunk_size:
            return [clean_text]

        return self._split(clean_text, list(self.separators))

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        if not current_text or not current_text.strip():
            return []

        current_text = current_text.strip()
        if len(current_text) <= self.chunk_size:
            return [current_text]

        if not remaining_separators:
            chunks: list[str] = []
            for i in range(0, len(current_text), self.chunk_size):
                piece = current_text[i : i + self.chunk_size].strip()
                if piece:
                    chunks.append(piece)
            return chunks

        separator = remaining_separators[0]

        if separator == "":
            return [current_text[i : i + self.chunk_size].strip() for i in range(0, len(current_text), self.chunk_size) if current_text[i : i + self.chunk_size].strip()]

        if separator not in current_text:
            return self._split(current_text, remaining_separators[1:])

        parts = [part.strip() for part in current_text.split(separator) if part and part.strip()]
        if len(parts) <= 1:
            return self._split(current_text, remaining_separators[1:])

        chunks: list[str] = []
        buffer = ""

        for part in parts:
            candidate = f"{buffer} {part}".strip() if buffer else part
            if len(candidate) <= self.chunk_size:
                buffer = candidate
                continue

            if buffer:
                chunks.append(buffer)
                buffer = part
            else:
                if len(part) <= self.chunk_size:
                    chunks.append(part)
                else:
                    chunks.extend(self._split(part, remaining_separators[1:]))

        if buffer:
            chunks.append(buffer)

        final_chunks: list[str] = []
        for chunk in chunks:
            if len(chunk) <= self.chunk_size:
                final_chunks.append(chunk)
            else:
                final_chunks.extend(self._split(chunk, remaining_separators[1:]))
        return final_chunks


class HeadingChunker:
    """
    Split markdown text by section headings (e.g. #, ##, ###).

    Each section defined by a heading forms a coherent semantic chunk.
    If a section's length exceeds max_chunk_size, it is further split using
    RecursiveChunker, with the section's heading automatically prepended to every
    sub-chunk to preserve the semantic context ("what section is this about?").
    """

    def __init__(
        self,
        max_chunk_size: int = 500,
        recursive_separators: list[str] | None = None,
    ) -> None:
        self.max_chunk_size = max_chunk_size
        self._fallback = RecursiveChunker(
            separators=recursive_separators,
            chunk_size=max_chunk_size,
        )

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        clean_text = text.strip()

        # Split text into sections starting with markdown headings
        heading_regex = re.compile(r"(?m)(?=^#{1,6}\s+)")
        raw_sections = heading_regex.split(clean_text)

        sections = [s.strip() for s in raw_sections if s and s.strip()]
        if not sections:
            return [clean_text]

        chunks: list[str] = []
        for sec in sections:
            if len(sec) <= self.max_chunk_size:
                chunks.append(sec)
            else:
                lines = sec.split("\n", 1)
                heading_line = lines[0].strip() if lines[0].strip().startswith("#") else ""
                body = lines[1].strip() if len(lines) > 1 else ""

                if not heading_line:
                    chunks.extend(self._fallback.chunk(sec))
                elif not body:
                    chunks.append(heading_line)
                else:
                    # Allocate room for heading prefix so sub-chunk + heading stays within max_chunk_size
                    sub_chunk_size = max(50, self.max_chunk_size - len(heading_line) - 1)
                    sub_chunker = RecursiveChunker(
                        separators=self._fallback.separators,
                        chunk_size=sub_chunk_size,
                    )
                    sub_pieces = sub_chunker.chunk(body)
                    for piece in sub_pieces:
                        if piece.strip():
                            chunks.append(f"{heading_line}\n{piece.strip()}")

        return chunks


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    if not vec_a or not vec_b:
        return 0.0

    if len(vec_a) != len(vec_b):
        length = min(len(vec_a), len(vec_b))
        vec_a = vec_a[:length]
        vec_b = vec_b[:length]

    dot_product = _dot(vec_a, vec_b)
    norm_a = math.sqrt(sum(value * value for value in vec_a))
    norm_b = math.sqrt(sum(value * value for value in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        fixed = FixedSizeChunker(chunk_size=chunk_size, overlap=chunk_size // 10)
        sentence = SentenceChunker(max_sentences_per_chunk=2)
        recursive = RecursiveChunker(chunk_size=chunk_size)

        strategies = {
            "fixed_size": fixed.chunk(text),
            "by_sentences": sentence.chunk(text),
            "recursive": recursive.chunk(text),
        }

        result: dict[str, dict] = {}
        for name, chunks in strategies.items():
            non_empty = [c for c in chunks if c]
            lengths = [len(c) for c in non_empty]
            avg_length = sum(lengths) / len(lengths) if lengths else 0.0
            result[name] = {
                "count": len(non_empty),
                "avg_length": avg_length,
                "chunks": non_empty,
            }
        return result

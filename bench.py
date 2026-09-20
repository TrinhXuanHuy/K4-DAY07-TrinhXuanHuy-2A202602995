from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:
    yaml = None
from dotenv import load_dotenv

from src.chunking import (
    FixedSizeChunker,
    HeadingChunker,
    RecursiveChunker,
    SentenceChunker,
)
from src.embeddings import (
    EMBEDDING_PROVIDER_ENV,
    GEMINI_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    GeminiEmbedder,
    LocalEmbedder,
    MockEmbedder,
    OpenAIEmbedder,
    _mock_embed,
)
from src.models import Document
from src.store import EmbeddingStore

# =============================================================================
# CHUNKER SELECTION: Thay đổi đúng 1 dòng này để đổi chiến lược giữa các thành viên
#
# Thành viên 1 (R1): chunker = FixedSizeChunker(chunk_size=200, overlap=20)
# Thành viên 2 (R2): chunker = SentenceChunker(max_sentences_per_chunk=2)
# Thành viên 3 (R3): chunker = HeadingChunker(max_chunk_size=400)
# =============================================================================
chunker = HeadingChunker(max_chunk_size=400)


# =============================================================================
# CACHE CHO EMBEDDINGS (tránh tốn chi phí khi dùng OpenAI/Gemini)
# =============================================================================
class CachedEmbedder:
    """Wrapper lưu cache embedding theo hash nội dung để tránh gọi lại API."""

    def __init__(self, embedder_fn: Callable[[str], list[float]], cache_file: str = ".embedding_cache.json") -> None:
        self.embedder_fn = embedder_fn
        self.cache_file = Path(cache_file)
        self._cache: dict[str, list[float]] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_file.exists():
            try:
                self._cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def _save(self) -> None:
        try:
            self.cache_file.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def __call__(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in self._cache:
            return self._cache[key]
        vector = self.embedder_fn(text)
        self._cache[key] = vector
        self._save()
        return vector


def get_embedder() -> Callable[[str], list[float]]:
    """Khởi tạo embedding provider theo cấu hình môi trường."""
    load_dotenv(override=False)
    provider = os.getenv(EMBEDDING_PROVIDER_ENV, "mock").strip().lower()

    base_embedder: Callable[[str], list[float]]
    if provider == "local":
        try:
            base_embedder = LocalEmbedder(model_name=os.getenv("LOCAL_EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL))
        except Exception:
            base_embedder = _mock_embed
    elif provider == "openai":
        try:
            base_embedder = OpenAIEmbedder(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", OPENAI_EMBEDDING_MODEL))
        except Exception:
            base_embedder = _mock_embed
    elif provider == "gemini":
        try:
            base_embedder = GeminiEmbedder(model_name=os.getenv("GEMINI_EMBEDDING_MODEL", GEMINI_EMBEDDING_MODEL))
        except Exception:
            base_embedder = _mock_embed
    else:
        base_embedder = _mock_embed

    return CachedEmbedder(base_embedder)


def parse_frontmatter_and_content(file_path: Path) -> tuple[dict[str, Any], str]:
    """1. Đọc từng file .md, tách frontmatter thành metadata và phần thân thành content."""
    raw_text = file_path.read_text(encoding="utf-8")
    if raw_text.startswith("---"):
        parts = raw_text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body_text = parts[2].strip()
            metadata: dict[str, Any] = {}
            if yaml is not None:
                try:
                    metadata = yaml.safe_load(fm_text) or {}
                except Exception:
                    metadata = {}
            else:
                for line in fm_text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or ":" not in line:
                        continue
                    key, val = line.split(":", 1)
                    metadata[key.strip()] = val.strip().strip('"').strip("'")
            return metadata, body_text
    return {}, raw_text.strip()


def load_and_chunk_corpus(data_dir: Path, selected_chunker: Any) -> list[Document]:
    """2. Chunk phần thân, mỗi chunk thành một Document kèm metadata và doc_id gốc."""
    documents: list[Document] = []
    md_files = sorted(data_dir.glob("*.md"))

    for md_path in md_files:
        frontmatter, content = parse_frontmatter_and_content(md_path)
        chunks = selected_chunker.chunk(content)
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            doc = Document(
                id=f"{md_path.stem}#{i}",
                content=chunk,
                metadata={
                    **frontmatter,
                    "doc_id": md_path.stem,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "source": str(md_path),
                },
            )
            documents.append(doc)
    return documents


# =============================================================================
# 5 BENCHMARK QUERIES (R2 chủ trì, cả nhóm thống nhất dùng chung)
# =============================================================================
BENCHMARK_QUERIES = [
    {
        "id": 1,
        "type": "Tra số liệu (Numeric lookup)",
        "query": "Thời gian nhận tiền hoàn vào ví ShopeePay là bao lâu sau khi Shopee chấp nhận?",
        "metadata_filter": {"audience": "buyer"},
        "gold_answer": "Trong vòng 24 giờ (với điều kiện Ví ShopeePay vẫn hoạt động bình thường).",
        "expected_doc_id": "thoi-gian-nhan-tien-hoan",
        "required_substrings": ["24 giờ", "24h", "ShopeePay"],
    },
    {
        "id": 2,
        "type": "Hỏi điều kiện (Condition check)",
        "query": "Lý do 'Đổi ý' có được áp dụng cho sản phẩm Thiết bị Điện tử & Công nghệ có niêm phong/kích hoạt/bảo hành không?",
        "metadata_filter": None,
        "gold_answer": "Không được áp dụng. Thiết bị Điện tử & Công nghệ (có niêm phong/kích hoạt/bảo hành) thuộc danh mục sản phẩm hạn chế trả hàng với lý do 'Đổi ý'.",
        "expected_doc_id": "quy-trinh-tra-hang-hoan-tien-nguoi-ban",
        "required_substrings": ["Điện tử", "hạn chế", "Đổi ý"],
    },
    {
        "id": 3,
        "type": "Phân biệt đối tượng (Audience filter required)",
        "query": "Khi Shopee chấp nhận phương án Trả hàng & Hoàn tiền, thời hạn xử lý là bao lâu?",
        "metadata_filter": {"audience": "buyer"},
        "gold_answer": "Người mua cần hoàn tất việc gửi trả hàng về kho Shopee/Người bán trong vòng 6 ngày kể từ thời điểm nhận được thông báo gửi trả hàng từ Shopee.",
        "expected_doc_id": "quy-trinh-shopee-xu-ly-yeu-cau-tra-hang",
        "required_substrings": ["6 ngày"],
        "demo_unfiltered": True,
        "note": "Câu hỏi không nêu rõ buyer hay seller. Nếu không lọc audience, retrieval sẽ lẫn với quy trình người bán (thời hạn khiếu nại 2 ngày).",
    },
    {
        "id": 4,
        "type": "Hỏi quy trình (Process inquiry)",
        "query": "Các bước gửi yêu cầu Trả hàng/Hoàn tiền trực tiếp tại trang đơn hàng trên ứng dụng Shopee như thế nào?",
        "metadata_filter": {"audience": "buyer"},
        "gold_answer": "1. Mở app Shopee > Tôi > Chờ giao hàng/Đã giao. 2. Bấm Trả hàng/Hoàn tiền. 3. Chọn tình huống. 4. Chọn sản phẩm. 5. Chọn lý do. 6. Chọn phương án. 7. Điền mô tả & tải bằng chứng. 8. Bấm Gửi yêu cầu.",
        "expected_doc_id": "gui-yeu-cau-tra-hang-hoan-tien",
        "required_substrings": ["Tôi", "Chờ giao hàng", "Trả hàng/Hoàn tiền", "Cách 1"],
    },
    {
        "id": 5,
        "type": "Liệt kê (Listing items)",
        "query": "Khi khiếu nại hàng bị bể vỡ hoặc lỗi, video mở kiện hàng cần thể hiện rõ những thông tin gì?",
        "metadata_filter": {"audience": "buyer"},
        "gold_answer": "Video cần quay liên tục không cắt ghép, rõ nét và thể hiện rõ: 1. Tình trạng kiện hàng (đủ 6 mặt); 2. Quá trình mở kiện thấy rõ mã vận đơn khớp đơn hàng; 3. Cận cảnh số lượng và tình trạng sản phẩm (đặc biệt niêm phong, tem nhãn).",
        "expected_doc_id": "chuan-bi-bang-chung-tra-hang",
        "required_substrings": ["6 mặt", "mở kiện", "quay"],
    },
]


def run_benchmark() -> None:
    data_dir = Path("data/ecommerce")
    if not data_dir.exists():
        print(f"Lỗi: Thư mục {data_dir} không tồn tại!")
        return

    output_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        output_lines.append(msg)

    log("=" * 80)
    log("BENCHMARK RETRIEVAL — LAB 7: EMBEDDING & VECTOR STORE (CHECKPOINT 6)")
    log(f"Chiến lược chunking đang dùng: {chunker.__class__.__name__}")
    log("=" * 80)

    # 1. Đọc file và chunk
    documents = load_and_chunk_corpus(data_dir, chunker)
    total_files = len(list(data_dir.glob("*.md")))
    log(f"[*] Đã nạp và chia nhỏ {len(documents)} chunks từ {total_files} tài liệu trong '{data_dir}'.")

    # 2. Khởi tạo EmbeddingStore
    embedder = get_embedder()
    store = EmbeddingStore(collection_name="ecommerce_benchmark", embedding_fn=embedder)
    store.add_documents(documents)
    log(f"[*] Đã nạp thành công {store.get_collection_size()} chunks vào EmbeddingStore.")

    # 3. Chạy 5 query và in top-3
    log("\n" + "=" * 80)
    log("KẾT QUẢ TRUY XUẤT 5 CÂU HỎI ĐÁNH GIÁ (CHẤM 2 MỨC: DOC-LEVEL & CONTENT-LEVEL)")
    log("=" * 80)

    total_naive_matches = 0
    total_content_matches = 0
    total_points = 0
    score_table: list[dict[str, Any]] = []

    for item in BENCHMARK_QUERIES:
        qid = item["id"]
        qtype = item["type"]
        query = item["query"]
        filt = item["metadata_filter"]
        gold = item["gold_answer"]
        expected_doc = item["expected_doc_id"]
        req_subs = item.get("required_substrings", [])

        log(f"\n--- [CÂU {qid}] [{qtype}] ---")
        log(f"Query:        {query}")
        log(f"Filter:       {filt}")
        log(f"Gold Answer:  {gold}")
        log(f"Expected Doc: {expected_doc}.md")
        log(f"Required Key: {req_subs}")

        # A/B Test: Minh họa câu hỏi cần lọc metadata (Unfiltered vs Filtered)
        if item.get("demo_unfiltered"):
            unfiltered_results = store.search(query, top_k=3)
            log("  [A/B TEST - KHÔNG LỌC metadata]:")
            for rank, r in enumerate(unfiltered_results, 1):
                doc_id = r.get("metadata", {}).get("doc_id", "unknown")
                aud = r.get("metadata", {}).get("audience", "unknown")
                log(f"    Top-{rank}: score={r['score']:.4f} | doc={doc_id} (audience={aud})")

        # Truy xuất chính thức với search_with_filter
        results = store.search_with_filter(query, top_k=3, metadata_filter=filt)

        doc_match_rank = None
        content_match_rank = None

        log("  [Kết quả TRUY XUẤT CHÍNH THỨC]:")
        for rank, r in enumerate(results, 1):
            chunk_id = r["id"]
            doc_id = r.get("metadata", {}).get("doc_id", "unknown")
            score = r["score"]
            content_text = r["content"]
            content_preview = content_text[:140].replace("\n", " ").strip()

            is_doc_match = doc_id == expected_doc
            is_content_match = is_doc_match and any(sub.lower() in content_text.lower() for sub in req_subs)

            if is_doc_match and doc_match_rank is None:
                doc_match_rank = rank
            if is_content_match and content_match_rank is None:
                content_match_rank = rank

            markers = []
            if is_doc_match:
                markers.append("ĐÚNG DOC")
            if is_content_match:
                markers.append("CHỨA ĐÁP ÁN")
            marker_str = f" -> [{', '.join(markers)}]" if markers else ""

            log(f"    {rank}. [Score: {score:.4f}] Doc: {doc_id} (Chunk: {chunk_id}){marker_str}")
            log(f"       Nội dung: {content_preview}...")

        # Tính điểm theo Rubric chính thức:
        # 2đ: Gold chunk ở Top-1 VÀ ngữ cảnh chứa đáp án
        # 1đ: Gold chunk ở Top-2 hoặc Top-3 VÀ ngữ cảnh chứa đáp án
        # 0đ: Vắng mặt khỏi top-3 HOẶC ngữ cảnh không chứa đáp án
        if content_match_rank == 1:
            points = 2
        elif content_match_rank in (2, 3):
            points = 1
        else:
            points = 0

        total_points += points
        if doc_match_rank is not None:
            total_naive_matches += 1
        if content_match_rank is not None:
            total_content_matches += 1

        score_table.append({
            "id": qid,
            "query": query,
            "expected_doc": expected_doc,
            "doc_rank": doc_match_rank,
            "content_rank": content_match_rank,
            "points": points,
            "top1_doc": results[0].get("metadata", {}).get("doc_id") if results else "none",
            "top1_score": results[0]["score"] if results else 0.0,
            "top1_preview": results[0]["content"][:90].replace("\n", " ").strip() if results else "",
        })

        log(f"  => Đánh giá 2 mức:")
        log(f"     * Mức 1 (Doc-level Naïve):     {'Top-' + str(doc_match_rank) if doc_match_rank else 'Không lọt Top-3'}")
        log(f"     * Mức 2 (Content-level Thực):  {'Top-' + str(content_match_rank) if content_match_rank else 'Không chứa đáp án'}")
        log(f"     * Điểm đạt được (Rubric):     {points}/2 điểm")

    log("\n" + "=" * 80)
    log("BẢNG TỔNG HỢP ĐÁNH GIÁ CHẤT LƯỢNG TRUY XUẤT")
    log("=" * 80)
    log(f"{'Câu':<4} | {'Doc-Level Match':<16} | {'Content-Level Match':<20} | {'Điểm Rubric':<12}")
    log("-" * 60)
    for row in score_table:
        d_str = f"Top-{row['doc_rank']}" if row['doc_rank'] else "Không có"
        c_str = f"Top-{row['content_rank']}" if row['content_rank'] else "Không chứa đáp án"
        p_str = f"{row['points']}/2"
        log(f"Q{row['id']:<3} | {d_str:<16} | {c_str:<20} | {p_str:<12}")
    log("-" * 60)
    log(f"Tổng kết Mức 1 (Doc trong Top-3):     {total_naive_matches}/{len(BENCHMARK_QUERIES)} câu")
    log(f"Tổng kết Mức 2 (Đáp án trong Top-3): {total_content_matches}/{len(BENCHMARK_QUERIES)} câu")
    log(f"TỔNG ĐIỂM TRUY XUẤT CÁ NHÂN:         {total_points}/10 điểm")
    log("=" * 80)

    # Ghi ra file ket_qua_benchmark.txt
    output_path = Path("ket_qua_benchmark.txt")
    output_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"\n[OK] Đã xuất toàn bộ kết quả benchmark vào file: {output_path.resolve()}")


if __name__ == "__main__":
    run_benchmark()

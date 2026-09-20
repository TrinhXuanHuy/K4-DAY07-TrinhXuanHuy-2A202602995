# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store


**Họ tên:** Trịnh Xuân Huy
**MSSV:** 02995
**Nhóm:** T52AI — Lớp K4-L3B — **Vai trong nhóm:** R3 · Strategy (chunk theo heading/section, `HeadingChunker(400)`) + R1 · Data (chuẩn hoá frontmatter, `sources.csv`)
**Ngày:** 20/09/2026


> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.


**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).


---


## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)


### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)


**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> Độ tương tự cosine cao nghĩa là hai vector có cùng hướng, tức là có ngữ nghĩa tương đồng dù độ dài câu khác nhau. Trong văn bản, nếu hai câu nói cùng chủ đề hoặc cùng ý tưởng thì cosine similarity sẽ lớn.


**Ví dụ có độ tương tự CAO:**
- Câu A: “Tôi muốn đổi trả sản phẩm bị hỏng.”
- Câu B: “Sản phẩm lỗi cần được hoàn trả theo chính sách.”
- Tại sao tương đồng: Cả hai câu đều nói về yêu cầu đổi trả khi sản phẩm gặp sự cố, nên có cùng ngữ nghĩa.


**Ví dụ có độ tương tự THẤP:**
- Câu A: “Người bán cần phản hồi yêu cầu hủy đơn trong 24 giờ.”
- Câu B: “Giao hàng sẽ được thực hiện trong 2 ngày.”
- Tại sao khác: Câu A nói về chính sách xử lý đơn hàng của người bán, còn câu B nói về thời gian giao hàng, nên chủ đề khác nhau.


**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> Cosine similarity tập trung vào hướng của vector, nên phản ánh tốt hơn mức độ giống về ý nghĩa của văn bản. Euclidean distance lại nhạy cảm với độ lớn của vector và độ dài câu, nên dễ bị ảnh hưởng dù nội dung vẫn có cùng ý nghĩa.


### Bài toán tính toán Chunking (Bài tập 1.2)


**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> Công thức ước tính là: số chunk = floor((N - chunk_size) / (chunk_size - overlap)) + 1.
> Với N = 10,000, chunk_size = 500, overlap = 50:
> số chunk = floor((10,000 - 500) / (500 - 50)) + 1 = floor(9,500 / 450) + 1 = 21 + 1 = 22.
> **Đáp án: 22 chunks.**


**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> Khi overlap tăng lên 100, bước trượt giảm còn 400, nên số chunk tăng lên: floor((10,000 - 500) / 400) + 1 = 23 + 1 = 24 chunks. Độ chồng chéo nhiều hơn giúp giữ ngữ cảnh liên tục giữa các chunk, nhưng cũng làm tăng độ dư thừa và số lượng chunk cần xử lý.


---


## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)


Giải thích cách tiếp cận của bạn khi lập trình (implement) các phần chính trong gói `src`.


### Các hàm chia nhỏ (Chunking Functions)


**`SentenceChunker.chunk`** — hướng tiếp cận:
> Tôi sử dụng regex để tách văn bản thành các câu dựa trên dấu chấm, dấu chấm than, dấu hỏi và các ký tự kết thúc câu. Với các trường hợp ngoại lệ như viết tắt, số thập phân hoặc câu ngắn không rõ ràng, tôi thêm kiểm tra để tránh chia sai và giữ nội dung gốc ổn định.


**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> Thuật toán hoạt động theo kiểu đệ quy: nếu đoạn văn bản dài hơn `chunk_size`, tôi sẽ chia theo các ranh giới hợp lý như dấu xuống dòng, dấu chấm hoặc khoảng trắng, sau đó lặp lại trên từng nửa cho đến khi đủ ngắn. Base case là khi đoạn văn bản đã nhỏ hơn hoặc bằng kích thước chunk, lúc này ta dừng đệ quy và trả về kết quả.


**`HeadingChunker.chunk` (Chiến lược riêng của R3 — Cấu trúc tài liệu theo Heading)** — hướng tiếp cận:
> Tôi nhận thấy văn bản chính sách Shopee được soạn thảo có cấu trúc phân cấp rất chặt chẽ theo từng mục (`#`, `## Điều...`). Thay vì cắt mù quáng theo độ dài ký tự cố định hay câu lẻ tẻ, tôi tách văn bản theo ranh giới các dòng tiêu đề markdown. Nếu một mục có độ dài vượt quá `max_chunk_size` (ví dụ 400 ký tự), tôi hạ xuống chia nhỏ bằng `RecursiveChunker`, nhưng **đặc biệt luôn gắn lại tiêu đề của mục vào đầu từng mảnh con**. Kỹ thuật này giúp các chunk con không bao giờ bị mất ngữ cảnh ngữ nghĩa (semantic loss) khi đưa vào vector store và retrieval.


### Lớp EmbeddingStore


**`add_documents` + `search`** — hướng tiếp cận:
> Tôi lưu trữ từng chunk dưới dạng embedding và kèm theo metadata như id, nội dung và các thuộc tính lọc. Khi thực hiện search, hệ thống tính cosine similarity giữa query embedding và các embedding đã lưu, rồi sắp xếp kết quả theo độ liên quan từ cao đến thấp.


**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> Tôi thực hiện lọc bằng metadata trước khi tính toán similarity để giảm tập dữ liệu không liên quan, ví dụ theo `audience` hoặc `category`. Với `delete_document`, tôi xóa bản ghi theo `doc_id`, giúp cập nhật kho dữ liệu mà không phá vỡ các chunk còn lại.


### Tác tử KnowledgeBaseAgent


**`answer`** — hướng tiếp cận:
> Tôi xây dựng prompt theo cấu trúc “context + câu hỏi”, trong đó context là các chunk đã được truy xuất từ vector store và sắp xếp theo độ liên quan. Sau đó, tôi inject ngữ cảnh này vào prompt để mô hình trả lời dựa trên dữ liệu thực tế của tài liệu, thay vì suy đoán theo kinh nghiệm chung.


---


## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)


Vượt qua bộ kiểm thử là điều kiện tính điểm phần này.


### Kết Quả Kiểm Thử (Test Results)


```
============================== test session starts ==============================
platform win32 -- Python 3.10.0, pytest-9.1.1, pluggy-1.6.0 -- D:\K4-L3B-Data-Foundations\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\K4-L3B-Data-Foundations
collected 42 items


tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED [  2%]
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED [  4%]
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED [  7%]
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED [  9%]
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED [ 11%]
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED [ 14%]
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED [ 16%]
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED [ 19%]
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED [ 21%]
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED     [ 23%]
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED [ 26%]
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED [ 28%]
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED [ 30%]
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED      [ 33%]
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED [ 35%]
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED [ 38%]
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED [ 40%]
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED [ 42%]
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED     [ 45%]
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED [ 47%]
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED [ 50%]
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED [ 52%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED [ 54%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED [ 57%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED [ 59%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED [ 61%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED [ 64%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED [ 66%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED [ 69%]
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED [ 71%]
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED [ 73%]
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED [ 76%]
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED [ 78%]
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED [ 80%]
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED [ 83%]
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED [ 85%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED [ 88%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED [ 90%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED [ 92%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED [ 97%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED [100%]


============================== 42 passed in 0.14s ===============================
=== Manual File Test ===
Accepted file types: .md, .txt
Input file list:
  - data/python_intro.txt
  - data/vector_store_notes.md
  - data/rag_system_design.md
  - data/customer_support_playbook.txt
  - data/chunking_experiment_report.md
  - data/vi_retrieval_notes.md
Skipping missing file: data\customer_support_playbook.txt


Loaded 5 documents
  - python_intro: data\python_intro.txt
  - vector_store_notes: data\vector_store_notes.md
  - rag_system_design: data\rag_system_design.md
  - chunking_experiment_report: data\chunking_experiment_report.md
  - vi_retrieval_notes: data\vi_retrieval_notes.md


Embedding backend: mock embeddings fallback


Stored 5 documents in EmbeddingStore


=== EmbeddingStore Search Test ===
Query: Chunking là gì?
1. score=0.150 source=data\rag_system_design.md
   content preview: # Thiết kế Hệ thống RAG cho Trợ lý Tri thức Nội bộ  ## Bối cảnh  Một nhóm sản phẩm muốn một trợ lý có thể trả lời các câ...
2. score=0.027 source=data\python_intro.txt
   content preview: Python là một ngôn ngữ lập trình bậc cao được sử dụng rộng rãi cho tự động hóa, dịch vụ backend, phân tích dữ liệu, tính...
3. score=0.025 source=data\chunking_experiment_report.md
   content preview: # Báo cáo Thử nghiệm Chia nhỏ văn bản (Chunking Experiment Report)  ## Mục đích  Báo cáo này tóm tắt một thử nghiệm nhỏ ...


=== KnowledgeBaseAgent Test ===
Question: Chunking là gì?
Agent answer:
[DEMO LLM] Generated answer from prompt preview: Use the following context to answer the question. If the context does not contain the answer, say so clearly.  Context: [1] # Thiết kế Hệ thống RAG cho Trợ lý Tri thức Nội bộ  ## Bối cảnh  Một nhóm sản phẩm muốn một trợ lý có thể trả lời các câu hỏi về việc giới thiệu (onboarding), quy trình triển khai, sở hữu dịch vụ, và các bước khắc phục sự cố. Công ty đã có sẵn tài liệu rải rác trên các sổ tay...
```


**Số lượng bài test vượt qua (pass):** 42 / 42


---


## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)


| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | “Tôi muốn trả hàng và hoàn tiền.” | “Hướng dẫn gửi yêu cầu trả hàng hoàn tiền.” | cao | 0.1081 | Sai (thấp hơn kỳ vọng) |
| 2 | “Thời gian nhận tiền hoàn vào ví ShopeePay.” | “Bao lâu thì nhận được tiền hoàn ShopeePay?” | cao | 0.0562 | Sai (rất thấp) |
| 3 | “Người bán khiếu nại đơn hàng.” | “Cách nuôi mèo con mới đẻ.” | thấp | 0.1146 | Sai (lại cao hơn câu cùng nghĩa) |
| 4 | “Video mở hộp quay 6 mặt kiện hàng.” | “Quay video bằng chứng bóc kiện hàng 6 mặt.” | cao | -0.2477 | Sai (điểm âm) |
| 5 | “Chính sách đổi trả cho hàng điện tử.” | “Bí quyết nấu phở bò gia truyền.” | thấp | 0.1293 | Sai (điểm dương cao) |


**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Kết quả bất ngờ nhất là Cặp 4 (“Video mở hộp quay 6 mặt kiện hàng” và “Quay video bằng chứng bóc kiện hàng 6 mặt”) có ngữ nghĩa thực tế gần như tương đồng hoàn toàn nhưng lại nhận điểm cosine âm (-0.2477), trong khi Cặp 3 (“khiếu nại đơn hàng” và “nuôi mèo con”) hoàn toàn khác chủ đề nhưng lại có điểm dương cao hơn (+0.1146). Điều này chứng minh rằng `MockEmbedder` chỉ băm MD5 chuỗi ký tự và sinh vector giả lập ngẫu nhiên (pseudo-random) chứ không hề mã hóa ngữ nghĩa văn bản. Muốn hệ thống hiểu được ý nghĩa thực sự của ngôn ngữ tự nhiên, bắt buộc phải dùng các mô hình embedding chuyên sâu (như Sentence Transformers hoặc OpenAI / Gemini embedding).


---


## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)


Chạy **5 câu hỏi đánh giá của nhóm** trên mã nguồn cá nhân của bạn trong gói `src` (chiến lược `HeadingChunker(max_chunk_size=400)`). **5 câu hỏi này trùng với các thành viên cùng nhóm** (xem `REPORT_NHOM.md` và `ket_qua_benchmark.txt`).


| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Thời gian nhận tiền hoàn vào ví ShopeePay là bao lâu sau khi Shopee chấp nhận? | `thoi-gian-nhan-tien-hoan#12`: `## ⚠️ Lưu ý: * Đối với các đơn hàng thanh toán bằng...` | 0.3459 | Đúng file tài liệu nhưng sai section (là phần lưu ý thanh toán, không chứa mốc 24h) | Nêu các lưu ý về thông tin tài khoản ngân hàng và ví ShopeePay, chưa trích được mốc 24 giờ chính xác. |
| 2 | Lý do 'Đổi ý' có được áp dụng cho sản phẩm Thiết bị Điện tử & Công nghệ có niêm phong/kích hoạt/bảo hành không? | `gui-yeu-cau-tra-hang-hoan-tien#5`: `### Cách 2: Gửi yêu cầu tại mục Trò Chuyện Với Shopee...` | 0.2344 | Không liên quan (bị trôi sang hướng dẫn chat CSKH) | Hướng dẫn mở ứng dụng vào mục chat với Shopee, không trả lời được điều kiện hạn chế của hàng điện tử. |
| 3 | Khi Shopee chấp nhận phương án Trả hàng & Hoàn tiền, thời hạn xử lý là bao lâu? (`audience: buyer`) | `phuong-thuc-gui-hang-hoan-tra-va-phi#1`: `## Hình thức## Các bước trả hàng...` | 0.3249 | Đúng đối tượng người mua (buyer) nhờ filter, nhưng trúng tài liệu phương thức gửi thay vì quy trình Shopee xử lý (6 ngày) | Liệt kê các hình thức trả hàng bưu cục/lấy hàng, chưa nêu được thời hạn 6 ngày. |
| 4 | Các bước gửi yêu cầu Trả hàng/Hoàn tiền trực tiếp tại trang đơn hàng trên ứng dụng Shopee như thế nào? | `thoi-gian-nhan-tien-hoan#4`: `# Thời gian nhận tiền hoàn... Google Pay Thẻ tín dụng/ghi nợ...` | 0.2936 | Không liên quan (trôi sang tài liệu phương thức hoàn tiền) | Giải thích về hoàn tiền qua Google Pay, không hướng dẫn đúng các bước 1 đến 8 tại trang đơn hàng. |
| 5 | Khi khiếu nại hàng bị bể vỡ hoặc lỗi, video mở kiện hàng cần thể hiện rõ những thông tin gì? | `quy-trinh-shopee-xu-ly-yeu-cau-tra-hang#20`: `# Quy trình Shopee xử lý yêu cầu Trả hàng/Hoàn tiền Người mua không thể thao tác...` | 0.3012 | Không liên quan (trôi sang phần câu hỏi thường gặp về thời gian khiếu nại) | Trả lời về việc hết hạn khiếu nại trên hệ thống, không nêu được 3 yêu cầu quay video mở kiện (6 mặt, mã vận đơn, tình trạng hàng). |


**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?**
- **Theo cách chấm ngây thơ (Doc-level Match):** 1 / 5 câu (Câu 1 lọt top-1 đúng tài liệu `thoi-gian-nhan-tien-hoan.md`).
- **Theo cách chấm thực tế (Content-level Grounding):** 0 / 5 câu (do môi trường benchmark sử dụng `MockEmbedder` băm MD5 chuỗi ký tự nên vector bị chi phối bởi hàm băm ngẫu nhiên, không phản ánh ngữ nghĩa).


**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
> 1. **Chấm hai mức (Doc-level vs Content-level):** Đây là phát hiện quan trọng nhất. Một chiến lược có thể đưa đúng file tài liệu vào top-1 (như Câu 1 lọt đúng `thoi-gian-nhan-tien-hoan.md`) nhưng bên trong lại là section sai, không chứa đáp án cần tìm. Nếu chỉ kiểm tra `doc_id` thì kết quả bị thổi phồng giả tạo.
> 2. **Sự đánh đổi trong Chunking:** `HeadingChunker` phân chia theo từng mục rất sạch và giữ được ngữ cảnh tiêu đề, nhưng do không có overlap nên mỗi thông tin chỉ có đúng 1 cơ hội lọt top-k. Nếu embedding bị nhiễu, chunk chứa con số cụ thể dễ bị các chunk khác cùng chủ đề lấn át.
> 3. **Hiệu quả của Metadata Filter:** Ở Câu 3, khi không có filter thì tài liệu của seller lọt lên Top-1 (score 0.3703), nhưng khi áp dụng `metadata_filter={"audience": "buyer"}` thì toàn bộ tài liệu seller bị chặn lại, bảo vệ tác tử không trả lời nhầm đối tượng.


---


## Tự Đánh Giá (Phần Cá Nhân)


| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 10 / 10 |
| **Tổng phần cá nhân** | **60 / 60** |




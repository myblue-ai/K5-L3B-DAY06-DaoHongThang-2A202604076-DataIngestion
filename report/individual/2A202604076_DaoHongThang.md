# Báo cáo cá nhân — Day 6

**Đào Hồng Thắng** · MSSV 2A202604076 · Lớp L3B

## Dữ liệu và pipeline

- **Chủ đề, nguồn, quyền, số trang:**
  - **Nguồn:** *Giáo trình Quản trị học cơ bản* trên VOER (http://voer.edu.vn/c/28562d8b). Em dùng chương 3 (Môi trường quản trị), chương 4 (Thông tin quản trị) và chương 5 (Quyết định quản trị).
  - **Giấy phép:** sách theo CC BY (trang 204–206 của PDF), nên em đưa luôn file PDF vào repo kèm ghi nguồn.
  - **Cách đếm trang:** em đếm theo số trang của trình xem PDF, không theo số "x/204" in ở chân trang. Em bỏ trang 62–63 (chỉ có tình huống Xerox) và trang 91 (chỉ có hình).
  - **Kết quả:** còn **60 trang nội dung, khoảng 120 nghìn ký tự**, không trang nào bị lỗi khi đọc. Chi tiết nằm trong `data/manifest.json` và `results/page_stats.csv`.
- **Chuẩn hóa, lỗi, giới hạn:**
  - **Đọc PDF:** em dùng PyMuPDF đọc theo từng khối chữ (block), mỗi block coi là một đoạn văn.
  - **Chuẩn hóa:** đưa Unicode về NFC, sửa ký tự ghép, nối các dòng bị ngắt, giữ dòng trống giữa các đoạn.
  - **Hai lỗi em thấy khi đọc lại chunk:**
    1. Bản thân file PDF bị dính chữ ở nhiều chỗ, ví dụ "thực tếcủa", "khảnăng".
    2. Số trang in ở chân trang ("99/204") lọt vào văn bản.

    Em chưa sửa hai lỗi này, mà giữ lại để ghi thành hạn chế.
- **Embedding và vector store:**
  - **Model:** `intfloat/multilingual-e5-small` chạy local trên CPU, 384 chiều, đọc tối đa 512 token. Câu hỏi được thêm tiền tố `query:`, tài liệu thêm `passage:` theo hướng dẫn của model.
  - **Vì sao chọn model này:** em không dùng MiniLM như gợi ý trong docs vì MiniLM chỉ đọc được 128 token, chunk dài của B sẽ bị cắt mất. Với e5, chunk dài nhất chỉ 287 token nên không chunk nào bị cắt.
  - **Vector store:** PostgreSQL 16 + pgvector 0.8 chạy trên Docker, tìm kiếm chính xác (exact search) bằng khoảng cách cosine.
  - **Chi phí:** 0 đồng. Cách chạy lại có trong README.
- **Metadata:**
  - **Bắt buộc:** mỗi chunk có `document_id`, `source` (URL), `page` (số trang PDF) và `char_start` để truy về đúng vị trí trong trang.
  - **Trường để lọc:** `chapter` (3/4/5) và `chapter_title`, lấy theo dải trang của mục lục.
  - **Lý do chọn `chapter`:** ba chương dùng chung rất nhiều thuật ngữ như "nội dung", "chức năng", "hình thức". Ngoài ra, người học thường biết mình đang ôn chương nào, nên giá trị chương có thể cho trước khi tìm.

## Cấu hình và benchmark

- **A / B / C:**
  - **A:** cắt cố định 500 ký tự, overlap 50, không lọc.
  - **B:** gom các đoạn văn cho đến tối đa 1.000 ký tự; đoạn nào dài hơn thì tách theo câu. Không lọc.
  - **C:** dùng lại đúng index của B, chỉ thêm điều kiện lọc `chapter` cho những câu có filter.
  - Như vậy A–B chỉ khác cách cắt, còn B–C chỉ khác ở filter. Chunk không bao giờ vượt qua ranh giới trang.
- **Bộ câu hỏi:**
  - 20 câu, gồm 15 dev (q01–q15) và 5 test (q16–q20). Em chốt và commit bộ câu hỏi (commit `cafa587`) trước khi chạy thử.
  - Có đủ các loại: câu hỏi trực tiếp, diễn đạt lại, có điều kiện, và 4 câu có filter (q05, q14, q15, q18). Trong đó q18 thuộc tập test.
  - Em chép evidence từ văn bản đã chuẩn hóa, rồi kiểm tra bằng `python -m src.corpus --validate`.
- **Tiêu chí chọn cấu hình (chốt trước khi chạy):** ưu tiên Hit@3 trên dev; nếu bằng nhau thì xét Hit@1, rồi đến coherence, rồi đến thời gian ingest.

## Kết quả

Một chunk được tính là hit khi nó nằm đúng trang gold **và** chứa nguyên văn evidence.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 8/15 | 12/15 | 289 | ingest 9,7 s · tìm ~40 ms/câu | 0 |
| A | test | 3/5 | 4/5 | 289 | | 0 |
| B | dev | 12/15 | 14/15 | 168 | ingest 9,3 s · tìm ~40 ms/câu | 0 |
| B | test | 4/5 | 4/5 | 168 | | 0 |
| C | dev | 12/15 | 14/15 | 168 (dùng index B) | không tốn thêm | 0 |
| C | test | 4/5 | 4/5 | 168 (dùng index B) | | 0 |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,80 (10) | 15/15 | test 0/1 · dev 2/3 | 1 / 0 / 4 → 1,60 |
| B | 1,90 (10) | 15/15 | test 0/1 · dev 1/3 | 1 / 0 / 4 → 1,60 |
| C | 1,90 (10, cùng chunk với B) | 15/15 | test 1/1 · dev 3/3 | 1 / 0 / 4 → 1,60 |

Khi nạp lại lần 2, số dòng giữ nguyên (A: 289, B: 168), tức là không bị nhân đôi.

**Trace, nhãn và cách chọn mẫu:**
- Trace top-3 của từng cấu hình nằm ở `results/traces_{A,B,C}.jsonl`. Các con số ở bảng trên lấy từ `results/summary.json`, `results/ingest_stats.json` và `results/audit/audit_summary.json`.
- **Coherence:** em chấm 10 vị trí cố định, là điểm giữa của 10 trang đầu (trang 43–52). Các vị trí này được chọn trước khi xem kết quả.
- **Metadata và grounding:** chấm trên 5 câu test.
- **Về cách chấm:** nhãn chấm tay do Claude đề xuất theo thang điểm trong GUIDE, kèm lý do cho từng dòng; sau đó em đọc lại và chỉnh. Người chấm chỉ có một mình em, lại là tác giả bài, nên có thể bị thiên lệch.

## Phân tích và kết luận

- **A so với B:**
  - Cắt theo đoạn tốt hơn hẳn. Trên dev, Hit@1 tăng từ 8 lên 12 câu, coherence tăng từ 0,8 lên 1,9.
  - Chunk của A hay bị cắt giữa từ và giữa câu. Vì vậy A thường tìm đúng trang nhưng chunk xếp đầu lại thiếu đúng câu cần tìm, ví dụ q07, q08, q16.
  - B còn tạo ít chunk hơn (168 so với 289).
  - Trên test, hai cấu hình gần như ngang nhau, và grounding cũng bằng nhau, vì tập test chỉ có 5 câu.
- **B so với C:**
  - Filter không làm tăng Hit, vì với các câu có filter thì B vốn đã tìm được chunk đúng.
  - Cái lợi của filter là top-3 sạch hơn. Ví dụ ở q15, B trả về 2 chunk của chương 4 trong khi câu hỏi về chương 5; C thì toàn chunk chương 5. Tỉ lệ tuân thủ filter tăng từ 1/3 lên 3/3 (dev) và từ 0/1 lên 1/1 (test).
- **Ví dụ sai:**
  - **q03, A sai nhưng B đúng:** chunk `p44:c2` của A đã kể chuyện Rolls Royce, nhưng bị cắt ngay trước câu "Doanh số giảm sút không phải do lỗi của nhà quản trị". B giữ trọn đoạn nên tìm đúng ngay hạng 1.
  - **q18 (test), cả ba đều sai:** câu hỏi "Những hình thức chủ yếu thường được sử dụng trong quản trị là gì?" thiếu chữ "thông tin". C đã lọc đúng chương 4, nhưng vẫn lấy về `p80:c0`, một đoạn nói về "hình thức quản lý thông tin". Filter chỉ thu hẹp về đúng chương, không giải quyết được việc câu hỏi viết mơ hồ.
  - **q12, cả ba đều sai:** câu hỏi diễn đạt lại ("đánh giá tình huống") nên không trùng từ với câu gốc ("xét đoán"). Thêm vào đó, ý văn kéo dài từ trang 101 sang 102, mà chunk lại không được nối qua trang.
- **Chọn cấu hình:**
  - Theo tiêu chí đã chốt, B và C bằng nhau ở mọi tiêu chí, và cả hai đều hơn A. **Em chọn C** vì nó giữ nguyên kết quả của B, lại cho top-3 đúng chương khi biết trước chương cần tìm.
  - Nói cho đúng, tiêu chí "tuân thủ filter" không có trong danh sách em chốt từ đầu, mà em chỉ dùng nó để phân định khi hai cấu hình hòa nhau.
  - C chỉ có ích khi người dùng chọn đúng chương. Nếu chọn sai, C sẽ loại mất chunk đúng; trường hợp này em chưa đo.
- **Hạn chế:**
  - Tập test chỉ có 5 câu nên mỗi câu đã chiếm 20%; không thể kết luận chắc chắn từ chênh lệch trên test.
  - Em so khớp evidence nguyên văn, nên một chunk chứa câu trả lời nhưng diễn đạt khác vẫn bị tính là sai.
  - PDF bị dính chữ và lọt số trang chân trang vào văn bản.
  - Thời gian chỉ đo một lần trên laptop.
  - Kết quả chỉ đúng với bộ dữ liệu 60 trang này.
- **Nếu làm tiếp:**
  - Lọc bỏ số trang chân trang và thử sửa lỗi dính chữ.
  - Cho phép chunk nối qua trang, lưu thêm `page_start` / `page_end`.
  - Thử kết hợp BM25 với tìm kiếm vector, và viết thêm câu hỏi test cho đủ lớn.
- **Về việc dùng AI:** em dùng Claude để hiểu đề, viết khung code và đề xuất nhãn chấm tay. Em tự chạy pipeline, đối chiếu evidence với PDF và đọc lại trace của các câu sai trước khi viết phần phân tích.

# Benchmark

- **20 câu, chia dev/test ngay từ đầu (15 dev: q01–q15, 5 test: q16–q20) và không đổi sau đó.** Test có đủ 4 loại câu (trực tiếp, diễn đạt lại, điều kiện, filter), rải đều 3 chương (ch3: 1 câu, ch4: 2 câu, ch5: 2 câu), trong đó có 1 câu filter (q18, chapter 4).
- **Loại câu:** 7 trực tiếp, 5 diễn đạt lại, 4 điều kiện/ngoại lệ, 4 có filter. Các câu filter dùng khái niệm có ở nhiều chương (môi trường bên trong, nội dung, chức năng, hình thức), nên nếu không filter thì dễ tìm nhầm chương.
- **Nguy cơ rò rỉ:** chỉ được tinh chỉnh cấu hình (chunk size, overlap, top-k...) trên dev. Tập test chỉ chạy một lần, sau khi đã chốt cấu hình. Câu hỏi không chứa số trang hay tên nguồn. Một số câu dùng lại thuật ngữ của sách, nên cấu hình tìm theo từ khóa có thể được lợi trên các câu này.
- **Tiêu chí chọn cấu hình:** ưu tiên Evidence Hit@3 trên dev → nếu bằng nhau thì xét Hit@1 → tiếp theo là coherence của chunk → cuối cùng là thời gian ingest.
- Mọi `evidence_quote` được chép từ `results/pages.jsonl` và đã kiểm tra bằng `python -m src.corpus --validate`.

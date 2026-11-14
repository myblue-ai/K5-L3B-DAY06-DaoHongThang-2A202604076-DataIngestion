# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

---

## Bài làm — Đào Hồng Thắng (2A202604076)

**Corpus:** Giáo trình Quản trị học cơ bản (VOER, CC BY), PDF trang 43–105, gồm 60 trang nội dung thuộc chương 3–5. Chi tiết nguồn, giấy phép và quy tắc đếm trang xem [data/manifest.json](data/manifest.json).
**Embedding:** `intfloat/multilingual-e5-small`, chạy local trên CPU, 384 chiều, chi phí 0 USD.
**Vector store:** PostgreSQL 16 + pgvector 0.8, exact search, khoảng cách cosine.

### Cách chạy lại

Chạy từ thư mục `starter/` (cần Docker, Python 3.12):

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt pymupdf sentence-transformers   # phiên bản chính xác: requirements-lock.txt
Copy-Item .env.example .env        # đặt EMBEDDING_MODEL=intfloat/multilingual-e5-small
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py      # kiểm tra DB + pgvector
python -m src.corpus --validate    # đọc PDF -> results/pages.jsonl, kiểm tra benchmark
python -m src.run                  # index A, B; chạy A/B/C; trace + summary + bảng chấm tay
python -m src.audit                # tổng hợp nhãn chấm tay -> results/audit/audit_summary.json
```

Lần chạy đầu sẽ tải model khoảng 470MB từ Hugging Face. `src.run` không ghi đè các file chấm tay đã có: nếu file đã tồn tại, nó ghi ra file `*.new.csv` thay thế.

### Vị trí các file

| Nội dung | Đường dẫn |
|---|---|
| Code pipeline | [starter/src/](starter/src/): `ingestion`, `corpus`, `chunking`, `embeddings`, `store`, `evaluation`, `run`, `audit` |
| Manifest và PDF | [data/manifest.json](data/manifest.json), `data/raw/` |
| Benchmark (20 câu, 15 dev / 5 test) | [benchmark/](benchmark/) |
| Cấu hình A/B/C | [results/strategies.json](results/strategies.json), [artifacts/experiment_log.csv](artifacts/experiment_log.csv) |
| Trang đã chuẩn hóa, log lỗi | `results/pages.jsonl`, `results/page_stats.csv`, `results/ingest_errors.json` |
| Trace top-3 | `results/traces_{A,B,C}.jsonl` |
| Chỉ số và tài nguyên | `results/summary.json`, `results/ingest_stats.json` |
| Nhãn chấm tay | `results/audit/` |
| Báo cáo | [report/individual/2A202604076_DaoHongThang.md](report/individual/2A202604076_DaoHongThang.md) |

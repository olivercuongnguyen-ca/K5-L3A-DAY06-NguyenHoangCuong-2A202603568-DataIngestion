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

# Bài làm cá nhân — cách cài đặt, chạy và đường dẫn

Chủ đề: so sánh ba chiến lược dữ liệu (A: chunk cố định, B: chunk theo đoạn, C: B + filter `section`) trên bài báo *Large Language Models: A Survey* (arXiv 2402.06196v3, CC BY 4.0). Báo cáo: [report/individual/2A202603568_NguyenHoangCuong.md](report/individual/2A202603568_NguyenHoangCuong.md).

## Cài đặt (từ thư mục `starter/`)

```bash
cd starter
python3.12 -m venv .venv && source .venv/bin/activate      # Python 3.12.16
python -m pip install -r requirements.txt                    # psycopg, pypdf, python-dotenv
python -m pip install fastembed==0.9.1                       # embedding local, không cần API key
cp .env.example .env                                         # rồi đặt EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
docker compose -p day6_student_starter up -d --wait          # PostgreSQL 16 + pgvector 0.8.7
python scripts/check_setup.py                                # kỳ vọng: Setup OK
```

Model: `BAAI/bge-small-en-v1.5` (384 chiều), chạy local, chi phí 0. Không commit `.env`.

## Dữ liệu

File PDF **không** nằm trong repo. Tải đúng bản đã ghim và kiểm tra hash:

```bash
curl -L https://arxiv.org/pdf/2402.06196v3 -o ../data/2402.06196v3.pdf
shasum -a 256 ../data/2402.06196v3.pdf      # phải là c5b884dc070cc6ed3e4ec06214fa84d4afff0873e7e7f66f8dcdcd2285e10914
```

Manifest (nguồn, quyền, trang được tính, quy tắc tính trang): `data/manifest.json`, sinh bằng `python starter/scripts/build_manifest.py` (chạy từ thư mục gốc repo).

## Chạy

```bash
python scripts/verify_benchmark.py       # kiểm tra 20 trích dẫn evidence và quy tắc benchmark -> OK
python -m src.run --splits dev           # chỉ dev (dùng khi phát triển)
python -m src.run                        # dev + test, ba chiến lược (chạy test một lần)
```

## Đường dẫn

| Nội dung | Đường dẫn |
|---|---|
| Benchmark (20 câu: 15 dev / 5 test, gold evidence) | `benchmark/benchmark.json` |
| Code pipeline | `starter/src/` (`ingestion.py`, `chunking.py`, `embeddings.py`, `store.py`, `evaluation.py`, `run.py`) |
| Trace top-3 và chỉ số | `results/traces.jsonl`, `results/summary.json` |
| Nhãn chấm thủ công và lý do | `results/manual_audit.txt` |
| Nhật ký thí nghiệm A/B/C | `artifacts/experiment_log.csv` |
| Báo cáo cá nhân | `report/individual/2A202603568_NguyenHoangCuong.md` |

## Kết quả tóm tắt (lần chạy đầy đủ 2026-11-13)

| Strategy | dev Hit@1 / Hit@3 | test Hit@1 / Hit@3 | Chunk |
|---|---|---|---|
| A (fixed 500/50) | 6/15 / 7/15 | 3/5 / 3/5 | 389 |
| B (paragraph 1200) | 11/15 / 12/15 | 4/5 / 4/5 | 185 |
| C (B + filter section) | 11/15 / 12/15 | 4/5 / 4/5 | 185 |

Mật khẩu PostgreSQL trong `docker-compose.yml` là giá trị cố định chỉ dùng local của starter. Trace chứa văn bản trích từ bài báo CC BY 4.0.

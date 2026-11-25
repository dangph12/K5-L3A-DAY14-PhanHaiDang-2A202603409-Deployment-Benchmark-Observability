# MISSION ANSWERS — Day 14

## Part 1 — Localhost vs Production (CP1)

### Exercise 1.1 — Phát hiện anti-patterns

Các vấn đề trong `01-localhost-vs-production/develop/app.py`:

| Vấn đề | Dẫn chứng | Rủi ro |
|---|---|---|
| Hardcode API key | `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` (dòng 17) | Nếu dùng key thật, push code sẽ làm lộ key. |
| Hardcode thông tin DB | `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` | Lộ tài khoản DB và phụ thuộc cấu hình máy local. |
| Cấu hình cố định | `DEBUG = True`, `MAX_TOKENS = 500` | Phải sửa code để đổi cấu hình giữa các môi trường. |
| Ghi secret vào log | `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` (dòng 34) | Người có quyền đọc log có thể lấy key. |
| Logging bằng print | `print(f"[DEBUG] Got question: {question}")` | Thiếu mức log và cấu trúc phục vụ tìm kiếm, giám sát. |
| Thiếu health check | Không có endpoint `/health` | Nền tảng thiếu endpoint kiểm tra liveness. |
| Chỉ bind localhost | `host="localhost"` | Không nhận kết nối từ bên ngoài container. |
| Port cố định | `port=8000` (dòng 52) | Không đọc biến `PORT` do nền tảng cloud cấp. |
| Bật auto-reload | `reload=True` (dòng 53) | Theo dõi và tải lại code không phù hợp khi chạy production. |
| Thiếu lifecycle cleanup | Không khai báo `lifespan` | Không có bước riêng để giải phóng tài nguyên khi dừng. |

Hardcode secret nguy hiểm vì secret có thể tồn tại trong lịch sử Git dù đã xóa khỏi phiên bản mới. Cần lấy secret từ biến môi trường, không commit và không ghi secret vào log. Key trong bài mẫu là key giả.

### Exercise 1.2 — Chạy bản develop

Môi trường kiểm tra: Python trong `.venv/` ở gốc repo, FastAPI `0.115.0`. Chạy ứng dụng bằng Uvicorn tại `127.0.0.1:18001` để tránh xung đột cổng 8000. Gửi HTTP request bằng thư viện `urllib.request` của Python.

Lệnh tương đương để chạy lại từ gốc repo, trong PowerShell:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app:app --app-dir 01-localhost-vs-production/develop --host 127.0.0.1 --port 18001
```

Mở terminal khác và gọi:

```powershell
curl.exe -i -X POST "http://127.0.0.1:18001/ask?question=Hello"
```

Kết quả thực tế:

```text
POST /ask?question=Hello
HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Ứng dụng dùng mock LLM, không cần key LLM thật.

**Điểm khác với lệnh trong CODE_LAB.md:** endpoint develop khai báo `def ask_agent(question: str)`, nên FastAPI nhận `question` qua query parameter. Gửi JSON body `{"question":"Hello"}` đến `/ask` mà không có query parameter cho kết quả thực tế:

```text
POST /ask
HTTP 422
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

Kết luận: bản develop gọi được API nhưng chưa production-ready vì các vấn đề ở Exercise 1.1. Server kiểm tra đã được dừng sau khi lấy kết quả.

### Exercise 1.3 — So sánh develop và production

| Feature | Develop | Production | Tại sao quan trọng? |
|---|---|---|---|
| Config | Hardcode trong `app.py` | `settings` đọc biến môi trường qua `config.py` | Đổi cấu hình giữa local, staging và production mà không sửa code. |
| Secret | Hardcode và in key vào log | Đọc key từ môi trường; endpoint không log key | Hạn chế lộ thông tin xác thực qua code và log. |
| Health check | Không có | `/health` trả trạng thái, uptime, version | Cung cấp tín hiệu liveness cho hệ thống giám sát. |
| Readiness | Không có | `/ready` trả `503` khi `is_ready` là `False` | Giúp load balancer tránh gửi request khi instance chưa sẵn sàng. |
| Logging | `print()` | `logging`, mức log theo `settings.debug`, định dạng hướng JSON | Hỗ trợ lọc theo mức log và thu thập log tập trung. |
| Shutdown | Không có lifecycle cleanup riêng | `lifespan` có startup và shutdown | Có nơi khởi tạo, đóng kết nối và giải phóng tài nguyên. |
| Host | `localhost` | `settings.host`, mặc định `0.0.0.0` | Nhận kết nối từ bên ngoài container. |
| Port | `8000` cố định | `settings.port` đọc `PORT` | Tương thích port do nền tảng cloud cung cấp. |
| Reload | Luôn bật | Theo `settings.debug`, mặc định tắt | Không bật auto-reload mặc định khi triển khai. |
| Input | Nhận câu hỏi qua query parameter | Đọc JSON body; trả `422` khi câu hỏi thiếu hoặc rỗng | Phản hồi rõ khi request thiếu dữ liệu cần thiết. |

#### Dẫn chứng anti-pattern đã được sửa

Trong `01-localhost-vs-production/develop/app.py`, dòng 52–53:

```python
port=8000,          # ❌ cứng port
reload=True         # ❌ debug reload trong production
```

Trong `01-localhost-vs-production/production/app.py`, dòng 197–198:

```python
port=settings.port,    # ✅ từ PORT env var
reload=settings.debug, # ✅ reload chỉ khi DEBUG=true
```

`production/config.py` đọc `PORT` từ biến môi trường, mặc định `8000`; đọc `DEBUG`, mặc định `false`. Nhờ đó có thể đổi port và bật/tắt reload mà không sửa code.

#### Vì sao cần health check và graceful shutdown?

- **Liveness `/health`:** cho biết ứng dụng còn phản hồi, kèm uptime và phiên bản. Endpoint này không kiểm tra kết nối DB hoặc Redis trong bài mẫu.
- **Readiness `/ready`:** cho biết ứng dụng đã sẵn sàng nhận request. `is_ready` chuyển thành `True` sau startup và thành `False` khi bắt đầu shutdown.
- **Graceful shutdown:** Uvicorn quản lý việc chờ request đang xử lý trong giới hạn timeout; phần shutdown của `lifespan` là nơi đóng tài nguyên. Code mẫu mới mô phỏng cleanup bằng log và `time.sleep(0.1)`, chưa đóng kết nối DB/Redis thật. Hàm `handle_sigterm` chỉ ghi log, không tự thực hiện cơ chế chờ request.

### Tự kiểm tra CP1

- [x] Liệt kê ít nhất 5 anti-pattern kèm dẫn chứng.
- [x] Gọi bản develop thành công và ghi output thực tế.
- [x] Có bảng so sánh develop/production kèm giải thích.
- [x] Chỉ ra anti-pattern được sửa kèm dòng code.
- [x] Giải thích secret, health check và graceful shutdown.

## AI log

### CP1 — Ngày 25/11/2026

- **Đã hỏi:** tìm mẫu Part 1 và hoàn thiện CP1 do đọc thấy code đã có câu trả lời cho CP1.
- **Đã nhận:** Ghi lại nội dung báo cáo.
- **AI đã kiểm tra:** đọc hai bản `app.py` và `production/config.py`; chạy bản develop bằng Python trong `.venv`; gửi request thật, ghi nhận `200` với query parameter và `422` với JSON body thiếu query parameter; dừng server sau kiểm tra.

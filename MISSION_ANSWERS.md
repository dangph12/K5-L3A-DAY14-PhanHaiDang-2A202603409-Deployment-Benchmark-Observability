# MISSION ANSWERS — Day 14

## Part 1 — Localhost vs Production (CP1)

### Exercise 1.1 — Phát hiện anti-patterns

Các vấn đề trong `01-localhost-vs-production/develop/app.py`:

| Vấn đề                  | Dẫn chứng                                                             | Rủi ro                                                      |
| ----------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------- |
| Hardcode API key        | `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` (dòng 17)    | Nếu dùng key thật, push code sẽ làm lộ key.                 |
| Hardcode thông tin DB   | `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` | Lộ tài khoản DB và phụ thuộc cấu hình máy local.            |
| Cấu hình cố định        | `DEBUG = True`, `MAX_TOKENS = 500`                                    | Phải sửa code để đổi cấu hình giữa các môi trường.          |
| Ghi secret vào log      | `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` (dòng 34)             | Người có quyền đọc log có thể lấy key.                      |
| Logging bằng print      | `print(f"[DEBUG] Got question: {question}")`                          | Thiếu mức log và cấu trúc phục vụ tìm kiếm, giám sát.       |
| Thiếu health check      | Không có endpoint `/health`                                           | Nền tảng thiếu endpoint kiểm tra liveness.                  |
| Chỉ bind localhost      | `host="localhost"`                                                    | Không nhận kết nối từ bên ngoài container.                  |
| Port cố định            | `port=8000` (dòng 52)                                                 | Không đọc biến `PORT` do nền tảng cloud cấp.                |
| Bật auto-reload         | `reload=True` (dòng 53)                                               | Theo dõi và tải lại code không phù hợp khi chạy production. |
| Thiếu lifecycle cleanup | Không khai báo `lifespan`                                             | Không có bước riêng để giải phóng tài nguyên khi dừng.      |

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

| Feature      | Develop                          | Production                                                     | Tại sao quan trọng?                                               |
| ------------ | -------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| Config       | Hardcode trong `app.py`          | `settings` đọc biến môi trường qua `config.py`                 | Đổi cấu hình giữa local, staging và production mà không sửa code. |
| Secret       | Hardcode và in key vào log       | Đọc key từ môi trường; endpoint không log key                  | Hạn chế lộ thông tin xác thực qua code và log.                    |
| Health check | Không có                         | `/health` trả trạng thái, uptime, version                      | Cung cấp tín hiệu liveness cho hệ thống giám sát.                 |
| Readiness    | Không có                         | `/ready` trả `503` khi `is_ready` là `False`                   | Giúp load balancer tránh gửi request khi instance chưa sẵn sàng.  |
| Logging      | `print()`                        | `logging`, mức log theo `settings.debug`, định dạng hướng JSON | Hỗ trợ lọc theo mức log và thu thập log tập trung.                |
| Shutdown     | Không có lifecycle cleanup riêng | `lifespan` có startup và shutdown                              | Có nơi khởi tạo, đóng kết nối và giải phóng tài nguyên.           |
| Host         | `localhost`                      | `settings.host`, mặc định `0.0.0.0`                            | Nhận kết nối từ bên ngoài container.                              |
| Port         | `8000` cố định                   | `settings.port` đọc `PORT`                                     | Tương thích port do nền tảng cloud cung cấp.                      |
| Reload       | Luôn bật                         | Theo `settings.debug`, mặc định tắt                            | Không bật auto-reload mặc định khi triển khai.                    |
| Input        | Nhận câu hỏi qua query parameter | Đọc JSON body; trả `422` khi câu hỏi thiếu hoặc rỗng           | Phản hồi rõ khi request thiếu dữ liệu cần thiết.                  |

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

## Part 2 — Docker (CP2)

**Trạng thái:** đã hoàn thành phần đọc code, build image và chạy stack. Người học đã chạy Docker; AI kiểm tra lại image, container và HTTP endpoint ngày 25/11/2026.

### Exercise 2.1 — Dockerfile cơ bản

1. **Base image:** `python:3.11`, được khai báo bằng `FROM python:3.11`. Image cung cấp Python và môi trường hệ điều hành để cài dependencies, chạy ứng dụng.
2. **Working directory:** `/app`, được đặt bằng `WORKDIR /app`. Các lệnh tiếp theo như `COPY ... .`, `RUN` và `CMD` sử dụng thư mục này làm thư mục làm việc.
3. **COPY requirements.txt trước source:** Docker có thể tái sử dụng layer cài dependencies khi chỉ source code thay đổi. Khi requirements thay đổi, bước copy requirements và cài dependencies mới cần chạy lại. Trong Dockerfile develop, thứ tự là copy requirements, `RUN pip install`, rồi copy `app.py` và mock utils. `pip install --no-cache-dir` tắt cache của pip, không tắt Docker layer cache.
4. **CMD và ENTRYPOINT:** `CMD` đặt lệnh hoặc đối số mặc định, có thể bị thay bằng lệnh sau tên image trong `docker run`. `ENTRYPOINT` đặt chương trình chính; với dạng exec, đối số sau tên image được truyền cho chương trình đó. Có thể thay ENTRYPOINT bằng `--entrypoint`. Dockerfile develop dùng `CMD ["python", "app.py"]`, không khai báo ENTRYPOINT riêng.

### Exercise 2.2 — Build và chạy container develop

Các lệnh PowerShell dưới đây chạy từ **gốc repo**. Build context phải là gốc repo vì Dockerfile copy cả `02-docker/develop/...` và `utils/mock_llm.py`.

```powershell
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name cp2-develop -p 8000:8000 my-agent:develop
docker ps --filter name=cp2-develop
curl.exe -i "http://localhost:8000/health"
curl.exe -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker%3F"
docker images my-agent:develop
```

`-p 8000:8000` ánh xạ cổng 8000 của máy host vào cổng 8000 của container. `EXPOSE 8000` trong Dockerfile chỉ mô tả cổng, không tự publish ra host.

Endpoint develop nhận `question` qua query parameter, không nhận JSON body. Dừng ứng dụng cũ đang dùng cổng 8000 trước khi chạy container.

**Output thực tế của người học:**

```text
Output do người học ghi lại:
docker ps
CONTAINER ID   IMAGE                           COMMAND                  CREATED             STATUS                       PORTS                                         NAMES
ade0192c2c4e   my-agent:develop                "python app.py"          9 minutes ago       Up 9 minutes                 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp   suspicious_grothendieck

/health
{"status":"ok","uptime_seconds":468.2,"container":true}

/ask?question="What is Docker?"
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

Output image do người học ghi lại:

docker images my-agent:develop
i Info →   U  In Use
IMAGE              ID             DISK USAGE   CONTENT SIZE   EXTRA
my-agent:develop   1842a068cb3c       1.67GB          426MB    U
```

Sau khi lấy bằng chứng, dừng và xóa container thử nghiệm:

```powershell
docker stop cp2-develop
docker rm cp2-develop
```

### Exercise 2.3 — Multi-stage build

- **Stage 1 — builder:** dùng `python:3.11-slim`; cài `gcc`, `libpq-dev`; cài Python dependencies bằng `pip install --user` vào `/root/.local`.
- **Stage 2 — runtime:** bắt đầu lại từ `python:3.11-slim`; copy dependencies từ builder sang `/home/appuser/.local`, copy `main.py` và mock utils; chạy bằng user `appuser`; khai báo health check; khởi động Uvicorn với 2 worker.
- **Vì sao image nhỏ hơn:** runtime không kế thừa các layer cài compiler và build dependencies của builder. So với develop, runtime còn dùng base `slim` thay cho bản Python đầy đủ. Final image vẫn có Python và các công cụ có sẵn trong base image; multi-stage không có nghĩa tự động xóa pip.
- **Lưu ý:** 2 worker Uvicorn trong một container không phải 2 replica container. Chỉ xác nhận mức giảm dung lượng sau khi đo.

Build từ gốc repo:

```powershell
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

**Output và bảng số đo thực tế:**

```text
docker images my-agent
IMAGE               ID             DISK USAGE   CONTENT SIZE
my-agent:advanced   09397ab052b8        240MB         57.4MB
my-agent:develop    1842a068cb3c       1.67GB          426MB

docker image inspect my-agent:develop my-agent:advanced --format '{{.RepoTags}} {{.Size}}'
[my-agent:develop] 1667792174
[my-agent:advanced] 239815423
```

| Image             | Kích thước đo được (MB) |
| ----------------- | ----------------------: |
| my-agent:develop  |                 1667.79 |
| my-agent:advanced |                  239.82 |

Tỷ lệ giảm so với develop: **(size_develop − size_advanced) / size_develop × 100%**.

Để tính nhất quán từ kích thước byte, chạy PowerShell sau; `MB` ở đây là đơn vị thập phân, 1 MB = 1.000.000 byte:

```powershell
$developBytes = [double](docker image inspect my-agent:develop --format '{{.Size}}')
$advancedBytes = [double](docker image inspect my-agent:advanced --format '{{.Size}}')
"Develop: {0:N2} MB" -f ($developBytes / 1000000)
"Production: {0:N2} MB" -f ($advancedBytes / 1000000)
"Giam so voi develop: {0:N2}%" -f (($developBytes - $advancedBytes) / $developBytes * 100)
```

**Kết luận từ số đo:** image production giảm **85,62%**, tính từ số byte chính xác: `(1667792174 − 239815423) / 1667792174 × 100`. Bảng dùng MB thập phân từ trường `.Size`, tương ứng cột DISK USAGE làm tròn ở trên; không trộn với CONTENT SIZE.

### Exercise 2.4 — Docker Compose stack

```mermaid
flowchart LR
    client["Client"]

    subgraph internal["Docker bridge network: internal"]
        nginx["Nginx :80<br/>Reverse proxy, rate limit"]
        agent["FastAPI agent :8000<br/>1 container, 2 Uvicorn worker<br/>Mock LLM"]
        redis["Redis :6379"]
        qdrant["Qdrant :6333"]

        nginx -->|"HTTP agent:8000"| agent
        agent -.->|"REDIS_URL: chưa dùng trong main.py"| redis
        agent -.->|"QDRANT_URL: chưa dùng trong main.py"| qdrant
    end

    client -->|"HTTP localhost:80"| nginx
    redis --- redis_data[("Volume: redis_data")]
    qdrant --- qdrant_data[("Volume: qdrant_data")]
```

Nét đứt biểu thị kết nối đã cấu hình nhưng code agent chưa sử dụng. Agent chờ Redis và Qdrant healthy khi khởi động. Cổng 443 được publish nhưng chưa cấu hình HTTPS trong Nginx.

| Thành phần | Vai trò và kết nối                                                                                                                    |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Client     | Gửi HTTP đến host cổng 80.                                                                                                            |
| Nginx      | Publish `80:80`; proxy request đến `agent:8000`; áp dụng rate limit 10 request/giây/IP, burst 20. `/health` không áp dụng rate limit. |
| Agent      | FastAPI, không publish cổng trực tiếp ra host; nhận request từ Nginx qua network `internal`.                                          |
| Redis      | `redis:7-alpine`, cổng nội bộ 6379; volume `redis_data`; cấu hình giới hạn bộ nhớ 256 MB và eviction `allkeys-lru`.                   |
| Qdrant     | `qdrant/qdrant:v1.9.0`, cổng HTTP nội bộ 6333; volume `qdrant_data` lưu dữ liệu vector.                                               |

Các service cùng tham gia bridge network tên logic `internal`. Docker DNS cho phép dùng tên service, ví dụ `agent:8000`, `redis:6379`, `qdrant:6333`, thay vì hardcode IP.

Compose truyền `REDIS_URL=redis://redis:6379/0` và `QDRANT_URL=http://qdrant:6333` cho agent. Tuy nhiên, `production/main.py` hiện chỉ gọi mock LLM, chưa sử dụng Redis/Qdrant. Vì vậy đây là các kết nối đã cấu hình cho mở rộng, chưa phải luồng truy cập dữ liệu đã được thực thi.

Agent chờ Redis và Qdrant có trạng thái healthy trước khi khởi động. Nginx phụ thuộc agent nhưng `depends_on` ở đây không chờ agent healthy. Compose không cấu hình replica, nên mặc định chạy một container agent, dù comment đầu file ghi 2 replica.

Docker health check đánh dấu healthy/unhealthy; bản thân trạng thái unhealthy không tự kích hoạt restart. `restart: unless-stopped` xử lý trường hợp tiến trình container thoát. Nginx publish cả cổng 443 nhưng file cấu hình chỉ có `listen 80`, chưa cấu hình HTTPS/certificate.

Chạy từ gốc repo. Tạo `.env.local` trống nếu chưa tồn tại, không ghi đè file hiện có:

```powershell
if (-not (Test-Path -LiteralPath '02-docker/production/.env.local')) {
    New-Item -ItemType File -Path '02-docker/production/.env.local' | Out-Null
}
docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml up -d --build
docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml ps
curl.exe -i "http://localhost/health"
$askBody = '{"question":"Explain microservices"}'
$askBody | curl.exe -i -X POST "http://localhost/ask" -H "Content-Type: application/json" --data-binary '@-'
```

Production nhận JSON body, khác develop. Cách truyền body qua stdin tránh lỗi escape dấu nháy trên Windows PowerShell.

**Output thực tế qua Nginx:**

```text
Output do người học ghi lại:
/health
{"status":"ok","uptime_seconds":51.1,"version":"2.0.0","timestamp":"2026-11-25T08:50:09.913626"}

/ask
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

AI kiểm tra lại bằng HTTP request thực tế ngày 25/11/2026:

```text
GET http://localhost:8000/health
HTTP 200
{"status":"ok","uptime_seconds":1805.2,"container":true}

POST http://localhost:8000/ask?question=What%20is%20Docker%3F
HTTP 200
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

GET http://localhost/health
HTTP 200
{"status":"ok","uptime_seconds":178.5,"version":"2.0.0","timestamp":"2026-11-25T08:52:17.356038"}

POST http://localhost/ask
Body: {"question":"Explain microservices"}
HTTP 200
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Container thực tế quan sát bằng `docker ps -a`:

```text
NAME                       IMAGE                  STATUS                  PORTS
production-nginx-1         nginx:alpine           Up 2 minutes            80:80, 443:443
production-agent-1         production-agent       Up 2 minutes (healthy)  8000/tcp
production-redis-1         redis:7-alpine          Up 3 minutes (healthy)  6379/tcp
production-qdrant-1        qdrant/qdrant:v1.9.0    Up 3 minutes (healthy)  6333-6334/tcp
suspicious_grothendieck    my-agent:develop       Up 29 minutes           8000:8000
```

Stack người học chạy dùng Compose project `production`, khác tên project trong các lệnh hướng dẫn. Khi xem log hoặc dừng stack hiện tại, dùng `-p production` thay cho `-p k5-day14-docker`. Container develop thực tế tên `suspicious_grothendieck`, thay cho `cp2-develop` trong lệnh dọn container. AI chỉ đọc trạng thái và gọi API, chưa dừng container.

Lệnh debug khi cần:

```powershell
docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml logs --tail 100 agent nginx
docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml exec agent sh
```

Sau khi lưu output, dừng stack; lệnh không dùng `-v` nên giữ named volumes:

```powershell
docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml down
```

### Tự kiểm tra CP2

- [x] Trả lời 4 câu Exercise 2.1.
- [x] Giải thích hai stage và Docker layer cache.
- [x] Mô tả service, network và có sơ đồ stack.
- [x] Chạy container develop, dán output API.
- [x] Đo kích thước hai image, tính phần trăm chênh lệch.
- [x] Chạy Compose, dán kết quả test qua Nginx.

## AI log

### CP1 — Ngày 25/11/2026

- **Đã hỏi:** tìm mẫu Part 1 và hoàn thiện CP1 do đọc thấy code đã có câu trả lời cho CP1.
- **Đã nhận:** Ghi lại nội dung báo cáo.
- **AI đã kiểm tra:** đọc hai bản `app.py` và `production/config.py`; chạy bản develop bằng Python trong `.venv`; gửi request thật, ghi nhận `200` với query parameter và `422` với JSON body thiếu query parameter; dừng server sau kiểm tra.

### CP2 — Ngày 25/11/2026

- **Đã hỏi:** điền CP2 vào báo cáo; người học tự chạy Docker.
- **Đã nhận:** 4 đáp án Dockerfile, giải thích multi-stage/cache, sơ đồ stack, lệnh PowerShell và các ô chờ bằng chứng thực tế.
- **AI đã kiểm tra:** đọc code và cấu hình; sau khi người học chạy Docker, đọc `docker images`, `docker image inspect`, `docker ps -a`; gọi lại develop và Nginx, xác nhận cả bốn request trả `200`; tính mức giảm 85,62% từ kích thước byte thực tế. Không build hoặc dừng container trong lần kiểm tra này.
- **Tự sửa và tự kiểm tra của người học:** đã chạy Docker, bổ sung output develop, kích thước image và response qua Nginx vào báo cáo; thông báo đã chạy xong để kiểm tra lại.
- **Cập nhật sơ đồ:** theo yêu cầu người học, AI thay liên kết draw.io bằng sơ đồ Mermaid trực tiếp trong Exercise 2.4, đối chiếu với Compose và luồng xử lý đã đọc trong `main.py`.

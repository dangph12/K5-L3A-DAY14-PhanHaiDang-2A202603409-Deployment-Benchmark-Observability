# Deployment Information

## Public URL

https://day14-agent-gm6b.onrender.com

## Platform

Render, agent Part 6 trong `06-lab-complete/`.

- Service ID: `srv-dc3bf00u01pc73e5q6pg`
- Deployment ID: `dep-dc3bgdkipgvc7386rgjg`
- Người học thông báo deployment succeeded.
- Blueprint: `06-lab-complete/render.yaml`; root directory: `06-lab-complete`.

## Test Results

Kiểm tra public URL thực tế ngày 25/11/2026, không gửi API key:

```text
GET /health
HTTP 200
{"status":"ok"}

GET /ready
HTTP 200
{"ready":true}

POST /ask
Body: {"question":"Hello"}
HTTP 401
{"detail":"Missing or invalid API key"}
```

`/ready` trả 200 nghĩa là Redis ping thành công theo code đã triển khai. Người học đã chạy request `/ask` có key và nhận `200`. AI đã xem ảnh `screenshots/test.PNG`, xác nhận đủ bốn mã theo thứ tự `200`, `200`, `401`, `200`; ảnh không hiển thị giá trị key thật. CP6 đã đủ bằng chứng.

## Test Commands — Windows CMD

Đặt biến `BASE` và `AGENT_API_KEY` trong terminal riêng. Lấy key ở Environment của service agent trên Render; không ghi key thật vào file này hoặc ảnh chụp.

```cmd
set "BASE=https://day14-agent-gm6b.onrender.com"
set "AGENT_API_KEY=THAY_BANG_KEY_TREN_RENDER"
curl.exe -sS -o NUL -w "%{http_code}\n" "%BASE%/health"
curl.exe -sS -o NUL -w "%{http_code}\n" "%BASE%/ready"
echo {"question":"Hello"}|curl.exe -sS -o NUL -w "%{http_code}\n" -X POST "%BASE%/ask" -H "Content-Type: application/json" --data-binary @-
echo {"question":"Hello"}|curl.exe -sS -o NUL -w "%{http_code}\n" -X POST "%BASE%/ask" -H "Content-Type: application/json" -H "X-API-Key: %AGENT_API_KEY%" --data-binary @-
```

Kỳ vọng: `200`, `200`, `401`, `200`. Chỉ chụp kết quả, không chụp dòng đặt key hoặc giá trị header.

## Environment Variables

Blueprint khai báo `ENVIRONMENT=production`, `AGENT_API_KEY` tự sinh, `REDIS_URL` từ service `day14-cache`, `RATE_LIMIT_PER_MINUTE=10`, `DAILY_BUDGET_USD=1.0`. Docker CMD đọc `PORT` do nền tảng cấp. Không cần API key LLM thật vì ứng dụng dùng mock LLM.

## Screenshots

- [Deployment dashboard](screenshots/dashboard.PNG): service `day14-agent` ở trạng thái Live, commit `1f593c4`.
- [Service running](screenshots/running.PNG): URL public `/health` trả `{"status":"ok"}`.
- [Test results](screenshots/test.PNG): bốn mã HTTP `200`, `200`, `401`, `200`.

AI đã mở và đối chiếu cả ba ảnh; dùng đúng phần mở rộng `.PNG` để liên kết hoạt động trên hệ thống phân biệt chữ hoa/thường.

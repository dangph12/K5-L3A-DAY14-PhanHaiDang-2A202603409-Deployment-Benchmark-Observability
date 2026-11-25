# Benchmark & Observability Report — Day 14

> CP7 đã hoàn thành. Mục 4–6 thuộc CP8, chưa thực hiện và chưa có số đo production.
> Mọi con số CP7 dưới đây lấy từ JSON trong `06-lab-complete/benchmark-observability/develop/reports/`.

**Họ tên:** Phan Hải Đăng
**Ngày chạy:** 25/11/2026, bắt đầu 19:31 và kết thúc 19:34 (GMT+7).
**Môi trường:** Windows 10 build 19045, Python 3.13.14 trong `.venv` tại gốc repo; Intel Core i7-7700HQ 2,80 GHz, 4 core/8 logical CPU, RAM 25.614.184.448 byte. Hai phiên bản được chạy local lần lượt ở cổng 8001 và 8002, không gọi URL Render.

**Điều kiện đo:** một process Uvicorn cho mỗi agent; model `mock-llm-small`; 300 request mỗi load test, warm-up bị loại khỏi số đo. Load giữ `MOCK_ERROR_RATE=0.01`, latency cơ bản 120 ms, jitter 60 ms, retrieval 20 ms, slow delay thêm 1.500 ms. Bảng concurrency dùng slow rate 0.03; bảng tail dùng concurrency 20. Eval tắt `MOCK_ERROR_RATE` và `MOCK_SLOW_RATE` để tách chất lượng khỏi lỗi ngẫu nhiên. Không đặt random seed; mỗi cấu hình chỉ chạy một lần, không chọn lại kết quả đẹp.

Latency của `load_test.py` chỉ tính trên response `200`; RPS đếm cả request thành công và lỗi. Load test và eval baseline chạy trước khi bổ sung KB và metric độ dài câu hỏi. Eval cuối và snapshot metrics chạy sau hai thay đổi đó. Metadata: `develop/reports/cp7_run.json` (đường dẫn tính từ thư mục benchmark-observability).

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Giới hạn độ trễ cho phần lớn request, tránh average che giấu request chậm. |
| Error rate `/ask` | ≤ 2% | Theo ngưỡng mặc định của load test, error budget 2%. |
| Accuracy trên golden dataset | ≥ 80% cho baseline; 100% cho v2 sau sửa | Default gate dùng để so sánh, gate cuối CP7 phải đúng đủ 23 câu và không regression. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.17 | 205.9 | 235.4 | 1726.4 | 1.67% | PASS |
| 10 | 37.06 | 203.0 | 241.9 | 1710.3 | 0.33% | PASS |
| 50 | 38.20 | 596.0 | 4333.0 | 5482.3 | 2.00% | FAIL: p95 |
| 100 | 37.71 | 1380.4 | 5433.7 | 5940.4 | 0.67% | FAIL: p95 |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

RPS không tăng tuyến tính: từ concurrency 10 lên 50, RPS chỉ tăng từ 37.06 lên 38.20; lên 100 còn 37.71. Đồng thời p95 tăng mạnh. Trong lần đo này, tăng số request chờ không làm tăng khả năng xử lý tương ứng. CPU, event loop, logging đồng bộ và chi phí HTTP/client trên cùng máy đều có thể góp phần; chưa profile để kết luận thành phần nào là nút thắt chính. Không suy ra đây là giới hạn của production trên cloud.

Nguồn: `load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`. Các file `.log` cùng tên ghi output SLO; runner ghi exit code 1 cho hai cấu hình FAIL và vẫn giữ JSON.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 222.7 | 509.0 | 553.7 |
| 0.03 (mặc định) | 302.2 | 1681.6 | 1731.3 |
| 0.1 | 419.7 | 1716.8 | 1737.6 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

Từ slow rate 0 lên 0.03, avg tăng 79.5 ms, còn p99 tăng 1177.6 ms và p95 tăng 1172.6 ms. Tail percentile phản ánh nhóm request chậm rõ hơn average. Khi 10% request có thể chậm, p95 cũng rơi vào vùng tail. Trong mẫu 0.03 này, p95 đã tăng mạnh; cấu hình xác suất không bảo đảm đúng 3% trên 300 request, và latency còn chịu ảnh hưởng môi trường local.

Ngay slow rate 0, p95 là 509.0 ms, nhỉnh hơn SLO 500 ms; không được diễn giải rằng tắt slow injection bảo đảm PASS. Cả ba lượt tail đều FAIL p95, vẫn nộp nguyên kết quả. Nguồn: `load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.3 | 109.1 | 113.5 |
| Tổng cost (USD) | 0.000406 | 0.000762 | 0.000789 |
| Cost / câu đúng (USD) | 0.00040635 | 0.00003627 | 0.00003430 |
| Quality gate | FAIL (min 80%) | PASS (min 80%, 0 regression) | PASS (min 100%, 0 regression) |

Nguồn: `eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`. Accuracy trong JSON được làm tròn 4 chữ số thập phân; số câu đúng là số đếm gốc. `cost_per_correct_usd` được tính trước khi tổng cost được làm tròn để hiển thị, nên không tính lại từ tổng cost đã làm tròn trong bảng. Đây là chi phí mock theo bảng giá trong code, không phải phí API thực tế.

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm tài liệu phân biệt JWT có chữ ký/thời hạn và API key; keyword kích hoạt `jwt`, `api key`. |
| scaling-03 | cpu, memory, custom metrics | Thêm tài liệu Kubernetes HPA scale pod theo CPU, memory hoặc custom metrics; keyword `hpa`, `kubernetes`, `autoscal`. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Retrieval tăng context và token, nên v2 tốn nhiều chi phí mỗi câu hơn v1. Đổi lại, số câu đúng tăng từ 1 lên 21 và sau sửa KB lên 23. Cost/câu đúng giảm mạnh; v2 sau sửa tốn thêm tổng 0.000027 USD mock so với v2 ban đầu nhưng trả lời đúng thêm hai câu. Không dùng 23 câu eval để kết luận hiệu năng; latency cần dựa vào load test ở mục 2.

### 3.1 Quality gate và chặn merge

Đã gọi v1 với baseline v2 và lưu `eval_v1_regression.json`: accuracy 4.35%, 20 regression, quality gate FAIL, exit code **1**. Eval cuối v2 dùng `--min-accuracy 1.0 --baseline reports/eval_v2.json`, đạt **23/23**, 0 regression, exit code **0**. Log: `eval_v1_regression.log`, `eval_v2_fixed.log`.

Trong CI, cài `develop/requirements.txt`, bật v2 với fault injection tắt, chờ `/health` trả 200 rồi chạy bước sau từ thư mục develop:

```yaml
- name: Eval quality gate
  run: python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.85 --baseline reports/eval_v2_fixed.json --out reports/eval_ci.json
```

Không dùng `continue-on-error` hoặc `|| true`: exit code 1 phải làm job fail. Đặt job này làm required status check trong branch protection/ruleset để chặn merge. Baseline cố định hiện có 23 câu đúng nên bất kỳ câu nào từ đúng thành sai cũng bị chặn, kể cả tổng accuracy còn trên 85%. Đây là cách cấu hình CI được giải thích trong bài, chưa xác nhận đã bật ruleset trên GitHub.

### 3.2 Metrics — Exercise 7.1

Đã thêm Histogram `agent_question_length_chars`, buckets 10, 25, 50, 100, 200, 500, 1000, 2000 ký tự. Mỗi body `/ask` hợp lệ được observe một lần. Không thêm question hoặc request ID làm label.

Ví dụ thật từ `develop/reports/metrics_v2_fixed.txt` sau eval cuối:

```text
# TYPE http_requests_total counter
http_requests_total{method="POST",route="/ask",status="200"} 23.0
# TYPE agent_in_flight_requests gauge
agent_in_flight_requests 0.0
agent_question_length_chars_bucket{le="50.0"} 16.0
agent_question_length_chars_count 23.0
agent_question_length_chars_sum 1066.0
```

Counter chỉ tăng; Gauge có thể tăng/giảm; Histogram đếm quan sát theo bucket, có count/sum để tính phân bố. Snapshot xác nhận metric độ dài đã ghi đủ 23 câu, tổng 1066 ký tự.

Middleware dùng `route.path` để gom theo route template, ví dụ `/ask`, và `unmatched` cho URL không khớp. Nếu dùng URL thật, bot quét hàng nghìn đường dẫn lạ sẽ tạo hàng nghìn tổ hợp label/time series, làm tăng RAM và chi phí scrape/lưu trữ.

### 3.3 Tính toàn vẹn và chạy lại

Golden dataset giữ nguyên SHA256 `22E672344EF72779959F3CF480391CEF247B2F8CE86415010DDEA9B315E959EC`. Không sửa `load_test.py`, `eval/run_eval.py` hoặc dữ liệu chấm. Chỉ bổ sung KB và metric trong agent; helper `develop/run_cp7.py` gọi các lệnh lab, lưu log và dừng server do chính nó tạo.

Từ gốc repo, chạy lại eval cuối bằng CMD:

```cmd
.venv\Scripts\python.exe 06-lab-complete\benchmark-observability\develop\run_cp7.py fixed
```

Phase `measure` dành cho KB ban đầu; helper từ chối ghi đè baseline nếu `eval_v2.json` đã tồn tại. Muốn đo lại baseline phải lưu riêng report cũ và khôi phục KB ban đầu trước. Khi chạy lại và thay đổi số liệu, cần cập nhật các bảng tương ứng.

---

## 4. Observability stack (production)

**Chưa thực hiện — CP8.** Các ô dưới đây chờ dữ liệu thật từ Docker stack.

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

**Chưa thực hiện — CP8.** Chưa có CSV scale 1/3 instance.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

**Chờ hoàn tất CP8** để kết luận cả benchmark và observability.

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...

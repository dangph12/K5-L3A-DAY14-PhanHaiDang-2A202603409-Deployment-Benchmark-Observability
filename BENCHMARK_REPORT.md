# Benchmark & Observability Report — Day 14

> CP7 và CP8 đã hoàn thành. Số đo, trace/log và bốn ảnh CP8 đã được đối chiếu; stack lab đã được dọn sau khi lưu bằng chứng.
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

Nguồn: `load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`. Hai cấu hình FAIL trả exit code 1 và vẫn lưu JSON. Log console lặp đã bỏ khi đóng gói; kết quả SLO có trong từng JSON.

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

Đã gọi v1 với baseline v2 và lưu `eval_v1_regression.json`: accuracy 4.35%, 20 regression, quality gate FAIL, exit code **1**. Eval cuối v2 dùng `--min-accuracy 1.0 --baseline reports/eval_v2.json`, đạt **23/23**, 0 regression, exit code **0**. Trường `quality_gate` trong các JSON giữ kết quả; log console lặp đã được bỏ.

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

Golden dataset giữ nguyên SHA256 `22E672344EF72779959F3CF480391CEF247B2F8CE86415010DDEA9B315E959EC`. Không sửa `load_test.py`, `eval/run_eval.py` hoặc dữ liệu chấm. Chỉ bổ sung KB và metric trong agent. Helper điều phối tạm đã được bỏ khi đóng gói; dùng trực tiếp lệnh gốc bên dưới để chạy lại.

Từ gốc repo, terminal CMD thứ nhất chạy agent v2 với fault injection tắt:

```cmd
set "AGENT_VERSION=v2"
set "PORT=8002"
set "MOCK_ERROR_RATE=0"
set "MOCK_SLOW_RATE=0"
set "PYTHONUTF8=1"
cd 06-lab-complete\benchmark-observability\develop
..\..\..\.venv\Scripts\python.exe app.py
```

Terminal CMD thứ hai, từ gốc repo:

```cmd
set "PYTHONUTF8=1"
cd 06-lab-complete\benchmark-observability\develop
..\..\..\.venv\Scripts\python.exe eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json
```

Không ghi đè baseline v1/v2 ban đầu bằng KB đã sửa. Muốn đo lại baseline phải lưu riêng report cũ và khôi phục KB ban đầu trước. Khi chạy lại và thay đổi số liệu, cập nhật các bảng tương ứng.

---

## 4. Observability stack (production)

Đã khởi động project `k5-day14-observability`, thu metrics bằng Prometheus, trace qua OpenTelemetry/Jaeger và tạo tải Locust. Người học đã chụp đủ ảnh; AI đã mở từng ảnh và đối chiếu với bằng chứng đã lưu.

### 4.1 Screenshot

- [x] [Dashboard Grafana khi có tải](screenshots/grafana-dashboard.png): thấy Golden Signals, 2 instance, traffic, error rate và latency.
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png): ID bắt đầu `5b759e2`, tổng khoảng 1,8 giây, span LLM khoảng 1,7 giây.
- [x] [Trace lỗi trong Jaeger](screenshots/jaeger-error-trace.png): ID bắt đầu `f90c083`, HTTP 503, span LLM có event `exception`.
- [x] [Prometheus Alerts](screenshots/prometheus-alert-firing.png): cùng thấy `AgentHighErrorRate` và `AgentHighLatencyP95` **firing**.

Ảnh Grafana được chụp sau snapshot đo: hiển thị khoảng 15,4 req/s, error rate 19,50%, p95 1,90 giây và 2 instance. Giá trị realtime thay đổi theo cửa sổ thời gian; số liệu báo cáo bên dưới lấy từ snapshot/CSV đã nêu rõ, không thay bằng giá trị ở thời điểm chụp khác. Đuôi bốn ảnh CP8 được chuẩn hóa `.png` để khớp liên kết và tên yêu cầu.

**Exercise 7.4 — đọc dashboard:** snapshot `production/benchmark-results/baseline_2_agents.json`, lúc 20:07:58 ngày 25/11/2026 (GMT+7), với 2 agent và tải web 30 users / ramp 5 users/giây:

1. p95 `/ask` = **295.59 ms**, average = **242.02 ms**, chênh **53.57 ms**. p95 được ước lượng từ histogram Prometheus trong cửa sổ 1 phút; không phải cùng cách tính percentile chính xác của load JSON CP7. Average không mô tả đầy đủ nhóm request chậm.
2. RPS hai instance là **9.15** (`172.20.0.5:8000`) và **9.16** (`172.20.0.8:8000`), gần đều trong cửa sổ quan sát. Đây là bằng chứng phân tải thực tế, không bảo đảm mọi khoảng thời gian luôn chia đúng 50/50.
3. Input **1397.62 tokens/s**, output **729.38 tokens/s**. Input gồm system prompt, tài liệu retrieval và câu hỏi; output là câu trả lời ngắn nên input lớn hơn.
4. Gọi `http://localhost:8080/metrics` thực tế trả **404**. Nginx chặn route này; Prometheus scrape thẳng từng agent trong mạng Docker.

**Kiểm tra alert rules:** chạy `promtool test rules /p/alert_rules_test.yml` bằng image Prometheus của stack, kết quả `SUCCESS`. Không sửa rule hoặc file test để làm alert firing.

**Sửa lỗi khởi động:** agent ban đầu báo `ModuleNotFoundError: No module named 'uvicorn'`. Dockerfile copy user packages vào `/home/agent/.local`, còn home của user là `/app`; đã thêm `PYTHONUSERBASE=/home/agent/.local`. Kiểm tra lại trong container: UID 999, user site `/home/agent/.local/lib/python3.11/site-packages`, import Uvicorn 0.30.0 thành công. Hai tài liệu KB JWT/HPA từ CP7 cũng đã được đồng bộ sang production.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2`, slow rate giữ 0.03 | `AgentHighErrorRate` | 87.4 giây | Error rate: 19.73%; p95 295.90 ms |
| B | `MOCK_SLOW_RATE=0.3`, tiếp tục giữ error rate 0.2 từ A | `AgentHighLatencyP95`; cùng `AgentHighErrorRate` firing | 160.9 giây từ lúc đổi slow rate | p95 1897.40 ms, avg 597.18 ms, error rate 20.75% |
| C | `LLM_MODEL=mock-llm-large` | Không thực hiện; không gán alert baseline cho thí nghiệm chưa chạy | Không đo | Không đo |
| D | `docker pause` 1 instance | Không thực hiện | Không đo | Không đo |
| E | `AGENT_VERSION=v1` | Không thực hiện trong stack; CP7 đã có eval downgrade chứng minh regression | Không đo | Chất lượng phải theo dõi bằng eval, không chỉ metric hạ tầng |

Đã thực hiện hai thay đổi bắt buộc A và B, không chạy C/D/E trong stack. B giữ lỗi từ A để có ít nhất hai alert cùng firing cho ảnh nộp, không phải phép thử độc lập chỉ thay một biến so với baseline.

Thời gian đo từ `changed_at` trước lệnh Compose recreate đến lần đầu quan sát alert firing; bao gồm thời gian tạo lại container, DNS/scrape và đánh giá rule, không chỉ giá trị `for`. Poll mỗi 5 giây nên thời điểm quan sát có độ phân giải khoảng 5 giây. A đổi lúc `2026-11-25T13:07:58.261853+00:00`, thấy firing lúc `13:09:25.689606+00:00`; B đổi lúc `13:09:25.799664+00:00`, thấy firing lúc `13:12:06.688731+00:00`.

Nguồn: `experiment_a_change.json`, `experiment_a_alerts.json`, `experiment_a_snapshot.json`, `experiment_b_change.json`, `experiment_b_alerts.json`, `alerts_firing_snapshot.json` trong `production/benchmark-results/`. Snapshot cuối xác nhận **AgentHighErrorRate và AgentHighLatencyP95 cùng firing**. Không hạ ngưỡng hay sửa `for` để đạt kết quả.

`LLMCostBurnRateHigh` đã firing ngay từ baseline model nhỏ (snapshot khoảng 4.13 USD/giờ mock). Không tính đó là kết quả thí nghiệm đổi model C. Tại snapshot cuối, burn rate còn khoảng 1.58 USD/giờ và alert cost đã hết firing; cost ở đây hoàn toàn mô phỏng, không có hóa đơn API thật.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Metric hạ tầng chỉ cho biết tốc độ, lỗi HTTP, tài nguyên và chi phí; trả lời sai vẫn có thể HTTP 200 và nhanh hơn. Cần quality gate trên golden dataset trước deploy, eval định kỳ hoặc shadow/canary trên traffic thật, theo dõi accuracy theo phiên bản và feedback người dùng. CP7 đã chứng minh downgrade v1 có 20 regression dù request vẫn được xử lý; không suy ra metric xanh nghĩa là câu trả lời đúng.

### 4.3 Debug bằng trace

Trace chậm nhất trong tập kết quả đã truy vấn và đối chiếu được với log của container hiện tại:

- `trace_id`: `5b759e26f97e23a2b5bc72c6140589ff`.
- Tổng thời gian: **1770.017 ms**.
- Span LLM `chat mock-llm-small`: **1681.862 ms**, chiếm **95.02%** thời gian trace. Đây là span con xử lý công việc chậm; không cộng thời lượng span cha/con vì bị tính trùng.
- Mở Jaeger: http://localhost:16686/trace/5b759e26f97e23a2b5bc72c6140589ff
- Dữ liệu: `trace_slow.json`, `trace_slow_log.json`, `trace_summary.json` trong `production/benchmark-results/`.
- Dòng log JSON cùng trace_id (giá trị `llm_ms` trong log là latency mô phỏng do mock trả về; span đo wall-clock thực tế nên có thể khác nhẹ):

```json
{"ts":"2026-11-25T13:11:42.389236+00:00","level":"INFO","service":"observable-agent","instance":"55864082354f","event":"llm_call","trace_id":"5b759e26f97e23a2b5bc72c6140589ff","span_id":"c3acbcbb9981f363","request_id":"5dfa769086a4","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":0.000047,"llm_ms":1681.1}
```

**Trace lỗi:** `f90c08398270acd34187636f0156dc36`, tổng **931.854 ms**. Span `chat mock-llm-small` có status ERROR và event `exception`, ghi lỗi upstream giả lập. Agent trả HTTP 503 cho loại lỗi này.

- Mở Jaeger: http://localhost:16686/trace/f90c08398270acd34187636f0156dc36
- Dữ liệu: `trace_error.json`, `trace_error_log.json` trong cùng thư mục kết quả.
- Log khớp trace_id:

```json
{"ts":"2026-11-25T13:11:56.979042+00:00","level":"INFO","service":"observable-agent","instance":"b4a70b35d692","event":"llm_error","trace_id":"f90c08398270acd34187636f0156dc36","span_id":"ce428934cc1395af","request_id":"f60adad7ae43","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

Trace được lấy từ API v3 của Jaeger 2.23 và đối chiếu trực tiếp với output `docker compose -p k5-day14-observability logs agent`, không tạo trace giả. Tham khảo giao thức: [Jaeger APIs](https://www.jaegertracing.io/docs/2.23/architecture/apis/).

### 4.4 Trạng thái lúc chụp và dọn stack

Lúc chụp, stack có **2 agent**, tải Locust web **30 users / ramp 5**, `MOCK_ERROR_RATE=0.2`, `MOCK_SLOW_RATE=0.3`. Hai lượt CSV scaling đã kết thúc trước khi tiêm lỗi, không dùng trạng thái này làm số liệu scale 1/3.

Grafana dùng http://localhost:3000/d/day14-agent-overview, Prometheus dùng http://localhost:9090/alerts. Các URL localhost/trace chỉ mở được khi stack còn chạy; sau dọn, dùng ảnh cùng JSON đã lưu làm bằng chứng. Dữ liệu Jaeger/Prometheus tạm trong container không còn được giữ.

Sau khi xác minh đủ bốn ảnh, đã trả `.env` local về `MOCK_ERROR_RATE=0.01`, `MOCK_SLOW_RATE=0.03`. Đã dừng/xóa container tải cùng các service của riêng project CP8 bằng lệnh sau; CSV, JSON và ảnh trong repo vẫn được giữ:

```cmd
docker compose -p k5-day14-observability -f 06-lab-complete/benchmark-observability/production/docker-compose.yml down -v
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Đã chạy Locust **headless**, 100 users, ramp 10 users/giây, thời lượng cấu hình 2 phút cho mỗi mức scale. Cả hai lượt dùng v2, `mock-llm-small`, `MOCK_ERROR_RATE=0.01`, `MOCK_SLOW_RATE=0.03`, giới hạn mỗi agent 0,5 CPU / 256 MB. Chỉ có một process Uvicorn trong mỗi container.

Nguồn: `production/benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv` (đường dẫn từ thư mục benchmark-observability). Bảng dùng đúng hàng **Aggregated**, gồm `/ask` và `/health`; không lấy tổng cuối console thay cho CSV vì thời điểm ghi snapshot có thể khác nhau.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 55.97 | 260 | 1700 | 2400 | 67/6641 (1.01%) |
| 3 | 64.04 | 210 | 570 | 1700 | 67/7640 (0.88%) |

**Giải thích kết quả:** RPS tăng **14,43%**, p95 giảm từ 1700 xuống 570 ms, p99 từ 2400 xuống 1700 ms. Riêng `/ask`, CSV cho p95 1700 → 600 ms, RPS 50.96 → 58.12. Không trộn percentile của hàng `/ask` với hàng Aggregated.

Tăng số container giúp giảm áp lực lên mỗi instance trong phép đo này. RPS không tăng 3 lần: đây là tải closed-loop với 100 user cố định, mỗi user nghỉ 0,5–2 giây giữa các lần gọi, nên throughput còn phụ thuộc thời gian nghỉ và latency. Slow injection vẫn thêm 1500 ms cho một phần request, vì vậy tail còn tồn tại khi scale. Chưa profile CPU để kết luận một nút thắt duy nhất.

**Kiểm soát replica:** đã xác nhận Prometheus có đúng 1 rồi 3 target healthy trước hai lượt đo chính thức. Dùng `run --rm --no-deps locust` vì `compose run` có thể áp dụng lại `deploy.replicas: 2` cho dependency agent và làm sai lượt scale 1. Output preflight sai replica đã bỏ, không dùng làm số liệu. Giữ `scale_1_snapshot.json`, `scale_3_snapshot.json` để đối chiếu target thực tế.

Lệnh từ gốc repo (chờ DNS/target cập nhật sau khi đổi scale):

```cmd
docker compose -p k5-day14-observability -f 06-lab-complete/benchmark-observability/production/docker-compose.yml up -d --build --scale agent=1
docker compose -p k5-day14-observability -f 06-lab-complete/benchmark-observability/production/docker-compose.yml run --rm --no-deps locust -f /mnt/locust/locustfile.py --host http://nginx --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
docker compose -p k5-day14-observability -f 06-lab-complete/benchmark-observability/production/docker-compose.yml up -d --scale agent=3
docker compose -p k5-day14-observability -f 06-lab-complete/benchmark-observability/production/docker-compose.yml run --rm --no-deps locust -f /mnt/locust/locustfile.py --host http://nginx --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

Locust trả exit code 1 do có response `503` giả lập; CSV vẫn được tạo. Không coi exit code này là mất toàn bộ kết quả đo.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Average không thay thế percentile: số ít request chậm có thể bị che giấu; load test phải lưu cả latency và error rate.
  2. Chất lượng và hiệu năng là hai trục riêng: v2 trả lời đúng nhiều hơn nhưng tốn token/context; cần eval gate ngoài dashboard hạ tầng.
  3. Scale và observability phải được kiểm chứng: xác nhận số target thực tế, giữ CSV và dùng trace_id để đối chiếu log với request cụ thể.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

Tôi sẽ thêm metric/alert ở Nginx hoặc synthetic probe bên ngoài để thấy lỗi 502/504 mà agent không ghi nhận; theo dõi chất lượng bằng eval định kỳ và mẫu traffic thật, đồng thời tách chi phí theo phiên bản/model. Với traffic lớn cần sampling trace và kiểm soát cardinality, không đưa user_id hoặc câu hỏi vào metric label.

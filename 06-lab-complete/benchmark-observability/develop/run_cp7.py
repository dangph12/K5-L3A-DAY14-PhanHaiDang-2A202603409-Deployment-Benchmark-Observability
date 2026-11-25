"""Run the CP7 lab commands without changing the benchmark or evaluation scripts."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORTS = BASE / "reports"
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def start_agent(version, port, slow_rate=0.03, error_rate=0.01):
    env = {**ENV, "AGENT_VERSION": version, "PORT": str(port),
           "LLM_MODEL": "mock-llm-small", "MOCK_LATENCY_MS": "120",
           "MOCK_JITTER_MS": "60", "MOCK_SLOW_RATE": str(slow_rate),
           "MOCK_SLOW_MS": "1500", "MOCK_ERROR_RATE": str(error_rate),
           "MOCK_RETRIEVAL_MS": "20"}
    log = (REPORTS / f"agent_{version}.log").open("a", encoding="utf-8")
    process = subprocess.Popen([sys.executable, "app.py"], cwd=BASE, env=env,
                               stdout=log, stderr=subprocess.STDOUT)
    process.cp7_log = log
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError(f"Agent {version} exited; inspect {log.name}")
            try:
                with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=1) as response:
                    if json.load(response)["agent_version"] == version:
                        return process
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError(f"Agent {version} did not start on port {port}")
    except Exception:
        stop_agent(process)
        raise


def stop_agent(process):
    if process is not None:
        process.terminate()
        process.wait(timeout=10)
        process.cp7_log.close()


def run(script, output, *args):
    path = REPORTS / f"{output}.json"
    previous_mtime = path.stat().st_mtime_ns if path.exists() else None
    command = [sys.executable, script, *map(str, args), "--out", f"reports/{output}.json"]
    print("RUN " + " ".join(command[1:]), flush=True)
    result = subprocess.run(command, cwd=BASE, env=ENV, capture_output=True, text=True, encoding="utf-8")
    (REPORTS / f"{output}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode not in (0, 1) or not path.exists():
        raise RuntimeError(f"Command failed; inspect reports/{output}.log")
    if path.stat().st_mtime_ns == previous_mtime:
        raise RuntimeError(f"Command did not update reports/{output}.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    if script == "load_test.py" and report["total_requests"] != 300:
        raise RuntimeError("Load run did not collect all 300 requests")
    print(f"SAVED {path.name}; exit={result.returncode}", flush=True)
    return result.returncode, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("measure", "fixed"))
    phase = parser.parse_args().phase
    REPORTS.mkdir(exist_ok=True)
    report_path = BASE.parents[2] / "BENCHMARK_REPORT.md"
    if not report_path.exists():
        shutil.copyfile(BASE.parent / "BENCHMARK_REPORT_TEMPLATE.md", report_path)
    dataset_hash = hashlib.sha256((BASE / "eval/golden_dataset.jsonl").read_bytes()).hexdigest()
    if phase == "measure":
        if (REPORTS / "eval_v2.json").exists():
            raise SystemExit("Baseline reports already exist. Archive them and restore the original KB before remeasuring.")
        metadata = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(), "python": sys.version,
            "processor": os.getenv("PROCESSOR_IDENTIFIER", platform.processor()),
            "logical_cpus": os.cpu_count(), "dataset_sha256": dataset_hash,
            "kb_before_sha256": hashlib.sha256((BASE / "utils/mock_llm.py").read_bytes()).hexdigest(),
            "load_environment": {"MOCK_ERROR_RATE": 0.01, "MOCK_LATENCY_MS": 120,
                "MOCK_JITTER_MS": 60, "MOCK_RETRIEVAL_MS": 20, "MOCK_SLOW_MS": 1500},
            "eval_environment": {"MOCK_ERROR_RATE": 0, "MOCK_SLOW_RATE": 0},
        }
        (REPORTS / "cp7_run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        agent = None
        try:
            agent = start_agent("v2", 8002)
            for concurrency in (1, 10, 50, 100):
                run("load_test.py", f"load_v2_c{concurrency}", "--url", "http://localhost:8002",
                    "--requests", 300, "--concurrency", concurrency)
            stop_agent(agent)
            agent = None
            for slow_rate in (0, 0.03, 0.1):
                agent = start_agent("v2", 8002, slow_rate)
                run("load_test.py", f"load_v2_slow_{slow_rate}", "--url", "http://localhost:8002",
                    "--requests", 300, "--concurrency", 20)
                stop_agent(agent)
                agent = None
            agent = start_agent("v1", 8001, 0, 0)
            run("eval/run_eval.py", "eval_v1", "--url", "http://localhost:8001")
            stop_agent(agent)
            agent = None
            agent = start_agent("v2", 8002, 0, 0)
            run("eval/run_eval.py", "eval_v2", "--url", "http://localhost:8002",
                "--baseline", "reports/eval_v1.json")
            stop_agent(agent)
            agent = None
            agent = start_agent("v1", 8001, 0, 0)
            code, _ = run("eval/run_eval.py", "eval_v1_regression", "--url", "http://localhost:8001",
                          "--baseline", "reports/eval_v2.json")
            if code != 1:
                raise RuntimeError("Expected the v1 regression check to reject the downgrade")
        finally:
            stop_agent(agent)
    else:
        agent = None
        try:
            agent = start_agent("v2", 8002, 0, 0)
            code, report = run("eval/run_eval.py", "eval_v2_fixed", "--url", "http://localhost:8002",
                               "--min-accuracy", 1.0, "--baseline", "reports/eval_v2.json")
            if code != 0 or report["accuracy"] != 1.0:
                raise RuntimeError("Final quality gate did not pass at 100% accuracy")
            with urllib.request.urlopen("http://localhost:8002/metrics") as response:
                metrics = response.read().decode("utf-8")
            if "agent_question_length_chars_count 23.0" not in metrics:
                raise RuntimeError("Question-length histogram did not observe all 23 eval requests")
            (REPORTS / "metrics_v2_fixed.txt").write_text(metrics, encoding="utf-8")
            metadata_path = REPORTS / "cp7_run.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata.update({"finished_at": datetime.now(timezone.utc).isoformat(),
                "kb_after_sha256": hashlib.sha256((BASE / "utils/mock_llm.py").read_bytes()).hexdigest()})
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        finally:
            stop_agent(agent)
    if hashlib.sha256((BASE / "eval/golden_dataset.jsonl").read_bytes()).hexdigest() != dataset_hash:
        raise RuntimeError("Golden dataset changed")


if __name__ == "__main__":
    main()

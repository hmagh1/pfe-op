import json
import sys
import time
import urllib.request
import urllib.error


API_BASE = "http://127.0.0.1:8000/api"
TEST_BASICAT = "GRC"


def request_json(method: str, path: str, payload=None, timeout: int = 60):
    url = f"{API_BASE}{path}"

    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP {e.code} on {method} {path}: {body}")

    except Exception as e:
        raise RuntimeError(f"Request failed on {method} {path}: {e}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    print("=== CI MAF WORKFLOW TEST START ===")

    print("1. Health check...")
    health = request_json("GET", "/health")
    assert_true(health.get("status") == "ok", "Health check failed")
    print("OK health:", health)

    print(f"2. Create job for BASICAT={TEST_BASICAT}...")
    job = request_json("POST", "/jobs", {"basicat": TEST_BASICAT})
    job_id = job.get("job_id")

    assert_true(job_id, "job_id missing after create job")
    assert_true(job.get("basicat") == TEST_BASICAT, "basicat mismatch after create job")

    print("OK job created:", job_id)

    print("3. Run FR...")
    fr_result = request_json("POST", f"/jobs/{job_id}/run-fr", timeout=120)

    assert_true(fr_result.get("job_id") == job_id, "job_id mismatch after run-fr")
    assert_true(fr_result.get("basicat") == TEST_BASICAT, "basicat mismatch after run-fr")

    status = fr_result.get("status")
    phase = fr_result.get("phase")
    generated_envs = fr_result.get("generated_envs") or []

    assert_true(status, "status missing after run-fr")
    assert_true(phase, "phase missing after run-fr")
    assert_true(isinstance(generated_envs, list), "generated_envs is not a list")

    print("OK FR result:")
    print("status:", status)
    print("phase:", phase)
    print("generated_envs:", generated_envs)

    print("4. Fetch job after FR...")
    job_after_fr = request_json("GET", f"/jobs/{job_id}")

    assert_true(job_after_fr.get("job_id") == job_id, "job_id mismatch on get job")
    assert_true(job_after_fr.get("basicat") == TEST_BASICAT, "basicat mismatch on get job")

    print("OK job fetched")

    print("5. Check jobs list...")
    jobs_payload = request_json("GET", "/jobs")
    jobs = jobs_payload.get("jobs") or []

    assert_true(isinstance(jobs, list), "jobs is not a list")
    assert_true(
        any(j.get("job_id") == job_id for j in jobs),
        "created job not found in jobs list",
    )

    print("OK jobs list contains created job")

    print("6. Train ML model...")
    train_result = request_json("POST", "/ml/train", timeout=180)

    assert_true(train_result.get("status") == "trained", "ML training status is not trained")
    assert_true(train_result.get("training_rows", 0) > 0, "ML training_rows is empty")

    print("OK ML trained")
    print("training_rows:", train_result.get("training_rows"))
    print("model_id:", train_result.get("model_id"))

    print("7. Check model versions...")
    versions_payload = request_json("GET", "/ml/model-versions")
    models = versions_payload.get("models") or []

    assert_true(isinstance(models, list), "models is not a list")
    assert_true(len(models) > 0, "No model versions found after training")

    print("OK model versions:", len(models))

    print("8. Check decision stats...")
    stats = request_json("GET", "/ml/decision-stats")

    assert_true(isinstance(stats, dict), "decision stats is not a dict")
    assert_true("total_decisions" in stats, "total_decisions missing in stats")

    print("OK decision stats:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("=== CI MAF WORKFLOW TEST SUCCESS ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("=== CI MAF WORKFLOW TEST FAILED ===")
        print(str(e))
        sys.exit(1)
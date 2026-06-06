import json
import sys
import urllib.parse
import urllib.request
import urllib.error


API_BASE = "http://127.0.0.1:8000/api"


def request_json(method: str, path: str, payload=None, timeout: int = 360):
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


def ask(question: str):
    encoded = urllib.parse.quote(question)
    return request_json("GET", f"/rag/ask?question={encoded}", timeout=420)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_contains(value, expected, message):
    value = str(value or "")
    expected = str(expected or "")

    if expected not in value:
        raise AssertionError(f"{message}. Expected '{expected}' in '{value}'")


def test_active_model_direct():
    print("=" * 80)
    print("TEST 1 - RAG direct MySQL: active model")

    data = ask("Quel est le modele actif ?")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    assert_true(data.get("model") == "rag-direct", "Active model should use rag-direct")
    assert_true(data.get("source") == "mysql_active_model", "Active model should use MySQL source")
    assert_true(
        data.get("router_reason") == "direct_mysql_factuel",
        "Active model should use direct_mysql_factuel router",
    )
    assert_true(bool(data.get("answer")), "Active model answer should not be empty")


def test_bdd_excel_direct():
    print("=" * 80)
    print("TEST 2 - RAG direct Excel: BDD flux")

    data = ask("Combien de lignes contient la BDD flux ?")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    assert_true(data.get("model") == "rag-direct", "BDD question should use rag-direct")
    assert_true(data.get("source") == "excel_bdd_flux", "BDD question should use Excel BDD source")
    assert_true(
        data.get("router_reason") == "direct_excel_bdd",
        "BDD question should use direct_excel_bdd router",
    )
    assert_contains(data.get("answer"), "BDD", "BDD answer should mention BDD")


def test_vmliste_excel_direct():
    print("=" * 80)
    print("TEST 3 - RAG direct Excel: VLISTE BASICAT")

    data = ask("Est-ce que GRC existe dans la VLISTE ?")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    assert_true(data.get("model") == "rag-direct", "VLISTE question should use rag-direct")
    assert_true(data.get("source") == "excel_vmliste", "VLISTE question should use Excel VLISTE source")
    assert_true(
        data.get("router_reason") == "direct_excel_vmliste",
        "VLISTE question should use direct_excel_vmliste router",
    )
    assert_contains(data.get("answer"), "GRC", "VLISTE answer should mention GRC")


def test_fast_llama_router():
    print("=" * 80)
    print("TEST 4 - RAG router: fast model llama3.2:3b")

    data = ask("Que fait ce projet ?")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    assert_true(data.get("source") == "ollama_rag", "Simple question should use Ollama RAG")
    assert_true(data.get("model") == "llama3.2:3b", "Simple question should use llama3.2:3b")
    assert_true(
        data.get("router_reason") == "question_simple_rapide",
        "Simple question should use question_simple_rapide router",
    )
    assert_true(bool(data.get("answer")), "Simple LLM answer should not be empty")


def test_quality_llama_router():
    print("=" * 80)
    print("TEST 5 - RAG router: quality model llama3.1:8b")

    data = ask("Explique le role du MLOps et du RAG dans ce projet.")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    assert_true(data.get("source") == "ollama_rag", "Complex question should use Ollama RAG")
    assert_true(data.get("model") == "llama3.1:8b", "Complex question should use llama3.1:8b")
    assert_true(
        data.get("router_reason") == "question_complexe_qualite",
        "Complex question should use question_complexe_qualite router",
    )
    assert_true(bool(data.get("answer")), "Complex LLM answer should not be empty")


def main():
    print("=== CI LLM/RAG WORKFLOW TEST START ===")

    print("0. Health check...")
    health = request_json("GET", "/health")
    assert_true(health.get("status") == "ok", "Health check failed")
    print("OK health:", health)

    test_active_model_direct()
    test_bdd_excel_direct()
    test_vmliste_excel_direct()
    test_fast_llama_router()
    test_quality_llama_router()

    print("=" * 80)
    print("=== CI LLM/RAG WORKFLOW TEST SUCCESS ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("=== CI LLM/RAG WORKFLOW TEST FAILED ===")
        print(str(e))
        sys.exit(1)
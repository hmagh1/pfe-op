import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from app.services.job_store import (
    list_jobs,
    list_all_decisions,
    list_model_versions,
    get_decision_stats,
    get_active_model_version,
)


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "llama3.2:3b")
OLLAMA_QUALITY_MODEL = os.getenv("OLLAMA_QUALITY_MODEL", "llama3.1:8b")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
VLISTE_FILE = DATA_DIR / "vmliste_remplie.xlsx"
BDD_FILE = DATA_DIR / "bdd_flux_maf.xlsx"


# =========================
# Helpers
# =========================
def _safe_text(value) -> str:
    return str(value or "").strip()


def _pct(value) -> str:
    if value is None or value == "":
        return "-"

    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return str(value)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _find_column(df: pd.DataFrame, expected_name: str):
    expected = expected_name.strip().lower()

    for col in df.columns:
        if str(col).strip().lower() == expected:
            return col

    return None


def _load_excel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")

    df = pd.read_excel(path, dtype=str).fillna("")
    return _normalize_columns(df)


# =========================
# Question classification
# =========================
def _is_active_model_question(question: str) -> bool:
    q = question.lower()
    return (
        "modèle actif" in q
        or "modele actif" in q
        or "active model" in q
        or "model actif" in q
    )


def _is_model_versions_question(question: str) -> bool:
    q = question.lower()
    return (
        "versions" in q
        or "model versions" in q
        or "modèles" in q
        or "modeles" in q
        or "registre" in q
        or "registry" in q
    )


def _is_stats_question(question: str) -> bool:
    q = question.lower()
    return (
        "stat" in q
        or "kpi" in q
        or "acceptation" in q
        or "correction" in q
        or "confiance" in q
        or "décision" in q
        or "decision" in q
    )


def _is_vmliste_question(question: str) -> bool:
    q = question.lower()

    return (
        "vmliste" in q
        or "v liste" in q
        or "vm liste" in q
        or "basicat" in q
        or "existe dans la vliste" in q
        or "existe dans vmliste" in q
        or "existe dans la liste" in q
        or "ligne vliste" in q
        or "lignes vliste" in q
        or "environnement" in q
        or "environnements" in q
        or "horsprod" in q
        or "hors prod" in q
    )


def _is_bdd_question(question: str) -> bool:
    q = question.lower()
    return (
        "bdd" in q
        or "bdd flux" in q
        or "bdd_flux_maf" in q
        or "flux maf" in q
        or "colonnes bdd" in q
        or "lignes bdd" in q
    )


def _is_excel_question(question: str) -> bool:
    return _is_vmliste_question(question) or _is_bdd_question(question)


def _is_complex_question(question: str) -> bool:
    q = question.lower()

    complex_words = [
        "explique",
        "analyse",
        "compare",
        "pourquoi",
        "comment",
        "architecture",
        "détaille",
        "detaille",
        "résume",
        "resume",
        "workflow",
        "mlops",
        "rag",
        "jenkins",
        "avantages",
        "limites",
        "amélioration",
        "amelioration",
        "human-in-the-loop",
        "human in the loop",
    ]

    if len(question) > 120:
        return True

    return any(word in q for word in complex_words)


def choose_model(question: str) -> Dict[str, Any]:
    if _is_complex_question(question):
        return {
            "model": OLLAMA_QUALITY_MODEL,
            "reason": "question_complexe_qualite",
            "num_predict": 260,
            "timeout": 300,
        }

    return {
        "model": OLLAMA_FAST_MODEL,
        "reason": "question_simple_rapide",
        "num_predict": 140,
        "timeout": 180,
    }


# =========================
# Compact context
# =========================
def _compact_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "basicat": job.get("basicat"),
        "status": job.get("status"),
        "phase": job.get("phase"),
        "updated_at": job.get("updated_at"),
    }


def _compact_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "basicat": decision.get("basicat"),
        "env": decision.get("env"),
        "from_phase": decision.get("from_phase"),
        "action": decision.get("action"),
        "src_ip": decision.get("src_ip"),
        "dst_ip": decision.get("dst_ip"),
        "port": decision.get("port"),
        "flowMainSG": decision.get("flowMainSG"),
        "flowGrefSG": decision.get("flowGrefSG"),
        "final_flux": decision.get("final_flux"),
        "final_nom": decision.get("final_nom"),
        "ml_modele": decision.get("ml_modele"),
        "ml_confiance": decision.get("ml_confiance"),
        "updated_at": decision.get("updated_at"),
    }


def _compact_model(model: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not model:
        return None

    return {
        "model_id": model.get("model_id"),
        "model_name": model.get("model_name"),
        "training_rows": model.get("training_rows"),
        "excel_rows": model.get("excel_rows"),
        "mysql_rows": model.get("mysql_rows"),
        "n_classes": model.get("n_classes"),
        "accuracy": model.get("accuracy"),
        "precision": model.get("precision"),
        "recall": model.get("recall"),
        "f1_score": model.get("f1_score"),
        "is_active": model.get("is_active"),
        "created_at": model.get("created_at"),
    }


# =========================
# Direct MySQL answers
# =========================
def answer_active_model_direct(question: str) -> Dict[str, Any]:
    active_model = get_active_model_version()

    if not active_model:
        answer = (
            "Aucun modèle actif n'est actuellement sélectionné. "
            "Il faut promouvoir une version de modèle depuis le dashboard MLOps."
        )
    else:
        answer = (
            "Le modèle actif actuellement est "
            f"{active_model.get('model_id')}. "
            f"Il s'agit d'un modèle {active_model.get('model_name') or 'ML'} "
            f"avec {active_model.get('training_rows') or '-'} lignes d'entraînement. "
            f"Accuracy: {_pct(active_model.get('accuracy'))}, "
            f"F1-score: {_pct(active_model.get('f1_score'))}. "
            f"Créé le: {active_model.get('created_at') or '-'}."
        )

    return {
        "question": question,
        "answer": answer,
        "model": "rag-direct",
        "context_used": True,
        "source": "mysql_active_model",
        "router_reason": "direct_mysql_factuel",
    }


def answer_model_versions_direct(question: str) -> Dict[str, Any]:
    models = list_model_versions(limit=10)

    if not models:
        answer = "Aucune version de modèle n'est sauvegardée pour le moment."
    else:
        active = [m for m in models if str(m.get("is_active")) == "true"]
        answer_lines = [
            f"{len(models)} version(s) de modèle sont disponibles dans le registre ML."
        ]

        if active:
            answer_lines.append(
                f"Le modèle actif est {active[0].get('model_id')} "
                f"avec un F1-score de {_pct(active[0].get('f1_score'))}."
            )
        else:
            answer_lines.append("Aucun modèle n'est actuellement marqué comme actif.")

        latest = models[0]
        answer_lines.append(
            f"La dernière version créée est {latest.get('model_id')} "
            f"avec {latest.get('training_rows') or '-'} lignes d'entraînement."
        )

        answer = " ".join(answer_lines)

    return {
        "question": question,
        "answer": answer,
        "model": "rag-direct",
        "context_used": True,
        "source": "mysql_model_versions",
        "router_reason": "direct_mysql_factuel",
    }


def answer_stats_direct(question: str) -> Dict[str, Any]:
    stats = get_decision_stats()

    answer = (
        f"Le système contient {stats.get('total_decisions', 0)} décision(s), "
        f"dont {stats.get('validated_decisions', 0)} validée(s) et "
        f"{stats.get('corrected_decisions', 0)} corrigée(s). "
        f"Le taux d'acceptation ML est de {stats.get('ml_acceptance_rate', 0)}%, "
        f"le taux de correction ML est de {stats.get('ml_correction_rate', 0)}%, "
        f"et la confiance moyenne ML est de {stats.get('average_ml_confidence', 0)}."
    )

    return {
        "question": question,
        "answer": answer,
        "model": "rag-direct",
        "context_used": True,
        "source": "mysql_decision_stats",
        "router_reason": "direct_mysql_factuel",
    }


# =========================
# Direct Excel answers
# =========================
def _extract_basicat_from_question(question: str, df_vmliste: pd.DataFrame) -> str | None:
    basicat_col = _find_column(df_vmliste, "BASICAT")

    if not basicat_col:
        return None

    q_words = (
        question.upper()
        .replace("?", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace(":", " ")
        .replace(";", " ")
        .split()
    )

    q_words = [w.strip() for w in q_words if w.strip()]

    basicats = (
        df_vmliste[basicat_col]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

    basicats_upper = {str(b).strip().upper(): str(b).strip().upper() for b in basicats}

    for word in q_words:
        if word in basicats_upper:
            return basicats_upper[word]

    return None


def _detect_envs_for_basicat(df_vmliste: pd.DataFrame, basicat: str) -> List[str]:
    basicat_col = _find_column(df_vmliste, "BASICAT")

    if not basicat_col:
        return []

    rows = df_vmliste[
        df_vmliste[basicat_col].astype(str).str.strip().str.upper()
        == str(basicat).strip().upper()
    ]

    if rows.empty:
        return []

    envs = set()

    row_text = " ".join(
        rows.astype(str)
        .fillna("")
        .apply(lambda r: " ".join(r.values), axis=1)
        .tolist()
    ).upper()

    if "PROD" in row_text or "PRODUCTION" in row_text:
        envs.add("prod")

    if (
        "HORS" in row_text
        or "UTILISATION" in row_text
        or "RECETTE" in row_text
        or "QUALIF" in row_text
        or "DEV" in row_text
        or "TEST" in row_text
        or "UAT" in row_text
        or "PREPROD" in row_text
        or "PRE-PROD" in row_text
        or "PRE PROD" in row_text
    ):
        envs.add("horsprod")

    if not envs:
        envs.add("prod")

    ordered = []

    if "prod" in envs:
        ordered.append("prod")

    if "horsprod" in envs:
        ordered.append("horsprod")

    return ordered


def answer_vmliste_direct(question: str) -> Dict[str, Any] | None:
    if not VLISTE_FILE.exists():
        return {
            "question": question,
            "answer": "Le fichier vmliste_remplie.xlsx est introuvable dans backend/data.",
            "model": "rag-direct",
            "context_used": True,
            "source": "excel_vmliste",
            "router_reason": "direct_excel_vmliste",
        }

    df = _load_excel(VLISTE_FILE)
    basicat_col = _find_column(df, "BASICAT")

    if not basicat_col:
        return {
            "question": question,
            "answer": "La colonne BASICAT est introuvable dans vmliste_remplie.xlsx.",
            "model": "rag-direct",
            "context_used": True,
            "source": "excel_vmliste",
            "router_reason": "direct_excel_vmliste",
        }

    q = question.lower()
    basicat = _extract_basicat_from_question(question, df)

    total_rows = len(df)
    total_basicats = df[basicat_col].astype(str).str.strip().replace("", pd.NA).dropna().nunique()

    if basicat:
        rows = df[df[basicat_col].astype(str).str.strip().str.upper() == basicat]
        envs = _detect_envs_for_basicat(df, basicat)

        if "existe" in q or "exist" in q:
            answer = (
                f"Oui, le BASICAT {basicat} existe dans la VLISTE. "
                f"{len(rows)} ligne(s) ont été trouvée(s). "
                f"Environnement(s) détecté(s): {', '.join(envs).upper()}."
            )
        elif "combien" in q or "nombre" in q or "lignes" in q:
            answer = (
                f"Le BASICAT {basicat} contient {len(rows)} ligne(s) dans la VLISTE. "
                f"Environnement(s) détecté(s): {', '.join(envs).upper()}."
            )
        elif "environnement" in q or "env" in q or "prod" in q or "horsprod" in q:
            answer = (
                f"Pour le BASICAT {basicat}, les environnement(s) détecté(s) sont: "
                f"{', '.join(envs).upper()}."
            )
        else:
            answer = (
                f"Le BASICAT {basicat} est présent dans la VLISTE avec {len(rows)} ligne(s). "
                f"Environnement(s) détecté(s): {', '.join(envs).upper()}."
            )
    else:
        if "colonnes" in q or "columns" in q:
            answer = (
                "Les colonnes présentes dans vmliste_remplie.xlsx sont: "
                + ", ".join([str(c) for c in df.columns])
                + "."
            )
        else:
            answer = (
                f"Le fichier vmliste_remplie.xlsx contient {total_rows} ligne(s) "
                f"et {total_basicats} BASICAT distinct(s). "
                "Pour une réponse plus précise, indique le BASICAT concerné."
            )

    return {
        "question": question,
        "answer": answer,
        "model": "rag-direct",
        "context_used": True,
        "source": "excel_vmliste",
        "router_reason": "direct_excel_vmliste",
    }


def answer_bdd_direct(question: str) -> Dict[str, Any] | None:
    if not BDD_FILE.exists():
        return {
            "question": question,
            "answer": "Le fichier bdd_flux_maf.xlsx est introuvable dans backend/data.",
            "model": "rag-direct",
            "context_used": True,
            "source": "excel_bdd_flux",
            "router_reason": "direct_excel_bdd",
        }

    df = _load_excel(BDD_FILE)
    q = question.lower()

    total_rows = len(df)
    columns = [str(c) for c in df.columns]

    if "colonnes" in q or "columns" in q:
        answer = (
            "Les colonnes présentes dans bdd_flux_maf.xlsx sont: "
            + ", ".join(columns)
            + "."
        )
    elif "combien" in q or "nombre" in q or "lignes" in q:
        answer = f"La BDD flux contient {total_rows} ligne(s)."
    elif "flux" in q:
        flux_col = _find_column(df, "flux")

        if flux_col:
            flux_counts = (
                df[flux_col]
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .value_counts()
                .head(5)
                .to_dict()
            )

            if flux_counts:
                formatted = ", ".join([f"{k}: {v}" for k, v in flux_counts.items()])
                answer = (
                    f"La BDD flux contient {total_rows} ligne(s). "
                    f"Top flux détectés: {formatted}."
                )
            else:
                answer = "La colonne flux existe, mais aucun flux exploitable n'a été trouvé."
        else:
            answer = "La colonne flux est introuvable dans bdd_flux_maf.xlsx."
    else:
        answer = (
            f"La BDD flux bdd_flux_maf.xlsx contient {total_rows} ligne(s) "
            f"et {len(columns)} colonne(s)."
        )

    return {
        "question": question,
        "answer": answer,
        "model": "rag-direct",
        "context_used": True,
        "source": "excel_bdd_flux",
        "router_reason": "direct_excel_bdd",
    }


def answer_excel_direct(question: str) -> Dict[str, Any] | None:
    if _is_bdd_question(question):
        return answer_bdd_direct(question)

    if _is_vmliste_question(question):
        return answer_vmliste_direct(question)

    return None


# =========================
# RAG context for Llama
# =========================
def build_rag_context(question: str) -> str:
    jobs = list_jobs(limit=5)
    decisions = list_all_decisions(limit=30)
    models = list_model_versions(limit=5)
    stats = get_decision_stats()
    active_model = get_active_model_version()

    excel_summary = {}

    try:
        if VLISTE_FILE.exists():
            df_vmliste = _load_excel(VLISTE_FILE)
            basicat_col = _find_column(df_vmliste, "BASICAT")
            excel_summary["vmliste"] = {
                "file": "vmliste_remplie.xlsx",
                "rows": len(df_vmliste),
                "columns": list(df_vmliste.columns),
                "basicat_count": (
                    df_vmliste[basicat_col].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
                    if basicat_col
                    else None
                ),
            }

        if BDD_FILE.exists():
            df_bdd = _load_excel(BDD_FILE)
            excel_summary["bdd_flux"] = {
                "file": "bdd_flux_maf.xlsx",
                "rows": len(df_bdd),
                "columns": list(df_bdd.columns),
            }
    except Exception as e:
        excel_summary["error"] = str(e)

    keywords = []

    for item in question.replace("?", " ").replace(",", " ").replace(":", " ").split():
        item = item.strip().upper()
        if len(item) >= 3:
            keywords.append(item)

    relevant_decisions = []

    if keywords:
        for d in decisions:
            row_text = json.dumps(d, ensure_ascii=False).upper()
            if any(k in row_text for k in keywords):
                relevant_decisions.append(d)

    if not relevant_decisions:
        relevant_decisions = decisions[:8]
    else:
        relevant_decisions = relevant_decisions[:8]

    context = {
        "project": "MAF Automation Studio",
        "description": (
            "Application FastAPI/React pour automatiser la génération FR, "
            "le traitement SNIF, la génération MAF, le ML, le MLOps, Jenkins CI/CD "
            "et le chatbot RAG."
        ),
        "definitions": {
            "RAG": "Retrieval-Augmented Generation. Dans ce projet, le RAG récupère des informations depuis MySQL, les fichiers Excel et le contexte projet avant de générer une réponse avec Llama.",
            "MLOps": "Ensemble des pratiques permettant de gérer l'entraînement, le versioning, la promotion, le monitoring et la validation des modèles ML.",
            "Human-in-the-loop": "Approche où le modèle propose une décision, mais l'humain valide ou corrige la décision finale.",
        },
        "excel_summary": excel_summary,
        "active_model": _compact_model(active_model),
        "model_versions": [_compact_model(m) for m in models[:3]],
        "decision_stats": stats,
        "recent_jobs": [_compact_job(j) for j in jobs[:3]],
        "relevant_decisions": [_compact_decision(d) for d in relevant_decisions],
    }

    return json.dumps(context, ensure_ascii=False, default=str)


# =========================
# Ollama call
# =========================
def ask_ollama(prompt: str, model: str, num_predict: int, timeout: int) -> str:
    url = f"{OLLAMA_HOST}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.8,
            "num_predict": num_predict,
        },
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            return parsed.get("response", "").strip()

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Ollama HTTP error {e.code}: {body}")

    except Exception as e:
        raise RuntimeError(f"Ollama request failed: {e}")


# =========================
# Main RAG function
# =========================
def ask_rag(question: str) -> Dict[str, Any]:
    question = _safe_text(question)

    if not question:
        raise ValueError("Question vide.")

    # 1. Direct MySQL answers
    if _is_active_model_question(question):
        return answer_active_model_direct(question)

    if _is_model_versions_question(question):
        return answer_model_versions_direct(question)

    if _is_stats_question(question):
        return answer_stats_direct(question)

    # 2. Direct Excel answers
    if _is_excel_question(question):
        excel_answer = answer_excel_direct(question)

        if excel_answer:
            return excel_answer

    # 3. Smart model routing
    route = choose_model(question)
    selected_model = route["model"]

    context = build_rag_context(question)

    prompt = f"""
Tu es le chatbot interne du projet MAF Automation Studio.

Dans ce projet:
- RAG signifie Retrieval-Augmented Generation.
- Le RAG récupère des informations depuis MySQL, les fichiers Excel et le contexte projet avant de générer une réponse avec Llama.
- MLOps signifie Machine Learning Operations.
- Le MLOps couvre l'entraînement, le versioning, la promotion, le monitoring et la validation des modèles ML.
- Le système utilise aussi une approche Human-in-the-loop: le modèle propose, mais l'utilisateur valide ou corrige.

Réponds uniquement à partir du contexte fourni.
Réponds en français.
Sois clair, utile et professionnel.
Ne donne pas d'informations inventées.
Si l'information n'est pas dans le contexte, dis:
"Je n'ai pas trouvé cette information dans les données disponibles."

CONTEXTE JSON:
{context}

QUESTION:
{question}

RÉPONSE:
"""

    answer = ask_ollama(
        prompt=prompt,
        model=selected_model,
        num_predict=route["num_predict"],
        timeout=route["timeout"],
    )

    return {
        "question": question,
        "answer": answer,
        "model": selected_model,
        "context_used": True,
        "source": "ollama_rag",
        "router_reason": route["reason"],
    }
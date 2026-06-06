from pathlib import Path
from typing import Dict, Any
import uuid
import pandas as pd
from app.services.job_store import (
    save_job,
    load_job,
    delete_all_jobs,
    list_jobs,
    save_decision,
)
from app.core.config import OUTPUT_DIR, UPLOAD_DIR, VMLISTE_FILE
from app.services import maf_core
from app.services.maf_core import (
    run_maf,
    load_bdd,
    save_bdd,
    add_bdd_learning_row,
    BDD_FILE,
    generate_final_maf_matrix,
    process_snif_file,
)
from app.services.file_detector import (
    auto_detect_and_load_vmliste,
    auto_detect_and_load_bdd,
)


JOBS: Dict[str, Dict[str, Any]] = {}


def reset_jobs() -> Dict[str, Any]:
    cleared_memory = len(JOBS)
    JOBS.clear()

    try:
        cleared_db = delete_all_jobs()
    except Exception:
        cleared_db = 0

    try:
        maf_core.PENDING_DECISIONS = []
    except Exception:
        pass

    try:
        maf_core.HISTORICAL_DECISIONS = []
    except Exception:
        pass

    try:
        maf_core.API_MODE = False
    except Exception:
        pass

    return {
        "status": "reset",
        "cleared": cleared_memory,
        "cleared_db": cleared_db,
    }


def _list_output_basicat_files(basicat: str) -> list[dict]:
    files = []
    root = OUTPUT_DIR / "output_basicat" / basicat

    if not root.exists():
        return files

    for path in root.rglob("*"):
        if path.is_file():
            files.append({
                "name": path.name,
                "path": str(path.relative_to(OUTPUT_DIR)),
            })

    return files


def _normalize_pending_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(decision or {})
    dst_ip = str(normalized.get("dst_ip") or normalized.get("dstIp") or normalized.get("destination_ip") or "").strip()
    flow_gref_sg = str(
        normalized.get("flowGrefSG")
        or normalized.get("flow_gref_sg")
        or normalized.get("flowGretSG")
        or normalized.get("sg_cible")
        or ""
    ).strip()

    if dst_ip:
        normalized.setdefault("dst_ip", dst_ip)
        normalized.setdefault("dstIp", dst_ip)
        normalized.setdefault("destination_ip", dst_ip)
        normalized.setdefault("Configured Destination", dst_ip)

    if flow_gref_sg:
        normalized.setdefault("flowGrefSG", flow_gref_sg)
        normalized.setdefault("flow_gref_sg", flow_gref_sg)
        normalized.setdefault("flowGretSG", flow_gref_sg)
        normalized.setdefault("sg_cible", flow_gref_sg)
        normalized.setdefault("Configured Service", normalized.get("Configured Service", ""))

    return normalized


def _normalize_basicat(basicat: str) -> str:
    return str(basicat or "").strip().upper()


def _basicat_exists_in_vmliste(basicat: str) -> bool:
    try:
        # Détection automatique du fichier vmliste
        df = auto_detect_and_load_vmliste(Path("data"))
    except Exception as exc:
        # Si détection échoue, essayer le chemin par défaut
        if not VMLISTE_FILE.exists():
            raise ValueError(f"Fichier introuvable: {VMLISTE_FILE}")
        try:
            df = pd.read_excel(VMLISTE_FILE, dtype=str)
        except Exception:
            raise ValueError(f"Impossible de lire le fichier vmliste: {exc}")

    basicat_col = None
    for col in df.columns:
        if str(col).strip().upper() in ["BASICAT", "BASIC_CAT", "CODE_BASICAT"]:
            basicat_col = col
            break

    if basicat_col is None:
        raise ValueError("La colonne BASICAT est introuvable dans vmliste")

    known = {
        str(value).strip().upper()
        for value in df[basicat_col].dropna().tolist()
        if str(value).strip()
    }
    return basicat in known


def create_job(basicat: str) -> Dict[str, Any]:
    basicat = _normalize_basicat(basicat)

    if not basicat:
        raise ValueError("Le BASICAT est obligatoire")

    if not _basicat_exists_in_vmliste(basicat):
        raise ValueError(
            f"BASICAT inexistant: '{basicat}' n'est pas present dans {VMLISTE_FILE}"
        )

    job_id = str(uuid.uuid4())

    JOBS[job_id] = {
        "job_id": job_id,
        "basicat": basicat,
        "status": "created",
        "phase": "created",
        "message": "Job créé. Prêt à générer le FR.",
        "generated_envs": [],
        "snif_env_status": {},
        "skipped_snif_envs": [],
        "current_snif_env": None,
        "pending_decisions": [],
        "historical_decisions": [],
        "validated_decisions": [],
        "files": [],
        "benchmark": [],
        "conflicts": [],
        "output_path": "",
        "uploaded_files": {},
    }

    save_job(JOBS[job_id])
    return JOBS[job_id]


def _next_snif_env(job: Dict[str, Any]) -> str | None:
    for env in job.get("generated_envs", []):
        if job.get("snif_env_status", {}).get(env) != "done":
            return env
    return None


def _apply_result_to_job(job: Dict[str, Any], result: Dict[str, Any], phase: str) -> None:
    """
    Injecte le résultat maf_core dans le job.

    Règle:
    - pending_decisions = nouvelles lignes à valider/corriger obligatoirement
    - historical_decisions = lignes déjà connues, affichées séparément et ne bloquent pas le workflow
    """
    basicat = job["basicat"]
    result = result or {}

    pending = [
        _normalize_pending_decision(p)
        for p in (result.get("pending_decisions", []) or [])
    ]

    historical = [
        _normalize_pending_decision(h)
        for h in (result.get("historical_decisions", []) or [])
    ]

    # Annoter la phase.
    for p in pending:
        if isinstance(p, dict):
            p["from_phase"] = phase

    for h in historical:
        if isinstance(h, dict):
            h["from_phase"] = phase
            h["historical"] = True
            h["requires_validation"] = False
            h["can_correct"] = True
            h.setdefault("score", "100")
            h.setdefault("ml_confiance", "1.0")

    # Merge envs sans écraser la liste complète avec un résultat SNIF par env.
    result_envs = result.get("envs")
    existing_envs = job.get("generated_envs", []) or []

    if result_envs:
        job["generated_envs"] = list(dict.fromkeys(existing_envs + result_envs))
    else:
        job["generated_envs"] = existing_envs

    existing_pending = [
        _normalize_pending_decision(p)
        for p in (job.get("pending_decisions", []) or [])
    ]

    existing_historical = [
        _normalize_pending_decision(h)
        for h in (job.get("historical_decisions", []) or [])
    ]

    validated_list = job.get("validated_decisions", []) or []

    def _is_same_decision(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        try:
            return (
                str(a.get("env") or "").strip().lower() == str(b.get("env") or "").strip().lower()
                and str(a.get("src_ip") or a.get("srcIp") or "").strip() == str(b.get("src_ip") or b.get("srcIp") or "").strip()
                and str(a.get("dst_ip") or a.get("dstIp") or a.get("destination_ip") or "").strip() == str(b.get("dst_ip") or b.get("dstIp") or b.get("destination_ip") or "").strip()
                and str(a.get("port") or "").strip() == str(b.get("port") or "").strip()
                and str(a.get("flowMainSG") or "").strip() == str(b.get("flowMainSG") or "").strip()
                and str(a.get("flowGrefSG") or a.get("flow_gref_sg") or a.get("sg_cible") or "").strip()
                == str(b.get("flowGrefSG") or b.get("flow_gref_sg") or b.get("sg_cible") or "").strip()
            )
        except Exception:
            return False

    def _decision_key(d: Dict[str, Any]) -> str:
        if not isinstance(d, dict):
            return ""

        technical_signature = str(d.get("technical_signature") or "").strip()
        if technical_signature:
            return f"sig::{technical_signature}"

        return "|".join([
            str(d.get("env") or "").strip().lower(),
            str(d.get("from_phase") or "").strip(),
            str(d.get("src_ip") or d.get("srcIp") or "").strip(),
            str(d.get("dst_ip") or d.get("dstIp") or d.get("destination_ip") or "").strip(),
            str(d.get("port") or "").strip(),
            str(d.get("flowMainSG") or "").strip(),
            str(d.get("flowGrefSG") or d.get("flow_gref_sg") or d.get("sg_cible") or "").strip(),
            str(d.get("decision_id") or "").strip(),
        ])

    # -------------------------
    # pending_decisions
    # -------------------------
    if phase == "fr":
        combined_pending = {
            p.get("decision_id"): p
            for p in existing_pending
            if isinstance(p, dict) and p.get("decision_id")
        }

        for p in pending:
            if isinstance(p, dict) and p.get("decision_id"):
                matched_valid = next((v for v in validated_list if _is_same_decision(v, p)), None)
                combined_pending[p.get("decision_id")] = matched_valid if matched_valid else p

        job["pending_decisions"] = [
            _normalize_pending_decision(p)
            for p in list(combined_pending.values())
        ]

    elif phase.startswith("snif_"):
        current_env = phase.split("snif_", 1)[1]
        kept_pending = [
            p for p in existing_pending
            if str(p.get("env") or "").strip().lower() != current_env
        ]

        replaced_pending = []
        for p in pending:
            if isinstance(p, dict):
                matched_valid = next((v for v in validated_list if _is_same_decision(v, p)), None)
                replaced_pending.append(matched_valid if matched_valid else p)

        job["pending_decisions"] = [
            _normalize_pending_decision(p)
            for p in (kept_pending + replaced_pending)
        ]

    else:
        job["pending_decisions"] = [_normalize_pending_decision(p) for p in pending]

    # -------------------------
    # historical_decisions
    # -------------------------
    if phase == "fr":
        combined_historical = {
            _decision_key(h): h
            for h in existing_historical
            if _decision_key(h)
        }

        for h in historical:
            key = _decision_key(h)
            if key:
                combined_historical[key] = h

        job["historical_decisions"] = [
            _normalize_pending_decision(h)
            for h in list(combined_historical.values())
        ]

    elif phase.startswith("snif_"):
        current_env = phase.split("snif_", 1)[1]
        kept_historical = [
            h for h in existing_historical
            if str(h.get("env") or "").strip().lower() != current_env
        ]

        combined_historical = {
            _decision_key(h): h
            for h in kept_historical
            if _decision_key(h)
        }

        for h in historical:
            key = _decision_key(h)
            if key:
                combined_historical[key] = h

        job["historical_decisions"] = [
            _normalize_pending_decision(h)
            for h in list(combined_historical.values())
        ]

    else:
        job["historical_decisions"] = [_normalize_pending_decision(h) for h in historical]

    job["files"] = _list_output_basicat_files(basicat)
    job["benchmark"] = result.get("benchmark", [])
    job["conflicts"] = result.get("conflicts", [])
    job["phase"] = phase

    if phase == "fr":
        job["snif_env_status"] = {env: "pending" for env in job["generated_envs"]}
        job["current_snif_env"] = _next_snif_env(job)

    if phase.startswith("snif_"):
        env = phase.split("snif_", 1)[1]
        if env:
            snif_env_status = job.setdefault("snif_env_status", {})

            pending_for_env_status = [
                p for p in job.get("pending_decisions", []) or []
                if str(p.get("env") or "").strip().lower() == env
            ]

            historical_for_env_status = [
                h for h in job.get("historical_decisions", []) or []
                if str(h.get("env") or "").strip().lower() == env
            ]

            if pending_for_env_status or historical_for_env_status:
                snif_env_status[env] = "reviewing"
                job["current_snif_env"] = env
            else:
                snif_env_status[env] = "done"
                job["current_snif_env"] = _next_snif_env(job)

    pending_for_phase = []
    historical_for_phase = []

    if phase == "fr":
        pending_for_phase = [
            p for p in job.get("pending_decisions", []) or []
            if str(p.get("from_phase") or "") == "fr"
        ]

        historical_for_phase = [
            h for h in job.get("historical_decisions", []) or []
            if str(h.get("from_phase") or "") == "fr"
        ]

    elif phase.startswith("snif_"):
        env = phase.split("snif_", 1)[1]

        pending_for_phase = [
            p for p in job.get("pending_decisions", []) or []
            if str(p.get("env") or "").strip().lower() == env
        ]

        historical_for_phase = [
            h for h in job.get("historical_decisions", []) or []
            if str(h.get("env") or "").strip().lower() == env
        ]

    else:
        pending_for_phase = job.get("pending_decisions", []) or []
        historical_for_phase = job.get("historical_decisions", []) or []

    if pending_for_phase:
        job["status"] = "waiting_decision"

        if phase == "fr":
            label = "FR"
        elif phase.startswith("snif_"):
            label = f"SNIF {phase.split('snif_', 1)[1].upper()}"
        else:
            label = "SNIF/MAF"

        job["message"] = (
            f"{label} généré, mais {len(pending_for_phase)} nouvelle(s) ligne(s) "
            f"doivent être validées/corrigées."
        )

    elif historical_for_phase:
        if phase == "fr":
            job["status"] = "fr_done"
            job["message"] = (
                "FR généré avec uniquement des lignes déjà connues. "
                "Tu peux maintenant traiter le SNIF étape par étape."
            )

        elif phase.startswith("snif_"):
            env = phase.split("snif_", 1)[1]
            job["status"] = "historical_review"
            job["phase"] = phase
            job["current_snif_env"] = env

            snif_env_status = job.setdefault("snif_env_status", {})
            snif_env_status[env] = "reviewing"

            job["message"] = (
                f"SNIF {env.upper()} généré avec uniquement des lignes déjà connues. "
                f"Vérifie les lignes historiques si nécessaire puis clique sur Terminer SNIF."
            )

        else:
            job["status"] = "completed"
            job["message"] = "Traitement généré avec uniquement des lignes déjà connues."

    else:
        if phase == "fr":
            job["status"] = "fr_done"
            job["message"] = (
                "FR généré avec succès. "
                "Tu peux maintenant traiter le SNIF étape par étape."
            )

        elif phase.startswith("snif_"):
            next_env = _next_snif_env(job)

            if next_env:
                job["status"] = "snif_ready_next"
                job["message"] = (
                    f"SNIF {phase.split('snif_', 1)[1].upper()} finalisé. "
                    f"Tu peux passer à l'étape {('3.1' if next_env == 'prod' else '3.2')} "
                    f"pour {next_env.upper()}."
                )
            else:
                job["status"] = "snif_complete"
                job["message"] = "SNIF terminé. Tu peux maintenant générer le MAF final."

        else:
            job["status"] = "completed"
            job["message"] = "SNIF + MAF générés avec succès."
def run_fr_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)

    if not job:
        job = load_job(job_id)
        if job:
            JOBS[job_id] = job

    if not job:
        raise ValueError("Job introuvable")

    basicat = job["basicat"]

    try:
        job["status"] = "running_fr"
        job["phase"] = "fr"
        job["message"] = f"Génération FR en cours pour BASICAT {basicat}."

        maf_core.API_MODE = True
        maf_core.PENDING_DECISIONS = []
        try:
            maf_core.HISTORICAL_DECISIONS = []
        except Exception:
            pass

        result = run_maf(
            basicat_code=basicat,
            snif_prod=None,
            snif_horsprod=None,
            finalize_maf=False,
        )

        maf_core.API_MODE = False
        _apply_result_to_job(job, result or {}, phase="fr")

    except Exception as e:
        maf_core.API_MODE = False
        job["status"] = "error"
        job["message"] = f"Erreur pendant la génération FR : {str(e)}"

    save_job(job)
    return job

def run_snif_job(job_id: str, env_name: str | None = None) -> Dict[str, Any]:
    job = JOBS.get(job_id)

    if not job:
        job = load_job(job_id)
        if job:
            JOBS[job_id] = job

    if not job:
        raise ValueError("Job introuvable")

    basicat = job["basicat"]
    envs = job.get("generated_envs", [])

    current_env = (
        env_name
        or job.get("current_snif_env")
        or _next_snif_env(job)
        or ""
    ).strip().lower()

    if not envs:
        raise ValueError("FR non termine: genere d abord le FR pour detecter les environnements")

    if not current_env:
        raise ValueError("Aucun environnement SNIF disponible")

    if current_env not in envs:
        raise ValueError(f"Environnement SNIF inconnu: {current_env}")

    if job.get("snif_env_status", {}).get(current_env) == "done":
        save_job(job)
        return job

    if job.get("pending_decisions") and job.get("phase") not in [f"snif_{current_env}", "fr"]:
        raise ValueError("Termine l'environnement SNIF courant avant de passer au suivant")

    if (
        job.get("status") not in [
            "fr_done",
            "snif_ready_next",
            "snif_complete",
            "waiting_decision",
        ]
        and job.get("phase") not in [f"snif_{current_env}", "fr"]
    ):
        raise ValueError("SNIF est autorise uniquement apres finalisation du FR")

    try:
        job["status"] = "running_snif"
        job["phase"] = f"snif_{current_env}"
        job["current_snif_env"] = current_env
        job["message"] = (
            f"Génération SNIF {current_env.upper()} en cours pour BASICAT {basicat}."
        )

        uploaded_files = job.get("uploaded_files", {}) or {}
        snif_file_value = uploaded_files.get(current_env)

        if not snif_file_value:
            raise ValueError(
                f"Aucun fichier SNIF uploadé pour {current_env.upper()} sur ce job"
            )

        snif_file = Path(snif_file_value)

        if not snif_file.exists():
            raise ValueError(
                f"Fichier SNIF introuvable pour {current_env.upper()}: {snif_file}"
            )

        maf_core.API_MODE = True
        maf_core.PENDING_DECISIONS = []
        try:
            maf_core.HISTORICAL_DECISIONS = []
        except Exception:
            pass

        result = process_snif_file(
            snif_path=snif_file,
            bdd_path=Path(BDD_FILE),
            basicat_code=basicat,
            env_name=current_env,
        )

        maf_core.API_MODE = False

        _apply_result_to_job(job, result or {}, phase=f"snif_{current_env}")

    except Exception as e:
        maf_core.API_MODE = False
        job["status"] = "error"
        job["message"] = (
            f"Erreur pendant la génération SNIF {current_env.upper()} : {str(e)}"
        )

    save_job(job)
    return job

def finalize_maf_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)

    if not job:
        job = load_job(job_id)
        if job:
            JOBS[job_id] = job

    if not job:
        raise ValueError("Job introuvable")

    basicat = job["basicat"]
    envs = job.get("generated_envs", []) or []

    if not envs:
        raise ValueError("FR non termine: aucun environnement SNIF n'a été détecté")

    if any(job.get("snif_env_status", {}).get(env) != "done" for env in envs):
        raise ValueError("Termine d'abord toutes les étapes SNIF avant de générer le MAF final")

    try:
        job["status"] = "running_maf"
        job["phase"] = "maf"
        job["message"] = f"Génération du MAF final en cours pour BASICAT {basicat}."

        last_output = None
        skipped_envs = set(job.get("skipped_snif_envs", []) or [])

        for env in envs:
            env = str(env or "").strip().lower()

            if env in skipped_envs:
                print(f"[DEBUG] MAF final ignoré pour {env.upper()} car SNIF passé.")
                continue

            output_file = generate_final_maf_matrix(basicat, env)

            if output_file is not None:
                last_output = output_file

        job["files"] = _list_output_basicat_files(basicat)
        job["output_path"] = str(last_output) if last_output is not None else ""
        job["status"] = "completed"
        job["phase"] = "completed"

        if skipped_envs:
            skipped_label = ", ".join(env.upper() for env in skipped_envs)
            job["message"] = (
                f"Traitement terminé. Le MAF final a été généré avec succès. "
                f"Environnement(s) ignoré(s): {skipped_label}."
            )
        else:
            job["message"] = "Traitement terminé. Le MAF final a été généré avec succès."

    except Exception as exc:
        job["status"] = "error"
        job["message"] = f"Erreur pendant la génération du MAF final : {exc}"

    save_job(job)
    return job

def run_job(job_id: str) -> Dict[str, Any]:
    # Ancienne route /run conservée comme alias de run-fr
    return run_fr_job(job_id)


def skip_snif_env(job_id: str, env_name: str) -> Dict[str, Any]:
    """
    Marque un environnement SNIF comme passé.
    Important:
    - Ne génère aucun fichier SNIF.
    - Supprime les éventuels anciens fichiers SNIF/MAF liés à cet environnement.
    - Marque l'environnement comme done pour permettre de continuer le workflow.
    - Ajoute l'environnement dans skipped_snif_envs pour que finalize_maf_job l'ignore.
    """
    job = JOBS.get(job_id)

    if not job:
        job = load_job(job_id)
        if job:
            JOBS[job_id] = job

    if not job:
        raise ValueError("Job introuvable")

    env_name = str(env_name or "").strip().lower()
    basicat = str(job.get("basicat") or "").strip()
    envs = job.get("generated_envs", []) or []

    if env_name not in envs:
        raise ValueError(f"Environnement inconnu: {env_name}")

    skipped = job.setdefault("skipped_snif_envs", [])
    if env_name not in skipped:
        skipped.append(env_name)

    snif_env_status = job.setdefault("snif_env_status", {})
    snif_env_status[env_name] = "done"

    existing_pending = job.get("pending_decisions", []) or []
    job["pending_decisions"] = [
        p for p in existing_pending
        if str(p.get("env") or "").strip().lower() != env_name
    ]

    existing_historical = job.get("historical_decisions", []) or []
    job["historical_decisions"] = [
        h for h in existing_historical
        if str(h.get("env") or "").strip().lower() != env_name
    ]

    env_folder = OUTPUT_DIR / "output_basicat" / basicat / env_name

    if env_folder.exists():
        patterns = [
            f"*_{env_name}_snif.xlsx",
            f"*_{env_name}-snif.xlsx",
            f"*_{env_name}_SNIF.xlsx",
            f"*_{env_name}-SNIF.xlsx",
            f"*_{env_name}_MAF.xlsx",
            f"*_{env_name}-MAF.xlsx",
            f"*{env_name}*snif*.xlsx",
            f"*{env_name}*SNIF*.xlsx",
            f"*{env_name}*MAF*.xlsx",
        ]

        for pattern in patterns:
            for path in env_folder.glob(pattern):
                try:
                    if path.is_file():
                        path.unlink()
                        print(f"[DEBUG] Fichier supprimé car SNIF passé: {path}")
                except Exception as exc:
                    print(f"[DEBUG] Impossible de supprimer {path}: {exc}")

    next_env = _next_snif_env(job)

    if next_env:
        job["current_snif_env"] = next_env
        job["status"] = "snif_ready_next"
        job["phase"] = f"snif_{next_env}"
        job["message"] = (
            f"SNIF {env_name.upper()} passé. "
            f"Aucun fichier ne sera généré pour cet environnement. "
            f"Tu peux maintenant traiter le SNIF {next_env.upper()}."
        )
    else:
        job["current_snif_env"] = None
        job["status"] = "snif_complete"
        job["phase"] = "snif_complete"
        job["message"] = (
            "SNIF terminé pour tous les environnements. "
            "Les environnements passés seront ignorés dans le MAF final."
        )

    job["files"] = _list_output_basicat_files(basicat)

    save_job(job)
    return job
def complete_snif_env_review(job_id: str, env_name: str) -> Dict[str, Any]:
    """
    Termine un environnement SNIF lorsque toutes les lignes restantes sont
    historiques / déjà connues et ne nécessitent pas de validation.
    """
    job = JOBS.get(job_id)

    if not job:
        job = load_job(job_id)
        if job:
            JOBS[job_id] = job

    if not job:
        raise ValueError("Job introuvable")

    env_name = str(env_name or "").strip().lower()
    envs = job.get("generated_envs", []) or []

    if env_name not in envs:
        raise ValueError(f"Environnement inconnu: {env_name}")

    pending_for_env = [
        p for p in job.get("pending_decisions", []) or []
        if str(p.get("env") or "").strip().lower() == env_name
    ]

    if pending_for_env:
        raise ValueError(
            f"Impossible de terminer SNIF {env_name.upper()} : "
            f"{len(pending_for_env)} nouvelle(s) ligne(s) restent à valider."
        )

    snif_env_status = job.setdefault("snif_env_status", {})
    snif_env_status[env_name] = "done"

    next_env = _next_snif_env(job)

    if next_env:
        job["current_snif_env"] = next_env
        job["status"] = "snif_ready_next"
        job["phase"] = f"snif_{next_env}"
        job["message"] = (
            f"SNIF {env_name.upper()} finalisé. "
            f"Tu peux maintenant traiter le SNIF {next_env.upper()}."
        )
    else:
        job["current_snif_env"] = None
        job["status"] = "snif_complete"
        job["phase"] = "snif_complete"
        job["message"] = "SNIF terminé. Tu peux maintenant générer le MAF final."

    job["files"] = _list_output_basicat_files(job.get("basicat"))

    save_job(job)
    return job

def _learn_from_decision(decision: Dict[str, Any]) -> None:
    """
    Ajoute la validation/correction dans la BDD sans écraser l'existant.

    Important:
    - On recharge directement le fichier bdd_flux_maf.xlsx existant.
    - On ajoute la nouvelle ligne validée.
    - On supprime uniquement les doublons exacts.
    - On sauvegarde la BDD complète, pas seulement la nouvelle ligne.
    """
    action = decision.get("action")
    if action == "ignore":
        return

    flux = decision.get("flux") or decision.get("proposed_flux") or decision.get("suggested_flux") or ""
    nom = decision.get("nom") or decision.get("proposed_nom") or decision.get("suggested_nom") or ""

    if not flux or not nom:
        raise ValueError("flux et nom sont obligatoires pour validate/correct")

    bdd_path = Path(BDD_FILE)

    # 1. Charger la BDD existante directement depuis le fichier Excel.
    # Cela évite que auto_detect/load_bdd retourne une BDD vide ou un mauvais fichier.
    if bdd_path.exists():
        try:
            df_bdd = pd.read_excel(bdd_path, dtype=str).fillna("")
            df_bdd.columns = [str(c).strip() for c in df_bdd.columns]
        except Exception as exc:
            raise ValueError(f"Impossible de lire la BDD existante: {bdd_path} - {exc}")
    else:
        df_bdd = pd.DataFrame(columns=[
            "protocol",
            "port",
            "src_ip",
            "dst_ip",
            "flowMainSG",
            "flowGrefSG",
            "direction",
            "flux",
            "Nom",
        ])

    # 2. Garantir que toutes les colonnes existent.
    required_columns = [
        "protocol",
        "port",
        "src_ip",
        "dst_ip",
        "flowMainSG",
        "flowGrefSG",
        "direction",
        "flux",
        "Nom",
    ]

    for col in required_columns:
        if col not in df_bdd.columns:
            df_bdd[col] = ""

    df_bdd = df_bdd[required_columns].copy()

    for col in required_columns:
        df_bdd[col] = df_bdd[col].astype(str).fillna("").str.strip()

    # 3. Construire la nouvelle ligne validée.
    new_row = {
        "protocol": str(decision.get("protocol", "") or "").strip(),
        "port": str(decision.get("port", "") or "").strip(),
        "src_ip": str(decision.get("src_ip", "") or decision.get("srcIp", "") or "").strip(),
        "dst_ip": str(
            decision.get("dst_ip", "")
            or decision.get("dstIp", "")
            or decision.get("destination_ip", "")
            or ""
        ).strip(),
        "flowMainSG": str(
            decision.get("flowMainSG", "")
            or decision.get("flow_main_sg", "")
            or ""
        ).strip(),
        "flowGrefSG": str(
            decision.get("flowGrefSG", "")
            or decision.get("flow_gref_sg", "")
            or decision.get("sg_cible", "")
            or ""
        ).strip(),
        "direction": str(decision.get("direction", "") or "").strip(),
        "flux": str(flux or "").strip(),
        "Nom": str(nom or "").strip(),
    }

    # 4. Ajouter la nouvelle ligne à la BDD existante.
    df_new = pd.DataFrame([new_row], columns=required_columns)
    df_bdd = pd.concat([df_bdd, df_new], ignore_index=True)

    # 5. Nettoyer les doublons exacts uniquement.
    # Attention: on ne supprime pas les anciennes lignes utiles.
    df_bdd = df_bdd.drop_duplicates().reset_index(drop=True)

    # 6. Backup avant sauvegarde.
    if bdd_path.exists():
        backup_dir = bdd_path.parent / "bdd_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{bdd_path.stem}_backup_{timestamp}{bdd_path.suffix}"

        try:
            import shutil
            shutil.copy2(bdd_path, backup_file)
        except Exception:
            pass

    # 7. Sauvegarder la BDD complète.
    df_bdd.to_excel(bdd_path, index=False)

    try:
        maf_core.autosize_excel_columns(bdd_path)
    except Exception:
        pass


def _apply_decision_to_fr_outputs(job: Dict[str, Any], decision: Dict[str, Any]) -> None:
    """
    Apply corrected/validated flux/nom to existing FR output files for the job.
    This is needed because the FR Excel is generated before human validation.
    """
    try:
        env = str(decision.get("env") or "").strip().lower()
        basicat = str(job.get("basicat") or "").strip()

        if not env or not basicat:
            return

        files = job.get("files", []) or []
        targets = []

        for f in files:
            p = str(f.get("path") or "")
            name = str(f.get("name") or "")

            if (
                name.endswith(f"_{env}-FR.xlsx")
                or name.endswith(f"{env}-FR.xlsx")
                or p.endswith(f"_{env}-FR.xlsx")
                or p.endswith(f"{env}-FR.xlsx")
            ):
                targets.append(Path(OUTPUT_DIR) / p)

        # Fallback direct path
        fallback = OUTPUT_DIR / "output_basicat" / basicat / env / f"{basicat}_{env}-FR.xlsx"
        if fallback.exists() and fallback not in targets:
            targets.append(fallback)

        if not targets:
            print(f"[DEBUG] Aucun fichier FR trouvé pour env={env}")
            return

        src_ip = str(
            decision.get("src_ip")
            or decision.get("srcIp")
            or decision.get("Configured Source")
            or ""
        ).strip()

        dst_ip = str(
            decision.get("dst_ip")
            or decision.get("dstIp")
            or decision.get("destination_ip")
            or decision.get("Configured Destination")
            or ""
        ).strip()

        port = str(decision.get("port") or "").strip()

        flow_main = str(
            decision.get("flowMainSG")
            or decision.get("flow_main_sg")
            or ""
        ).strip()

        flow_gref = str(
            decision.get("flowGrefSG")
            or decision.get("flow_gref_sg")
            or decision.get("sg_cible")
            or ""
        ).strip()

        new_flux = str(
            decision.get("flux")
            or decision.get("proposed_flux")
            or decision.get("suggested_flux")
            or ""
        ).strip()

        new_nom = str(
            decision.get("nom")
            or decision.get("Nom")
            or decision.get("proposed_nom")
            or decision.get("suggested_nom")
            or ""
        ).strip()

        if not new_flux and not new_nom:
            print("[DEBUG] Aucun flux/Nom à appliquer au FR")
            return

        for path in targets:
            try:
                if not path.exists():
                    continue

                df = pd.read_excel(path, dtype=str).fillna("")
                df.columns = [str(c).strip() for c in df.columns]

                if "flux" not in df.columns:
                    df["flux"] = ""

                if "Nom" not in df.columns:
                    df["Nom"] = ""

                mask = pd.Series([True] * len(df))

                if "Configured Source" in df.columns and src_ip:
                    mask = mask & (df["Configured Source"].astype(str).str.strip() == src_ip)

                if "Configured Destination" in df.columns and dst_ip:
                    mask = mask & (df["Configured Destination"].astype(str).str.strip() == dst_ip)

                if "port" in df.columns and port:
                    mask = mask & (df["port"].astype(str).str.strip() == port)

                if "flowMainSG" in df.columns and flow_main:
                    mask = mask & (df["flowMainSG"].astype(str).str.strip() == flow_main)

                if "flowGrefSG" in df.columns and flow_gref:
                    mask = mask & (df["flowGrefSG"].astype(str).str.strip() == flow_gref)

                # Fallback plus faible : source IP + flowMainSG
                if not mask.any():
                    mask = pd.Series([True] * len(df))

                    if "Configured Source" in df.columns and src_ip:
                        mask = mask & (df["Configured Source"].astype(str).str.strip() == src_ip)

                    if "flowMainSG" in df.columns and flow_main:
                        mask = mask & (df["flowMainSG"].astype(str).str.strip() == flow_main)

                # Fallback dernier recours : source IP uniquement
                if not mask.any():
                    mask = pd.Series([True] * len(df))

                    if "Configured Source" in df.columns and src_ip:
                        mask = mask & (df["Configured Source"].astype(str).str.strip() == src_ip)

                if not mask.any():
                    print(f"[DEBUG] Aucune ligne FR matchée dans {path.name}")
                    continue

                if new_flux:
                    df.loc[mask, "flux"] = new_flux

                if new_nom:
                    df.loc[mask, "Nom"] = new_nom

                df.to_excel(path, index=False)

                try:
                    maf_core.autosize_excel_columns(path)
                    maf_core.apply_security_colors(path)
                except Exception:
                    pass

                print(f"[DEBUG] FR mis à jour: {path} | lignes={int(mask.sum())}")

            except Exception as exc:
                print(f"[DEBUG] Erreur update FR {path}: {exc}")
                continue

    except Exception as exc:
        print(f"[DEBUG] Erreur _apply_decision_to_fr_outputs: {exc}")
        return

def _apply_decision_to_snif_outputs(job: Dict[str, Any], decision: Dict[str, Any]) -> None:
    """Apply corrected/validated flux/nom to existing SNIF output files for the job.
    Matches rows by src/dst/port/flowMainSG and updates 'flux' and 'Nom' columns.
    """
    try:
        env = (decision.get("env") or job.get("current_snif_env") or "").strip()
        if not env:
            # try to extract from job phase
            phase = job.get("phase", "")
            if isinstance(phase, str) and phase.startswith("snif_"):
                env = phase.split("snif_", 1)[1]

        if not env:
            return

        # find snif output files in job files
        files = job.get("files", []) or []
        targets = []
        for f in files:
            p = str(f.get("path") or "")
            if p.endswith(f"_{env}_snif.xlsx") or f.get("name", "").endswith(f"_{env}_snif.xlsx"):
                targets.append(Path(OUTPUT_DIR) / p)

        if not targets:
            return

        src_ip = str(decision.get("src_ip") or decision.get("srcIp") or "").strip()
        dst_ip = str(decision.get("dst_ip") or decision.get("dstIp") or decision.get("destination_ip") or "").strip()
        port = str(decision.get("port") or "").strip()
        flow_main = str(decision.get("flowMainSG") or decision.get("flow_main_sg") or "").strip()
        new_flux = decision.get("flux") or decision.get("proposed_flux") or decision.get("suggested_flux") or ""
        new_nom = decision.get("nom") or decision.get("proposed_nom") or decision.get("suggested_nom") or ""

        for path in targets:
            try:
                if not path.exists():
                    continue
                df = pd.read_excel(path, dtype=str).fillna("")

                # attempt match on common columns
                src_cols = [c for c in df.columns if str(c).strip().lower() in {"configured source", "src_ip", "source ip", "source"}]
                dst_cols = [c for c in df.columns if str(c).strip().lower() in {"configured destination", "dst_ip", "destination ip", "destination"}]
                flow_cols = [c for c in df.columns if str(c).strip().lower() in {"flowmainsg", "flowmainsg", "flowMainSG"}]

                # fallback column names
                src_col = src_cols[0] if src_cols else None
                dst_col = dst_cols[0] if dst_cols else None
                flow_col = "flowMainSG" if "flowMainSG" in df.columns else (flow_cols[0] if flow_cols else None)

                mask = pd.Series([True] * len(df))
                if src_col and src_ip:
                    mask = mask & (df[src_col].astype(str).str.strip() == src_ip)
                if dst_col and dst_ip:
                    mask = mask & (df[dst_col].astype(str).str.strip() == dst_ip)
                if port:
                    if "port" in df.columns:
                        mask = mask & (df["port"].astype(str).str.strip() == port)
                if flow_col and flow_main:
                    if flow_col in df.columns:
                        mask = mask & (df[flow_col].astype(str).str.strip() == flow_main)

                if not mask.any():
                    # try weaker match: src+dst only
                    mask = pd.Series([True] * len(df))
                    if src_col and src_ip:
                        mask = mask & (df[src_col].astype(str).str.strip() == src_ip)
                    if dst_col and dst_ip:
                        mask = mask & (df[dst_col].astype(str).str.strip() == dst_ip)

                if not mask.any():
                    continue

                updated = False
                if "flux" in df.columns and new_flux:
                    df.loc[mask, "flux"] = new_flux
                    updated = True
                if "Nom" in df.columns and new_nom:
                    df.loc[mask, "Nom"] = new_nom
                    updated = True

                if updated:
                    df.to_excel(path, index=False)
                    try:
                        maf_core.autosize_excel_columns(path)
                        maf_core.apply_security_colors(path)
                    except Exception:
                        pass
            except Exception:
                continue
    except Exception:
        return


def _rerun_after_decisions(job: Dict[str, Any]) -> None:
    """
    Après validation/correction des lignes, on met à jour l'état du job.
    - Pour FR: on met juste à jour le status à "fr_done" si tout est validé.
    - Pour SNIF: on marque l'env comme "done" et passe à l'env suivant.
    (On ne regénère PAS les fichiers, car les décisions ont déjà été traitées.)
    """
    phase = job.get("phase")

    if phase == "fr":
        # FR: toutes les décisions FR sont validées, on passe au SNIF
        job["status"] = "fr_done"
        job["message"] = "FR finalisé. Tu peux maintenant traiter le SNIF étape par étape."
        print(f"[DEBUG] FR validation complete. Moving to SNIF.")

    elif phase.startswith("snif_"):
        current_env = phase.split("snif_", 1)[1]
        print(f"[DEBUG] SNIF {current_env} validation complete. Marking as 'done'.")
        
        # Marquer cet env comme done
        snif_env_status = job.setdefault("snif_env_status", {})
        snif_env_status[current_env] = "done"
        
        # Trouver le prochain env
        next_env = _next_snif_env(job)
        if next_env:
            job["current_snif_env"] = next_env
            job["status"] = "snif_ready_next"
            job["message"] = (
                f"SNIF {current_env.upper()} finalisé avec succès. "
                f"Tu peux passer à l'étape {('3.1' if next_env == 'prod' else '3.2')} pour {next_env.upper()}."
            )
            print(f"[DEBUG] Moving to next env: {next_env}")
        else:
            # Tous les envs SNIF sont done
            job["current_snif_env"] = None
            job["status"] = "snif_complete"
            job["message"] = "SNIF terminé pour tous les environnements. Tu peux maintenant générer le MAF final."
            print(f"[DEBUG] All SNIF envs complete. Ready for MAF finalization.")



def submit_decision(job_id: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    job = JOBS.get(job_id)

    if not job:
        job = load_job(job_id)
        if job:
            JOBS[job_id] = job

    if not job:
        raise ValueError("Job introuvable")

    decision_id = decision.get("decision_id")
    action = decision.get("action")

    if not decision_id:
        raise ValueError("decision_id manquant")

    if action not in ["validate", "correct", "ignore"]:
        raise ValueError("Action invalide")

    matching = None
    matching_source = None

    remaining_pending = []
    for pending in job.get("pending_decisions", []) or []:
        if pending.get("decision_id") == decision_id:
            matching = pending
            matching_source = "pending"
        else:
            remaining_pending.append(pending)

    remaining_historical = []
    if matching is None:
        for historical in job.get("historical_decisions", []) or []:
            if historical.get("decision_id") == decision_id:
                matching = historical
                matching_source = "historical"
            else:
                remaining_historical.append(historical)
    else:
        remaining_historical = job.get("historical_decisions", []) or []

    if matching is None:
        raise ValueError("Décision introuvable")

    merged = {**matching, **decision}

    try:
        extra = decision.get("extra")
        if isinstance(extra, dict):
            merged.update(extra)
    except Exception:
        pass

    if action in ["validate", "correct"]:
        _learn_from_decision(merged)

    phase = str(job.get("phase") or "")
    from_phase = str(merged.get("from_phase") or "")

    if phase == "fr" or from_phase == "fr":
        _apply_decision_to_fr_outputs(job, merged)

    elif phase.startswith("snif_") or from_phase.startswith("snif_"):
        _apply_decision_to_snif_outputs(job, merged)

    job["files"] = _list_output_basicat_files(job.get("basicat"))

    validated = job.setdefault("validated_decisions", [])

    merged_copy = dict(merged)
    merged_copy["score"] = "100"
    merged_copy["validated"] = True
    merged_copy["historical"] = True
    merged_copy["requires_validation"] = False
    merged_copy["can_correct"] = True
    merged_copy["ml_confiance"] = "1.0"
    merged_copy["source"] = "HISTORICAL_VALIDATED"

    validated.append(merged_copy)

    save_decision(job, merged_copy)

    if matching_source == "pending":
        job["pending_decisions"] = remaining_pending

        historical_list = job.setdefault("historical_decisions", [])

        already_exists = False
        for h in historical_list:
            if h.get("decision_id") == merged_copy.get("decision_id"):
                h.update(merged_copy)
                already_exists = True
                break

        if not already_exists:
            historical_list.append(merged_copy)

    elif matching_source == "historical":
        job["pending_decisions"] = remaining_pending

        updated_historical = []
        replaced = False

        for h in remaining_historical:
            if h.get("decision_id") == merged_copy.get("decision_id"):
                updated_historical.append(merged_copy)
                replaced = True
            else:
                updated_historical.append(h)

        if not replaced:
            updated_historical.append(merged_copy)

        job["historical_decisions"] = updated_historical

    print(f"[DEBUG] Decision {decision_id} processed. Remaining pending: {len(job.get('pending_decisions', []))}")
    print(f"[DEBUG] Historical decisions: {len(job.get('historical_decisions', []))}")

    if job.get("pending_decisions"):
        job["status"] = "waiting_decision"
        job["message"] = f"Il reste {len(job['pending_decisions'])} décision(s) à traiter."
    else:
        _rerun_after_decisions(job)

    save_job(job)
    return job

def get_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)

    if not job:
        job = load_job(job_id)

        if job:
            JOBS[job_id] = job

    if not job:
        raise ValueError("Job introuvable")

    job["pending_decisions"] = [
        _normalize_pending_decision(p)
        for p in (job.get("pending_decisions") or [])
    ]

    job["historical_decisions"] = [
        _normalize_pending_decision(h)
        for h in (job.get("historical_decisions") or [])
    ]

    return job

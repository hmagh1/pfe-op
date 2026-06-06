import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from sqlalchemy import Column, String, DateTime, Text, Integer, Float, text
from sqlalchemy.orm import Session

from app.services.db import Base, SessionLocal


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    basicat = Column(String(100), index=True, nullable=False)
    status = Column(String(100), index=True, nullable=False)
    phase = Column(String(100), index=True, nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class JobDecisionRecord(Base):
    __tablename__ = "job_decisions"

    decision_id = Column(String(100), primary_key=True, index=True)
    job_id = Column(String(64), index=True, nullable=False)
    basicat = Column(String(100), index=True, nullable=False)
    technical_signature = Column(Text, nullable=True)
    env = Column(String(50), index=True, nullable=True)
    from_phase = Column(String(100), index=True, nullable=True)
    action = Column(String(50), index=True, nullable=True)

    src_ip = Column(String(255), index=True, nullable=True)
    dst_ip = Column(String(255), index=True, nullable=True)
    port = Column(String(100), nullable=True)

    flowMainSG = Column(String(255), nullable=True)
    flowGrefSG = Column(String(255), nullable=True)

    proposed_flux = Column(String(255), nullable=True)
    proposed_nom = Column(String(255), nullable=True)

    final_flux = Column(String(255), nullable=True)
    final_nom = Column(String(255), nullable=True)

    score = Column(String(100), nullable=True)

    ml_modele = Column(String(100), nullable=True)
    ml_confiance = Column(String(100), nullable=True)
    seuil_auto = Column(String(100), nullable=True)

    validated = Column(String(20), index=True, nullable=True)

    payload_json = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModelVersionRecord(Base):
    __tablename__ = "model_versions"

    model_id = Column(String(100), primary_key=True, index=True)
    model_name = Column(String(100), index=True, nullable=False)

    source = Column(String(255), nullable=True)

    model_path = Column(String(500), nullable=True)
    metrics_path = Column(String(500), nullable=True)

    training_rows = Column(Integer, nullable=True)
    excel_rows = Column(Integer, nullable=True)
    mysql_rows = Column(Integer, nullable=True)
    n_classes = Column(Integer, nullable=True)

    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    is_active = Column(String(20), index=True, nullable=False, default="false")
    payload_json = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def _safe_json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, default=str)


def _safe_json_loads(payload_json: str) -> Dict[str, Any]:
    if not payload_json:
        return {}

    try:
        return json.loads(payload_json)
    except Exception:
        return {}


def _pick(payload: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _to_int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _to_float(value, default: float | None = None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default
def ensure_model_versions_schema() -> None:
    """
    Migration légère pour ajouter la colonne is_active si elle n'existe pas.

    SQLAlchemy create_all() crée les nouvelles tables, mais ne modifie pas
    automatiquement les tables existantes. Cette fonction évite l'erreur
    "Unknown column is_active" sur une base déjà créée.
    """
    db: Session = SessionLocal()

    try:
        db.execute(
            text(
                """
                ALTER TABLE model_versions
                ADD COLUMN is_active VARCHAR(20) NOT NULL DEFAULT 'false'
                """
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

# =========================
# JOBS
# =========================
def save_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée ou met à jour un job dans MySQL.
    """
    if not job:
        raise ValueError("Job vide impossible à sauvegarder")

    job_id = str(job.get("job_id") or "").strip()
    basicat = str(job.get("basicat") or "").strip()
    status = str(job.get("status") or "").strip()
    phase = str(job.get("phase") or "").strip()

    if not job_id:
        raise ValueError("job_id manquant")

    if not basicat:
        raise ValueError("basicat manquant")

    db: Session = SessionLocal()

    try:
        existing = db.get(JobRecord, job_id)
        now = datetime.utcnow()

        if existing:
            existing.basicat = basicat
            existing.status = status
            existing.phase = phase
            existing.payload_json = _safe_json_dumps(job)
            existing.updated_at = now
        else:
            record = JobRecord(
                job_id=job_id,
                basicat=basicat,
                status=status,
                phase=phase,
                payload_json=_safe_json_dumps(job),
                created_at=now,
                updated_at=now,
            )
            db.add(record)

        db.commit()
        return job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Charge un job depuis MySQL.
    """
    db: Session = SessionLocal()

    try:
        record = db.get(JobRecord, job_id)

        if not record:
            return None

        return _safe_json_loads(record.payload_json)

    finally:
        db.close()


def delete_all_jobs() -> int:
    """
    Supprime tous les jobs et toutes les décisions associées.
    Ne supprime pas model_versions, car les versions ML doivent rester traçables.
    """
    db: Session = SessionLocal()

    try:
        jobs_count = db.query(JobRecord).count()

        db.query(JobDecisionRecord).delete()
        db.query(JobRecord).delete()

        db.commit()
        return jobs_count

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def list_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Liste les derniers jobs.
    """
    db: Session = SessionLocal()

    try:
        records = (
            db.query(JobRecord)
            .order_by(JobRecord.updated_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "job_id": r.job_id,
                "basicat": r.basicat,
                "status": r.status,
                "phase": r.phase,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            }
            for r in records
        ]

    finally:
        db.close()

def build_decision_signature(
    basicat: str,
    env: str,
    protocol: str,
    port: str,
    src_ip: str,
    dst_ip: str,
    flowMainSG: str,
    flowGrefSG: str,
    direction: str,
) -> str:
    """
    Construit une signature technique stable pour reconnaître une ligne déjà traitée.

    Cette signature sert à retrouver les anciennes décisions validées
    lorsqu'on relance le même BASICAT.
    """
    parts = [
        str(basicat or "").strip().upper(),
        str(env or "").strip().lower(),
        str(protocol or "").strip().upper(),
        str(port or "").strip(),
        str(src_ip or "").strip(),
        str(dst_ip or "").strip(),
        str(flowMainSG or "").strip().upper(),
        str(flowGrefSG or "").strip().upper(),
        str(direction or "").strip().lower(),
    ]

    return "|".join(parts)
# =========================
# JOB DECISIONS
# =========================
def save_decision(job: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sauvegarde une décision validée/corrigée dans MySQL.

    Cette table sert pour:
    - ML training
    - RAG
    - audit trail
    - analyse des corrections humaines
    - suivi des performances ML
    """
    if not job:
        raise ValueError("Job manquant pour sauvegarder la décision")

    if not decision:
        raise ValueError("Décision vide impossible à sauvegarder")

    decision_id = _pick(decision, "decision_id")

    if not decision_id:
        raise ValueError("decision_id manquant pour sauvegarder la décision")

    job_id = _pick(job, "job_id")
    basicat = _pick(job, "basicat")
    raw_decision_id = _pick(decision, "decision_id")
    decision_id = f"{job_id}-{raw_decision_id}"

    if not job_id:
        raise ValueError("job_id manquant pour sauvegarder la décision")

    if not basicat:
        raise ValueError("basicat manquant pour sauvegarder la décision")

    action = _pick(decision, "action")
    env = _pick(decision, "env")
    protocol = _pick(decision, "protocol", "IP Protocol")
    port = _pick(decision, "port")
    src_ip = _pick(decision, "src_ip", "srcIp", "Configured Source")
    dst_ip = _pick(decision, "dst_ip", "dstIp", "destination_ip", "Configured Destination")
    flow_main_sg = _pick(decision, "flowMainSG", "flow_main_sg")
    flow_gref_sg = _pick(decision, "flowGrefSG", "flow_gref_sg", "sg_cible")
    direction = _pick(decision, "direction", "Direction")

    technical_signature = build_decision_signature(
    basicat=basicat,
    env=env,
    protocol=protocol,
    port=port,
    src_ip=src_ip,
    dst_ip=dst_ip,
    flowMainSG=flow_main_sg,
    flowGrefSG=flow_gref_sg,
    direction=direction,
)

    proposed_flux = _pick(
        decision,
        "proposed_flux",
        "suggested_flux",
        "ml_suggested_flux",
    )

    proposed_nom = _pick(
        decision,
        "proposed_nom",
        "suggested_nom",
        "ml_suggested_nom",
    )

    final_flux = _pick(
        decision,
        "flux",
        "final_flux",
        "proposed_flux",
        "suggested_flux",
        "ml_suggested_flux",
    )

    final_nom = _pick(
        decision,
        "nom",
        "Nom",
        "final_nom",
        "proposed_nom",
        "suggested_nom",
        "ml_suggested_nom",
    )

    db: Session = SessionLocal()

    try:
        existing = db.get(JobDecisionRecord, decision_id)
        now = datetime.utcnow()

        values = {
            "decision_id": decision_id,
            "job_id": job_id,
            "basicat": basicat,
            "env": _pick(decision, "env"),
            "from_phase": _pick(decision, "from_phase"),
            "action": action,
            "technical_signature": technical_signature,
            "src_ip": _pick(
                decision,
                "src_ip",
                "srcIp",
                "Configured Source",
            ),
            "dst_ip": _pick(
                decision,
                "dst_ip",
                "dstIp",
                "destination_ip",
                "Configured Destination",
            ),
            "port": _pick(decision, "port"),

            "flowMainSG": _pick(
                decision,
                "flowMainSG",
                "flow_main_sg",
            ),
            "flowGrefSG": _pick(
                decision,
                "flowGrefSG",
                "flow_gref_sg",
                "sg_cible",
            ),

            "proposed_flux": proposed_flux,
            "proposed_nom": proposed_nom,

            "final_flux": final_flux,
            "final_nom": final_nom,

            "score": _pick(decision, "score"),

            "ml_modele": _pick(decision, "ml_modele", "model", "model_name"),
            "ml_confiance": _pick(decision, "ml_confiance", "confidence"),
            "seuil_auto": _pick(decision, "seuil_auto", "threshold"),

            "validated": "true" if action in ["validate", "correct"] else "false",

            "payload_json": _safe_json_dumps(decision),
            "updated_at": now,
        }

        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            record = JobDecisionRecord(
                **values,
                created_at=now,
            )
            db.add(record)

        db.commit()
        return decision

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def list_job_decisions(job_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Liste les décisions sauvegardées pour un job.
    """
    db: Session = SessionLocal()

    try:
        records = (
            db.query(JobDecisionRecord)
            .filter(JobDecisionRecord.job_id == job_id)
            .order_by(JobDecisionRecord.updated_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "decision_id": r.decision_id,
                "job_id": r.job_id,
                "basicat": r.basicat,
                "env": r.env,
                "from_phase": r.from_phase,
                "action": r.action,
                "src_ip": r.src_ip,
                "dst_ip": r.dst_ip,
                "port": r.port,
                "flowMainSG": r.flowMainSG,
                "flowGrefSG": r.flowGrefSG,
                "proposed_flux": r.proposed_flux,
                "proposed_nom": r.proposed_nom,
                "final_flux": r.final_flux,
                "final_nom": r.final_nom,
                "score": r.score,
                "ml_modele": r.ml_modele,
                "ml_confiance": r.ml_confiance,
                "seuil_auto": r.seuil_auto,
                "validated": r.validated,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            }
            for r in records
        ]

    finally:
        db.close()


def list_all_decisions(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Liste les dernières décisions tous jobs confondus.
    Utile plus tard pour ML/RAG.
    """
    db: Session = SessionLocal()

    try:
        records = (
            db.query(JobDecisionRecord)
            .order_by(JobDecisionRecord.updated_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "decision_id": r.decision_id,
                "job_id": r.job_id,
                "basicat": r.basicat,
                "env": r.env,
                "from_phase": r.from_phase,
                "action": r.action,
                "src_ip": r.src_ip,
                "dst_ip": r.dst_ip,
                "port": r.port,
                "flowMainSG": r.flowMainSG,
                "flowGrefSG": r.flowGrefSG,
                "proposed_flux": r.proposed_flux,
                "proposed_nom": r.proposed_nom,
                "final_flux": r.final_flux,
                "final_nom": r.final_nom,
                "score": r.score,
                "ml_modele": r.ml_modele,
                "ml_confiance": r.ml_confiance,
                "seuil_auto": r.seuil_auto,
                "validated": r.validated,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            }
            for r in records
        ]

    finally:
        db.close()


def get_training_decisions(limit: int = 5000) -> List[Dict[str, Any]]:
    """
    Retourne uniquement les décisions validées/corrigées utilisables pour entraîner le ML.

    Le ML doit apprendre uniquement depuis les décisions humaines validées.
    """
    db: Session = SessionLocal()

    try:
        records = (
            db.query(JobDecisionRecord)
            .filter(JobDecisionRecord.validated == "true")
            .filter(JobDecisionRecord.final_flux.isnot(None))
            .filter(JobDecisionRecord.final_nom.isnot(None))
            .order_by(JobDecisionRecord.updated_at.desc())
            .limit(limit)
            .all()
        )

        rows = []

        for r in records:
            final_flux = str(r.final_flux or "").strip()
            final_nom = str(r.final_nom or "").strip()

            if not final_flux or not final_nom:
                continue

            rows.append(
                {
                    "decision_id": r.decision_id,
                    "job_id": r.job_id,
                    "basicat": r.basicat,
                    "env": r.env or "",
                    "from_phase": r.from_phase or "",
                    "protocol": "",
                    "src_ip": r.src_ip or "",
                    "dst_ip": r.dst_ip or "",
                    "port": r.port or "",
                    "flowMainSG": r.flowMainSG or "",
                    "flowGrefSG": r.flowGrefSG or "",
                    "flux": final_flux,
                    "Nom": final_nom,
                    "score": r.score or "",
                    "ml_modele": r.ml_modele or "",
                    "ml_confiance": r.ml_confiance or "",
                    "seuil_auto": r.seuil_auto or "",
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                    "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                }
            )

        return rows

    finally:
        db.close()


# =========================
# MODEL VERSIONS / MLOPS
# =========================
def save_model_version(training_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sauvegarde une version de modèle ML dans MySQL.
    """
    if not training_result:
        raise ValueError("Résultat d'entraînement vide")
    ensure_model_versions_schema()
    import uuid

    info = training_result.get("info") or {}

    model_id = str(training_result.get("model_id") or f"model_{uuid.uuid4()}")
    model_name = str(training_result.get("model_name") or "RandomForest")

    model_path = str(info.get("model_path") or training_result.get("model_path") or "")
    metrics_path = str(info.get("metrics_path") or training_result.get("metrics_path") or "")

    metrics = info.get("metrics") or training_result.get("metrics") or {}

    record_payload = dict(training_result)
    record_payload["model_id"] = model_id
    record_payload["model_name"] = model_name

    db: Session = SessionLocal()

    try:
        existing = db.get(ModelVersionRecord, model_id)

        values = {
            "model_id": model_id,
            "model_name": model_name,
            "source": str(training_result.get("source") or ""),
            "model_path": model_path,
            "metrics_path": metrics_path,
            "training_rows": _to_int(training_result.get("training_rows")),
            "excel_rows": _to_int(training_result.get("excel_rows")),
            "mysql_rows": _to_int(training_result.get("mysql_rows")),
            "n_classes": _to_int(
                info.get("n_classes")
                or training_result.get("n_classes")
                or training_result.get("flux_classes")
            ),
            "accuracy": _to_float(metrics.get("accuracy") or info.get("accuracy")),
            "precision": _to_float(metrics.get("precision") or info.get("precision")),
            "recall": _to_float(metrics.get("recall") or info.get("recall")),
            "f1_score": _to_float(
                metrics.get("f1_score")
                or metrics.get("f1")
                or info.get("f1_score")
                or info.get("f1")
            ),
            "is_active": str(training_result.get("is_active") or "false"),
            "payload_json": _safe_json_dumps(record_payload),
        }

        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            record = ModelVersionRecord(
                **values,
                created_at=datetime.utcnow(),
            )
            db.add(record)

        db.commit()

        return record_payload

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def list_model_versions(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Liste les versions de modèles entraînées.
    """
    ensure_model_versions_schema()
    db: Session = SessionLocal()

    try:
        records = (
            db.query(ModelVersionRecord)
            .order_by(ModelVersionRecord.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "model_id": r.model_id,
                "model_name": r.model_name,
                "source": r.source,
                "model_path": r.model_path,
                "metrics_path": r.metrics_path,
                "training_rows": r.training_rows,
                "excel_rows": r.excel_rows,
                "mysql_rows": r.mysql_rows,
                "n_classes": r.n_classes,
                "accuracy": r.accuracy,
                "precision": r.precision,
                "recall": r.recall,
                "f1_score": r.f1_score,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ]

    finally:
        db.close()



def promote_model_version(model_id: str) -> Dict[str, Any]:
    """
    Promeut une version de modèle comme modèle actif.

    Règle:
    - un seul modèle actif à la fois
    - tous les autres modèles deviennent inactifs
    """
    ensure_model_versions_schema()

    model_id = str(model_id or "").strip()

    if not model_id:
        raise ValueError("model_id manquant")

    db: Session = SessionLocal()

    try:
        target = db.get(ModelVersionRecord, model_id)

        if not target:
            raise ValueError(f"Modèle introuvable: {model_id}")

        records = db.query(ModelVersionRecord).all()

        for record in records:
            record.is_active = "true" if record.model_id == model_id else "false"

        db.commit()

        return {
            "model_id": target.model_id,
            "model_name": target.model_name,
            "source": target.source,
            "model_path": target.model_path,
            "metrics_path": target.metrics_path,
            "training_rows": target.training_rows,
            "excel_rows": target.excel_rows,
            "mysql_rows": target.mysql_rows,
            "n_classes": target.n_classes,
            "accuracy": target.accuracy,
            "precision": target.precision,
            "recall": target.recall,
            "f1_score": target.f1_score,
            "is_active": target.is_active,
            "created_at": target.created_at.isoformat() if target.created_at else "",
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_active_model_version() -> Dict[str, Any] | None:
    """
    Retourne le modèle actuellement actif.
    """
    ensure_model_versions_schema()

    db: Session = SessionLocal()

    try:
        record = (
            db.query(ModelVersionRecord)
            .filter(ModelVersionRecord.is_active == "true")
            .order_by(ModelVersionRecord.created_at.desc())
            .first()
        )

        if not record:
            return None

        return {
            "model_id": record.model_id,
            "model_name": record.model_name,
            "source": record.source,
            "model_path": record.model_path,
            "metrics_path": record.metrics_path,
            "training_rows": record.training_rows,
            "excel_rows": record.excel_rows,
            "mysql_rows": record.mysql_rows,
            "n_classes": record.n_classes,
            "accuracy": record.accuracy,
            "precision": record.precision,
            "recall": record.recall,
            "f1_score": record.f1_score,
            "is_active": record.is_active,
            "created_at": record.created_at.isoformat() if record.created_at else "",
        }

    finally:
        db.close()
def get_decision_stats() -> Dict[str, Any]:
    """
    Calcule des statistiques MLOps à partir des décisions sauvegardées.

    Objectif:
    - suivre les validations humaines
    - mesurer l'acceptation des suggestions ML
    - mesurer les corrections
    - suivre la confiance moyenne du ML
    - suivre la répartition des flux finaux
    """
    db: Session = SessionLocal()

    try:
        records = db.query(JobDecisionRecord).all()

        total_decisions = len(records)

        if total_decisions == 0:
            return {
                "total_decisions": 0,
                "validated_decisions": 0,
                "corrected_decisions": 0,
                "ml_decisions": 0,
                "ml_accepted": 0,
                "ml_corrected": 0,
                "ml_acceptance_rate": 0,
                "ml_correction_rate": 0,
                "average_ml_confidence": 0,
                "final_flux_distribution": {},
                "actions_distribution": {},
            }

        validated_decisions = 0
        corrected_decisions = 0

        ml_decisions = 0
        ml_accepted = 0
        ml_corrected = 0

        ml_confidences = []

        final_flux_distribution = {}
        actions_distribution = {}

        for r in records:
            action = str(r.action or "").strip().lower()
            final_flux = str(r.final_flux or "").strip()
            ml_modele = str(r.ml_modele or "").strip()
            ml_confiance = str(r.ml_confiance or "").strip()

            if action in ["validate", "validated"]:
                validated_decisions += 1

            if action in ["correct", "corrected"]:
                corrected_decisions += 1

            if action:
                actions_distribution[action] = actions_distribution.get(action, 0) + 1

            if final_flux:
                final_flux_distribution[final_flux] = (
                    final_flux_distribution.get(final_flux, 0) + 1
                )

            # Décision liée au ML si modèle ou confiance présente
            is_ml_decision = bool(ml_modele or ml_confiance)

            if is_ml_decision:
                ml_decisions += 1

                if action in ["validate", "validated"]:
                    ml_accepted += 1

                if action in ["correct", "corrected"]:
                    ml_corrected += 1

                try:
                    if ml_confiance:
                        ml_confidences.append(float(ml_confiance))
                except Exception:
                    pass

        ml_acceptance_rate = (
            round((ml_accepted / ml_decisions) * 100, 2)
            if ml_decisions > 0
            else 0
        )

        ml_correction_rate = (
            round((ml_corrected / ml_decisions) * 100, 2)
            if ml_decisions > 0
            else 0
        )

        average_ml_confidence = (
            round(sum(ml_confidences) / len(ml_confidences), 4)
            if ml_confidences
            else 0
        )

        return {
            "total_decisions": total_decisions,
            "validated_decisions": validated_decisions,
            "corrected_decisions": corrected_decisions,
            "ml_decisions": ml_decisions,
            "ml_accepted": ml_accepted,
            "ml_corrected": ml_corrected,
            "ml_acceptance_rate": ml_acceptance_rate,
            "ml_correction_rate": ml_correction_rate,
            "average_ml_confidence": average_ml_confidence,
            "final_flux_distribution": final_flux_distribution,
            "actions_distribution": actions_distribution,
        }

    finally:
        db.close()       
def find_previous_decision_by_signature(
    basicat: str,
    env: str,
    protocol: str,
    port: str,
    src_ip: str,
    dst_ip: str,
    flowMainSG: str,
    flowGrefSG: str,
    direction: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrouve la dernière décision validée/corrigée pour une ligne technique identique.

    Sert à reconnaître une ligne déjà traitée lorsqu'on relance le même BASICAT.
    """
    signature = build_decision_signature(
        basicat=basicat,
        env=env,
        protocol=protocol,
        port=port,
        src_ip=src_ip,
        dst_ip=dst_ip,
        flowMainSG=flowMainSG,
        flowGrefSG=flowGrefSG,
        direction=direction,
    )

    db: Session = SessionLocal()

    try:
        record = (
            db.query(JobDecisionRecord)
            .filter(JobDecisionRecord.technical_signature == signature)
            .filter(JobDecisionRecord.validated == "true")
            .order_by(JobDecisionRecord.updated_at.desc())
            .first()
        )

        if not record:
            return None

        return {
            "decision_id": record.decision_id,
            "job_id": record.job_id,
            "basicat": record.basicat,
            "env": record.env,
            "from_phase": record.from_phase,
            "action": record.action,
            "technical_signature": record.technical_signature,
            "src_ip": record.src_ip,
            "dst_ip": record.dst_ip,
            "port": record.port,
            "flowMainSG": record.flowMainSG,
            "flowGrefSG": record.flowGrefSG,
            "proposed_flux": record.proposed_flux,
            "proposed_nom": record.proposed_nom,
            "final_flux": record.final_flux,
            "final_nom": record.final_nom,
            "score": record.score,
            "ml_modele": record.ml_modele,
            "ml_confiance": record.ml_confiance,
            "seuil_auto": record.seuil_auto,
            "validated": record.validated,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "updated_at": record.updated_at.isoformat() if record.updated_at else "",
        }

    finally:
        db.close()        
def find_previous_decision_loose(
    basicat: str,
    env: str,
    src_ip: str,
    flowMainSG: str,
) -> Optional[Dict[str, Any]]:
    """
    Recherche souple pour retrouver une ancienne décision FR.

    Utilisée quand la signature complète ne matche pas parce que
    port / dst_ip / flowGrefSG ne sont pas encore connus au moment du FR.
    """
    db: Session = SessionLocal()

    try:
        records = (
            db.query(JobDecisionRecord)
            .filter(JobDecisionRecord.basicat == str(basicat or "").strip())
            .filter(JobDecisionRecord.env == str(env or "").strip())
            .filter(JobDecisionRecord.validated == "true")
            .filter(JobDecisionRecord.src_ip == str(src_ip or "").strip())
            .filter(JobDecisionRecord.flowMainSG == str(flowMainSG or "").strip())
            .order_by(JobDecisionRecord.updated_at.desc())
            .all()
        )

        if not records:
            return None

        # On prend la dernière décision validée.
        record = records[0]

        return {
            "decision_id": record.decision_id,
            "job_id": record.job_id,
            "basicat": record.basicat,
            "env": record.env,
            "from_phase": record.from_phase,
            "action": record.action,
            "technical_signature": record.technical_signature,
            "src_ip": record.src_ip,
            "dst_ip": record.dst_ip,
            "port": record.port,
            "flowMainSG": record.flowMainSG,
            "flowGrefSG": record.flowGrefSG,
            "proposed_flux": record.proposed_flux,
            "proposed_nom": record.proposed_nom,
            "final_flux": record.final_flux,
            "final_nom": record.final_nom,
            "score": record.score,
            "ml_modele": record.ml_modele,
            "ml_confiance": record.ml_confiance,
            "seuil_auto": record.seuil_auto,
            "validated": record.validated,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "updated_at": record.updated_at.isoformat() if record.updated_at else "",
        }

    finally:
        db.close()        
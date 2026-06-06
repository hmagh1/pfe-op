from pathlib import Path

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import FileResponse

from app.core.config import OUTPUT_DIR
from app.schemas.maf import RunMafRequest, DecisionPayload
from app.services.storage_service import save_job_upload, list_output_files
from app.services.maf_engine import (
    create_job,
    run_job,
    run_fr_job,
    run_snif_job,
    finalize_maf_job,
    submit_decision,
    get_job,
    reset_jobs,
    complete_snif_env_review,
)
from app.services.job_store import (
    list_jobs,
    list_job_decisions,
    get_training_decisions,
    save_model_version,
    list_model_versions,
    get_decision_stats,
)
from app.services import llm_service, ml_service, maf_core
from app.services.precheck_service import precheck_basicat

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


# =========================
# Jobs
# =========================
@router.get("/jobs")
def list_maf_jobs():
    return {"jobs": list_jobs()}


@router.post("/jobs")
def create_maf_job(payload: RunMafRequest):
    try:
        return create_job(payload.basicat)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/reset-jobs")
def reset_maf_jobs():
    return reset_jobs()


@router.post("/jobs/{job_id}/run")
def run_maf_job(job_id: str):
    try:
        return run_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/run-fr")
def run_fr(job_id: str):
    try:
        return run_fr_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/run-snif")
def run_snif(job_id: str):
    try:
        return run_snif_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/run-snif/{env_name}")
def run_snif_env(job_id: str, env_name: str):
    try:
        return run_snif_job(job_id, env_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/finalize-maf")
def finalize_maf(job_id: str):
    try:
        return finalize_maf_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}/decisions-history")
def get_job_decisions_history(job_id: str):
    try:
        get_job(job_id)
        return {"decisions": list_job_decisions(job_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/precheck-basicat/{basicat}")
def precheck_basicat_route(basicat: str):
    try:
        return precheck_basicat(basicat)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/jobs/{job_id}")
def get_maf_job(job_id: str):
    try:
        return get_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))



@router.post("/jobs/{job_id}/decisions")
def decide(job_id: str, payload: DecisionPayload):
    try:
        return submit_decision(job_id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/skip-snif/{env_name}")
def skip_snif(job_id: str, env_name: str):
    try:
        from app.services import maf_engine

        return maf_engine.skip_snif_env(job_id, env_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/complete-snif-review/{env_name}")
def complete_snif_review(job_id: str, env_name: str):
    try:
        return complete_snif_env_review(job_id, env_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Upload SNIF par job
# =========================
@router.post("/jobs/{job_id}/upload/snif/prod")
def upload_snif_prod(job_id: str, file: UploadFile = File(...)):
    try:
        job = get_job(job_id)
        basicat = job.get("basicat")

        if not basicat:
            raise ValueError("BASICAT introuvable pour ce job")

        path = save_job_upload(
            file=file,
            job_id=job_id,
            basicat=basicat,
            target_name="SNIF_prod.xlsx",
        )

        job.setdefault("uploaded_files", {})
        job["uploaded_files"]["prod"] = str(path)

        from app.services.job_store import save_job

        save_job(job)

        return {
            "message": "SNIF prod uploaded",
            "job_id": job_id,
            "basicat": basicat,
            "path": str(path),
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/upload/snif/horsprod")
def upload_snif_horsprod(job_id: str, file: UploadFile = File(...)):
    try:
        job = get_job(job_id)
        basicat = job.get("basicat")

        if not basicat:
            raise ValueError("BASICAT introuvable pour ce job")

        path = save_job_upload(
            file=file,
            job_id=job_id,
            basicat=basicat,
            target_name="SNIF_horsprod.xlsx",
        )

        job.setdefault("uploaded_files", {})
        job["uploaded_files"]["horsprod"] = str(path)

        from app.services.job_store import save_job

        save_job(job)

        return {
            "message": "SNIF horsprod uploaded",
            "job_id": job_id,
            "basicat": basicat,
            "path": str(path),
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =========================
# SNIF Preview
# =========================
@router.get("/jobs/{job_id}/snif-preview/{env_name}")
def snif_preview(job_id: str, env_name: str):
    try:
        job = get_job(job_id)
        basicat = job.get("basicat")

        if not basicat:
            raise ValueError("Job basicat introuvable")

        preview = maf_core.generate_applications_ip_preview(basicat, env_name)
        return preview

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Outputs
# =========================
@router.get("/outputs")
def outputs():
    return {"files": list_output_files()}


@router.get("/download/{file_path:path}")
def download(file_path: str):
    target = OUTPUT_DIR / file_path

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(target, filename=target.name)


# =========================
# LLM
# =========================
@router.post("/llm")
def llm(prompt: dict = Body(...)):
    text = prompt.get("prompt") if isinstance(prompt, dict) else None

    if not text:
        raise HTTPException(status_code=400, detail="Missing 'prompt' in body")

    try:
        out = llm_service.generate(text)
        return {"text": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# ML / MLOps
# =========================
@router.get("/ml/training-data")
def ml_training_data():
    try:
        rows = get_training_decisions()
        return {
            "count": len(rows),
            "rows": rows,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/model-versions")
def ml_model_versions():
    try:
        return {"models": list_model_versions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/decision-stats")
def ml_decision_stats():
    try:
        return get_decision_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/train")
def ml_train():
    try:
        required_columns = [
            "protocol",
            "src_ip",
            "dst_ip",
            "port",
            "flowMainSG",
            "flowGrefSG",
            "flux",
            "Nom",
        ]

        frames = []

        data_path = Path(__file__).parent.parent.parent / "data" / "bdd_flux_maf.xlsx"
        excel_rows = 0

        if data_path.exists():
            df_excel = pd.read_excel(data_path, dtype=str).fillna("")
            df_excel.columns = [str(c).strip() for c in df_excel.columns]

            for col in required_columns:
                if col not in df_excel.columns:
                    df_excel[col] = ""

            df_excel = df_excel[required_columns].fillna("").astype(str)
            excel_rows = len(df_excel)
            frames.append(df_excel)

        rows = get_training_decisions()
        mysql_rows = len(rows) if rows else 0

        if rows:
            df_mysql = pd.DataFrame(rows).fillna("")
            df_mysql.columns = [str(c).strip() for c in df_mysql.columns]

            for col in required_columns:
                if col not in df_mysql.columns:
                    df_mysql[col] = ""

            df_mysql = df_mysql[required_columns].fillna("").astype(str)
            frames.append(df_mysql)

        if not frames:
            raise ValueError(
                "Aucune donnée disponible pour entraîner le modèle: ni BDD Excel ni décisions MySQL."
            )

        df_train = pd.concat(frames, ignore_index=True)

        for col in required_columns:
            df_train[col] = df_train[col].astype(str).fillna("").str.strip()

        df_train = df_train[
            (df_train["flux"] != "") &
            (df_train["Nom"] != "")
        ].copy()

        if df_train.empty:
            raise ValueError(
                "Les données trouvées ne contiennent aucune ligne exploitable avec flux et Nom."
            )

        df_train = df_train.drop_duplicates().reset_index(drop=True)

        flux_classes = df_train["flux"].nunique()
        nom_classes = df_train["Nom"].nunique()

        if len(df_train) < 5:
            raise ValueError(
                f"Pas assez de lignes pour entraîner le modèle. "
                f"Lignes disponibles: {len(df_train)}. "
                f"Excel: {excel_rows}, MySQL: {mysql_rows}."
            )

        if flux_classes < 2:
            raise ValueError(
                f"Impossible d'entraîner le modèle: une seule classe flux trouvée. "
                f"Classes flux: {df_train['flux'].unique().tolist()}. "
                f"Lignes: {len(df_train)}."
            )

        info = ml_service.train_from_dataframe(df_train)

        training_result = {
            "status": "trained",
            "source": "excel_bdd_flux_maf + mysql_job_decisions",
            "training_rows": len(df_train),
            "excel_rows": excel_rows,
            "mysql_rows": mysql_rows,
            "flux_classes": flux_classes,
            "nom_classes": nom_classes,
            "columns": required_columns,
            "info": info,
        }

        saved_version = save_model_version(training_result)

        training_result["model_id"] = saved_version.get("model_id")
        training_result["model_name"] = saved_version.get("model_name")

        return training_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/predict")
def ml_predict(payload: dict = Body(...)):
    rows = payload.get("rows")

    if not rows or not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="Provide 'rows' as list of objects")

    try:
        df = pd.DataFrame(rows)
        preds = ml_service.predict(df)
        return {"predictions": preds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
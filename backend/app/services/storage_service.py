from pathlib import Path
from fastapi import UploadFile
import shutil

from app.core.config import UPLOAD_DIR, OUTPUT_DIR


def safe_folder_name(value: str) -> str:
    """
    Nettoie un nom pour l'utiliser dans un dossier.
    """
    value = str(value or "").strip().upper()
    invalid = '<>:"/\\|?* '

    cleaned = "".join("_" if c in invalid else c for c in value)
    return cleaned or "JOB"


def get_job_upload_dir(job_id: str, basicat: str | None = None) -> Path:
    """
    Retourne le dossier upload propre au job.

    Format:
    uploads/<BASICAT>_<JOB_ID_COURT>/

    Exemple:
    uploads/BI_2ce0ae97/
    """
    short_id = str(job_id or "").strip()[:8]

    if basicat:
        folder_name = f"{safe_folder_name(basicat)}_{short_id}"
    else:
        folder_name = short_id

    target_dir = UPLOAD_DIR / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    return target_dir


def save_upload(file: UploadFile, target_name: str) -> Path:
    """
    Ancienne fonction conservée pour compatibilité.
    Sauvegarde dans backend/uploads directement.
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    target = UPLOAD_DIR / target_name

    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return target


def save_job_upload(
    file: UploadFile,
    job_id: str,
    basicat: str,
    target_name: str,
) -> Path:
    """
    Sauvegarde un fichier uploadé dans un dossier propre au job.

    Exemple:
    uploads/BI_2ce0ae97/SNIF_prod.xlsx
    """
    job_upload_dir = get_job_upload_dir(job_id, basicat)

    target = job_upload_dir / target_name

    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return target


def list_output_files() -> list[dict]:
    """
    Liste tous les fichiers générés dans backend/outputs.
    """
    files = []

    for path in OUTPUT_DIR.rglob("*"):
        if path.is_file():
            files.append({
                "name": path.name,
                "path": str(path.relative_to(OUTPUT_DIR)),
            })

    return files
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"

VMLISTE_FILE = DATA_DIR / "vmliste_remplie.xlsx"
BDD_FILE = DATA_DIR / "bdd_flux_maf.xlsx"

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
BDD_BACKUP_DIR = BASE_DIR / "bdd_backups"

for folder in [UPLOAD_DIR, OUTPUT_DIR, BDD_BACKUP_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


# =========================
# DATABASE CONFIG
# =========================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "maf_db")
DB_USER = os.getenv("DB_USER", "maf_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "maf_password")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)
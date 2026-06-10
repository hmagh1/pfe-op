from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from app.services import ml_service
from app.services.job_store import list_model_versions, list_all_decisions


DATA_DIR = Path(__file__).parent.parent.parent / "data"
VLISTE_FILE = DATA_DIR / "vmliste_remplie.xlsx"
BDD_FILE = DATA_DIR / "bdd_flux_maf.xlsx"


REQUIRED_VLISTE_COLUMNS = [
    "BASICAT",
    "PRODUCTION",
    "SGIC",
    "NAME",
    "IP",
]

REQUIRED_BDD_COLUMNS = [
    "protocol",
    "port",
    "src_ip",
    "dst_ip",
    "flowMainSG",
    "flowGrefSG",
    "flux",
    "Nom",
]


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


def _check_required_columns(df: pd.DataFrame, required: List[str]) -> Dict[str, Any]:
    found = []
    missing = []

    for col in required:
        actual = _find_column(df, col)
        if actual:
            found.append(actual)
        else:
            missing.append(col)

    return {
        "found": found,
        "missing": missing,
        "ok": len(missing) == 0,
    }


def _detect_envs(df_vmliste: pd.DataFrame, basicat_col: str, basicat: str) -> List[str]:
    """
    Détecte les environnements disponibles pour un BASICAT.

    Règle métier retenue :
    - Si PRODUCTION = X / PROD / PRODUCTION / OUI / YES / TRUE / 1 => prod
    - Si PRODUCTION est vide ou indique hors production => horsprod
    - On ne se base pas sur UTILISATION, car certaines lignes peuvent contenir
      'preproduction' même lorsque PRODUCTION = X.
    """

    rows = df_vmliste[
        df_vmliste[basicat_col].astype(str).str.strip().str.upper()
        == str(basicat).strip().upper()
    ]

    if rows.empty:
        return []

    envs = set()

    prod_col = _find_column(df_vmliste, "PRODUCTION")

    if not prod_col:
        envs.add("prod")
    else:
        prod_values = {
            "X",
            "PROD",
            "PRODUCTION",
            "OUI",
            "YES",
            "Y",
            "TRUE",
            "1",
        }

        horsprod_values = {
            "",
            "N",
            "NO",
            "NON",
            "FALSE",
            "0",
            "HORS_PROD",
            "HORSPROD",
            "HORS PROD",
            "HORS-PROD",
            "DEV",
            "TEST",
            "RECETTE",
            "QUALIF",
            "QUALIFICATION",
            "UAT",
            "PREPROD",
            "PRE PROD",
            "PRE-PROD",
        }

        for _, row in rows.iterrows():
            production_value = str(row.get(prod_col, "") or "").strip().upper()

            if production_value in prod_values:
                envs.add("prod")
            elif production_value in horsprod_values:
                envs.add("horsprod")
            else:
                # Si la valeur est inconnue, on ne force pas prod/horsprod.
                # On laisse la sécurité plus bas décider.
                continue

    if not envs:
        envs.add("prod")

    ordered_envs = []

    if "prod" in envs:
        ordered_envs.append("prod")

    if "horsprod" in envs:
        ordered_envs.append("horsprod")

    return ordered_envs


def precheck_basicat(basicat: str) -> Dict[str, Any]:
    basicat = str(basicat or "").strip()

    if not basicat:
        return {
            "basicat": basicat,
            "ready": False,
            "status": "failed",
            "detected_envs": [],
            "checks": [],
            "errors": ["BASICAT vide."],
            "warnings": [],
            "summary": {},
        }

    checks = []
    errors = []
    warnings = []

    df_vmliste = None
    basicat_rows = pd.DataFrame()
    detected_envs = []
    model_loaded = False
    model_versions = []
    historical_for_basicat = []

    # =========================
    # 1. Vérifier fichier VLISTE
    # =========================
    if not VLISTE_FILE.exists():
        errors.append(f"Fichier vmliste introuvable: {VLISTE_FILE}")
        return {
            "basicat": basicat,
            "ready": False,
            "status": "failed",
            "detected_envs": [],
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "vmliste_file": str(VLISTE_FILE),
                "bdd_file": str(BDD_FILE),
                "basicat_rows": 0,
                "model_available": False,
                "model_versions_count": 0,
                "historical_decisions_count": 0,
            },
        }

    checks.append(
        {
            "name": "VLISTE file",
            "ok": True,
            "message": "Fichier vmliste_remplie.xlsx disponible.",
        }
    )

    try:
        df_vmliste = pd.read_excel(VLISTE_FILE, dtype=str).fillna("")
        df_vmliste = _normalize_columns(df_vmliste)
    except Exception as e:
        errors.append(f"Impossible de lire vmliste_remplie.xlsx: {e}")
        return {
            "basicat": basicat,
            "ready": False,
            "status": "failed",
            "detected_envs": [],
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "vmliste_file": str(VLISTE_FILE),
                "bdd_file": str(BDD_FILE),
                "basicat_rows": 0,
                "model_available": False,
                "model_versions_count": 0,
                "historical_decisions_count": 0,
            },
        }

    vmliste_columns_check = _check_required_columns(df_vmliste, REQUIRED_VLISTE_COLUMNS)

    checks.append(
        {
            "name": "VLISTE required columns",
            "ok": vmliste_columns_check["ok"],
            "message": "Colonnes obligatoires VLISTE vérifiées.",
            "found": vmliste_columns_check["found"],
            "missing": vmliste_columns_check["missing"],
        }
    )

    if not vmliste_columns_check["ok"]:
        errors.append(
            "Colonnes manquantes dans vmliste_remplie.xlsx: "
            + ", ".join(vmliste_columns_check["missing"])
        )

    basicat_col = _find_column(df_vmliste, "BASICAT")

    if not basicat_col:
        errors.append("Colonne BASICAT introuvable dans vmliste_remplie.xlsx.")
        return {
            "basicat": basicat,
            "ready": False,
            "status": "failed",
            "detected_envs": [],
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "vmliste_file": str(VLISTE_FILE),
                "bdd_file": str(BDD_FILE),
                "basicat_rows": 0,
                "model_available": False,
                "model_versions_count": 0,
                "historical_decisions_count": 0,
            },
        }

    basicat_rows = df_vmliste[
        df_vmliste[basicat_col].astype(str).str.strip().str.upper()
        == basicat.upper()
    ]

    basicat_found = not basicat_rows.empty

    checks.append(
        {
            "name": "BASICAT existence",
            "ok": basicat_found,
            "message": (
                f"BASICAT {basicat} trouvé dans la VLISTE."
                if basicat_found
                else f"BASICAT {basicat} introuvable dans la VLISTE."
            ),
            "rows_found": int(len(basicat_rows)),
        }
    )

    if not basicat_found:
        errors.append(f"BASICAT {basicat} introuvable dans vmliste_remplie.xlsx.")

    detected_envs = _detect_envs(df_vmliste, basicat_col, basicat) if basicat_found else []

    checks.append(
        {
            "name": "Environment detection",
            "ok": len(detected_envs) > 0,
            "message": (
                "Environnement détecté: " + ", ".join(detected_envs)
                if detected_envs
                else "Aucun environnement détecté."
            ),
            "detected_envs": detected_envs,
        }
    )

    if not detected_envs:
        warnings.append("Aucun environnement détecté pour ce BASICAT.")

    # =========================
    # 2. Vérifier BDD flux
    # =========================
    if not BDD_FILE.exists():
        errors.append(f"Fichier BDD introuvable: {BDD_FILE}")
    else:
        checks.append(
            {
                "name": "BDD file",
                "ok": True,
                "message": "Fichier bdd_flux_maf.xlsx disponible.",
            }
        )

        try:
            df_bdd = pd.read_excel(BDD_FILE, dtype=str).fillna("")
            df_bdd = _normalize_columns(df_bdd)

            bdd_columns_check = _check_required_columns(df_bdd, REQUIRED_BDD_COLUMNS)

            checks.append(
                {
                    "name": "BDD required columns",
                    "ok": bdd_columns_check["ok"],
                    "message": "Colonnes obligatoires BDD vérifiées.",
                    "found": bdd_columns_check["found"],
                    "missing": bdd_columns_check["missing"],
                    "rows": int(len(df_bdd)),
                }
            )

            if not bdd_columns_check["ok"]:
                errors.append(
                    "Colonnes manquantes dans bdd_flux_maf.xlsx: "
                    + ", ".join(bdd_columns_check["missing"])
                )

            if len(df_bdd) == 0:
                errors.append("La BDD flux est vide.")

        except Exception as e:
            errors.append(f"Impossible de lire bdd_flux_maf.xlsx: {e}")

    # =========================
    # 3. Vérifier modèle ML
    # =========================
    try:
        model_loaded = ml_service.load_model() is not None
    except Exception:
        model_loaded = False

    try:
        model_versions = list_model_versions(limit=5)
    except Exception:
        model_versions = []

    checks.append(
        {
            "name": "ML model availability",
            "ok": model_loaded,
            "message": (
                "Un modèle ML entraîné est disponible."
                if model_loaded
                else "Aucun modèle ML entraîné disponible. Le système utilisera la BDD/historique."
            ),
            "model_versions_count": len(model_versions),
        }
    )

    if not model_loaded:
        warnings.append("Aucun modèle ML entraîné disponible pour le moment.")

    # =========================
    # 4. Vérifier historique décisions
    # =========================
    try:
        decisions = list_all_decisions(limit=5000)
    except Exception:
        decisions = []

    historical_for_basicat = [
        d for d in decisions
        if str(d.get("basicat") or "").strip().upper() == basicat.upper()
    ]

    checks.append(
        {
            "name": "Historical decisions",
            "ok": True,
            "message": (
                f"{len(historical_for_basicat)} décision(s) historique(s) trouvée(s) pour {basicat}."
                if historical_for_basicat
                else f"Aucune décision historique trouvée pour {basicat}."
            ),
            "historical_decisions_count": len(historical_for_basicat),
        }
    )

    # =========================
    # Résultat final
    # =========================
    ready = len(errors) == 0

    return {
        "basicat": basicat,
        "ready": ready,
        "status": "ready" if ready else "failed",
        "detected_envs": detected_envs,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "vmliste_file": str(VLISTE_FILE),
            "bdd_file": str(BDD_FILE),
            "basicat_rows": int(len(basicat_rows)) if basicat_found else 0,
            "model_available": model_loaded,
            "model_versions_count": len(model_versions),
            "historical_decisions_count": len(historical_for_basicat),
        },
    }
from pathlib import Path
import random
import re
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

VMLISTE_PATH = BASE_DIR / "data" / "vmliste_remplie.xlsx"
OUTPUT_DIR = BASE_DIR / "outputs-snif"

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

MIN_SNIF_ROWS = 8
MAX_SNIF_ROWS = 18


# ============================================================
# COLONNES SNIF À GÉNÉRER
# ============================================================

SNIF_COLUMNS = [
    "name",
    "Traffic Rate (In bps)",
    "Total Traffic (In Bytes)",
    "Destination Security Groups",
    "Source Security Groups",
    "Destination IPSets",
    "Source IPSets",
    "firewall action",
    "Protocol",
    "port.display",
    "Destination IP Address",
    "Source IP Address",
    "Source VM",
    "Destination VM",
    "Commentaire",
    "Application",
    "flux",
    "type",
    "Nom",
]


# ============================================================
# OUTILS
# ============================================================

def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize(value):
    return clean_text(value).upper()


def safe_name(value):
    value = clean_text(value)
    value = re.sub(r"[^A-Za-z0-9_\-]+", "_", value)
    return value.strip("_") or "UNKNOWN"


def find_column(df, expected_name):
    expected = expected_name.upper().strip()

    for col in df.columns:
        if str(col).upper().strip() == expected:
            return col

    return None


def require_columns(df, required):
    missing = []

    for col in required:
        if find_column(df, col) is None:
            missing.append(col)

    if missing:
        raise ValueError(
            f"Colonnes manquantes dans la VMLISTE: {missing}\n"
            f"Colonnes disponibles: {list(df.columns)}"
        )


def is_prod(row):
    production = normalize(row.get("PRODUCTION", ""))
    utilisation = normalize(row.get("UTILISATION", ""))
    domain = normalize(row.get("DOMAIN", ""))
    sgic = normalize(row.get("SGIC", ""))

    prod_values = {
        "X",
        "OUI",
        "YES",
        "TRUE",
        "1",
        "PROD",
        "PRODUCTION",
    }

    if production in prod_values:
        return True

    joined = f"{utilisation} {domain} {sgic}"

    if "PROD" in joined and "HORS" not in joined and "PREPROD" not in joined:
        return True

    return False


def is_horsprod(row):
    utilisation = normalize(row.get("UTILISATION", ""))
    domain = normalize(row.get("DOMAIN", ""))
    sgic = normalize(row.get("SGIC", ""))

    joined = f"{utilisation} {domain} {sgic}"

    horsprod_keywords = [
        "HORS",
        "HORSPROD",
        "HORS PROD",
        "DEV",
        "TEST",
        "RECETTE",
        "QUALIF",
        "QUALIFICATION",
        "UAT",
        "PREPROD",
        "PRE PROD",
        "PRE-PROD",
        "METROLOGIE",
        "MÉTROLOGIE",
    ]

    if any(keyword in joined for keyword in horsprod_keywords):
        return True

    return not is_prod(row)


def detect_envs(df_basicat):
    envs = []

    if not df_basicat[df_basicat.apply(is_prod, axis=1)].empty:
        envs.append("prod")

    if not df_basicat[df_basicat.apply(is_horsprod, axis=1)].empty:
        envs.append("horsprod")

    return envs


def get_env_df(df_basicat, env):
    if env == "prod":
        return df_basicat[df_basicat.apply(is_prod, axis=1)].copy()

    if env == "horsprod":
        return df_basicat[df_basicat.apply(is_horsprod, axis=1)].copy()

    return pd.DataFrame()


def make_ip_cache(df_env):
    """
    Reproduit le résultat que tu veux :
    NAME | IP | IDCARTO
    à partir de la VMLISTE filtrée par BASICAT et environnement.
    """

    name_col = find_column(df_env, "NAME")
    ip_col = find_column(df_env, "IP")
    idcarto_col = find_column(df_env, "IDCARTO")

    result = pd.DataFrame()

    result["NAME"] = df_env[name_col].astype(str).str.strip()
    result["IP"] = df_env[ip_col].astype(str).str.strip()

    if idcarto_col:
        result["IDCARTO"] = df_env[idcarto_col].astype(str).str.strip()
    else:
        result["IDCARTO"] = ""

    result = result.replace("", pd.NA).dropna(subset=["NAME", "IP"])
    result = result.drop_duplicates(subset=["NAME", "IP"])
    result = result.reset_index(drop=True)

    return result


def choose_service():
    services = [
        {
            "protocol": "TCP",
            "port": 80,
            "flux": "client",
            "nom": "HTTP-OPS",
            "dst_sg": "SG_WEB",
        },
        {
            "protocol": "TCP",
            "port": 443,
            "flux": "client",
            "nom": "HTTP-OPS",
            "dst_sg": "SG_APP_API",
        },
        {
            "protocol": "TCP",
            "port": 8080,
            "flux": "service",
            "nom": "API-REST-CRM",
            "dst_sg": "SG_APP_API",
        },
        {
            "protocol": "TCP",
            "port": 8443,
            "flux": "service",
            "nom": "API-REST-GRC",
            "dst_sg": "SG_APP_API",
        },
        {
            "protocol": "TCP",
            "port": 1521,
            "flux": "service",
            "nom": "DB-ORACLE",
            "dst_sg": "SG_DB",
        },
        {
            "protocol": "TCP",
            "port": 3306,
            "flux": "service",
            "nom": "DB-MYSQL",
            "dst_sg": "SG_DB",
        },
        {
            "protocol": "TCP",
            "port": 5432,
            "flux": "service",
            "nom": "DB-POSTGRES",
            "dst_sg": "SG_DB",
        },
        {
            "protocol": "TCP",
            "port": 9200,
            "flux": "service",
            "nom": "Elasticsearch",
            "dst_sg": "SG_LOG",
        },
        {
            "protocol": "UDP",
            "port": 53,
            "flux": "service",
            "nom": "DNS",
            "dst_sg": "SG_DNS",
        },
    ]

    return random.choice(services)


def choose_source_and_destination(ip_cache):
    """
    Le SNIF est généré uniquement à partir des IP filtrées du BASICAT.
    Source et destination viennent du même cache BASICAT/env.
    """

    if len(ip_cache) == 1:
        src = ip_cache.iloc[0]
        dst = ip_cache.iloc[0]
        return src, dst

    selected = ip_cache.sample(
        n=2,
        replace=False,
        random_state=random.randint(1, 999999),
    )

    return selected.iloc[0], selected.iloc[1]


def build_snif_dataframe(basicat, env, ip_cache):
    if ip_cache.empty:
        return pd.DataFrame(columns=SNIF_COLUMNS)

    row_count = random.randint(MIN_SNIF_ROWS, MAX_SNIF_ROWS)

    if len(ip_cache) < row_count:
        row_count = len(ip_cache) if len(ip_cache) >= 3 else MIN_SNIF_ROWS

    rows = []

    for i in range(1, row_count + 1):
        src, dst = choose_source_and_destination(ip_cache)
        service = choose_service()

        src_name = clean_text(src["NAME"])
        src_ip = clean_text(src["IP"])
        src_idcarto = clean_text(src["IDCARTO"])

        dst_name = clean_text(dst["NAME"])
        dst_ip = clean_text(dst["IP"])

        env_upper = env.upper()

        src_sg = f"SGIC-{basicat}-{env_upper}-{i:03d}"

        row = {
            "name": f"{basicat}_{env}_{i:04d}",
            "Traffic Rate (In bps)": random.randint(1000, 90000),
            "Total Traffic (In Bytes)": random.randint(1000000, 500000000),
            "Destination Security Groups": service["dst_sg"],
            "Source Security Groups": src_sg,
            "Destination IPSets": dst_ip,
            "Source IPSets": src_ip,
            "firewall action": "ALLOW",
            "Protocol": service["protocol"],
            "port.display": service["port"],
            "Destination IP Address": dst_ip,
            "Source IP Address": src_ip,
            "Source VM": src_name,
            "Destination VM": dst_name,
            "Commentaire": f"Generated from VMLISTE - BASICAT {basicat} - {env_upper} - IDCARTO {src_idcarto}",
            "Application": basicat,
            "flux": service["flux"],
            "type": "generated",
            "Nom": service["nom"],
        }

        rows.append(row)

    return pd.DataFrame(rows, columns=SNIF_COLUMNS)


def save_excel(df, output_path, sheet_name):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

        ws = writer.sheets[sheet_name]

        for column_cells in ws.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter

            for cell in column_cells:
                value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(value))

            ws.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 38)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 80)
    print("GENERATION SNIF PAR BASICAT DEPUIS VMLISTE")
    print("=" * 80)

    if not VMLISTE_PATH.exists():
        raise FileNotFoundError(f"Fichier VMLISTE introuvable: {VMLISTE_PATH}")

    df_vm = pd.read_excel(VMLISTE_PATH)
    df_vm.columns = [clean_text(c) for c in df_vm.columns]
    df_vm = df_vm.fillna("")

    require_columns(df_vm, ["BASICAT", "NAME", "IP"])

    basicat_col = find_column(df_vm, "BASICAT")

    basicats = (
        df_vm[basicat_col]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

    basicats = sorted([b for b in basicats if clean_text(b)])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"VMLISTE utilisée : {VMLISTE_PATH}")
    print(f"Nombre de BASICAT détectés : {len(basicats)}")
    print(f"Dossier de sortie : {OUTPUT_DIR}")
    print("-" * 80)

    summary = []

    for basicat in basicats:
        df_basicat = df_vm[df_vm[basicat_col].astype(str).str.strip() == basicat].copy()

        envs = detect_envs(df_basicat)

        if not envs:
            print(f"[SKIP] {basicat} : aucun environnement détecté")
            continue

        print(f"[BASICAT] {basicat} -> environnements : {', '.join(envs)}")

        for env in envs:
            df_env = get_env_df(df_basicat, env)
            ip_cache = make_ip_cache(df_env)

            if ip_cache.empty:
                print(f"  - {env}: aucune IP disponible")
                continue

            basicat_dir = OUTPUT_DIR / safe_name(basicat) / env
            basicat_dir.mkdir(parents=True, exist_ok=True)

            # Cache IP filtré du BASICAT/env
            cache_path = basicat_dir / "applications_ip.xlsx"
            save_excel(ip_cache, cache_path, "applications_ip")

            # SNIF généré depuis ce cache IP
            snif_df = build_snif_dataframe(basicat, env, ip_cache)

            snif_filename = "SNIF_prod.xlsx" if env == "prod" else "SNIF_horsprod.xlsx"
            snif_path = basicat_dir / snif_filename

            sheet_name = "SNIF_prod" if env == "prod" else "SNIF_horsprod"
            save_excel(snif_df, snif_path, sheet_name)

            print(f"  - {env}: cache IP = {len(ip_cache)} ligne(s), SNIF = {len(snif_df)} ligne(s)")
            print(f"    cache : {cache_path}")
            print(f"    snif  : {snif_path}")

            summary.append({
                "BASICAT": basicat,
                "ENV": env,
                "IP_CACHE_ROWS": len(ip_cache),
                "SNIF_ROWS": len(snif_df),
                "CACHE_FILE": str(cache_path),
                "SNIF_FILE": str(snif_path),
            })

    summary_df = pd.DataFrame(summary)
    summary_path = OUTPUT_DIR / "generation_summary.xlsx"

    if not summary_df.empty:
        save_excel(summary_df, summary_path, "summary")

    print("-" * 80)
    print(f"Résumé : {summary_path}")
    print("Génération terminée avec succès.")


if __name__ == "__main__":
    main()
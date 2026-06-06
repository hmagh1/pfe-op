import pandas as pd
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _guess_column(df, keywords):
    for col in df.columns:
        name = str(col).lower()
        if all(k.lower() in name for k in keywords):
            return col
    # fallback: return first column containing any keyword
    for col in df.columns:
        name = str(col).lower()
        for k in keywords:
            if k.lower() in name:
                return col
    return None


def analyze_and_suggest(bdd_path: Path, vmlist_path: Path, out_dir: Path):
    bdd_df = pd.read_excel(bdd_path, engine="openpyxl")
    vml_df = pd.read_excel(vmlist_path, engine="openpyxl")

    # heuristics for columns
    bdd_src_col = _guess_column(bdd_df, ["src", "ip"]) or _guess_column(bdd_df, ["adresse", "ip"]) or "src_ip"
    bdd_dst_col = _guess_column(bdd_df, ["dst", "ip"]) or "dst_ip"
    bdd_flowmain_col = _guess_column(bdd_df, ["flowmain", "flow_main", "flowmainsg"]) or _guess_column(bdd_df, ["flowmainsg"]) or "flowMainSG"
    bdd_flowgref_col = _guess_column(bdd_df, ["flowgref", "gref"]) or _guess_column(bdd_df, ["flowgret"]) or "flowGrefSG"

    # vmlist heuristics
    v_src_col = _guess_column(vml_df, ["ip"]) or _guess_column(vml_df, ["adresse"]) or "ip"
    v_flowmain_col = _guess_column(vml_df, ["sg"]) or _guess_column(vml_df, ["flowmain"]) or None

    suggestions = []

    for idx, vrow in vml_df.iterrows():
        vm_src = vrow.get(v_src_col, None) if v_src_col in vml_df.columns else None
        vm_flow = vrow.get(v_flowmain_col, None) if v_flowmain_col and v_flowmain_col in vml_df.columns else None

        # find matches by src ip or flowMainSG
        match_by_ip = False
        match_by_flow = False
        if vm_src and vm_src == vm_src:  # not NaN
            match_by_ip = (bdd_df.astype(str).get(bdd_src_col, "")==str(vm_src)).any()
        if vm_flow and vm_flow == vm_flow:
            match_by_flow = (bdd_df.astype(str).get(bdd_flowmain_col, "")==str(vm_flow)).any()

        if not match_by_ip and not match_by_flow:
            suggestion = {
                "protocol": "",
                "port": "",
                "src_ip": vm_src if vm_src and vm_src==vm_src else "",
                "dst_ip": "",
                "flowMainSG": vm_flow if vm_flow and vm_flow==vm_flow else "",
                "flowGrefSG": "A_COMPLETER",
                "direction": "",
                "flux": "",
                "Nom": vrow.get("Nom", "") if "Nom" in vml_df.columns else "",
            }
            suggestions.append(suggestion)

    out_dir.mkdir(parents=True, exist_ok=True)
    sug_df = pd.DataFrame(suggestions)
    sug_csv = out_dir / "suggested_bdd_rows.csv"
    sug_xlsx = out_dir / "suggested_bdd_rows.xlsx"
    sug_df.to_csv(sug_csv, index=False, encoding="utf-8")
    sug_df.to_excel(sug_xlsx, index=False)

    # create a fixed version by appending suggestions (only if any)
    fixed_path = out_dir / "bdd_flux_maf_fixed.xlsx"
    if not sug_df.empty:
        combined = pd.concat([bdd_df, sug_df], ignore_index=True, sort=False)
        combined.to_excel(fixed_path, index=False)

    return {
        "suggestions_count": len(suggestions),
        "suggestions_csv": str(sug_csv),
        "suggestions_xlsx": str(sug_xlsx),
        "fixed_bdd_xlsx": str(fixed_path) if not sug_df.empty else None,
    }


def main():
    base = DATA_DIR
    bdd_path = base / "bdd_flux_maf.xlsx"
    vml_path = base / "vmliste_remplie.xlsx"
    out_dir = base / "fix_suggestions"

    if not bdd_path.exists() or not vml_path.exists():
        print("Files not found in", base)
        return

    res = analyze_and_suggest(bdd_path, vml_path, out_dir)
    print(res)


if __name__ == "__main__":
    main()

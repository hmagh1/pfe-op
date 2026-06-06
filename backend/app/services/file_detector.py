"""
Détection automatique des fichiers Excel par colonnes.
Mapping automatique des colonnes avec normalisation et scoring.

But : rendre le système indépendant des noms exacts de fichiers et colonnes.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
import unicodedata
import re


def normalize_string(s: str) -> str:
    """
    Normalise une chaîne pour matching de colonnes :
    - minuscules
    - suppression accents
    - suppression caractères spéciaux
    - suppression espaces
    """
    if not s:
        return ""
    s = str(s).strip()
    # Minuscules
    s = s.lower()
    # Suppression accents
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    # Suppression caractères spéciaux, garder alphanumérique + underscore
    s = re.sub(r'[^\w]', '', s)
    return s


def score_column_match(col1: str, col2: str) -> float:
    """
    Score de similarité entre deux noms de colonne (0-100).
    Utilise normalisation + distance partielle.
    """
    norm1 = normalize_string(col1)
    norm2 = normalize_string(col2)
    
    if norm1 == norm2:
        return 100.0
    
    # Matching partiel (substring)
    if norm1 in norm2 or norm2 in norm1:
        return 75.0
    
    # Levenshtein simple
    if len(norm1) == 0 or len(norm2) == 0:
        return 0.0
    
    # Calcul distance (simplifiée)
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio * 100.0


def find_best_column_match(
    target_col: str,
    available_cols: List[str],
    min_score: float = 50.0,
    min_match_score: Optional[float] = None,
) -> Optional[Tuple[str, float]]:
    """
    Cherche la meilleure correspondance pour une colonne cible.
    Retourne (nom_colonne, score) ou None si score < min_score.

    Accepte soit `min_score` soit `min_match_score` pour compatibilité
    avec différents appels dans le code.
    """
    best = None
    # Prioriser la valeur explicite `min_match_score` si fournie
    effective_min = min_match_score if min_match_score is not None else min_score
    best_score = effective_min
    
    for col in available_cols:
        score = score_column_match(target_col, col)
        if score > best_score:
            best_score = score
            best = (col, score)
    
    return best


def detect_file_by_columns(
    data_dir: Path,
    required_columns: List[str],
    min_match_score: float = 70.0,
) -> Optional[Path]:
    """
    Détecte un fichier Excel dans data_dir basé sur ses colonnes.
    
    Args:
        data_dir: répertoire avec fichiers Excel
        required_columns: liste de colonnes attendues
        min_match_score: score minimum pour matcher une colonne
    
    Returns:
        Chemin du fichier le plus recent matchant, ou None
    """
    if not data_dir.exists():
        return None
    
    candidates = []
    
    for excel_file in sorted(data_dir.glob("*.xlsx")):
        try:
            df = pd.read_excel(excel_file, nrows=1, dtype=str)
            cols = list(df.columns)
            
            # Vérifier combien de colonnes on peut matcher
            matched = 0
            for req in required_columns:
                match = find_best_column_match(req, cols, min_match_score=min_match_score)
                if match:
                    matched += 1
            
            # Si au moins 50% des colonnes matchent, c'est bon
            if matched >= len(required_columns) * 0.5:
                candidates.append((excel_file, matched))
        except Exception as e:
            print(f"Erreur lecture {excel_file}: {e}")
    
    if not candidates:
        return None
    
    # Retourner le fichier avec le plus de matches, puis le plus récent
    candidates.sort(key=lambda x: (-x[1], -x[0].stat().st_mtime))
    return candidates[0][0]


def map_columns(
    df: pd.DataFrame,
    target_columns: List[str],
    min_score: float = 50.0,
) -> Dict[str, str]:
    """
    Mappe les colonnes d'un DataFrame aux colonnes cibles.
    
    Returns:
        Dict {target_col: actual_col_in_df}
    """
    mapping = {}
    used_cols = set()
    
    for target in target_columns:
        match = find_best_column_match(target, list(df.columns), min_score=min_score)
        if match:
            actual_col, score = match
            if actual_col not in used_cols:
                mapping[target] = actual_col
                used_cols.add(actual_col)
                print(f"  {target} → {actual_col} (score: {score:.0f})")
    
    return mapping


def load_file_with_mapping(
    file_path: Path,
    target_columns: List[str],
    min_score: float = 50.0,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Charge un Excel et mappe ses colonnes automatiquement.
    
    Returns:
        (dataframe_avec_colonnes_cibles, mapping)
    """
    print(f"Chargement {file_path.name}...")
    df = pd.read_excel(file_path, dtype=str)
    
    mapping = map_columns(df, target_columns, min_score=min_score)
    
    if not mapping:
        raise ValueError(
            f"Impossible de mapper les colonnes dans {file_path.name}. "
            f"Colonnes attendues: {target_columns}, "
            f"Colonnes trouvées: {list(df.columns)}"
        )
    
    # Renommer les colonnes au format standard
    df = df.rename(columns=mapping)
    
    # Garder seulement les colonnes mappées
    df = df[[col for col in target_columns if col in df.columns]].copy()
    
    return df, mapping


# Signatures de détection (colonnes minimales pour identifier un type de fichier)
VMLISTE_SIGNATURE = ["BASICAT", "PRODUCTION", "SGIC", "NAME", "IP", "IDCARTO"]  # UTILISATION est optionnel mais utile
BDD_SIGNATURE = ["protocol", "port", "src_ip", "dst_ip", "flowMainSG", "flowGrefSG", "direction", "flux", "Nom"]
SNIF_SIGNATURE = ["Name", "Direction", "IP Protocol", "port", "Configured Service", "Configured Source", "Configured Destination"]


def auto_detect_and_load_vmliste(data_dir: Path) -> pd.DataFrame:
    """Détecte et charge vmliste automatiquement."""
    print(f"Détection vmliste dans {data_dir}...")
    file_path = detect_file_by_columns(data_dir, VMLISTE_SIGNATURE, min_match_score=70.0)
    
    if not file_path:
        raise ValueError(
            f"Aucun fichier vmliste détecté dans {data_dir}. "
            f"Colonnes attendues: {VMLISTE_SIGNATURE}"
        )
    
    df, mapping = load_file_with_mapping(file_path, VMLISTE_SIGNATURE, min_score=70.0)
    print(f"✓ Vmliste chargée ({len(df)} lignes)")
    return df


def auto_detect_and_load_bdd(data_dir: Path) -> pd.DataFrame:
    """Détecte et charge BDD automatiquement."""
    print(f"Détection BDD dans {data_dir}...")
    file_path = detect_file_by_columns(data_dir, BDD_SIGNATURE, min_match_score=60.0)
    
    if not file_path:
        raise ValueError(
            f"Aucun fichier BDD détecté dans {data_dir}. "
            f"Colonnes attendues: {BDD_SIGNATURE}"
        )
    
    df, mapping = load_file_with_mapping(file_path, BDD_SIGNATURE, min_score=60.0)
    print(f"✓ BDD chargée ({len(df)} lignes)")
    return df


def auto_detect_snif_signature(file_path: Path) -> Dict[str, str]:
    """Détecte et mappe les colonnes d'un fichier SNIF."""
    print(f"Détection colonnes SNIF dans {file_path.name}...")
    df = pd.read_excel(file_path, nrows=1, dtype=str)
    mapping = map_columns(df, SNIF_SIGNATURE, min_score=50.0)
    
    if not mapping:
        print(f"⚠️  Colonnes SNIF détectées : {list(df.columns)}")
        raise ValueError(
            f"Impossible de mapper les colonnes SNIF. "
            f"Colonnes attendues: {SNIF_SIGNATURE}"
        )
    
    return mapping

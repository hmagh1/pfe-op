#!/usr/bin/env python3
"""
Script de test de détection automatique des fichiers et colonnes.
Lance-le pour vérifier que la détection fonctionne avec tes vrais fichiers.

Usage:
    cd backend
    python test_file_detection.py
"""

from pathlib import Path
from app.services.file_detector import (
    auto_detect_and_load_vmliste,
    auto_detect_and_load_bdd,
    detect_file_by_columns,
    VMLISTE_SIGNATURE,
    BDD_SIGNATURE,
)
from app.core.config import VMLISTE_FILE, BDD_FILE, OUTPUT_DIR


def test_detection():
    print("=" * 80)
    print("TEST : Détection automatique des fichiers et colonnes")
    print("=" * 80)
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"❌ Dossier {data_dir} n'existe pas!")
        return False
    
    print(f"\n📁 Fichiers trouvés dans {data_dir}:")
    for f in sorted(data_dir.glob("*")):
        print(f"   - {f.name}")
    
    # Test 1: Détection vmliste
    print("\n" + "=" * 80)
    print("Test 1 : Détection VMLISTE")
    print("=" * 80)
    try:
        df_vmliste = auto_detect_and_load_vmliste(data_dir)
        print(f"✅ Vmliste détectée : {df_vmliste.shape[0]} lignes, {df_vmliste.shape[1]} colonnes")
        print(f"   Colonnes : {list(df_vmliste.columns)[:5]}...")
    except Exception as e:
        print(f"❌ Erreur vmliste : {e}")
        return False
    
    # Test 2: Détection BDD
    print("\n" + "=" * 80)
    print("Test 2 : Détection BDD")
    print("=" * 80)
    try:
        df_bdd = auto_detect_and_load_bdd(data_dir)
        print(f"✅ BDD détectée : {df_bdd.shape[0]} lignes, {df_bdd.shape[1]} colonnes")
        print(f"   Colonnes : {list(df_bdd.columns)}")
    except Exception as e:
        print(f"❌ Erreur BDD : {e}")
        return False
    
    print("\n" + "=" * 80)
    print("✅ TOUS LES TESTS RÉUSSIS")
    print("=" * 80)
    print("\nLa détection automatique fonctionne avec tes vrais fichiers !")
    print("Tu peux maintenant lancer l'app normalement.")
    return True


if __name__ == "__main__":
    success = test_detection()
    exit(0 if success else 1)

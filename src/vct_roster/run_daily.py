"""
run_daily.py
============
Lance la routine quotidienne complète, dans le bon ordre :

  1. update_rankings.py   -> scrape les stats du jour et ajoute un onglet daté
                              à data/vct.xlsx (colorie déjà les équipes éliminées
                              sur ce nouvel onglet, d'après data/bracket_results.csv).
  2. bracket_status.py    -> recolorie TOUS les onglets de data/vct.xlsx d'après
                              data/bracket_results.csv — utile si tu as ajouté des
                              résultats de matchs sans relancer le scraping entre-temps,
                              pour que les anciens onglets restent cohérents aussi.
                              (Rendu redondant sur le tout nouvel onglet, ce qui est
                              sans effet — mais indispensable pour les précédents.)
  3. compare_rankings.py  -> compare les deux onglets datés les plus récents de
                              data/vct.xlsx et écrit un rapport dans output/.

S'arrête au premier script qui échoue (code de retour non nul) plutôt que de
continuer sur un état incohérent.

Usage :
    python tracker/run_daily.py
    python tracker/run_daily.py --skip-compare
        (ex: tout premier lancement du projet -> un seul onglet daté existe
        encore, compare_rankings.py n'aurait rien à comparer)
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def run_step(script_name: str, label: str) -> None:
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path)]
    print(f"\n{'=' * 60}\n▶ {label} ({script_name})\n{'=' * 60}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n❌ {script_name} a échoué (code {result.returncode}) — arrêt de la routine.")
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Lance update_rankings.py -> bracket_status.py -> compare_rankings.py, dans l'ordre."
    )
    parser.add_argument(
        "--skip-compare",
        action="store_true",
        help="Ne pas lancer compare_rankings.py (ex: un seul onglet daté existe encore, rien à comparer).",
    )
    args = parser.parse_args()

    run_step("update_rankings.py", "1/3 — Classement du jour (scraping + rôles)")
    run_step("bracket_status.py", "2/3 — Mise en rouge des équipes éliminées")
    if not args.skip_compare:
        run_step("compare_rankings.py", "3/3 — Comparaison avec le jour précédent")

    print(f"\n{'=' * 60}\n✅ Routine quotidienne terminée.\n{'=' * 60}")


if __name__ == "__main__":
    main()

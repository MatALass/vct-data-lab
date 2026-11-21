"""
compare_vct_rankings.py
=========================
Compare deux onglets datés de vct.xlsx et explique, joueur par joueur puis équipe
par équipe, ce qui a bougé — dans un fichier Excel séparé dédié.

Usage :
    python compare_vct_rankings.py
        (compare automatiquement les deux onglets les plus récents)
    python compare_vct_rankings.py --before "Classement Playin 08-08" --after "Classement Playin 09-08"
    python compare_vct_rankings.py --output evolution_09-08.xlsx
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_XLSX = PROJECT_ROOT / "data" / "vct.xlsx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

DATE_IN_SHEETNAME = re.compile(r"(\d{2})-(\d{2})\s*$")


def sheet_sort_key(name: str):
    """Essaie d'extraire une date JJ-MM du nom d'onglet pour trier chronologiquement.
    Les onglets sans date reconnaissable sont mis en tout début (les plus anciens)."""
    m = DATE_IN_SHEETNAME.search(name)
    if not m:
        return (0, 0)
    day, month = int(m.group(1)), int(m.group(2))
    return (month, day)


def pick_two_most_recent(xlsx_path: Path):
    xls = pd.ExcelFile(xlsx_path)
    sheets = sorted(xls.sheet_names, key=sheet_sort_key)
    if len(sheets) < 2:
        raise RuntimeError(f"Il faut au moins 2 onglets datés dans {xlsx_path} pour comparer (trouvé {len(sheets)}).")
    return sheets[-2], sheets[-1]


def build_comparison(df_before: pd.DataFrame, df_after: pd.DataFrame) -> tuple:
    merged = df_before.merge(
        df_after, on="player", how="outer", suffixes=("_avant", "_apres"), indicator=True
    )

    rows_players = []
    for _, r in merged.iterrows():
        statut = {"both": "présent aux deux relevés", "left_only": "absent aujourd'hui", "right_only": "nouveau"}[r["_merge"]]

        role_avant = r.get("team_slot_avant")
        role_apres = r.get("team_slot_apres")
        role_change = pd.notna(role_avant) and pd.notna(role_apres) and role_avant != role_apres

        delta_role_rank = None
        if r["_merge"] == "both" and not role_change:
            ca, cb = r.get("Classement Role_avant"), r.get("Classement Role_apres")
            if pd.notna(ca) and pd.notna(cb):
                delta_role_rank = int(cb - ca)  # positif = a reculé (rang plus grand = moins bon)

        commentaire = ""
        if statut == "nouveau":
            commentaire = "Nouveau joueur dans le classement (à vérifier dans roles.csv)."
        elif statut == "absent aujourd'hui":
            commentaire = "N'apparaît plus dans les stats du jour (banc, forfait, ou hors échantillon)."
        elif role_change:
            commentaire = f"Changement de rôle détecté ({role_avant} -> {role_apres}) : comparaison de rang non pertinente."
        elif delta_role_rank is not None and delta_role_rank != 0:
            direction = "recule" if delta_role_rank > 0 else "progresse"
            commentaire = (
                f"{direction.capitalize()} de {abs(delta_role_rank)} place(s) dans le classement "
                f"{r.get('team_slot_apres', r.get('team_slot_avant'))} "
                f"({int(r.get('Classement Role_avant'))}e -> {int(r.get('Classement Role_apres'))}e)."
            )
        elif delta_role_rank == 0:
            commentaire = "Stable."

        rows_players.append({
            "player": r["player"],
            "team_avant": r.get("team_avant"),
            "team_apres": r.get("team_apres"),
            "role_avant": role_avant,
            "role_apres": role_apres,
            "rating_avant": r.get("rating_avant"),
            "rating_apres": r.get("rating_apres"),
            "delta_rating": round(r.get("rating_apres") - r.get("rating_avant"), 3)
            if pd.notna(r.get("rating_avant")) and pd.notna(r.get("rating_apres")) else None,
            "classement_role_avant": r.get("Classement Role_avant"),
            "classement_role_apres": r.get("Classement Role_apres"),
            "delta_classement_role": delta_role_rank,
            "statut": statut,
            "commentaire": commentaire,
        })

    df_players = pd.DataFrame(rows_players)
    df_players = df_players.reindex(
        df_players["delta_classement_role"].abs().sort_values(ascending=False, na_position="last").index
    )

    # --- Bilan équipe ---
    team_before = df_before.drop_duplicates("team")[["team", "Classement équipe"]].rename(
        columns={"Classement équipe": "classement_avant"}
    )
    div_col_before = [c for c in df_before.columns if c.startswith("Divise par")][0]
    team_before["point_moyen_avant"] = df_before.drop_duplicates("team").set_index("team")[div_col_before].values

    team_after = df_after.drop_duplicates("team")[["team", "Classement équipe"]].rename(
        columns={"Classement équipe": "classement_apres"}
    )
    div_col_after = [c for c in df_after.columns if c.startswith("Divise par")][0]
    team_after["point_moyen_apres"] = df_after.drop_duplicates("team").set_index("team")[div_col_after].values

    team_cmp = team_before.merge(team_after, on="team", how="outer")
    team_cmp["delta_classement"] = team_cmp["classement_avant"] - team_cmp["classement_apres"]  # positif = progresse

    def top_contributor(team):
        team_players = df_players[
            (df_players["team_apres"] == team) & df_players["delta_classement_role"].notna()
        ]
        if team_players.empty:
            return None
        idx = team_players["delta_classement_role"].abs().idxmax()
        row = team_players.loc[idx]
        return f"{row['player']} ({row['commentaire']})" if row["commentaire"] else row["player"]

    team_cmp["joueur_qui_explique_le_plus"] = team_cmp["team"].apply(top_contributor)
    team_cmp = team_cmp.sort_values("delta_classement", ascending=False)

    return df_players, team_cmp


def write_output(path: Path, sheet_before: str, sheet_after: str, df_players: pd.DataFrame, team_cmp: pd.DataFrame):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        meta = pd.DataFrame({"info": [f"Comparaison : '{sheet_before}' -> '{sheet_after}'", f"Généré le {datetime.now():%d/%m/%Y %H:%M}"]})
        meta.to_excel(writer, sheet_name="Info", index=False, header=False)

        team_cmp.to_excel(writer, sheet_name="Évolution équipes", index=False)
        df_players.to_excel(writer, sheet_name="Évolution joueurs", index=False)

        for sheet_name in ["Évolution équipes", "Évolution joueurs"]:
            ws = writer.sheets[sheet_name]
            for col_cells in ws.columns:
                length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
                col_letter = get_column_letter(col_cells[0].column)
                ws.column_dimensions[col_letter].width = min(length + 2, 55)
            ws.freeze_panes = "A2"


def main():
    parser = argparse.ArgumentParser(description="Compare deux jours de classement VCT EMEA.")
    parser.add_argument("--file", default=str(DEFAULT_XLSX), help=f"Fichier Excel source (défaut: {DEFAULT_XLSX})")
    parser.add_argument("--before", default=None, help="Nom de l'onglet 'avant' (sinon: avant-dernier onglet daté)")
    parser.add_argument("--after", default=None, help="Nom de l'onglet 'après' (sinon: dernier onglet daté)")
    parser.add_argument("--output", default=None, help=f"Fichier de sortie (défaut: {DEFAULT_OUTPUT_DIR}/evolution_JJ-MM.xlsx)")
    args = parser.parse_args()

    xlsx_path = Path(args.file)

    if args.before and args.after:
        sheet_before, sheet_after = args.before, args.after
    else:
        sheet_before, sheet_after = pick_two_most_recent(xlsx_path)

    print(f"Comparaison : '{sheet_before}' -> '{sheet_after}'")

    df_before = pd.read_excel(xlsx_path, sheet_name=sheet_before)
    df_after = pd.read_excel(xlsx_path, sheet_name=sheet_after)

    df_players, team_cmp = build_comparison(df_before, df_after)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"evolution_{datetime.now():%d-%m}.xlsx"
    write_output(output_path, sheet_before, sheet_after, df_players, team_cmp)

    print(f"\n✅ Fichier de comparaison écrit : {output_path.resolve()}")
    print("\n=== Plus gros mouvements d'équipe ===")
    print(team_cmp[["team", "classement_avant", "classement_apres", "delta_classement", "joueur_qui_explique_le_plus"]].to_string(index=False))


if __name__ == "__main__":
    main()

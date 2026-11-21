"""
bracket_status.py
==================
Détermine automatiquement quelles équipes sont éliminées du Play-In et/ou des
Playoffs, à partir de data/bracket_results.csv (résultats de matchs saisis au
fur et à mesure du tournoi), puis colore en rouge les lignes correspondantes
dans data/vct.xlsx.

RÈGLE D'ÉLIMINATION (double élimination, celle utilisée par la VCT)
---------------------------------------------------------------------
Une équipe est éliminée dès qu'elle PERD un match joué dans le lower bracket
("bracket_side" = Lower). Une défaite dans l'upper bracket ne fait que la
faire descendre en lower bracket : elle continue de jouer, elle n'est donc
PAS encore éliminée à ce stade.

    Upper bracket, défaite  -> l'équipe descend en Lower bracket (pas éliminée)
    Lower bracket, défaite  -> l'équipe est ÉLIMINÉE

Le Play-In et les Playoffs sont deux brackets indépendants : une équipe
éliminée du Play-In ne l'est pas "par défaut" des Playoffs (si jamais un
format futur permettait malgré tout d'y accéder), et inversement une équipe
qui rate les Playoffs après le Play-In n'a simplement aucune ligne dans les
matchs "Playoffs" -> elle n'est pas coloriée sur ces onglets-là (colonne non
pertinente pour elle).

data/bracket_results.csv (à compléter à la main au fil des matchs, une ligne
par match JOUÉ, dans l'ordre chronologique) :

    stage,round,bracket_side,team_a,team_b,winner
    Playin,Upper Round 1,Upper,GX,EF,GX
    Playin,Upper Quarterfinal,Upper,FUT,GX,FUT
    Playin,Lower Round 1,Lower,EF,M8,EF
    Playin,Lower Round 2,Lower,EF,GX,GX
    ...

Colonnes :
    stage        "Playin" ou "Playoffs" — doit correspondre au mot présent
                 dans le nom de l'onglet (ex. "Classement Playin 13-08").
    round        Libre, juste pour la lisibilité humaine (non utilisé par le
                 calcul).
    bracket_side "Upper" ou "Lower" — bracket dans lequel CE match a été joué.
    team_a/team_b Tags d'équipe identiques à la colonne "team" de vct.xlsx
                 (ex: GX, VIT, KC, NAVI...).
    winner       Tag de l'équipe gagnante — doit être égal à team_a ou team_b.

Ce module est appelé automatiquement par tracker/update_rankings.py à chaque
écriture d'onglet (les nouveaux onglets sont donc coloriés dès leur création).
Il peut aussi être lancé seul pour recolorier tous les onglets déjà présents
dans vct.xlsx après avoir mis à jour bracket_results.csv, sans relancer tout
le scraping :

    python tracker/bracket_status.py
"""

from pathlib import Path

import pandas as pd
from openpyxl.styles import PatternFill

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_XLSX = DATA_DIR / "vct.xlsx"
DEFAULT_BRACKET_RESULTS = DATA_DIR / "bracket_results.csv"

BRACKET_COLUMNS = ["stage", "round", "bracket_side", "team_a", "team_b", "winner"]
VALID_SIDES = {"upper", "lower"}

# Rouge clair façon "mise en forme conditionnelle" Excel — reste lisible avec
# du texte noir par défaut.
ELIMINATED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")


def load_bracket_results(path: Path = DEFAULT_BRACKET_RESULTS) -> pd.DataFrame:
    """Charge data/bracket_results.csv. Le crée (vide, avec les bons en-têtes)
    s'il n'existe pas encore — dans ce cas, aucune équipe n'est éliminée tant
    que le fichier n'est pas complété."""
    if not path.exists():
        empty = pd.DataFrame(columns=BRACKET_COLUMNS)
        empty.to_csv(path, index=False)
        print(
            f"⚠️ {path} introuvable — fichier vide créé. Ajoute les résultats de "
            f"matchs (colonnes: {', '.join(BRACKET_COLUMNS)}) au fur et à mesure "
            f"du Play-In / des Playoffs pour activer la mise en rouge."
        )
        return empty

    df = pd.read_csv(path)
    if df.empty:
        return df

    missing_cols = set(BRACKET_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValueError(f"{path} : colonnes manquantes {sorted(missing_cols)}")
    return df


def stage_from_sheet_name(sheet_name: str):
    """Devine le stage ('Playin' ou 'Playoffs') à partir du nom de l'onglet.
    Retourne None si l'onglet ne correspond à aucune phase à bracket (ex:
    'Classement Groupes ...', 'Classement PrePlayin ...') : personne n'est
    encore éliminé à ce stade, donc rien à colorier.

    Attention : "PrePlayin" contient la sous-chaîne "playin" — il faut donc
    l'exclure explicitement AVANT de tester "playin", sinon les onglets de
    groupes seraient à tort traités comme des onglets de Play-In."""
    name_low = sheet_name.lower()
    if "preplayin" in name_low or "pre-playin" in name_low or "groupe" in name_low:
        return None
    if "playoffs" in name_low:
        return "Playoffs"
    if "playin" in name_low or "play-in" in name_low:
        return "Playin"
    return None


def compute_eliminated_teams(bracket_df: pd.DataFrame, stage: str) -> set:
    """Une équipe est éliminée dès qu'elle perd un match dont bracket_side
    vaut 'Lower' pour ce stage. Ignore silencieusement (avec avertissement)
    les lignes mal formées plutôt que de planter tout le run."""
    if bracket_df.empty:
        return set()

    stage_matches = bracket_df[
        bracket_df["stage"].astype(str).str.strip().str.lower() == stage.strip().lower()
    ]

    eliminated = set()
    for _, row in stage_matches.iterrows():
        side = str(row["bracket_side"]).strip().lower()
        if side not in VALID_SIDES:
            print(f"⚠️ bracket_side inconnu ignoré : {row['bracket_side']!r} (attendu Upper/Lower).")
            continue

        team_a, team_b, winner = row["team_a"], row["team_b"], row["winner"]
        if winner not in (team_a, team_b):
            print(
                f"⚠️ Ligne ignorée — winner {winner!r} ne correspond ni à "
                f"team_a ({team_a!r}) ni à team_b ({team_b!r})."
            )
            continue

        if side == "lower":
            loser = team_b if winner == team_a else team_a
            eliminated.add(loser)

    return eliminated


def highlight_eliminated_teams(ws, df: pd.DataFrame, eliminated_teams: set, team_col: str = "team") -> int:
    """Applique un fond rouge à toutes les lignes du DataFrame dont l'équipe
    est éliminée. `ws` doit être la feuille openpyxl qui vient d'être écrite
    avec `df` (en-tête en ligne 1, données à partir de la ligne 2, même
    ordre que df). Retourne le nombre de lignes coloriées."""
    if not eliminated_teams or team_col not in df.columns:
        return 0

    n_cols = len(df.columns)
    n_highlighted = 0
    for row_offset, team in enumerate(df[team_col]):
        if team in eliminated_teams:
            excel_row = row_offset + 2  # ligne 1 = en-tête, openpyxl est 1-indexé
            for col in range(1, n_cols + 1):
                ws.cell(row=excel_row, column=col).fill = ELIMINATED_FILL
            n_highlighted += 1
    return n_highlighted


def highlight_workbook(xlsx_path: Path = DEFAULT_XLSX, bracket_results_path: Path = DEFAULT_BRACKET_RESULTS):
    """Recolore TOUS les onglets déjà présents dans vct.xlsx d'après l'état
    actuel de bracket_results.csv — pratique pour rafraîchir la mise en forme
    après avoir ajouté des résultats de matchs, sans relancer tout le
    scraping quotidien. Modifie le fichier en place."""
    import openpyxl

    bracket_df = load_bracket_results(bracket_results_path)
    wb = openpyxl.load_workbook(xlsx_path)

    eliminated_cache = {}
    any_change = False

    for sheet_name in wb.sheetnames:
        stage = stage_from_sheet_name(sheet_name)
        if stage is None:
            continue

        if stage not in eliminated_cache:
            eliminated_cache[stage] = compute_eliminated_teams(bracket_df, stage)
        eliminated_teams = eliminated_cache[stage]
        if not eliminated_teams:
            continue

        ws = wb[sheet_name]
        header_row = next(ws.iter_rows(min_row=1, max_row=1))
        headers = [c.value for c in header_row]
        if "team" not in headers:
            continue
        team_col_idx = headers.index("team")
        n_cols = len(headers)

        n_highlighted = 0
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            if row[team_col_idx].value in eliminated_teams:
                for cell in row[:n_cols]:
                    cell.fill = ELIMINATED_FILL
                n_highlighted += 1

        if n_highlighted:
            any_change = True
            print(f"🔴 {sheet_name} : {n_highlighted} ligne(s) coloriée(s) en rouge — équipe(s) éliminée(s) : {sorted(eliminated_teams)}")

    wb.save(xlsx_path)
    if any_change:
        print(f"\n✅ Mise en forme des équipes éliminées mise à jour dans {xlsx_path.resolve()}")
    else:
        print(f"\nAucune équipe éliminée trouvée dans {bracket_results_path.name} — {xlsx_path.name} inchangé (pas de ligne à colorier).")


if __name__ == "__main__":
    highlight_workbook()

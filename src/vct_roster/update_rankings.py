"""
update_vct_rankings.py
=======================
A lancer chaque jour (manuellement) pour ajouter un nouvel onglet daté au fichier
vct.xlsx, avec le classement des équipes selon la méthode "somme des rangs par rôle".

Usage :
    python update_vct_rankings.py
    python update_vct_rankings.py --file vct.xlsx --roles roles.csv

Ce script NE choisit PAS le rôle des joueurs à ta place : il lit roles.csv (une
seule source de vérité, que tu maintiens à la main) et te dit clairement quels
joueurs y manquent si jamais un nouveau apparaît dans les stats (ex: transfert,
équipe promue en Play-Ins).
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from openpyxl.utils import get_column_letter

from bracket_status import (
    compute_eliminated_teams,
    highlight_eliminated_teams,
    load_bracket_results,
    stage_from_sheet_name,
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_XLSX = DATA_DIR / "vct.xlsx"
DEFAULT_ROLES = DATA_DIR / "roles.csv"
DEFAULT_BRACKET_RESULTS = DATA_DIR / "bracket_results.csv"

EVENT_ID = 2976
EVENT_SLUG = "vct-2026-emea-stage-2"
BASE_URL = "https://www.vlr.gg"
STATS_URL = f"{BASE_URL}/event/stats/{EVENT_ID}/{EVENT_SLUG}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Fenêtres de dates connues pour nommer automatiquement l'onglet (à ajuster si le
# calendrier change) — sinon, le script retombe sur un nom générique "Classement JJ-MM".
STAGE_WINDOWS = [
    (date(2026, 7, 15), date(2026, 8, 2), "Groupes"),
    (date(2026, 8, 5), date(2026, 8, 16), "Playin"),
    (date(2026, 8, 20), date(2026, 8, 30), "Playoffs"),
]

MIN_ROUNDS = 0  # mets par ex. 100 si tu veux exclure les échantillons trop faibles


def guess_stage_label(today: date) -> str:
    for start, end, label in STAGE_WINDOWS:
        if start <= today <= end:
            return label
    return "Classement"


def fetch_soup(url: str, retries: int = 3, delay: float = 2.0) -> BeautifulSoup:
    import time

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            last_exc = e
            print(f"[Tentative {attempt}/{retries}] échec: {e}")
            time.sleep(delay)
    raise RuntimeError(f"Impossible de récupérer {url}") from last_exc


def parse_player_cell(td):
    """Retourne (nom_joueur, tag_equipe)."""
    a = td.find("a")
    container = a if a is not None else td
    divs = container.find_all("div")
    leaf_divs = [d for d in divs if not d.find("div")]
    texts = [d.get_text(strip=True) for d in leaf_divs if d.get_text(strip=True)]
    if len(texts) >= 2:
        return texts[0], texts[1]
    if len(texts) == 1:
        return texts[0], None
    return td.get_text(strip=True), None


def to_float(x):
    try:
        return float(str(x).replace("%", "").strip())
    except ValueError:
        return None


def to_int(x):
    try:
        return int(str(x).strip())
    except ValueError:
        return None


def scrape_current_stats() -> pd.DataFrame:
    """Récupère (player, team, rating, rounds) pour l'event VCT EMEA Stage 2 actuel
    (inclut automatiquement les Play-Ins / Playoffs au fur et à mesure qu'ils sont
    joués, puisque c'est la même page qui accumule les matchs)."""
    soup = fetch_soup(STATS_URL)
    table = soup.select_one("table.wf-table-inset.mod-overview") or soup.find("table")
    if table is None:
        raise RuntimeError("Table de stats introuvable — la structure de la page a peut-être changé.")

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 23:
            continue
        player, team = parse_player_cell(tds[0])
        rnd = to_int(tds[3].get_text(strip=True))
        rating = to_float(tds[4].get_text(strip=True))
        if rating is None:
            continue
        rows.append({"player": player, "team": team, "rating": rating, "rounds": rnd})

    df = pd.DataFrame(rows)
    if MIN_ROUNDS > 0:
        before = len(df)
        df = df[df["rounds"].fillna(0) >= MIN_ROUNDS]
        print(f"Filtre MIN_ROUNDS={MIN_ROUNDS} : {before - len(df)} joueur(s) exclu(s).")
    return df


def load_roles(roles_path: Path) -> pd.DataFrame:
    if not roles_path.exists():
        print(f"⚠️ {roles_path} introuvable — il sera créé vide. Remplis-le (colonnes: player, team_slot) avant de relancer.")
        empty = pd.DataFrame(columns=["player", "team_slot"])
        empty.to_csv(roles_path, index=False)
        return empty
    return pd.read_csv(roles_path)


def compute_rankings(df_stats: pd.DataFrame, df_roles: pd.DataFrame):
    merged = df_stats.merge(df_roles, on="player", how="left")

    missing = merged[merged["team_slot"].isna()]
    if not missing.empty:
        print(f"\n⚠️ {len(missing)} joueur(s) sans rôle connu dans roles.csv (exclus du classement du jour) :")
        for _, r in missing.iterrows():
            print(f"   - {r['player']} ({r['team']}, rating {r['rating']})")
        print("   -> ajoute-les dans roles.csv (colonnes: player, team_slot) puis relance le script.\n")

    ranked = merged.dropna(subset=["team_slot"]).copy()
    if ranked.empty:
        raise RuntimeError("Aucun joueur avec un rôle connu — impossible de calculer un classement.")

    # Sécurité : un même (équipe, rôle) ne doit avoir qu'UN SEUL joueur — sinon la somme
    # "Point Equipe" additionne plus de 5 termes pour cette équipe (cas typique : un
    # remplaçant garde son rôle dans roles.csv en même temps que le titulaire actuel).
    # On garde celui qui a joué le plus de rounds cette période (le titulaire probable),
    # et on prévient clairement pour que roles.csv puisse être nettoyé.
    dup_mask = ranked.duplicated(subset=["team", "team_slot"], keep=False)
    if dup_mask.any():
        dups = ranked[dup_mask].sort_values(["team", "team_slot", "rounds"], ascending=[True, True, False])
        print("\n⚠️ Doublon de rôle détecté dans la même équipe (remplaçant vs titulaire probable) :")
        kept_idx = []
        for (team, slot), grp in dups.groupby(["team", "team_slot"]):
            grp_sorted = grp.sort_values("rounds", ascending=False, na_position="last")
            keep = grp_sorted.iloc[0]
            drop = grp_sorted.iloc[1:]
            kept_idx.append(keep.name)
            for _, d in drop.iterrows():
                print(f"   - {team} / {slot} : gardé '{keep['player']}' ({keep['rounds']} rounds), "
                      f"écarté '{d['player']}' ({d['rounds']} rounds) — vérifie roles.csv si ce n'est pas le bon.")
        drop_all_idx = dups.index.difference(kept_idx)
        ranked = ranked.drop(index=drop_all_idx)
        print()

    # Sécurité : une équipe incomplète (moins de 5 joueurs à rôle connu) fausserait la
    # somme "Point Equipe" (moins de termes additionnés = score artificiellement meilleur).
    # On exclut ces équipes entièrement plutôt que de produire un classement biaisé.
    team_counts = ranked.groupby("team")["player"].count()
    incomplete_teams = team_counts[team_counts < 5].index.tolist()
    if incomplete_teams:
        print(f"\n⚠️ Équipe(s) exclue(s) du classement (moins de 5 joueurs à rôle connu) : {incomplete_teams}")
        print("   -> complète roles.csv pour les joueurs manquants de ces équipes.\n")
        ranked = ranked[~ranked["team"].isin(incomplete_teams)]

    if ranked.empty:
        raise RuntimeError("Plus aucune équipe complète après filtrage — vérifie roles.csv.")


    # Classement Role : 1 = meilleur rating du groupe de rôle (tous équipes confondues)
    ranked["Classement Role"] = ranked.groupby("team_slot")["rating"].rank(ascending=False, method="min").astype(int)

    team_points = ranked.groupby("team")["Classement Role"].sum().rename("Point Equipe")
    n_teams = ranked["team"].nunique()
    col_divise = f"Divise par {n_teams}"

    ranked = ranked.merge(team_points, on="team", how="left")
    ranked[col_divise] = (ranked["Point Equipe"] / n_teams).round(6)

    # IMPORTANT : le rang doit être calculé sur les valeurs UNIQUES par équipe, pas sur
    # le tableau au niveau joueur (qui répète 5x la même valeur par équipe) — sinon
    # chaque équipe "consomme" 5 crans de rang au lieu d'1 (bug corrigé ici : les
    # classements sautaient par paliers de 5 : 1, 6, 11, 16...).
    team_rank = (
        ranked.drop_duplicates("team")
        .set_index("team")[col_divise]
        .rank(ascending=True, method="min")
        .astype(int)
        .rename("Classement équipe")
    )
    ranked = ranked.drop(columns=["Classement équipe"], errors="ignore").merge(
        team_rank, on="team", how="left"
    )

    ranked = ranked.drop(columns=["rounds"], errors="ignore")
    ranked = ranked.sort_values(["Classement équipe", "team", "Classement Role"]).reset_index(drop=True)

    return ranked, missing


def write_sheet(xlsx_path: Path, sheet_name: str, df: pd.DataFrame, bracket_results_path: Path = DEFAULT_BRACKET_RESULTS):
    mode = "a" if xlsx_path.exists() else "w"
    kwargs = {"if_sheet_exists": "replace"} if mode == "a" else {}
    with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode=mode, **kwargs) as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
            col_letter = get_column_letter(col_cells[0].column)
            ws.column_dimensions[col_letter].width = min(length + 2, 40)
        ws.freeze_panes = "A2"

        # Équipes éliminées du Play-In / des Playoffs -> ligne coloriée en
        # rouge, calculé automatiquement depuis bracket_results.csv (voir
        # bracket_status.py : une défaite en lower bracket = élimination).
        stage = stage_from_sheet_name(sheet_name)
        if stage is not None:
            bracket_df = load_bracket_results(bracket_results_path)
            eliminated_teams = compute_eliminated_teams(bracket_df, stage)
            n_highlighted = highlight_eliminated_teams(ws, df, eliminated_teams)
            if n_highlighted:
                print(f"🔴 {sheet_name} : {n_highlighted} ligne(s) coloriée(s) en rouge — équipe(s) éliminée(s) ({stage}) : {sorted(eliminated_teams)}")


def main():
    parser = argparse.ArgumentParser(description="Met à jour le classement VCT EMEA du jour.")
    parser.add_argument("--file", default=str(DEFAULT_XLSX), help=f"Fichier Excel de classement (défaut: {DEFAULT_XLSX})")
    parser.add_argument("--roles", default=str(DEFAULT_ROLES), help=f"Fichier CSV des rôles (défaut: {DEFAULT_ROLES})")
    parser.add_argument("--sheet-name", default=None, help="Nom d'onglet explicite (sinon auto-généré)")
    args = parser.parse_args()

    xlsx_path = Path(args.file)
    roles_path = Path(args.roles)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    roles_path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today()

    print(f"Récupération des stats actuelles ({STATS_URL})...")
    df_stats = scrape_current_stats()
    print(f"{len(df_stats)} joueurs récupérés.")

    df_roles = load_roles(roles_path)
    ranked, missing = compute_rankings(df_stats, df_roles)

    sheet_name = args.sheet_name or f"Classement {guess_stage_label(today)} {today.strftime('%d-%m')}"
    sheet_name = sheet_name[:31]  # limite Excel

    write_sheet(xlsx_path, sheet_name, ranked)
    print(f"\n✅ Onglet '{sheet_name}' écrit dans {xlsx_path.resolve()}")

    top_team = ranked.loc[ranked["Classement équipe"] == 1, "team"].iloc[0] if not ranked.empty else None
    if top_team:
        print(f"Équipe classée n°1 aujourd'hui : {top_team}")

    if not missing.empty:
        print(f"\n⚠️ Rappel : {len(missing)} joueur(s) restent à classer dans {roles_path} avant le prochain lancement.")
        sys.exit(0)


if __name__ == "__main__":
    main()

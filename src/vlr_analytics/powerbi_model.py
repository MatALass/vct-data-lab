"""Star schema of the VLR 2026 data for the Power BI report.

Reads the versioned marts and models (``data/marts``, ``data/models``,
``data/processed``) and writes one CSV per table in ``data/powerbi/vlr_2026``:

- ``Compositions``: one row per team and per map played (the five agents);
- ``Picks``: one row per composition and per agent;
- ``Paires``: one row per composition and per pair of agents (10 per composition);
- ``Joueurs``: player stats, EMEA Stage 1 only (the only event scraped for players);
- ``Evenements``, ``Maps``, ``Equipes``, ``Agents``: the dimensions.

Rates are not stored: Power BI computes them from these rows, so they stay right
under any filter (event, map, team, role). The precomputed ``pick_rate`` columns
of the marts are only valid for the grouping they were computed on.

Usage::

    python -m vlr_analytics.powerbi_model
"""

from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import pandas as pd

from vct_ranker.agents import AGENT_TO_ROLE
from vlr_analytics.config import DATA_DIR, MODELS_DIR, PROCESSED_DIR, TEAM_COMPOSITIONS

OUT_DIR = DATA_DIR / "powerbi" / "vlr_2026"
CLUSTERS = MODELS_DIR / "composition_clusters.csv"
TEAM_PROFILES = MODELS_DIR / "team_profile_scores.csv"
PLAYERS = PROCESSED_DIR / "vlr_players_processed.csv"

REGIONS = {"americas": "Americas", "emea": "EMEA", "pacific": "Pacific", "china": "China"}
REGION_ORDER = {"Americas": 1, "EMEA": 2, "Pacific": 3, "China": 4}
ROLE_ORDER = {"Duelist": 1, "Initiator": 2, "Controller": 3, "Sentinel": 4, "Flex": 5}
PROFILE_LABELS = {"stable_core": "Noyau stable", "flexible_pool": "Pool flexible"}
AGENT_LABELS = {"kayo": "KAY/O"}

# vlr.gg shows short team names on the player stats page, full names on the match pages.
EMEA_TEAM_CODES = {
    "BBL": "BBL Esports",
    "EF": "Eternal Fire",
    "FNC": "FNATIC",
    "FUT": "FUT Esports",
    "GX": "GIANTX",
    "KC": "Karmine Corp",
    "M8": "Gentle Mates",
    "NAVI": "Natus Vincere",
    "PCF": "PCIFIC Esports",
    "TH": "Team Heretics",
    "TL": "Team Liquid",
    "VIT": "Team Vitality",
}
UNKNOWN_TEAM = "(équipe non reconnue)"


def _event_label(event: str) -> str:
    region, _, stage = event.partition("_")
    return f"{REGIONS.get(region, region.title())} {stage.replace('_', ' ').title()}"


def _region(event: str) -> str:
    region = event.partition("_")[0]
    return REGIONS.get(region, region.title())


def _agent_label(agent: str) -> str:
    return AGENT_LABELS.get(agent, agent.title())


def build_tables(
    compositions: pd.DataFrame,
    clusters: pd.DataFrame,
    profiles: pd.DataFrame,
    players: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build the star schema from the pipeline outputs (pure function, no I/O)."""
    comps = compositions[compositions["observed"].astype(bool)].copy()
    comps["map"] = comps["map"].str.title()
    comps["agent_list"] = comps["agents"].str.split(",").map(lambda a: sorted(x.strip() for x in a))
    if comps.duplicated(["match_id", "team"]).any():
        raise ValueError("team_compositions: several rows for the same team on the same map")
    comps["CompID"] = comps["match_id"] + "__" + comps["team"]

    archetypes = clusters.assign(CompID=clusters["match_id"] + "__" + clusters["team"])
    comps = comps.merge(archetypes[["CompID", "cluster_label"]], on="CompID", how="left")

    compositions_out = pd.DataFrame(
        {
            "CompID": comps["CompID"],
            "Événement": comps["event"],
            "Map": comps["map"],
            "Équipe": comps["team"],
            "Adversaire": comps["opponent"],
            "Match": comps["match_id"],
            "Agents": comps["agent_list"].map(lambda a: ", ".join(_agent_label(x) for x in a)),
            "Archétype": comps["cluster_label"]
            .map(
                lambda c: " + ".join(_agent_label(x.strip()) for x in c.split("+")),
                na_action="ignore",
            )
            .fillna("(non classée)"),
        }
    )

    keys = comps[["CompID", "event", "map", "team"]].rename(
        columns={"event": "Événement", "map": "Map", "team": "Équipe"}
    )
    picks = (
        comps[["CompID", "agent_list"]]
        .explode("agent_list")
        .rename(columns={"agent_list": "Agent"})
    ).merge(keys, on="CompID")
    pairs = comps[["CompID", "agent_list"]].assign(
        Paire=comps["agent_list"].map(
            lambda a: [f"{_agent_label(x)} + {_agent_label(y)}" for x, y in combinations(a, 2)]
        )
    )
    pairs = pairs.explode("Paire")[["CompID", "Paire"]].merge(keys, on="CompID")

    agents = sorted(picks["Agent"].unique())
    missing_roles = [a for a in agents if a not in AGENT_TO_ROLE]
    if missing_roles:
        raise ValueError(f"agents without a role in vct_ranker.agents: {missing_roles}")
    dim_agent = pd.DataFrame(
        {
            "Agent": agents,
            "Nom": [_agent_label(a) for a in agents],
            "Rôle": [AGENT_TO_ROLE[a] for a in agents],
            "Ordre rôle": [ROLE_ORDER[AGENT_TO_ROLE[a]] for a in agents],
        }
    )

    events = sorted(comps["event"].unique(), key=lambda e: (REGION_ORDER.get(_region(e), 9), e))
    dim_event = pd.DataFrame(
        {
            "Événement": events,
            "Nom événement": [_event_label(e) for e in events],
            "Région": [_region(e) for e in events],
            "Ordre": range(1, len(events) + 1),
        }
    )

    dim_map = pd.DataFrame({"Map": sorted(comps["map"].unique())})

    team_region = comps.groupby("team")["event"].agg(
        lambda s: ", ".join(sorted({_region(e) for e in s}))
    )
    prof = profiles.set_index("team")
    teams = sorted(comps["team"].unique())
    dim_team = pd.DataFrame(
        {
            "Équipe": teams,
            "Région": [team_region[t] for t in teams],
            "Profil tactique": [
                PROFILE_LABELS.get(prof["tactical_profile_label"].get(t), "(non calculé)")
                for t in teams
            ],
            "Score profil": [
                round(float(prof["tactical_profile_score"].get(t, float("nan"))) * 100, 1)
                for t in teams
            ],
            "Taux de réutilisation": [prof["composition_reuse_rate"].get(t) for t in teams],
        }
    )

    p = players.copy()
    p["Équipe"] = p["team"].map(EMEA_TEAM_CODES).fillna(UNKNOWN_TEAM)
    dim_team = pd.concat(
        [
            dim_team,
            pd.DataFrame(
                [{"Équipe": UNKNOWN_TEAM, "Région": "EMEA", "Profil tactique": "(non calculé)"}]
            ),
        ]
        if (p["Équipe"] == UNKNOWN_TEAM).any()
        else [dim_team],
        ignore_index=True,
    )
    players_out = pd.DataFrame(
        {
            "Joueur": p["player"],
            "Équipe": p["Équipe"],
            "Événement": "emea_stage_1",
            "Rôle joué": p["inferred_role"],
            "Agents joués": p["agents"]
            .str.split(",")
            .map(lambda a: ", ".join(_agent_label(x.strip()) for x in a)),
            "Rounds": p["rounds"],
            "Rating": p["rating"],
            "ACS": p["acs"],
            "KD": p["kd"],
            "KAST": p["kast"] / 100,
            "ADR": p["adr"],
            "FKPR": p["fkpr"],
            "FDPR": p["fdpr"],
            "HS": p["hs_pct"] / 100,
        }
    )

    return {
        "Evenements": dim_event,
        "Maps": dim_map,
        "Equipes": dim_team,
        "Agents": dim_agent,
        "Compositions": compositions_out,
        "Picks": picks[["CompID", "Événement", "Map", "Équipe", "Agent"]],
        "Paires": pairs[["CompID", "Événement", "Map", "Équipe", "Paire"]],
        "Joueurs": players_out,
    }


def build(out_dir: Path = OUT_DIR) -> dict[str, pd.DataFrame]:
    tables = build_tables(
        pd.read_csv(TEAM_COMPOSITIONS),
        pd.read_csv(CLUSTERS),
        pd.read_csv(TEAM_PROFILES),
        pd.read_csv(PLAYERS),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8")
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    for name, df in build(args.out).items():
        print(f"{name:<13} {len(df):>5} rows")


if __name__ == "__main__":
    main()

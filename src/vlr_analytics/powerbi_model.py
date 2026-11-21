"""Star schema of the VCT season (vlr.gg) for the Power BI report.

Reads the pipeline outputs and writes one CSV per table in ``data/powerbi/vlr_2026``:

- ``Compositions``: one row per team and per map played (five agents, result);
- ``Picks``: one row per composition and per agent;
- ``Paires``: one row per composition and per pair of agents (10 per composition);
- ``Joueurs``: player stats, one row per player and per event;
- ``Evenements``, ``Maps``, ``Equipes``, ``Agents``: the dimensions.

Rates are not stored: Power BI computes them from these rows, so they stay right
under any filter (event, map, team, role). The precomputed ``pick_rate`` columns
of the marts are only valid for the grouping they were computed on.

Usage::

    python -m vlr_analytics.powerbi_model
"""

from __future__ import annotations

import argparse
import re
from itertools import combinations
from pathlib import Path

import pandas as pd

from vct_ranker.agents import AGENT_TO_ROLE
from vlr_analytics.config import (
    DATA_DIR,
    MODELS_DIR,
    PROCESSED_MATRIX,
    PROCESSED_SEASON_PLAYERS,
    RAW_EVENTS,
)

OUT_DIR = DATA_DIR / "powerbi" / "vlr_2026"
CLUSTERS = MODELS_DIR / "composition_clusters.csv"
TEAM_PROFILES = MODELS_DIR / "team_profile_scores.csv"

ROLE_ORDER = {"Duelist": 1, "Initiator": 2, "Controller": 3, "Sentinel": 4, "Flex": 5}
PROFILE_LABELS = {
    "stable_core": "Noyau stable",
    "flexible_pool": "Pool flexible",
    "low_sample_profile": "Échantillon faible",
}
AGENT_LABELS = {"kayo": "KAY/O"}
RESULTS = {"win": "Victoire", "loss": "Défaite"}


def _agent_label(agent: str) -> str:
    return AGENT_LABELS.get(agent, agent.title())


def event_label(name: str) -> str:
    """``VCT 2026: EMEA Stage 1`` -> ``EMEA Stage 1``.

    ``Valorant Masters London 2026`` -> ``Masters London``.
    """
    name = re.sub(r"^VCT \d{4}:\s*", "", name)
    name = re.sub(r"^Valorant\s+", "", name)
    return re.sub(r"\s+\d{4}$", "", name).strip()


def season_steps(events: pd.DataFrame) -> dict[str, str]:
    """Event -> step of the season, numbered so that it sorts in time order.

    The four regional leagues of a phase are one step (``3. Stage 1``); each
    international event is its own step (``2. Masters Santiago``).
    """
    events = events.sort_values("event_order")
    names = {
        ev.event: ev.phase if ev.region != "International" else event_label(ev.event_name)
        for ev in events.itertuples()
    }
    order = list(dict.fromkeys(names[e] for e in events["event"]))
    return {e: f"{order.index(step) + 1}. {step}" for e, step in names.items()}


def build_tables(
    matrix: pd.DataFrame,
    events: pd.DataFrame,
    clusters: pd.DataFrame,
    profiles: pd.DataFrame,
    players: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build the star schema from the pipeline outputs (pure function, no I/O)."""
    comps = (
        matrix.groupby(["event", "map", "match_id", "team"], as_index=False)
        .agg(
            opponent=("opponent", "first"),
            result=("result", "first"),
            agent_list=("agent", lambda a: sorted(set(a))),
        )
        .sort_values(["event", "map", "match_id", "team"], ignore_index=True)
    )
    bad = comps[comps["agent_list"].map(len) != 5]
    if not bad.empty:
        raise ValueError(
            f"{len(bad)} compositions without exactly 5 agents, e.g. {bad.iloc[0].to_dict()}"
        )
    comps["CompID"] = comps["match_id"] + "__" + comps["team"]
    archetypes = clusters.assign(CompID=clusters["match_id"] + "__" + clusters["team"])
    comps = comps.merge(archetypes[["CompID", "cluster_label"]], on="CompID", how="left")
    comps["Victoire"] = (comps["result"] == "win").astype(int)

    compositions_out = pd.DataFrame(
        {
            "CompID": comps["CompID"],
            "Événement": comps["event"],
            "Map": comps["map"],
            "Équipe": comps["team"],
            "Adversaire": comps["opponent"],
            "Match": comps["match_id"],
            "Résultat": comps["result"].map(RESULTS).fillna("(inconnu)"),
            "Victoire": comps["Victoire"],
            "Agents": comps["agent_list"].map(lambda a: ", ".join(_agent_label(x) for x in a)),
            "Archétype": comps["cluster_label"]
            .map(
                lambda c: " + ".join(_agent_label(x.strip()) for x in c.split("+")),
                na_action="ignore",
            )
            .fillna("(non classée)"),
        }
    )

    keys = comps[["CompID", "event", "map", "team", "Victoire"]].rename(
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

    ev = events.sort_values("event_order")
    ev = ev[ev["event"].isin(set(comps["event"]) | set(players["event"]))]
    steps = season_steps(ev)
    dim_event = pd.DataFrame(
        {
            "Événement": ev["event"],
            "Nom événement": ev["event_name"].map(event_label),
            "Région": ev["region"],
            "Phase": ev["phase"],
            "Étape": ev["event"].map(steps),
            "Ordre": ev["event_order"],
        }
    ).reset_index(drop=True)

    dim_map = pd.DataFrame({"Map": sorted(comps["map"].unique())})

    league = comps.merge(events[["event", "region"]], on="event")
    league = league[league["region"] != "International"]
    team_region = league.groupby("team")["region"].agg(lambda s: s.mode().iloc[0])
    prof = profiles.set_index("team")
    teams = sorted(set(comps["team"]) | set(players["team"].dropna()))
    dim_team = pd.DataFrame(
        {
            "Équipe": teams,
            "Région": [team_region.get(t, "International") for t in teams],
            "Profil tactique": [
                PROFILE_LABELS.get(prof["tactical_profile_label"].get(t), "(non calculé)")
                for t in teams
            ],
            "Score profil": [
                round(float(prof["tactical_profile_score"].get(t, float("nan"))) * 100, 1)
                for t in teams
            ],
        }
    )

    p = players[players["team"].notna() & (players["team"] != "")]
    players_out = pd.DataFrame(
        {
            "Joueur": p["player"],
            "Équipe": p["team"],
            "Événement": p["event"],
            "Rôle joué": p["inferred_role"],
            "Agents joués": p["agents"]
            .fillna("")
            .str.split(",")
            .map(lambda a: ", ".join(_agent_label(x.strip()) for x in a if x.strip())),
            "Maps": p["maps"],
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
    ).sort_values(["Événement", "Équipe", "Joueur"], ignore_index=True)

    return {
        "Evenements": dim_event,
        "Maps": dim_map,
        "Equipes": dim_team,
        "Agents": dim_agent,
        "Compositions": compositions_out,
        "Picks": picks[["CompID", "Événement", "Map", "Équipe", "Agent", "Victoire"]],
        "Paires": pairs[["CompID", "Événement", "Map", "Équipe", "Paire", "Victoire"]],
        "Joueurs": players_out,
    }


def build(out_dir: Path = OUT_DIR) -> dict[str, pd.DataFrame]:
    tables = build_tables(
        pd.read_csv(PROCESSED_MATRIX),
        pd.read_csv(RAW_EVENTS),
        pd.read_csv(CLUSTERS),
        pd.read_csv(TEAM_PROFILES),
        pd.read_csv(PROCESSED_SEASON_PLAYERS),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.csv"):
        old.unlink()
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8")
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    for name, df in build(args.out).items():
        print(f"{name:<13} {len(df):>6} rows")


if __name__ == "__main__":
    main()

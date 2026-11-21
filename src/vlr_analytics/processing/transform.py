import re

import pandas as pd

from vlr_analytics.config import (
    EXPECTED_AGENTS_PER_COMP,
    INVALID_COMPOSITIONS_REPORT,
    PROCESSED_MATRIX,
    PROCESSED_SEASON_PLAYERS,
    PROCESSED_SUMMARY,
    RAW_EVENTS,
    RAW_MATRIX,
    RAW_PLAYERS,
    RAW_SUMMARY,
    RAW_TEAMS,
)
from vlr_analytics.utils import (
    clean_text,
    normalize_map_name,
    percent_to_float,
    read_csv_required,
    require_columns,
    write_csv,
)

INVALID_COMPOSITION_COLUMNS = [
    "event",
    "map",
    "match_id",
    "team",
    "opponent",
    "agents_count",
    "expected_agents_count",
    "agents",
    "reason",
]


def build_match_id(row: pd.Series) -> str:
    """One id per map played. With the vlr.gg game id, two teams that meet twice on
    the same map in an event (group stage then playoffs) get two ids."""
    teams = sorted([str(row["team"]), str(row["opponent"])])
    game = row.get("game_id")
    suffix = f"__{int(game)}" if pd.notna(game) and str(game) != "" else ""
    raw = f"{row['event']}__{row['map']}__{teams[0]}__{teams[1]}{suffix}"
    return re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()


def transform_summary(input_path=RAW_SUMMARY, output_path=PROCESSED_SUMMARY) -> pd.DataFrame:
    df = read_csv_required(input_path)
    require_columns(
        df,
        {
            "event",
            "raw_map",
            "raw_maps_played",
            "raw_atk_win_rate",
            "raw_def_win_rate",
            "agent",
            "raw_pick_rate",
        },
        "summary raw",
    )
    out = pd.DataFrame(
        {
            "event": df["event"].map(clean_text),
            "map": df["raw_map"].map(normalize_map_name),
            "maps_played": df["raw_maps_played"].astype(int),
            "atk_win_rate": df["raw_atk_win_rate"].map(percent_to_float),
            "def_win_rate": df["raw_def_win_rate"].map(percent_to_float),
            "agent": df["agent"].map(clean_text).str.lower(),
            "pick_rate": df["raw_pick_rate"].map(percent_to_float),
        }
    )
    out = out.drop_duplicates()
    write_csv(out, output_path)
    return out


def build_invalid_compositions_report(
    matrix: pd.DataFrame,
    output_path=INVALID_COMPOSITIONS_REPORT,
) -> pd.DataFrame:
    """Build a data-quality report for incomplete or oversized compositions.

    A valid Valorant composition should contain exactly five unique agents for one
    team on one map. The report is intentionally non-blocking: it keeps the
    pipeline usable while making scraping/data-quality anomalies explicit.
    """
    if matrix.empty:
        report = pd.DataFrame(columns=INVALID_COMPOSITION_COLUMNS)
        write_csv(report, output_path)
        return report

    grouped = matrix.groupby(["event", "map", "match_id", "team"], as_index=False).agg(
        opponent=("opponent", "first"),
        agents_count=("agent", "nunique"),
        agents=("agent", lambda values: ",".join(sorted(set(map(str, values))))),
    )

    report = grouped[grouped["agents_count"] != EXPECTED_AGENTS_PER_COMP].copy()
    if report.empty:
        report = pd.DataFrame(columns=INVALID_COMPOSITION_COLUMNS)
    else:
        report["expected_agents_count"] = EXPECTED_AGENTS_PER_COMP
        report["reason"] = report["agents_count"].map(
            lambda count: (
                "missing_agents" if count < EXPECTED_AGENTS_PER_COMP else "too_many_agents"
            )
        )
        report = report[INVALID_COMPOSITION_COLUMNS].sort_values(
            ["event", "map", "match_id", "team"]
        )

    write_csv(report, output_path)
    return report


def transform_matrix(input_path=RAW_MATRIX, output_path=PROCESSED_MATRIX) -> pd.DataFrame:
    df = read_csv_required(input_path)
    require_columns(df, {"event", "map", "team", "opponent", "agent"}, "matrix raw")
    for col in ["event", "map", "team", "opponent", "agent"]:
        df[col] = df[col].map(clean_text)
    df["map"] = df["map"].map(normalize_map_name)
    df["agent"] = df["agent"].str.lower()
    extra = [c for c in ["game_id", "team_id", "result"] if c in df.columns]
    out = df[["event", "map", "team", "opponent", "agent", *extra]].drop_duplicates().copy()
    out["match_id"] = out.apply(build_match_id, axis=1)
    out = out[
        [
            "event",
            "map",
            "match_id",
            "team",
            "opponent",
            "agent",
            *[c for c in extra if c != "game_id"],
        ]
    ]

    invalid_report = build_invalid_compositions_report(out)
    if not invalid_report.empty:
        print(
            f"WARNING: {len(invalid_report)} compositions have != "
            f"{EXPECTED_AGENTS_PER_COMP} agents. "
            f"See {INVALID_COMPOSITIONS_REPORT}."
        )

    write_csv(out, output_path)
    return out


def transform_players(
    players_path=RAW_PLAYERS,
    matrix_path=RAW_MATRIX,
    teams_path=RAW_TEAMS,
    events_path=RAW_EVENTS,
    output_path=PROCESSED_SEASON_PLAYERS,
) -> pd.DataFrame:
    """Player stats of the season, with the full team name.

    The stats page shows a tag (``FNC``), the agents page the full name (``FNATIC``):
    the tag is looked up among the teams that played the same event.
    """
    if not players_path.exists():
        return pd.DataFrame()
    players = read_csv_required(players_path)
    matrix = read_csv_required(matrix_path)
    teams = read_csv_required(teams_path)
    events = read_csv_required(events_path)
    require_columns(players, {"player", "team", "event", "rounds", "rating"}, "players raw")

    event_teams = (
        matrix[["event", "team", "team_id"]]
        .dropna()
        .drop_duplicates()
        .merge(teams[["team_id", "tag"]], on="team_id", how="left")
    )
    lookup = {
        (r.event, str(r.tag).upper()): r.team for r in event_teams.itertuples() if pd.notna(r.tag)
    }
    out = players.rename(columns={"team": "team_tag"}).copy()
    out["team"] = [
        lookup.get((e, str(t).upper()), "") if pd.notna(t) else ""
        for e, t in zip(out["event"], out["team_tag"], strict=False)
    ]
    out = out.merge(events[["event", "event_name", "region", "phase"]], on="event", how="left")
    unmatched = out[out["team"] == ""]
    if not unmatched.empty:
        print(
            f"WARNING: {len(unmatched)} player rows without a known team tag: "
            f"{sorted(unmatched['team_tag'].astype(str).unique())[:10]}"
        )
    write_csv(out, output_path)
    return out


def process_all() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary, matrix = transform_summary(), transform_matrix()
    transform_players()
    return summary, matrix

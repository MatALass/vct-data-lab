from pathlib import Path

import pandas as pd

from vct_ranker.scraper import parse_stats_table
from vlr_analytics.processing.transform import build_match_id
from vlr_analytics.scraping.vlr import (
    event_key,
    parse_agents_matrix,
    parse_agents_summary,
    parse_season_events,
    parse_team_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "vlr"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_event_keys():
    assert event_key("vct-2026-emea-stage-1") == "emea_stage_1"
    assert event_key("valorant-masters-london-2026") == "masters_london"
    assert event_key("valorant-champions-2026") == "champions"


def test_season_events_are_sorted_by_start_date():
    events = parse_season_events(read("season.html"))
    assert events["event"].tolist() == [
        "emea_kickoff",
        "masters_santiago",
        "emea_stage_1",
        "champions",
    ]
    assert events["event_order"].tolist() == [1, 2, 3, 4]
    by_key = events.set_index("event")
    assert by_key.loc["masters_santiago", "region"] == "International"
    assert by_key.loc["emea_stage_1", "region"] == "EMEA"
    assert by_key.loc["emea_stage_1", "phase"] == "Stage 1"
    assert by_key.loc["champions", "event_name"] == "Valorant Champions 2026"


def test_matrix_gives_five_agents_per_team_and_game_with_the_result():
    matrix = parse_agents_matrix(read("agents.html"), "emea_stage_1")
    comps = matrix.groupby(["game_id", "team"])
    assert comps.size().eq(5).all()
    assert len(comps) == 4  # 2 games x 2 teams, the rematch on Bind is kept apart
    first = matrix[(matrix["game_id"] == "100") & (matrix["team"] == "FNATIC")]
    assert sorted(first["agent"]) == ["fade", "killjoy", "neon", "omen", "sova"]
    assert set(first["result"]) == {"win"}
    assert set(first["opponent"]) == {"GIANTX"}
    assert set(matrix["team_id"]) == {"2593", "14419"}
    assert set(matrix["map"]) == {"Bind"}


def test_rematch_on_the_same_map_gets_two_match_ids():
    matrix = parse_agents_matrix(read("agents.html"), "emea_stage_1")
    ids = matrix.apply(build_match_id, axis=1)
    assert ids.nunique() == 2
    # Both teams of the same game share the id.
    assert matrix.assign(mid=ids).groupby("mid")["team"].nunique().eq(2).all()


def test_summary_table():
    summary = parse_agents_summary(read("agents.html"), "emea_stage_1")
    assert len(summary) == 12
    assert set(summary["raw_map"]) == {"", "B Bind"}


def test_stats_keep_multi_word_nicknames_and_read_columns_by_header():
    rows = pd.DataFrame(parse_stats_table(read("stats.html"))).set_index("player")
    assert rows.loc["lovers rock", "team"] == "BBL"
    assert rows.loc["Ruxic", "team"] == "NAVI"
    assert rows.loc["Ruxic", "maps"] == 13
    assert rows.loc["Ruxic", "rounds"] == 281
    assert rows.loc["Ruxic", "rating"] == 1.20
    assert rows.loc["Ruxic", "kast"] == 75.0
    assert rows.loc["Ruxic", "hs_pct"] == 25.0
    assert rows.loc["Ruxic", "fkpr"] == round(25 / 281, 3)
    assert rows.loc["Ruxic", "agents"] == "astra,omen"


def test_team_page():
    assert parse_team_page(read("team.html")) == {"team": "Team Heretics", "tag": "TH"}

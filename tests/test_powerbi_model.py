import pandas as pd
import pytest

from vlr_analytics.powerbi_model import OUT_DIR, build, build_tables, event_label, season_steps

EVENTS = pd.DataFrame(
    [
        {
            "event": "emea_kickoff",
            "event_name": "VCT 2026: EMEA Kickoff",
            "region": "EMEA",
            "phase": "Kickoff",
            "event_order": 1,
        },
        {
            "event": "masters_santiago",
            "event_name": "Valorant Masters Santiago 2026",
            "region": "International",
            "phase": "Masters",
            "event_order": 2,
        },
        {
            "event": "emea_stage_1",
            "event_name": "VCT 2026: EMEA Stage 1",
            "region": "EMEA",
            "phase": "Stage 1",
            "event_order": 3,
        },
    ]
)


def _picks(event, match, team, opponent, result, agents):
    return [
        {
            "event": event,
            "map": "Bind",
            "match_id": match,
            "team": team,
            "opponent": opponent,
            "agent": a,
            "result": result,
        }
        for a in agents
    ]


MATRIX = pd.DataFrame(
    _picks(
        "emea_kickoff", "m1", "FNATIC", "GIANTX", "win", ["omen", "neon", "sova", "killjoy", "fade"]
    )
    + _picks(
        "emea_kickoff",
        "m1",
        "GIANTX",
        "FNATIC",
        "loss",
        ["viper", "neon", "kayo", "cypher", "miks"],
    )
    + _picks(
        "masters_santiago",
        "m2",
        "FNATIC",
        "GIANTX",
        "loss",
        ["omen", "neon", "sova", "veto", "fade"],
    )
    + _picks(
        "masters_santiago",
        "m2",
        "GIANTX",
        "FNATIC",
        "win",
        ["viper", "neon", "kayo", "cypher", "omen"],
    )
)
CLUSTERS = pd.DataFrame(
    {
        "match_id": ["m1", "m1"],
        "team": ["FNATIC", "GIANTX"],
        "cluster_label": ["omen + neon + sova", "viper + neon"],
    }
)
PROFILES = pd.DataFrame(
    {
        "team": ["FNATIC", "GIANTX"],
        "tactical_profile_label": ["stable_core", "low_sample_profile"],
        "tactical_profile_score": [0.61, 0.42],
    }
)
PLAYERS = pd.DataFrame(
    [
        {
            "player": "Boaster",
            "team": "FNATIC",
            "event": "emea_kickoff",
            "agents": "omen,astra",
            "inferred_role": "Controller",
            "maps": 5,
            "rounds": 100,
            "rating": 1.1,
            "acs": 180.0,
            "kd": 1.1,
            "kast": 75.0,
            "adr": 120.0,
            "fkpr": 0.1,
            "fdpr": 0.05,
            "hs_pct": 30.0,
        },
        {
            "player": "lovers rock",
            "team": "BBL Esports",
            "event": "emea_stage_1",
            "agents": "jett",
            "inferred_role": "Duelist",
            "maps": 3,
            "rounds": 50,
            "rating": 0.9,
            "acs": 186.0,
            "kd": 0.9,
            "kast": 61.0,
            "adr": 120.0,
            "fkpr": 0.13,
            "fdpr": 0.14,
            "hs_pct": 19.0,
        },
    ]
)


@pytest.fixture
def tables():
    return build_tables(MATRIX, EVENTS, CLUSTERS, PROFILES, PLAYERS)


def test_one_pick_per_agent_and_ten_pairs_per_composition(tables):
    assert len(tables["Compositions"]) == 4
    assert tables["Picks"].groupby("CompID").size().eq(5).all()
    assert tables["Paires"].groupby("CompID").size().eq(10).all()


def test_results_are_carried_to_every_fact(tables):
    comps = tables["Compositions"].set_index("CompID")
    assert comps["Victoire"].sum() == 2
    assert set(comps["Résultat"]) == {"Victoire", "Défaite"}
    picks = tables["Picks"].merge(
        comps[["Victoire"]], left_on="CompID", right_index=True, suffixes=("", "_c")
    )
    assert (picks["Victoire"] == picks["Victoire_c"]).all()


def test_dimension_keys_are_unique_and_cover_the_facts(tables):
    for dim, key in [
        ("Agents", "Agent"),
        ("Maps", "Map"),
        ("Equipes", "Équipe"),
        ("Evenements", "Événement"),
    ]:
        assert tables[dim][key].is_unique, dim
    for fact in ("Compositions", "Picks", "Paires", "Joueurs"):
        assert set(tables[fact]["Équipe"]) <= set(tables["Equipes"]["Équipe"]), fact
        assert set(tables[fact]["Événement"]) <= set(tables["Evenements"]["Événement"]), fact
    assert set(tables["Picks"]["Agent"]) <= set(tables["Agents"]["Agent"])


def test_events_and_season_steps():
    assert event_label("VCT 2026: EMEA Stage 1") == "EMEA Stage 1"
    assert event_label("Valorant Masters London 2026") == "Masters London"
    assert event_label("Valorant Champions 2026") == "Champions"
    assert season_steps(EVENTS) == {
        "emea_kickoff": "1. Kickoff",
        "masters_santiago": "2. Masters Santiago",
        "emea_stage_1": "3. Stage 1",
    }


def test_labels_and_team_attributes(tables):
    assert "KAY/O" in tables["Agents"]["Nom"].tolist()
    assert tables["Agents"].set_index("Agent").loc["veto", "Rôle"] == "Sentinel"
    teams = tables["Equipes"].set_index("Équipe")
    assert teams.loc["FNATIC", "Région"] == "EMEA"  # region of its league, not of the Masters
    assert teams.loc["GIANTX", "Profil tactique"] == "Échantillon faible"
    comps = tables["Compositions"].set_index("CompID")
    assert comps.loc["m1__FNATIC", "Archétype"] == "Omen + Neon + Sova"
    assert comps.loc["m2__FNATIC", "Archétype"] == "(non classée)"


def test_players_keep_multi_word_names(tables):
    players = tables["Joueurs"].set_index("Joueur")
    assert players.loc["lovers rock", "Équipe"] == "BBL Esports"
    assert players["KAST"].max() <= 1


def test_composition_without_five_agents_fails():
    with pytest.raises(ValueError, match="exactly 5 agents"):
        build_tables(MATRIX.iloc[1:], EVENTS, CLUSTERS, PROFILES, PLAYERS)


def test_agent_without_role_fails():
    bad = MATRIX.copy()
    bad.loc[0, "agent"] = "newagent"
    with pytest.raises(ValueError, match="newagent"):
        build_tables(bad, EVENTS, CLUSTERS, PROFILES, PLAYERS)


def test_versioned_powerbi_data_is_up_to_date(tmp_path):
    """The CSVs read by the Power BI report match what the builder produces."""
    for name, df in build(tmp_path).items():
        committed = pd.read_csv(OUT_DIR / f"{name}.csv")
        pd.testing.assert_frame_equal(
            df.reset_index(drop=True), committed, check_dtype=False, obj=name
        )

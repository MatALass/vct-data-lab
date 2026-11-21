import pandas as pd
import pytest

from vlr_analytics.powerbi_model import OUT_DIR, UNKNOWN_TEAM, build_tables

COMPS = pd.DataFrame(
    [
        {
            "event": "emea_stage_1",
            "map": "BIND",
            "match_id": "m1",
            "team": "FNATIC",
            "opponent": "GIANTX",
            "agents": "omen,neon,sova,killjoy,fade",
            "agents_count": 5,
            "observed": True,
        },
        {
            "event": "emea_stage_1",
            "map": "BIND",
            "match_id": "m1",
            "team": "GIANTX",
            "opponent": "FNATIC",
            "agents": "viper,neon,kayo,cypher,miks",
            "agents_count": 5,
            "observed": True,
        },
    ]
)
CLUSTERS = COMPS.assign(cluster_label=["omen + neon + sova", "viper + neon + kayo"])
PROFILES = pd.DataFrame(
    {
        "team": ["FNATIC", "GIANTX"],
        "tactical_profile_label": ["stable_core", "flexible_pool"],
        "tactical_profile_score": [0.61, 0.42],
        "composition_reuse_rate": [0.5, 0.2],
    }
)
PLAYERS = pd.DataFrame(
    [
        {
            "player": "Boaster",
            "team": "FNC",
            "agents": "omen,astra",
            "inferred_role": "Controller",
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
            "player": "lovers",
            "team": "rock",
            "agents": "jett",
            "inferred_role": "Duelist",
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
    return build_tables(COMPS, CLUSTERS, PROFILES, PLAYERS)


def test_one_pick_per_agent_and_ten_pairs_per_composition(tables):
    assert tables["Picks"].groupby("CompID").size().eq(5).all()
    assert tables["Paires"].groupby("CompID").size().eq(10).all()
    assert tables["Paires"]["Paire"].str.contains(r" \+ ").all()


def test_dimension_keys_are_unique_and_cover_the_facts(tables):
    for dim, key in [
        ("Agents", "Agent"),
        ("Maps", "Map"),
        ("Equipes", "Équipe"),
        ("Evenements", "Événement"),
    ]:
        assert tables[dim][key].is_unique, dim
    for fact in ("Compositions", "Picks", "Paires"):
        assert set(tables[fact]["Map"]) <= set(tables["Maps"]["Map"])
        assert set(tables[fact]["Équipe"]) <= set(tables["Equipes"]["Équipe"])
    assert set(tables["Picks"]["Agent"]) <= set(tables["Agents"]["Agent"])
    assert set(tables["Joueurs"]["Équipe"]) <= set(tables["Equipes"]["Équipe"])


def test_labels_are_readable(tables):
    assert tables["Maps"]["Map"].tolist() == ["Bind"]
    assert "KAY/O" in tables["Agents"]["Nom"].tolist()
    assert tables["Agents"].set_index("Agent").loc["miks", "Rôle"] == "Controller"
    assert tables["Compositions"]["Archétype"].iloc[0] == "Omen + Neon + Sova"
    assert tables["Evenements"]["Nom événement"].tolist() == ["EMEA Stage 1"]


def test_player_team_codes_map_to_full_names(tables):
    teams = tables["Joueurs"].set_index("Joueur")["Équipe"]
    assert teams["Boaster"] == "FNATIC"
    assert teams["lovers"] == UNKNOWN_TEAM
    assert tables["Joueurs"]["KAST"].max() <= 1


def test_agent_without_role_fails():
    bad = COMPS.assign(agents="omen,neon,sova,killjoy,newagent")
    with pytest.raises(ValueError, match="newagent"):
        build_tables(bad, CLUSTERS, PROFILES, PLAYERS)


def test_versioned_powerbi_data_is_up_to_date(tmp_path):
    """The CSVs read by the Power BI report match what the builder produces."""
    from vlr_analytics.powerbi_model import build

    fresh = build(tmp_path)
    for name, df in fresh.items():
        committed = pd.read_csv(OUT_DIR / f"{name}.csv")
        pd.testing.assert_frame_equal(
            df.reset_index(drop=True), committed, check_dtype=False, obj=name
        )

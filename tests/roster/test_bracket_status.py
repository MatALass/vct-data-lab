"""Règles d'élimination du suivi de bracket (module vct_roster)."""

import pandas as pd
import pytest

from vct_roster.bracket_status import (
    BRACKET_COLUMNS,
    DEFAULT_XLSX,
    compute_eliminated_teams,
    load_bracket_results,
    stage_from_sheet_name,
)


def test_default_paths_point_to_roster_data():
    assert DEFAULT_XLSX.parts[-3:] == ("data", "roster", "vct.xlsx")
    assert DEFAULT_XLSX.exists()


@pytest.mark.parametrize(
    ("sheet", "expected"),
    [
        ("Classement PrePlayin 12-08", None),
        ("Classement Groupes", None),
        ("Playin 14-08", "Playin"),
        ("Play-In J2", "Playin"),
        ("Playoffs 20-08", "Playoffs"),
    ],
)
def test_stage_from_sheet_name(sheet, expected):
    assert stage_from_sheet_name(sheet) == expected


def test_only_lower_bracket_losers_are_eliminated():
    df = pd.DataFrame(
        [
            ["Playoffs", "R1", "Upper", "FNC", "TH", "FNC"],
            ["Playoffs", "R2", "Lower", "TH", "KC", "KC"],
            ["Playoffs", "R2", "Lower", "VIT", "GX", "PRX"],  # winner invalide, ignorée
            ["Playin", "R1", "Lower", "BBL", "FUT", "BBL"],  # autre stage
        ],
        columns=BRACKET_COLUMNS,
    )
    assert compute_eliminated_teams(df, "Playoffs") == {"TH"}


def test_missing_results_file_is_created_empty(tmp_path):
    path = tmp_path / "bracket_results.csv"
    df = load_bracket_results(path)
    assert df.empty and path.exists()
    assert list(pd.read_csv(path).columns) == BRACKET_COLUMNS


def test_missing_columns_raise(tmp_path):
    path = tmp_path / "bracket_results.csv"
    pd.DataFrame([["Playoffs", "FNC"]], columns=["stage", "winner"]).to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_bracket_results(path)

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup

from vct_ranker.agents import normalize_agent_name
from vct_ranker.roles import enrich_player_roles, infer_player_role
from vct_ranker.vct import VctEvent

VLR_BASE_URL = "https://www.vlr.gg"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VCTRoleRanker/0.1; +https://example.local)",
    "Accept-Language": "en-US,en;q=0.9",
}

STAT_COLUMNS = [
    "rating",
    "acs",
    "kd",
    "kast",
    "adr",
    "kpr",
    "apr",
    "fkpr",
    "fdpr",
    "hs_pct",
]


@dataclass(frozen=True)
class VlrStatsQuery:
    event_id: int | None = None
    direct_url: str | None = None
    region: str | None = None
    timespan: str = "all"
    min_rounds: int = 0
    maps: str = "all"
    agents: str = "all"

    def to_url(self) -> str:
        if self.direct_url:
            params: dict[str, str | int] = {
                "timespan": self.timespan,
                "min_rounds": self.min_rounds,
                "maps": self.maps,
                "agents": self.agents,
            }
            return f"{self.direct_url}?{urlencode(params)}"

        params: dict[str, str | int] = {
            "event_id": self.event_id or "all",
            "region": self.region or "all",
            "timespan": self.timespan,
            "min_rounds": self.min_rounds,
            "maps": self.maps,
            "agents": self.agents,
        }
        return f"{VLR_BASE_URL}/stats/?{urlencode(params)}"


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strip_team_suffix_from_player(player: str, team: str | None) -> tuple[str, str | None]:
    player = clean_text(player)
    team = clean_text(team) if team else None
    if team and player and player != team:
        suffix = f" {team}"
        if player.endswith(suffix):
            player = player[: -len(suffix)].strip()
    return player or "Unknown", team


def parse_float(value: str | None) -> float | None:
    text = clean_text(value).replace("%", "")
    if not text or text in {"-", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    text = clean_text(value).replace(",", "")
    if not text or text in {"-", "nan"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _extract_agents(row) -> list[str]:
    agents: list[str] = []
    for img in row.select("img[src*='/agents/']"):
        src = img.get("src", "")
        agent = normalize_agent_name(src.split("/")[-1])
        if agent and agent not in agents:
            agents.append(agent)
    return agents


def _extract_player_and_team(row) -> tuple[str, str | None]:
    """Extract player and team without breaking multi-word player names.

    VLR renders the player cell as ``div.st-pl-name`` (nickname) and
    ``div.st-pl-country`` (team tag). Reading these two nodes keeps a nickname
    such as ``lovers rock`` whole; the old whitespace split turned it into
    player=``lovers`` and team=``rock``.
    """
    player_cell = row.select_one("td.mod-player") or row.select_one("td:nth-of-type(1)")
    if player_cell is None:
        return "Unknown", None

    name_node = player_cell.select_one(".st-pl-name, .text-of")
    if name_node is not None:
        player = clean_text(name_node.get_text(" ", strip=True))
        team_node = player_cell.select_one(".st-pl-country, .stats-player-country, .mod-team")
        team = clean_text(team_node.get_text(" ", strip=True)) if team_node else ""
        return player or "Unknown", team or None

    # Older markup without dedicated nodes: never split a nickname on spaces,
    # the team tag is the last token only if it looks like a tag (no lowercase).
    text = clean_text(player_cell.get_text(" ", strip=True))
    if not text:
        return "Unknown", None
    head, _, last = text.rpartition(" ")
    if head and last and not any(c.islower() for c in last):
        return head, last
    return text, None


# Header text of the VLR stats table -> output column.
HEADER_COLUMNS = {
    "MAPS": "maps",
    "RND": "rounds",
    "R": "rating",
    "R2.0": "rating",
    "ACS": "acs",
    "K:D": "kd",
    "KAST": "kast",
    "ADR": "adr",
    "KPR": "kpr",
    "APR": "apr",
    "FKPR": "fkpr",
    "FDPR": "fdpr",
    "HS%": "hs_pct",
    "FK": "fk",
    "FD": "fd",
}
INT_COLUMNS = {"maps", "rounds", "fk", "fd"}


def parse_stats_table(html: str) -> list[dict]:
    """Rows of a VLR player stats page, columns located by their header text.

    VLR added columns over time (MAPS, FK:FD, FK%...), so positions are not stable.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.st-table, table.wf-table") or soup.find("table")
    if table is None:
        return []
    headers = [clean_text(th.get_text(" ", strip=True)).upper() for th in table.select("thead th")]
    positions = {HEADER_COLUMNS[h]: i for i, h in enumerate(headers) if h in HEADER_COLUMNS}

    records: list[dict] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        player, team = _extract_player_and_team(row)
        texts = [clean_text(c.get_text(" ", strip=True)) for c in cells]
        values: dict = {}
        for column, i in positions.items():
            raw = texts[i] if i < len(texts) else None
            values[column] = parse_int(raw) if column in INT_COLUMNS else parse_float(raw)
        rounds = values.get("rounds")
        if rounds and "fkpr" not in positions and values.get("fk") is not None:
            values["fkpr"] = round(values["fk"] / rounds, 3)
        if rounds and "fdpr" not in positions and values.get("fd") is not None:
            values["fdpr"] = round(values["fd"] / rounds, 3)
        agents = _extract_agents(row)
        role, confidence = infer_player_role(agents)
        records.append(
            {
                "player": player,
                "team": team,
                "agents": ",".join(agents),
                "inferred_role": role,
                "role_confidence": confidence,
                **{column: values.get(column) for column in ["maps", "rounds", *STAT_COLUMNS]},
            }
        )
    return records


def scrape_vlr_player_stats(query: VlrStatsQuery, *, polite_delay: float = 0.7) -> pd.DataFrame:
    """Scrape VLR's public HTML stats table.

    This intentionally avoids private APIs. VLR markup can change, so parsing is defensive:
    missing metrics become null instead of crashing the whole app.
    """
    url = query.to_url()
    time.sleep(polite_delay)
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()

    records = [
        {**r, "source_url": url, "event_id": query.event_id}
        for r in parse_stats_table(response.text)
    ]
    df = pd.DataFrame(records)
    if df.empty:
        return df

    return df.drop_duplicates(subset=["player", "team"]).sort_values(
        ["inferred_role", "rating", "acs", "player"],
        ascending=[True, False, False, True],
    )


def scrape_vct_events(
    events: list[VctEvent], *, min_rounds: int = 0, timespan: str = "all"
) -> pd.DataFrame:
    """Scrape only configured VCT events and add region/event metadata.

    This is stricter than using VLR's global stats page: every returned player comes
    from one of the configured VCT regional league events.
    """
    frames: list[pd.DataFrame] = []

    for event in events:
        query = VlrStatsQuery(
            event_id=event.event_id,
            direct_url=event.stats_url,
            min_rounds=min_rounds,
            timespan=timespan,
        )
        frame = scrape_vlr_player_stats(query)
        if frame.empty:
            continue

        frame["vct_region"] = event.region
        frame["event_name"] = event.name
        frame["event_stage"] = event.stage
        frame["event_id"] = event.event_id
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["vct_region", "event_id", "player", "team"])
    df = enrich_player_roles(df)
    return df.sort_values(
        ["vct_region", "inferred_role", "rating", "acs", "player"],
        ascending=[True, True, False, False, True],
    )


def scrape_multiple_events(event_ids: list[int], *, min_rounds: int = 100) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for event_id in event_ids:
        query = VlrStatsQuery(event_id=event_id, min_rounds=min_rounds)
        frame = scrape_vlr_player_stats(query)
        if not frame.empty:
            frame["event_id"] = event_id
            frames.append(frame)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["event_id", "player", "team"])
    return enrich_player_roles(df)

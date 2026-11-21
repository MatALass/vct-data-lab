"""Scraper of a full VCT season on vlr.gg (HTML pages only, no private API).

For every event listed on ``https://www.vlr.gg/vct-<season>``:

- the agents page gives the pick rates per map (summary table) and, for each team
  and each map, the list of games with the opponent, the result and the five agents
  (a JSON block rendered in the page, one ``picks`` bit string aligned on the header);
- the stats page gives the player stats, with the team as a short tag (``FNC``);
- the team pages give the tag of each team, to join players to the full team names.

Outputs (``data/raw``): ``vlr_events.csv``, ``vlr_agents_summary_raw.csv``,
``vlr_agents_matrix_raw.csv`` (one row per team, game and agent), ``vlr_teams.csv``
and ``vlr_players_raw.csv``.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from vct_ranker.scraper import parse_stats_table
from vlr_analytics.config import (
    RAW_EVENTS,
    RAW_MATRIX,
    RAW_PLAYERS,
    RAW_SUMMARY,
    RAW_TEAMS,
    VCT_SEASON,
    VLR_BASE_URL,
)
from vlr_analytics.utils import clean_text, normalize_map_name, write_csv

HEADERS = {"User-Agent": "Mozilla/5.0 (vct-data-lab; github.com/MatALass/vct-data-lab)"}
REGIONS = ("Americas", "EMEA", "Pacific", "China")
MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        start=1,
    )
}


class VlrClient:
    """requests session with a polite delay and a few retries."""

    def __init__(self, delay: float = 1.0, retries: int = 3) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay
        self.retries = retries

    def get(self, path: str) -> str:
        url = path if path.startswith("http") else f"{VLR_BASE_URL}{path}"
        for attempt in range(1, self.retries + 1):
            time.sleep(self.delay)
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                time.sleep(5 * attempt)
        raise RuntimeError("unreachable")


# --------------------------------------------------------------------------- #
# Parsers (pure functions, tested on HTML fixtures)
# --------------------------------------------------------------------------- #
def event_key(slug: str, season: int = VCT_SEASON) -> str:
    """``vct-2026-emea-stage-1`` -> ``emea_stage_1``.

    ``valorant-masters-london-2026`` -> ``masters_london``.
    """
    key = slug.replace(f"vct-{season}-", "").replace("valorant-", "").replace(f"-{season}", "")
    return key.replace("-", "_")


def event_phase(name: str) -> str:
    for phase in ("Kickoff", "Stage 1", "Stage 2", "Masters", "Champions"):
        if phase.lower() in name.lower():
            return phase
    return "Other"


def event_region(name: str) -> str:
    return next((r for r in REGIONS if r.lower() in name.lower()), "International")


def parse_season_events(html: str, season: int = VCT_SEASON) -> pd.DataFrame:
    """Events of the season page, ordered by start date."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.select("a.event-item[href^='/event/']"):
        match = re.match(r"^/event/(\d+)/([^/?#]+)", a["href"])
        if not match:
            continue
        title = a.select_one(".event-item-title")
        name = clean_text(
            title.get_text(" ", strip=True)
            if title
            else a.get_text(" ", strip=True).split(" Completed")[0]
        )
        text = clean_text(a.get_text(" ", strip=True))
        start = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})\b", text)
        start_date = date(season, MONTHS[start.group(1)], int(start.group(2))) if start else None
        rows.append(
            {
                "event_id": int(match.group(1)),
                "slug": match.group(2),
                "event": event_key(match.group(2), season),
                "event_name": name,
                "region": event_region(name),
                "phase": event_phase(name),
                "start_date": start_date,
            }
        )
    events = pd.DataFrame(rows).drop_duplicates("event_id")
    if events.empty:
        raise ValueError("no event found on the season page")
    events = events.sort_values(["start_date", "event_id"], na_position="last").reset_index(
        drop=True
    )
    events["event_order"] = range(1, len(events) + 1)
    return events


def agent_from_src(src: str | None) -> str:
    if not src:
        return "unknown"
    return src.split("/")[-1].replace(".png", "").strip().lower()


def parse_agents_summary(html: str, event: str) -> pd.DataFrame:
    """Global table of the agents page: maps played, ATK/DEF win rate, pick rate per agent."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.mod-pr-global") or soup.find("table")
    if table is None:
        return pd.DataFrame()
    header = table.find("tr")
    agents = [agent_from_src(img.get("src")) for img in header.select("img[src*='/agents/']")]
    records = []
    for row in table.select("tr.pr-global-row"):
        cells = row.find_all("td")
        if len(cells) < 4 + len(agents):
            continue
        for agent, cell in zip(agents, cells[4 : 4 + len(agents)], strict=False):
            records.append(
                {
                    "event": event,
                    "raw_map": clean_text(cells[0].get_text(" ", strip=True)),
                    "raw_maps_played": clean_text(cells[1].get_text(strip=True)),
                    "raw_atk_win_rate": clean_text(cells[2].get_text(strip=True)),
                    "raw_def_win_rate": clean_text(cells[3].get_text(strip=True)),
                    "agent": agent,
                    "raw_pick_rate": clean_text(cell.get_text(strip=True)),
                }
            )
    return pd.DataFrame(records)


def parse_agents_matrix(html: str, event: str) -> pd.DataFrame:
    """One row per team, game (map) and agent, from the per-map matrices of the agents page."""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for container in soup.select(".pr-matrix-map"):
        header = container.find("tr")
        if header is None:
            continue
        map_name = normalize_map_name(header.find("th").get_text(" ", strip=True))
        agents = [agent_from_src(img.get("src")) for img in header.select("img[src*='/agents/']")]
        for row in container.select("tr.pr-matrix-row"):
            script = row.select_one("script[type='application/json']")
            if script is None:
                continue
            team_link = row.select_one("td a[href^='/team/']")
            name_node = row.select_one("td .text-of") or row.find("td")
            team = clean_text(name_node.get_text(" ", strip=True))
            team_id = re.search(r"/team/(\d+)", team_link["href"]).group(1) if team_link else None
            for game in json.loads(script.string or script.get_text()):
                game_id = re.search(r"game=(\d+)", game.get("link", ""))
                picks = game.get("picks", "")
                picked = [agent for agent, bit in zip(agents, picks, strict=False) if bit == "1"]
                for agent in picked:
                    records.append(
                        {
                            "event": event,
                            "map": map_name,
                            "game_id": game_id.group(1) if game_id else None,
                            "team": team,
                            "team_id": team_id,
                            "opponent": clean_text(game.get("opp_name", "")),
                            "result": game.get("result"),
                            "agent": agent,
                        }
                    )
    return pd.DataFrame(records)


def parse_event_teams(html: str) -> dict[str, str]:
    """Team id -> slug of the teams linked from an event page."""
    out = {}
    for a in BeautifulSoup(html, "html.parser").select("a[href^='/team/']"):
        match = re.match(r"^/team/(\d+)/([^/?#]+)", a["href"])
        if match:
            out[match.group(1)] = match.group(2)
    return out


def parse_team_page(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    name = soup.select_one(".team-header h1")
    tag = soup.select_one(".team-header-tag")
    return {
        "team": clean_text(name.get_text(" ", strip=True)) if name else "",
        "tag": clean_text(tag.get_text(" ", strip=True)) if tag else "",
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def scrape_season(
    season: int = VCT_SEASON, out_dir: Path | None = None, delay: float = 1.0
) -> dict[str, pd.DataFrame]:
    client = VlrClient(delay=delay)
    events = parse_season_events(client.get(f"/vct-{season}"), season)
    summaries, matrices, players = [], [], []
    team_ids: dict[str, str] = {}
    for i, ev in enumerate(events.itertuples(), start=1):
        agents_html = client.get(f"/event/agents/{ev.event_id}/{ev.slug}")
        summaries.append(parse_agents_summary(agents_html, ev.event))
        matrix = parse_agents_matrix(agents_html, ev.event)
        matrices.append(matrix)
        team_ids.update(parse_event_teams(client.get(f"/event/{ev.event_id}/{ev.slug}")))
        stats = pd.DataFrame(
            parse_stats_table(
                client.get(f"/event/stats/{ev.event_id}/{ev.slug}?timespan=all&min_rounds=0")
            )
        )
        if not stats.empty:
            players.append(stats.assign(event=ev.event, event_id=ev.event_id))
        print(
            f"[{i}/{len(events)}] {ev.event}: "
            f"{matrix['game_id'].nunique() if not matrix.empty else 0} maps, {len(stats)} players"
        )

    for matrix in matrices:
        if not matrix.empty:
            team_ids.update(
                {tid: "" for tid in matrix["team_id"].dropna().unique() if tid not in team_ids}
            )
    teams = []
    for team_id, slug in sorted(team_ids.items()):
        page = parse_team_page(
            client.get(f"/team/{team_id}/{slug}" if slug else f"/team/{team_id}")
        )
        teams.append({"team_id": team_id, **page})

    tables = {
        "events": events,
        "summary": pd.concat(summaries, ignore_index=True),
        "matrix": pd.concat(matrices, ignore_index=True),
        "teams": pd.DataFrame(teams),
        "players": pd.concat(players, ignore_index=True) if players else pd.DataFrame(),
    }
    paths = {
        "events": RAW_EVENTS,
        "summary": RAW_SUMMARY,
        "matrix": RAW_MATRIX,
        "teams": RAW_TEAMS,
        "players": RAW_PLAYERS,
    }
    for name, df in tables.items():
        path = paths[name] if out_dir is None else out_dir / paths[name].name
        write_csv(df, path)
    return tables


def scrape_all(output_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    return scrape_season(VCT_SEASON, output_dir)


if __name__ == "__main__":
    scrape_all()

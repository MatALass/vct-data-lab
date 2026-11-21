# VCT Data Lab

<p align="center">
  <strong>Competitive Valorant analytics, role inference, player ranking and playoff simulation.</strong>
</p>

<p align="center">
  <a href="https://github.com/MatALass/VCT-Data-Lab">
    <img src="https://img.shields.io/badge/status-active-success?style=for-the-badge" alt="Project status">
  </a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/tests-122%20passed-brightgreen?style=for-the-badge&logo=pytest" alt="Tests">
  <img src="https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Streamlit-apps-FF4B4B?style=for-the-badge&logo=streamlit" alt="Streamlit">
  <img src="https://img.shields.io/badge/React-frontends-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-frontend-3178C6?style=for-the-badge&logo=typescript" alt="TypeScript">
</p>

---

## Overview

**VCT Data Lab** is a full-stack analytics project focused on professional Valorant esports.

It combines eight previously separate projects into one unified, maintainable repository:

1. a VLR.gg analytics pipeline,
2. legacy VLR scraping and exploratory notebooks,
3. an Elo-based VCT role ranker,
4. a tournament-based VCT role ranker,
5. a playoff odds simulator with CLI, Streamlit and React interfaces,
6. **Meta Lens**: a Power BI star schema on the full 2025 VCT season (ex `vct-meta-lens`),
7. **Roster tracker**: daily roster and team ranking follow-up for VCT 2026 EMEA (ex `vct-roster-analytics`),
8. **Kickoff simulator**: a triple-elimination bracket and worst-to-best ranker (ex `vct-emea-kickoff-simulator`).

The last three were merged with their git history kept.

The goal is not only to display statistics, but to build a structured analytics platform with reproducible data processing, business rules, role inference, data-quality checks, APIs, dashboards and simulation tooling.

This project was developed by **Mathieu Alassoeur**.

---

## Project scope

VCT Data Lab currently covers six analytical areas:

| Module                     | Purpose                                                                                  |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| **VLR Analytics**          | Scrape, clean, transform and model Valorant agent/team composition data from VLR.gg      |
| **VCT Role Ranker**        | Infer player roles, compare players through duels, and build user-driven rankings        |
| **Playoff Odds Simulator** | Simulate qualification/playoff scenarios using Monte Carlo logic and what-if assumptions |
| **Meta Lens (Power BI)**   | Season-long meta: 15 tournaments, 59 teams, 349 players, 100,000+ kills, star schema and PBIP report |
| **Roster tracker**         | Daily ranking snapshots in Excel, transfers, eliminated teams highlighted from bracket results |
| **Kickoff simulator**      | Triple-elimination Kickoff bracket (BO3/BO5) and an interactive worst-to-best ranker |

---

## Why this project matters

Valorant esports data is messy, contextual and often difficult to interpret directly.

A simple table of agents played is not enough to understand a player profile. For example:

* Viper is often played by Sentinel/Flex profiles rather than pure Controllers.
* Chamber can behave like a Duelist in some pools, but like a Sentinel in others.
* Some teams use double Duelist setups.
* Some players should be classified as Flex because they cover multiple tactical needs.
* Roster changes can create misleading role duplication if the data is read naively.

VCT Data Lab tries to address these issues with explicit data processing rules and inspectable outputs rather than black-box assumptions.

---

## Main features

### 1. VLR Analytics Pipeline

The `vlr_analytics` module provides a reproducible data pipeline:

* VLR.gg scraping with Playwright,
* raw-to-processed transformations,
* analytical marts,
* descriptive modeling outputs,
* FastAPI endpoints,
* React dashboard,
* data-quality reports.

Main CLI commands:

```bash
vlr scrape
vlr process
vlr build-marts
vlr model
vlr full-run --skip-scrape
vlr api
```

The API exposes project metadata, health checks, available tables and analytical outputs.

Useful local URLs after running `vlr api`:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

---

### 2. Data-quality reporting

The processing pipeline validates Valorant team compositions.

A valid Valorant composition should normally contain exactly five unique agents for one team on one map.

If anomalies are detected, the pipeline does not fail silently. It writes a quality report:

```text
data/reports/invalid_compositions.csv
```

The report contains:

```text
event,map,match_id,team,opponent,agents_count,expected_agents_count,agents,reason
```

This makes scraping or source-data issues explicit and auditable.

---

### 3. VCT Role Ranker

The role ranker provides two modes:

```bash
python -m streamlit run apps/role_ranker_streamlit/tournament_app.py
python -m streamlit run apps/role_ranker_streamlit/elo_app.py
```

Tournament mode is the recommended mode.

The role inference system uses competitive Valorant-specific business rules instead of only counting the top three agents.

Role logic includes:

* Viper is treated as Sentinel-side / Flex-side zone control, not as a pure Controller.
* Chamber is treated as Duelist only in Duelist + Chamber pools.
* Duelist + Sentinel profiles are usually Sentinel or Flex depending on team context.
* Duelist + Initiator or Duelist + Controller profiles usually become Flex.
* Double Duelist lineups are allowed.
* Double Sentinel lineups in stable five-player teams are normalized when one player has Flex evidence.
* Teams should normally cover Duelist, Controller/Smoker, Initiator and Sentinel.
* Flex is expected unless the team clearly runs two locked Duelist profiles.

The Streamlit interface includes role-quality inspection so that inferred roles can be reviewed manually.

---

### 4. Playoff Odds Simulator

The former playoff odds project is integrated as a separate module:

```text
src/playoff_odds/
```

It includes:

* Monte Carlo qualification simulations,
* ranking and tie-break logic,
* what-if scenarios,
* JSON/CSV exports,
* CLI commands,
* Streamlit interface,
* preserved React/Vite frontend.

Main commands:

```bash
playoff-odds list-remaining-matches --config data/playoff_odds/config.sample.json

playoff-odds-simulate \
  --config data/playoff_odds/config.sample.json \
  --output-json data/playoff_odds/vct-emea-2026.json \
  --output-dir data/playoff_odds/output

playoff-odds-what-if \
  --config data/playoff_odds/config.sample.json \
  --output-json data/playoff_odds/vct-emea-2026-whatif.json \
  --force "GX vs EF=GX"
```

Streamlit app:

```bash
python -m streamlit run apps/playoff_odds_streamlit/app.py
```

React app:

```bash
cd apps/playoff_odds_react
npm install
npm run dev
```

### 5. Meta Lens: season-long meta in Power BI

Pipeline from the VLR.gg Kaggle export to a star schema and a Power BI project written as code
(TMDL + PBIR, generated with [pbip-generator](https://github.com/MatALass/pbip-generator)).
Full write-up, dataset pitfalls and data model: [docs/meta_lens/README.md](docs/meta_lens/README.md).

```bash
pip install -e ".[ingest,powerbi]"
python -m vct_meta_lens.ingest        # Kaggle CSV -> data/meta_lens/raw/
python -m vct_meta_lens.clean         # -> data/meta_lens/processed/*.parquet
python -m vct_meta_lens.build_model   # -> data/meta_lens/model/*.csv (star schema)
python powerbi/meta_lens/build_report.py --data-folder "<absolute path to data/meta_lens/model/>"
```

Then open `powerbi/meta_lens/VCTMetaLens/VCTMetaLens.pbip` in Power BI Desktop and refresh.
The CI regenerates the PBIP and fails if the committed project differs from the script.

### 6. Roster tracker (VCT 2026 EMEA)

```bash
python -m vct_roster.run_daily              # scrape, add a dated sheet to data/roster/vct.xlsx, compare
python -m streamlit run apps/roster_streamlit/app.py
```

Details: [docs/roster/README.md](docs/roster/README.md).

### 7. Kickoff simulator

```bash
python -m streamlit run apps/kickoff_streamlit/Home.py
```

Details: [docs/kickoff/README.md](docs/kickoff/README.md).

---

## Repository structure

```text
VCT-Data-Lab/
├── apps/
│   ├── playoff_odds_react/          # React frontend for playoff odds
│   ├── playoff_odds_streamlit/      # Streamlit playoff odds app
│   ├── role_ranker_streamlit/       # Streamlit role ranker apps
│   ├── roster_streamlit/            # Roster tracker dashboard
│   └── kickoff_streamlit/           # Kickoff bracket simulator
│
├── data/
│   ├── legacy_2026_agents/          # Preserved legacy data
│   ├── meta_lens/                   # Meta Lens raw/processed/model (not versioned)
│   ├── roster/                      # Roster tracker workbook, roles, bracket results
│   ├── marts/                       # Analytical marts
│   ├── models/                      # Modeling outputs
│   ├── playoff_odds/                # Playoff simulator configs/outputs
│   ├── processed/                   # Processed datasets
│   ├── raw/                         # Raw scraped datasets
│   ├── reports/                     # Data-quality reports
│   └── role_ranker/                 # Ranker local data/state
│
├── docs/                            # Technical documentation (one folder per merged module)
├── powerbi/meta_lens/               # Power BI report as code + generated PBIP
├── frontend/                        # React frontend for VLR analytics
├── notebooks/                       # Preserved exploratory notebooks
├── scripts/                         # Utility scripts
├── src/
│   ├── playoff_odds/                # Playoff odds simulation engine
│   ├── vct_ranker/                  # Tournament role ranker
│   ├── vct_ranker_elo/              # Legacy Elo role ranker
│   ├── vct_meta_lens/               # Meta Lens pipeline (ingest, clean, star schema)
│   ├── vct_roster/                  # Roster tracker scripts
│   └── vlr_analytics/               # VLR analytics pipeline/API
│
└── tests/                           # Python test suite
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/MatALass/VCT-Data-Lab.git
cd VCT-Data-Lab
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -e ".[dev]"
```

### 4. Install Playwright browser

```bash
python -m playwright install chromium
```

---

## Run the Python test suite

```bash
python -m pytest
```

Expected result:

```text
122 passed
```

---

## Run the VLR Analytics API

```bash
vlr api
```

Then open:

```text
http://127.0.0.1:8000/docs
```

---

## Run the VLR Analytics React frontend

```bash
cd frontend
npm install
npm run dev
```

For a production build:

```bash
npm run build
```

---

## Run the Role Ranker apps

Tournament mode:

```bash
python -m streamlit run apps/role_ranker_streamlit/tournament_app.py
```

Legacy Elo mode:

```bash
python -m streamlit run apps/role_ranker_streamlit/elo_app.py
```

---

## Run the Playoff Odds apps

Streamlit version:

```bash
python -m streamlit run apps/playoff_odds_streamlit/app.py
```

React version:

```bash
cd apps/playoff_odds_react
npm install
npm run dev
```

For a production build:

```bash
npm run build
```

---

## Validation status

The project has been validated with:

```text
Python tests: 122 passed (CI on every push)
VLR React frontend: build passed
Playoff Odds React frontend: build passed
Playoff Odds npm audit: 0 vulnerabilities
```

---

## Methodological notes

This project is descriptive and analytical.

It does **not** claim to estimate true player skill, hidden team strength, or guaranteed match outcomes.

The modeling layer focuses on:

* agent presence,
* role structure,
* composition stability,
* team identity,
* descriptive tactical patterns,
* qualification probability under explicit simulation assumptions.

The role-ranker logic is rule-based and inspectable. This makes the system easier to debug than a black-box model, but it also means that edge cases require explicit business rules.

---

## Data policy

Generated caches and build artifacts are intentionally excluded from the repository.

Preserved datasets remain under `data/` so the project can be inspected without rerunning every scraper.

The notebooks are kept for transparency and historical exploration, but the main production logic lives under `src/`.

---

## Tech stack

| Area            | Tools                     |
| --------------- | ------------------------- |
| Data processing | Python, pandas            |
| Scraping        | Playwright                |
| API             | FastAPI, Uvicorn          |
| Apps            | Streamlit                 |
| Frontend        | React, Vite, TypeScript   |
| Simulation      | Python Monte Carlo engine |
| Testing         | pytest                    |
| Packaging       | pyproject.toml            |
| Data outputs    | CSV, JSON                 |

---

## Author

**Mathieu Alassoeur**
Computer Science Engineering Student - Business Intelligence & Analytics
GitHub: [@MatALass](https://github.com/MatALass)

---

## Disclaimer

This project is an independent educational and portfolio project.

It is not affiliated with Riot Games, Valorant Champions Tour, VLR.gg or any esports organization.

Valorant, VCT and related names belong to their respective owners.

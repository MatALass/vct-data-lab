# VCT Roster Analytics

Analyse de rosters et de performance pour la VCT 2026 EMEA (scraping VLR.gg, rôles,
transferts, comparaison Stage 1/Stage 2/Kickoff, vivier Challengers, et suivi
quotidien du classement d'équipe).

## Structure du projet

```
vct-roster-analytics/
├── notebooks/
│   └── roster_analysis.ipynb    # Pipeline complet : scraping -> rôles -> transferts -> export Excel
├── dashboard/
│   └── app.py                    # Dashboard Streamlit (lit le .xlsx généré par le notebook)
├── tracker/
│   ├── update_rankings.py        # A lancer chaque jour : ajoute un onglet daté à data/vct.xlsx
│   ├── compare_rankings.py       # Compare deux jours, écrit un rapport dans output/
│   └── bracket_status.py         # Calcule les équipes éliminées et colorie les lignes en rouge
├── data/
│   ├── vct.xlsx                  # Classement quotidien (méthode somme des rangs par rôle)
│   ├── roles.csv                 # Référence des rôles par joueur (maintenue à la main)
│   ├── bracket_results.csv       # Résultats de matchs Play-In/Playoffs (maintenu à la main)
│   └── *.xlsx                    # Export du notebook (roster_analysis, transferts, etc.)
└── output/
    └── evolution_*.xlsx          # Rapports de comparaison jour/jour (générés, non versionnés)
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Utilisation

**Analyse complète (scraping + rôles + transferts + vivier Challengers)**
Ouvrir et exécuter `notebooks/roster_analysis.ipynb`. Produit un fichier dans `data/`.

**Dashboard interactif**
```bash
streamlit run dashboard/app.py
```
Détecte automatiquement les fichiers `.xlsx` présents dans `data/`.

**Suivi quotidien du classement**
```bash
python tracker/update_rankings.py
```
Ajoute un onglet daté à `data/vct.xlsx`. Si de nouveaux joueurs apparaissent
(transfert, équipe promue), le script le signale — complète `data/roles.csv`
(colonnes `player`, `team_slot`) puis relance.

**Comparer deux jours**
```bash
python tracker/compare_rankings.py
```
Compare automatiquement les deux onglets les plus récents de `data/vct.xlsx` et
écrit un rapport détaillé (par joueur et par équipe) dans `output/`.

**Équipes éliminées en rouge (Play-In / Playoffs)**
Au fur et à mesure des matchs, ajoute une ligne dans `data/bracket_results.csv`
(colonnes `stage, round, bracket_side, team_a, team_b, winner` — `stage` vaut
`Playin` ou `Playoffs`, `bracket_side` vaut `Upper` ou `Lower`). La règle est
automatique et codée dans `tracker/bracket_status.py` : une équipe est
éliminée dès qu'elle **perd un match joué en lower bracket** (une défaite en
upper bracket la fait seulement descendre en lower bracket, elle n'est pas
encore éliminée). `tracker/update_rankings.py` applique cette règle et
colorie en rouge les lignes des équipes éliminées à chaque nouvel onglet.
Pour recolorier les onglets déjà présents dans `vct.xlsx` après avoir ajouté
des résultats (sans relancer tout le scraping) :
```bash
python tracker/bracket_status.py
```

## Méthodologie — points d'attention

- Les scores sont des pistes de lecture statistiques, pas des prédictions : aucune
  donnée de contrat, budget, coaching ou volonté du joueur n'entre dans ces calculs.
- Le classement quotidien (`tracker/`) utilise une méthode par rangs (somme des rangs
  de rating par rôle) ; le notebook (`notebooks/`) utilise des z-scores normalisés par
  rôle. Les deux sont légitimes et ne donneront pas exactement le même ordre.
- Une équipe avec un joueur non référencé dans `roles.csv`, ou un doublon de rôle
  (remplaçant + titulaire tous deux assignés), est automatiquement exclue du
  classement du jour plutôt que de fausser le calcul — le script explique toujours
  pourquoi.

## Licence / usage

Projet personnel d'analyse esport, données publiques VLR.gg. Pas d'affiliation
avec Riot Games ou VLR.gg.

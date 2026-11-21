# Dictionnaire de données : VLR2026

Généré par pbip-generator : 8 tables, 22 mesures, 12 relations.

## Tables

| Table | Rôle | Source | Lignes | Colonnes | Mesures |
|---|---|---|---:|---:|---:|
| Compositions | faits | `Compositions.csv` | 464 | 8 | 4 |
| Joueurs | faits | `Joueurs.csv` | 63 | 14 | 8 |
| Paires | faits | `Paires.csv` | 4 640 | 5 | 2 |
| Picks | faits | `Picks.csv` | 2 320 | 5 | 7 |
| Agents | dimension | `Agents.csv` | 27 | 4 | 0 |
| Equipes | dimension | `Equipes.csv` | 49 | 5 | 1 |
| Evenements | dimension | `Evenements.csv` | 4 | 4 | 0 |
| Maps | dimension | `Maps.csv` | 7 | 1 | 0 |

## Schéma du modèle

```mermaid
erDiagram
    T0["Compositions (faits)"] {
        string CompID PK
        string Evenement FK "Événement"
        string Map FK
        string Equipe FK "Équipe"
    }
    T1["Joueurs (faits)"] {
        string Equipe FK "Équipe"
        string Evenement FK "Événement"
    }
    T2["Paires (faits)"] {
        string Evenement FK "Événement"
        string Map FK
        string Equipe FK "Équipe"
    }
    T3["Picks (faits)"] {
        string Evenement FK "Événement"
        string Map FK
        string Equipe FK "Équipe"
        string Agent FK
    }
    T4["Agents (dimension)"] {
        string Agent PK
    }
    T5["Equipes (dimension)"] {
        string Equipe PK "Équipe"
    }
    T6["Evenements (dimension)"] {
        string Evenement PK "Événement"
    }
    T7["Maps (dimension)"] {
        string Map PK
    }
    T3 }o--|| T4 : "Agent"
    T0 }o--|| T5 : "Équipe"
    T1 }o--|| T5 : "Équipe"
    T0 }o--|| T6 : "Événement"
    T0 }o--|| T7 : "Map"
    T3 }o--|| T5 : "Équipe"
    T3 }o--|| T6 : "Événement"
    T3 }o--|| T7 : "Map"
    T2 }o--|| T5 : "Équipe"
    T2 }o--|| T6 : "Événement"
    T2 }o--|| T7 : "Map"
    T1 }o--|| T6 : "Événement"
```

## Grain des tables de faits

- **Compositions** : une ligne par `CompID`
- **Joueurs** : aucune combinaison de ses clés et de ses dates n'est unique : vérifier les doublons
- **Paires** : aucune combinaison de ses clés et de ses dates n'est unique : vérifier les doublons
- **Picks** : aucune combinaison de ses clés et de ses dates n'est unique : vérifier les doublons

### Compositions

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| CompID | string |  | oui |
| Événement | string |  | oui |
| Map | string |  | oui |
| Équipe | string |  | oui |
| Adversaire | string |  | non |
| Match | string |  | oui |
| Agents | string |  | non |
| Archétype | string |  | non |

### Joueurs

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| Joueur | string |  | non |
| Équipe | string |  | oui |
| Événement | string |  | oui |
| Rôle joué | string |  | non |
| Agents joués | string |  | non |
| Rounds | int64 | `#,##0` | oui |
| Rating | double | `#,##0.00` | oui |
| ACS | double | `#,##0.00` | oui |
| KD | double | `#,##0.00` | oui |
| KAST | double | `#,##0.00` | oui |
| ADR | double | `#,##0.00` | oui |
| FKPR | double | `#,##0.00` | oui |
| FDPR | double | `#,##0.00` | oui |
| HS | double | `#,##0.00` | oui |

### Paires

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| CompID | string |  | oui |
| Événement | string |  | oui |
| Map | string |  | oui |
| Équipe | string |  | oui |
| Paire | string |  | non |

### Picks

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| CompID | string |  | oui |
| Événement | string |  | oui |
| Map | string |  | oui |
| Équipe | string |  | oui |
| Agent | string |  | oui |

### Agents

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| Agent | string |  | oui |
| Nom | string |  | non |
| Rôle | string |  | non |
| Ordre rôle | int64 | `#,##0` | oui |

### Equipes

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| Équipe | string |  | non |
| Région | string |  | non |
| Profil tactique | string |  | non |
| Score profil | double | `#,##0.00` | oui |
| Taux de réutilisation | double | `#,##0.00` | oui |

### Evenements

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| Événement | string |  | oui |
| Nom événement | string |  | non |
| Région | string |  | non |
| Ordre | int64 | `#,##0` | oui |

### Maps

| Colonne | Type | Format | Masquée |
|---|---|---|---|
| Map | string |  | non |

## Relations

| De (plusieurs) | Vers (un) | Active |
|---|---|---|
| Picks[Agent] | Agents[Agent] | oui |
| Compositions[Équipe] | Equipes[Équipe] | oui |
| Joueurs[Équipe] | Equipes[Équipe] | oui |
| Compositions[Événement] | Evenements[Événement] | oui |
| Compositions[Map] | Maps[Map] | oui |
| Picks[Équipe] | Equipes[Équipe] | oui |
| Picks[Événement] | Evenements[Événement] | oui |
| Picks[Map] | Maps[Map] | oui |
| Paires[Équipe] | Equipes[Équipe] | oui |
| Paires[Événement] | Evenements[Événement] | oui |
| Paires[Map] | Maps[Map] | oui |
| Joueurs[Événement] | Evenements[Événement] | oui |

## Mesures

| Mesure | Table | Dossier | Format | Description |
|---|---|---|---|---|
| Compositions | Compositions | Compositions | `#,##0` | Nombre de compositions jouées (une équipe, une map, cinq agents) |
| Maps jouées | Compositions | Compositions | `#,##0` | Nombre de maps jouées ; une map compte deux compositions, une par équipe |
| Compos différentes | Compositions | Compositions | `#,##0` | Nombre de combinaisons de cinq agents différentes |
| Diversité des compos | Compositions | Compositions | `0 %` | Part de compositions différentes ; 100 % = jamais deux fois la même, bas = compo fixe |
| Score profil tactique | Equipes | Équipes | `0.0` | Score de 0 à 100 du modèle de profils (stabilité des compos, pool d'agents, identité par map, fiabilité de l'échantillon), voir data/models/team_profile_scores.csv |
| Joueurs | Joueurs | Joueurs | `#,##0` | Nombre de joueurs (EMEA Stage 1 uniquement) |
| Rounds joués | Joueurs | Joueurs | `#,##0` | Rounds joués par les joueurs sélectionnés |
| Rating moyen | Joueurs | Joueurs | `0.00` | Rating vlr.gg pondéré par les rounds joués, pour qu'un remplaçant ne pèse pas autant qu'un titulaire |
| ACS moyen | Joueurs | Joueurs | `0` | Average combat score pondéré par les rounds |
| ADR moyen | Joueurs | Joueurs | `0` | Dégâts moyens par round, pondérés par les rounds |
| KAST moyen | Joueurs | Joueurs | `0 %` | Part des rounds avec un kill, une assist, une survie ou un trade, pondérée par les rounds |
| First kills - first deaths | Joueurs | Joueurs | `+0.00;-0.00;0.00` | Premiers kills moins premières morts, par round ; positif = gagne ses duels d'ouverture |
| Couleur Rating moyen (masquée) | Joueurs | Couleurs |  | Couleur de mise en évidence de Rating moyen |
| Pick rate paire | Paires | Paires | `0 %` | Part des compositions qui contiennent les deux agents de la paire |
| Équipes (paire) | Paires | Paires | `#,##0` | Nombre d'équipes qui ont joué la paire ; une paire jouée par une seule équipe est une signature, pas une méta |
| Pick rate | Picks | Agents | `0 %` | Part des compositions qui contiennent l'agent (ou au moins un agent du rôle), calculée sur les compositions du filtre en cours : le filtre agent ou rôle ne touche pas au dénominateur |
| Pick rate toutes maps | Picks | Agents | `0 %` | Pick rate de l'agent sur toutes les maps, avec les autres filtres |
| Écart à sa moyenne | Picks | Agents | `+0 %;-0 %;0 %` | Différence entre le pick rate sur la map et le pick rate toutes maps ; positif = agent de cette map |
| Agents par compo | Picks | Agents | `0.00` | Nombre moyen d'agents du rôle par composition (ex. 1,3 duelliste par compo) |
| Agents joués | Picks | Agents | `#,##0` | Nombre d'agents différents joués au moins une fois |
| Équipes qui le jouent | Picks | Agents | `#,##0` | Nombre d'équipes qui ont joué l'agent au moins une fois |
| Couleur Pick rate (masquée) | Picks | Couleurs |  | Couleur de mise en évidence de Pick rate |

### Compositions

Expression DAX (Compositions):

```dax
COUNTROWS(Compositions)
```

### Maps jouées

Expression DAX (Compositions):

```dax
DISTINCTCOUNT(Compositions[Match])
```

### Compos différentes

Expression DAX (Compositions):

```dax
DISTINCTCOUNT(Compositions[Agents])
```

### Diversité des compos

Expression DAX (Compositions):

```dax
DIVIDE([Compos différentes], [Compositions])
```

### Score profil tactique

Expression DAX (Equipes):

```dax
AVERAGE(Equipes[Score profil])
```

### Joueurs

Expression DAX (Joueurs):

```dax
COUNTROWS(Joueurs)
```

### Rounds joués

Expression DAX (Joueurs):

```dax
SUM(Joueurs[Rounds])
```

### Rating moyen

Expression DAX (Joueurs):

```dax
DIVIDE(SUMX(Joueurs, Joueurs[Rating] * Joueurs[Rounds]), [Rounds joués])
```

### ACS moyen

Expression DAX (Joueurs):

```dax
DIVIDE(SUMX(Joueurs, Joueurs[ACS] * Joueurs[Rounds]), [Rounds joués])
```

### ADR moyen

Expression DAX (Joueurs):

```dax
DIVIDE(SUMX(Joueurs, Joueurs[ADR] * Joueurs[Rounds]), [Rounds joués])
```

### KAST moyen

Expression DAX (Joueurs):

```dax
DIVIDE(SUMX(Joueurs, Joueurs[KAST] * Joueurs[Rounds]), [Rounds joués])
```

### First kills - first deaths

Expression DAX (Joueurs):

```dax
DIVIDE(SUMX(Joueurs, (Joueurs[FKPR] - Joueurs[FDPR]) * Joueurs[Rounds]), [Rounds joués])
```

### Couleur Rating moyen

Expression DAX (Joueurs):

```dax
VAR _v = [Rating moyen]
RETURN SWITCH(
    TRUE(),
    ISBLANK(_v), BLANK(),
    _v < 0.95, "#E03131",
    _v < 1.1, "#F59F00",
    "#12B886"
)
```

### Pick rate paire

Expression DAX (Paires):

```dax
DIVIDE(DISTINCTCOUNT(Paires[CompID]), [Compositions])
```

### Équipes (paire)

Expression DAX (Paires):

```dax
DISTINCTCOUNT(Paires[Équipe])
```

### Pick rate

Expression DAX (Picks):

```dax
DIVIDE(DISTINCTCOUNT(Picks[CompID]), [Compositions])
```

### Pick rate toutes maps

Expression DAX (Picks):

```dax
CALCULATE([Pick rate], REMOVEFILTERS(Maps))
```

### Écart à sa moyenne

Expression DAX (Picks):

```dax
[Pick rate] - [Pick rate toutes maps]
```

### Agents par compo

Expression DAX (Picks):

```dax
DIVIDE(COUNTROWS(Picks), [Compositions])
```

### Agents joués

Expression DAX (Picks):

```dax
DISTINCTCOUNT(Picks[Agent])
```

### Équipes qui le jouent

Expression DAX (Picks):

```dax
DISTINCTCOUNT(Picks[Équipe])
```

### Couleur Pick rate

Expression DAX (Picks):

```dax
VAR _v = [Pick rate]
RETURN SWITCH(
    TRUE(),
    ISBLANK(_v), BLANK(),
    _v < 0.1, "#677386",
    _v < 0.5, "#F59F00",
    "#FF4655"
)
```

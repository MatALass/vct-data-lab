# Rapport Power BI VLR 2026

Le rapport porte sur les données VLR.gg du Stage 1 2026 (Americas, EMEA, Pacific, China) que le pipeline `vlr_analytics` a déjà produites : 232 maps, 464 compositions, 48 équipes et 27 agents. Il répond à une question : quelles compositions jouent les équipes, map par map, et qui sort du lot ?

Tout est décrit dans `report.yaml` (modèle, mesures DAX, pages) et le projet `VLR2026/` est généré par [pbip-generator](https://github.com/MatALass/pbip-generator). Les données sont versionnées dans `data/powerbi/vlr_2026/`, donc le rapport s'ouvre sans lancer le scraper.

## Ouvrir le rapport

1. Dans Power BI Desktop, activer les préversions **Format de projet Power BI (.pbip)**, **TMDL** et **PBIR** (Fichier > Options > Fonctionnalités en préversion), puis redémarrer.
2. Ouvrir `powerbi/vlr_2026/VLR2026/VLR2026.pbip`.
3. Si le dépôt n'est pas cloné dans `C:\pbip\vct-data-lab\`, changer le paramètre `DataFolder` (Transformer les données > Gérer les paramètres) vers le dossier `data\powerbi\vlr_2026\` du dépôt, avec le `\` final.
4. Cliquer sur **Actualiser** : le projet s'ouvre sans données, c'est normal.

Pour un fichier unique : Fichier > Enregistrer sous > `.pbix`.

## Régénérer

```bash
pip install -e ".[powerbi]"
python -m vlr_analytics.powerbi_model      # marts et modèles -> data/powerbi/vlr_2026/*.csv
pbip-generator build data/powerbi/vlr_2026 --spec powerbi/vlr_2026/report.yaml -n VLR2026 \
  -o powerbi/vlr_2026 --data-folder 'C:\pbip\vct-data-lab\data\powerbi\vlr_2026\' --overwrite --strict
```

On ne modifie pas les fichiers de `VLR2026/` à la main : la CI régénère les CSV et le projet, et échoue s'ils diffèrent de ce qui est versionné. Un job Windows charge aussi le modèle avec TOM (la bibliothèque de Power BI) pour attraper les erreurs TMDL.

## Pages

| Page | Question | Contenu |
|---|---|---|
| Méta agents | Quels agents et quels rôles dominent ? | pick rate par agent, agents par compo selon le rôle, archétypes de compos |
| Agents par map | Qui est joué sur quelle map ? | matrice agent × map du pick rate, colorée par seuils |
| Maps | Où les équipes varient-elles leurs compos ? | maps jouées, diversité des compos, rôles par map, paires d'agents les plus jouées |
| Équipes | Qui a un noyau stable, qui change tout le temps ? | profil tactique, score, compos différentes, agents joués |
| Fiche équipe | Ce que joue une équipe | segment Équipe, agents et pick rate, liste des compos par map |
| Joueurs EMEA | Qui performe en EMEA Stage 1 ? | classement par rating, rating par rôle joué |

Exemples de ce qu'on y lit : Neon est dans 81 % des compositions, la paire Neon + Omen dans 41 %, et Breeze est la map où les équipes varient le plus (44 % de compos différentes contre 33 % sur Haven et Lotus).

## Choix de modélisation

- **Les taux sont calculés dans Power BI, pas stockés.** Les marts contiennent des `pick_rate` déjà calculés, mais ils ne valent que pour le regroupement d'origine : filtrer sur une équipe ou une région donnerait des moyennes de taux fausses. Le modèle garde donc une ligne par composition (`Compositions`), par agent joué (`Picks`) et par paire d'agents (`Paires`), et le pick rate est `compositions avec l'agent / compositions`, juste sous n'importe quel filtre.
- **`Picks` et `Paires` sont reliées directement aux dimensions**, pas à `Compositions` : sinon il y aurait deux chemins entre les mêmes tables. Le filtre Agent ou Rôle ne touche donc pas au dénominateur, ce qui est voulu.
- **Les stats joueurs sont pondérées par les rounds** (rating, ACS, ADR, KAST), sinon un remplaçant avec deux maps pèse autant qu'un titulaire.
- **Les paires jouées par moins de 3 équipes sont cachées** dans le tableau des paires : ce sont des signatures d'équipe, pas de la méta.
- **Pas de mesures automatiques** : pbip-generator aurait fait la somme des ratings et des KAST.

## Limites

- Les stats joueurs ne couvrent que l'EMEA Stage 1, le seul événement scrapé côté joueurs.
- vlr.gg affiche les équipes en abrégé sur la page des stats (`FNC`) et en entier sur les matchs (`FNATIC`) : la correspondance est écrite à la main dans `powerbi_model.py`. Un joueur sort en « (équipe non reconnue) » : le scraper coupe son pseudo, `lovers rock`, en joueur `lovers` et équipe `rock`. C'est à corriger dans le scraper.
- Les archétypes viennent d'un clustering exploratoire (`data/models/composition_clusters.csv`), à lire comme des familles de compos, pas comme une vérité.
- Le score de profil tactique vient de `data/models/team_profile_scores.csv`, il décrit la stabilité des compos et pas le niveau de l'équipe.

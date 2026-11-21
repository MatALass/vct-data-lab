# Rapport Power BI de la saison VCT 2026

Le rapport couvre toute la saison VCT 2026 telle que vlr.gg la publie : 15 événements (les 4 Kickoff, Masters Santiago, les 4 Stage 1, Masters London, les 4 Stage 2 et Champions), soit 1 582 maps, 3 164 compositions, 63 équipes, 29 agents et 1 022 lignes de stats joueurs. Il répond à une question : quelles compositions jouent les équipes, map par map et étape par étape, et qui sort du lot ?

Tout est décrit dans `report.yaml` (modèle, mesures DAX, pages) et le projet `VLR2026/` est généré par [pbip-generator](https://github.com/MatALass/pbip-generator). Les données sont versionnées dans `data/powerbi/vlr_2026/`, donc le rapport s'ouvre sans relancer le scraper.

## Ouvrir le rapport

1. Dans Power BI Desktop, activer les préversions **Format de projet Power BI (.pbip)**, **TMDL** et **PBIR** (Fichier > Options > Fonctionnalités en préversion), puis redémarrer.
2. Ouvrir `powerbi/vlr_2026/VLR2026/VLR2026.pbip`.
3. Si le dépôt n'est pas cloné dans `C:\pbip\vct-data-lab\`, changer le paramètre `DataFolder` (Transformer les données > Gérer les paramètres) vers le dossier `data\powerbi\vlr_2026\` du dépôt, avec le `\` final.
4. Cliquer sur **Actualiser** : le projet s'ouvre sans données, c'est normal.

Pour un fichier unique : Fichier > Enregistrer sous > `.pbix`.

## Mettre à jour les données

Le scraping se lance sur GitHub Actions (workflow `refresh-vlr-data`, onglet Actions > Run workflow, ou push sur une branche `data-refresh/...`). Il lit la liste des événements sur `vlr.gg/vct-2026` et commite `data/raw/` sur la branche. Ensuite, en local :

```bash
pip install -e ".[powerbi]"
vlr process && vlr build-marts && vlr model   # data/raw -> processed, marts, models
python -m vlr_analytics.powerbi_model          # -> data/powerbi/vlr_2026/*.csv
pbip-generator build data/powerbi/vlr_2026 --spec powerbi/vlr_2026/report.yaml -n VLR2026 \
  -o powerbi/vlr_2026 --data-folder 'C:\pbip\vct-data-lab\data\powerbi\vlr_2026\' --overwrite --strict
```

On ne modifie pas les fichiers de `VLR2026/` à la main : la CI régénère les CSV et le projet, et échoue s'ils diffèrent de ce qui est versionné. Un job Windows charge aussi le modèle avec TOM (la bibliothèque de Power BI) pour attraper les erreurs TMDL.

## Pages

| Page | Question | Contenu |
|---|---|---|
| Méta agents | Quels agents dominent, lesquels gagnent ? | pick rate et winrate par agent, agents par compo selon le rôle, archétypes |
| La méta sur la saison | Comment la méta évolue du Kickoff aux Champions ? | matrice agent × étape de la saison du pick rate |
| Agents par map | Qui est joué sur quelle map ? | matrice agent × map du pick rate |
| Maps | Où les équipes varient-elles leurs compos ? | maps jouées, diversité, rôles par map, paires d'agents avec leur winrate |
| Équipes | Qui gagne, qui change tout le temps ? | winrate, compos différentes, profil tactique |
| Fiche équipe | Ce que joue une équipe | segment Équipe, agents joués avec winrate, compos par map avec le résultat |
| Joueurs | Qui performe ? | nuage Rating × ACS (taille = rounds), classement, 200 rounds minimum |

Les segments Étape, Région et Map filtrent les pages ; l'étape est numérotée (`1. Kickoff` ... `6. Champions`) pour que les colonnes suivent la saison.

Exemples de ce qu'on y lit :
- Omen est l'agent de la saison (64 % des compos), devant Neon (58 %).
- Yoru passe de 59 % des compos au Kickoff à 1 % au Stage 1, puis revient à 31 % aux Champions.
- Neon + Omen est la paire la plus jouée (38 % des compos, 62 équipes).
- Split, Haven et Lotus sont les maps où les équipes varient le moins (15 à 16 % de compos différentes), Summit et Corrode celles où elles varient le plus (37 %).

## Choix de modélisation

- **Les taux sont calculés dans Power BI, pas stockés.** Le modèle garde une ligne par composition (`Compositions`), par agent joué (`Picks`) et par paire d'agents (`Paires`), et le pick rate est `compositions avec l'agent / compositions`, juste sous n'importe quel filtre. Les `pick_rate` des marts ne valent que pour leur regroupement d'origine.
- **Une map = un game vlr.gg.** L'identifiant du game sert de clé de map : deux équipes qui se rejouent sur la même map (poule puis playoffs) donnent deux maps, pas une compo à 10 agents.
- **`Picks` et `Paires` sont reliées directement aux dimensions**, pas à `Compositions` : sinon il y aurait deux chemins entre les mêmes tables. Le filtre Agent ou Rôle ne touche donc pas au dénominateur, ce qui est voulu.
- **Winrate par composition**, pas par agent pondéré : une compo avec deux duellistes compte une fois dans le winrate du rôle.
- **Stats joueurs pondérées par les rounds** (rating, ACS, ADR, KAST) et seuil de 200 rounds sur le nuage et le classement, sinon un remplaçant avec deux maps passe devant tout le monde.
- **Équipes : nom complet partout.** La page stats de vlr.gg donne un tag (`FNC`), la page agents le nom (`FNATIC`) : le tag est lu sur la page de chaque équipe puis cherché parmi les équipes du même événement. Les 1 022 lignes joueurs trouvent leur équipe.
- **Pas de mesures automatiques** : pbip-generator aurait fait la somme des ratings et des KAST.

## Limites

- Le winrate d'une équipe ou d'un agent est un winrate de maps, pas de séries.
- Un joueur est identifié par son pseudo : deux joueurs avec le même pseudo seraient fusionnés. Aucun pseudo n'apparaît deux fois dans un même événement ; 24 pseudos apparaissent dans deux équipes sur la saison, ce qui correspond en général à un transfert, mais je ne l'ai pas vérifié un par un.
- Les archétypes viennent d'un clustering exploratoire (`data/models/composition_clusters.csv`), à lire comme des familles de compos, pas comme une vérité.
- Le score de profil tactique est calculé sur toute la saison : le segment Étape ne le change pas.

# Hestia: état du projet et suite (passation au 13/11/2026)

Branche `feat/backend-core`, PR [#2](https://github.com/HonluePetnou/hestia/pull/2) vers `main`
(elle contient aussi les commits de `feat/ui-design` / PR #1, pas encore fusionnés).

## Ce qui marche

Données en base locale (Postgres sur le port 5434) :

| Élément | État |
|---|---|
| Corpus NTRS | 58 rapports au catalogue, 55 indexés, 3 607 passages, 2 PDF scannés exclus |
| FLEX Table IX | 276 essais sur 280, `data/flex/flex_table_ix.csv` (commité) |
| Expériences | 5 dans `data/experiments.json` + essais Saffire IV/V |
| Findings | 21 dans `data/findings.json`, pages vérifiées dans le texte extrait |

API :

| Route | État |
|---|---|
| `/ask` | Recherche hybride (pgvector + plein texte) ; les citations inventées sont supprimées ; `insufficient_data` ; historique accepté |
| `/predict` + `/predict/model` | Modèles scikit-learn entraînés sur FLEX (R² K ≈ 0,70, AUC extinction ≈ 0,89) |
| `/stats`, `/ranking`, `/compare`, `/compare/insights` | Données réelles ; insights mis en cache dans `ai_cache` |

Frontend : les 7 écrans lisent l'API. Les citations ouvrent le PDF NTRS à la page citée.

Qualité : 30 tests backend, ruff, eslint et `tsc` passent. `next build` n'a pas été lancé.

## Ce qui manque, par priorité

1. **Clé Gemini (bloquant pour la démo).** Rien n'a été testé avec un vrai LLM.
   - Dans `.env` : `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`.
   - Puis `make ingest ARGS=--force` pour recalculer les vecteurs. Les vecteurs actuels sont factices (mock) ; sur l'offre gratuite, ajouter `--pause 2` si le débit est limité.
   - Ensuite, tester `/ask` sur les suggestions de l'assistant et `/compare/insights`.
   - Ajuster `RETRIEVAL_MIN_SCORE` (0,55 par défaut) selon les scores observés.
2. **Relecture des findings par l'équipe.** Les notes de pertinence Lune/Mars et de confiance dans `data/findings.json` sont des jugements. Après modification : `uv run python -m pipeline.ingest --only findings`.
3. **ACME n'a aucun finding.** Rapports ACME disponibles : 20210022542, 20210021781, 20140009169, 20160012298 (20220015583 est scanné). Ajouter 2 ou 3 findings avec leur page.
4. **BASS n'a aucun essai** dans `test_runs`. Le rapport 20210011385 (BASS-II, 144 pages) contient des conditions d'essai ; on peut les ajouter dans `experiments.json` > `runs`.
5. **Production** : lancer `pnpm build`, vérifier la CI GitHub Actions (elle s'arrêtait au démarrage, probablement à cause d'un réglage du compte), puis fusionner #1 et #2.
6. **Optionnel** :
   - script d'extraction automatique des findings par LLM (pas fait : le curé main est plus fiable) ;
   - réponses en streaming ;
   - déploiement ;
   - vidéo et slides du pitch.

## Points d'attention

- Le simulateur ne gère que n-heptane et méthanol, en microgravité (domaine des données FLEX). La gravité n'est pas un paramètre du modèle.
- La page de détail FLEX est lourde (environ 590 Ko de payload, 276 essais). Si c'est lent, paginer côté API.
- `fetch_ntrs` fusionne désormais avec le catalogue existant (`--fresh` pour repartir de zéro).
- Les fichiers à connaître :
  - `backend/app/services/rag.py` : prompt et vérification des citations
  - `retrieval.py` : recherche
  - `flex_model.py` : modèle ML
  - `insights.py` : comparaison
  - `pipeline/flex_table.py` : extraction de la Table IX
- Commandes locales sous Windows : `uv` est dans `~/AppData/Roaming/Python/Python314/Scripts` et `make` n'est pas installé. Lancer les commandes du Makefile à la main, ou utiliser `.claude/launch.json` (serveurs `api` et `web`).

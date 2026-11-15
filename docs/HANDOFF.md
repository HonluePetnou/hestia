# Hestia: état du projet (passation au 15/11/2026)

Tout le travail est sur `main` (PR #1, #2 et #3 fusionnées). La PR #4 (`feat/polish-and-data`)
ajoute la mise en page mobile, le résumé du tableau FLEX pour l'assistant et les findings ACME.
Ce qui reste à faire est dans [TODO.md](TODO.md).

## Ce qui marche

### Données (Postgres + pgvector, port 5434)

| Élément | État |
|---|---|
| Corpus NTRS | 55 rapports indexés |
| Corpus PSI | 24 investigations, texte officiel mot pour mot (`data/psi_corpus/`) |
| Ressources NASA | Énoncé du challenge, Apollo 1 et 13, Mir, Glenn, spinoffs, Researcher's Guide complet, résumé du tableau FLEX |
| Embeddings | Tous les chunks en Gemini (`gemini-embedding-001`, 1 536 dimensions) |
| FLEX Table IX | 276 essais (`data/flex/flex_table_ix.csv`), identiques au tableau PSI officiel sur les 274 essais communs (voir `data/README.md`) |
| Tableau PSI FLEX | `data/flex/flex_psi_clean.csv`, script `backend/pipeline/clean_flex.py`, source brute `data/psi/FLEX/test_matrix.csv` |
| Findings | 24 dans `data/findings.json`, dont 3 ACME, chacun sourcé à la page |

### API

| Route | État |
|---|---|
| `/ask` | Recherche hybride (vecteurs + plein texte) sur NTRS, PSI et ressources NASA. Citations vérifiées. Répond en anglais par défaut. Si les embeddings sont indisponibles (quota), repli automatique sur le plein texte |
| `/predict` | Modèle FLEX (R² K ≈ 0,70, AUC extinction ≈ 0,89) et `nearest_test`, l'essai FLEX réel le plus proche avec son lien vers le rapport |
| `/compare/insights` | Différences clés en anglais, 2 citations par point au maximum, mises en cache (clé versionnée) |
| `/stats`, `/ranking`, `/compare`, `/experiments` | Données réelles |

`RETRIEVAL_MIN_SCORE` = 0,62, calibré le 15/11 : questions du corpus ≥ 0,671, hors corpus 0,48 à 0,69.

### Frontend (7 écrans)

- Accueil animé (étoiles, flamme, compteurs), barre de navigation collante, mise en page mobile sans débordement.
- Simulateur 3D : chambre de combustion de l'ISS (aiguille, allumeur, caméra, radiomètre, étiquettes), combustion animée (allumage, extinction au diamètre médian FLEX ou combustion complète), vue Terre / ISS (illustration), essai NASA le plus proche.
- Compare : cartes de hauteur indépendante, panneau IA collant. Relevance : panneau cible collant.

### Qualité

56 tests unitaires et 9 tests d'intégration, ruff, tsc, eslint et `pnpm build` passent.

## Points d'attention

- **Quotas Gemini (offre gratuite)** : 1 000 embeddings par jour et par projet Google Cloud. Plusieurs clés se mettent dans `GEMINI_API_KEYS`, séparées par des virgules, chacune dans un projet différent ; le code passe de l'une à l'autre. L'ingestion reprend là où elle s'est arrêtée.
- **Modèle de chat** : `LLM_MODEL=gemini-3.5-flash-lite` dans `.env`, car `gemini-3.8-flash` (le défaut du code) renvoyait des erreurs 504 côté Google le 15/11. À retester : vider `LLM_MODEL` pour revenir à la 3.8.
- **CI GitHub** : tous les lancements échouent au démarrage (`startup_failure`), probablement la facturation ou les minutes Actions du compte (dépôt privé). La correction de `setup-uv@v10.3.3` n'a pas suffi.
- **Port local** : sur la machine de HonluePetnou, l'API tourne sur 8001 (`web/.env.local` et `.claude/launch.json`, non commités) car le port 8000 est pris par un autre projet.
- Le simulateur ne couvre que n-heptane et méthanol, en microgravité. La vue Terre est une illustration.
- La page de détail FLEX est lourde (environ 590 Ko, 276 essais). Si c'est lent, paginer côté API.
- `fetch_ntrs` fusionne avec le catalogue existant (`--fresh` pour repartir de zéro).

## Fichiers à connaître

- `backend/app/services/rag.py` : prompt et vérification des citations
- `backend/app/services/retrieval.py` : recherche hybride, seuil, repli plein texte
- `backend/app/services/llm.py` : fournisseurs, rotation des clés Gemini
- `backend/app/services/flex_model.py` : modèle FLEX et essai le plus proche
- `backend/app/services/insights.py` : différences clés de Compare
- `data/psi_corpus/scripts/build_corpus.py` et `summarize_tests.py` : construction du corpus PSI
- `web/src/components/DropletScene.tsx` : scène 3D

## Commandes

Sous Windows, `make` n'est pas installé : lancer les commandes du `Makefile` à la main
(`uv` est dans `~/AppData/Roaming/Python/Python314/Scripts`), ou utiliser `.claude/launch.json`.

- Ingestion : `cd backend && uv run python -m pipeline.ingest --pause 2 --batch-size 20`
- État de l'index : `uv run python -m pipeline.status`
- Calibration : `uv run python -m pipeline.evaluate --calibrate`
- Corpus PSI : `cd data/psi_corpus && python scripts/summarize_tests.py && python scripts/build_corpus.py --max-chars 1800`

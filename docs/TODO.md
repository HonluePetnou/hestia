# Hestia : reste à faire (au 14/11/2026)

`main` contient désormais tout le travail : la maquette des 7 écrans (PR #1) et le backend, le RAG, le modèle FLEX et le corpus PSI (PR #2).
Pour le détail technique, voir [HANDOFF.md](HANDOFF.md) et [data/psi_corpus/README.md](../data/psi_corpus/README.md).

## Où on en est

| Brique | État |
|---|---|
| Frontend (7 écrans) | Branché sur l'API, citations vers les PDF NTRS |
| API `/ask`, `/predict`, `/stats`, `/ranking`, `/compare` | Fonctionne en local, testée avec un LLM factice uniquement |
| Corpus NTRS | 55 rapports, 3 607 passages indexés (vecteurs factices) |
| Corpus PSI + ressources du challenge | 323 chunks prêts, **pas encore ingérés** |
| Modèle FLEX | R² ≈ 0,70, AUC ≈ 0,89 |
| Tests | 30 tests backend, ruff, eslint et tsc passent |
| CI GitHub | Ne démarre pas (`startup_failure`) |
| Déploiement | Aucun |

## Planning

### Samedi 14/11 : faire marcher le vrai RAG
Matin
- [ ] Mettre la clé Gemini dans `.env`, puis relancer l'ingestion avec `--force`
- [ ] Brancher `data/psi_corpus/out/chunks.jsonl` dans `ingest.py`, puis l'ingérer
- [ ] Débloquer la CI (*Settings → Actions*)

Après-midi
- [ ] Tester `/ask` et `/compare/insights` avec le vrai LLM, puis ajuster `RETRIEVAL_MIN_SCORE`
- [ ] Lancer `pnpm build` et corriger ce qui casse
- [ ] Télécharger les CSV PSI de BASS-II et ajouter les essais BASS
- [ ] Ajouter 2 ou 3 findings ACME

Soir
- [ ] Relire les findings et les annotations en équipe
- [ ] Choisir l'hébergement (API, base pgvector, frontend)

### Dimanche 15/11 : déployer et préparer le pitch
Matin
- [ ] Déployer l'API, la base et le frontend, puis vérifier l'URL publique
- [ ] Faire un passage de démo complet sur l'URL publique et corriger ce qui bloque

Après-midi
- [ ] Écrire le script du pitch
- [ ] Faire les slides
- [ ] Tourner la vidéo de démo

Soir
- [ ] Soumettre (lien, vidéo, slides)
- [ ] S'il reste du temps : CSV de CFI-G et SPICE, streaming, pagination de la page FLEX

## 1. Bloquant pour la démo

- [ ] **Clé Gemini** : ajouter `LLM_PROVIDER=gemini` et `GEMINI_API_KEY=...` dans `.env`.
- [ ] **Ré-ingestion avec les vrais embeddings** : `make ingest ARGS=--force` (ajouter `--pause 2` en offre gratuite).
- [ ] **Ingérer le corpus PSI** : brancher `data/psi_corpus/out/chunks.jsonl` dans `backend/pipeline/ingest.py`. Garder les métadonnées `psi_id`, `doi`, `source_url`, `pillars` et `fire_safety_tier`, et mapper `source_url` et `doi` vers les citations.
- [ ] **Tester `/ask` et `/compare/insights`** avec le vrai LLM sur les suggestions de l'assistant et sur des questions couvertes seulement par PSI (SAME, SPICE, ACME BRE, Apollo 1).
- [ ] **Ajuster `RETRIEVAL_MIN_SCORE`** (0,55 par défaut) selon les scores observés.
- [ ] **Déployer** l'API, la base (Postgres + pgvector) et le frontend, pour avoir une URL publique à montrer.

## 2. Qualité et mise en production

- [ ] **CI** : vérifier *Settings → Actions* du dépôt (Actions activé, limite de facturation). Tous les lancements échouent avant de démarrer.
- [ ] **`pnpm build`** : la compilation de production du frontend n'a jamais été lancée.
- [ ] **Page de détail FLEX** : son payload fait environ 590 Ko. Si elle est lente, paginer côté API.
- [ ] **Brancher les futures branches sur `main`** : `feature/data-engineering` est vide. Repartir de `main` à jour.

## 3. Données

- [ ] **Tableaux d'essais PSI complets** : télécharger les CSV à la main depuis l'onglet « Experimental table » de chaque investigation. PSI n'en affiche que 5 lignes par page et ne répond pas aux requêtes automatiques. Par ordre de priorité :
  - BASS-II (130 essais) : comble l'absence d'essais BASS dans `test_runs`
  - CFI-G (1 016)
  - SPICE (470)
  - Flame Design (208)
  - CFI (88)
- [ ] **ACME** : ajouter 2 ou 3 findings, avec leur page, à partir des rapports 20210022542, 20210021781, 20140009169 et 20160012298.
- [ ] **BASS** : ajouter les conditions d'essai du rapport BASS-II (20210011385) dans `experiments.json` > `runs`.
- [ ] **Relire les findings en équipe** : les notes de pertinence Lune/Mars et de confiance dans `data/findings.json` sont des jugements. Après modification : `uv run python -m pipeline.ingest --only findings`.
- [ ] **Relire `data/psi_corpus/docs/psi/annotations_curated.json`** : niveau de priorité, piliers et pertinence pour l'habitat sont aussi des jugements. Ne pas les citer comme une source NASA.
- [ ] **Optionnel** : PDF de NASA Glenn (liens dans `data/psi_corpus/docs/resources/02_*.md`), transcription de la vidéo ScienceCasts, publications complètes des 9 investigations principales.

## 4. Pitch

- [ ] Vidéo de démo
- [ ] Slides
- [ ] Script : problème, données NASA utilisées, démo `/ask` avec citations, simulateur FLEX, limites

## 5. Optionnel

- [ ] Réponses en streaming pour `/ask`
- [ ] Extraction automatique des findings par LLM, à valider à la main

## Limites à garder en tête

- Le simulateur ne couvre que le n-heptane et le méthanol, en microgravité (domaine des données FLEX). La gravité n'est pas un paramètre du modèle.
- Sous Windows, `make` n'est pas installé : lancer les commandes du Makefile à la main, ou utiliser `.claude/launch.json` (serveurs `api` et `web`).

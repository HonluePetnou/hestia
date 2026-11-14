# Module IA / RAG — documentation technique

Pipeline : question → embedding → recherche pgvector (+ plein texte) → passages numérotés → LLM → citations vérifiées par le backend → réponse.
Les documents sont ingérés **en amont** (`make ingest`) ; une question n'appelle jamais NTRS ni PSI.

## 1. Sources et modèle de données

| `documents.source_type` | Origine | `external_id` | Page |
|---|---|---|---|
| `ntrs` | rapports NTRS (`data/ntrs/`) | id NTRS (= `ntrs_id`) | oui (page PDF) |
| `psi` | 24 investigations PSI (`data/psi_corpus/out/chunks.jsonl`) | `PSI-159`… | non |
| `nasa_resource` | Apollo 1/13, Mir, NASA Glenn, spinoffs, Researcher's Guide, énoncé du challenge | slug (`apollo-13`…) | seulement le Guide (« Page N ») |

Migration **0004** (additive, réversible) :
- `documents` : `+source_type`, `+external_id` (unique avec `source_type`), `+doi`, `+meta JSONB` ; `ntrs_id` devient nullable (conservé, unique, rempli pour NTRS).
- `chunks` : `page` nullable ; `+meta JSONB` (psi_id, fuel_category, pillars, fire_safety_tier, doi, source_url, section…) ; `+chunk_key` (unique par document) ; `+content_hash` ; `+embedding_model` ; index GIN sur `meta`.
- Backfill des lignes existantes (`external_id = ntrs_id`, `chunk_key = p<page>#<index>`). `embedding_model` reste NULL → ces chunks sont **réembeddés au prochain `make ingest`** (le HANDOFF indique que les vecteurs actuels sont des faux vecteurs du mock).
- `downgrade 0003` supprime uniquement ce que le schéma 0003 ne sait pas représenter (documents PSI/ressources et chunks sans page). Les données NTRS ne sont pas touchées.
- La dimension du vecteur (1536) n'est **pas** modifiée.

### Annotations de l'équipe ≠ données NASA
`build_corpus.py` ajoute « curated habitat relevance : … » dans les 24 chunks `overview`. À l'ingestion, cette phrase est **retirée du texte indexé** et conservée dans `chunks.meta.curated_habitat_relevance` avec `annotation_note`. `fire_safety_tier` et `pillars` sont des jugements de l'équipe : `meta.curated_fields` les signale. Ne jamais les présenter comme des résultats NASA.

## 2. Embeddings et ingestion

- Fournisseur : `LLM_PROVIDER` (chat) et, si besoin, `EMBEDDING_PROVIDER` (ex. `gemini` pour les embeddings + `anthropic`/`openai` pour le chat).
- Identifiant d'embedding stocké par chunk : `<fournisseur>:<modèle>:<dim>` (ex. `gemini:gemini-embedding-001:1536`). Une requête n'est comparée qu'aux vecteurs du **même** identifiant. Changer de fournisseur/modèle ⇒ `make ingest` réembedde automatiquement, sans `--force`.
- Gemini : `output_dimensionality=1536`, `task_type` document/requête, normalisation L2 des vecteurs < 3072 dim. Vérification de dimension à chaque lot (et de la colonne SQL au démarrage de l'ingestion).
- Lots configurables, retry avec backoff exponentiel + jitter (429/5xx/quotas), **commit après chaque lot** : une interruption perd au plus un lot.
- **Idempotence** : un chunk est ignoré si `content_hash`, vecteur et `embedding_model` sont à jour. Deuxième exécution = 0 appel d'embedding.
- Préfixe contextuel NTRS avant embedding : `Titre (année), p.N` (non stocké, non cité). Les chunks PSI ont déjà leur en-tête.
- Chunking NTRS : ~400 tokens, recouvrement 50, jamais à cheval sur deux pages, pages vides écartées.
- **Exclusion** : `20210015913` (texte insuffisant) est ignoré avec un avertissement ; ajouter d'autres ids dans `data/ntrs/excluded_ids.txt`.

### Commandes (depuis la racine du dépôt)

| Besoin | Commande |
|---|---|
| Tout (NTRS + PSI + expériences + findings), reprenable | `make ingest` |
| NTRS seul / PSI seul | `make ingest-ntrs` / `make ingest-psi` |
| Plan gratuit à quotas | `make ingest ARGS="--pause 4 --batch-size 20"` |
| Reprise après interruption | relancer la même commande |
| Recalculer les embeddings en place | `make ingest ARGS=--force` |
| État de l'index | `make ingest-status` |
| Reconstruire le corpus PSI | `make psi-corpus` |

Ce que fait `--force` : **recalcule les vecteurs sur place** (UPDATE). Il ne supprime aucun document ni chunk.
Suppressions possibles : les chunks *obsolètes d'un document ré-ingéré* (désactivable : `--no-prune`) ; les findings absents de `findings.json` seulement avec `--prune-findings`.
Garde-fou : avec `LLM_PROVIDER=mock`, l'ingestion refuse d'écraser des vrais embeddings.
Les findings sont maintenant **upsertés** (l'ancien `delete(Finding)` global a été retiré).

## 3. Retrieval (`services/retrieval.py`)
- Score = **similarité cosinus** (1 − distance), plus haut = plus proche. Seuil `RETRIEVAL_MIN_SCORE` (défaut 0,55, **provisoire**).
- Les résultats plein texte ne contournent plus le seuil : tout candidat reçoit sa vraie similarité. Le plein texte ajoute des candidats et influence le classement (RRF).
- `RETRIEVAL_K` passages (défaut 8), au plus `RETRIEVAL_MAX_PER_DOC` (défaut 3) par document pour que le Researcher's Guide (89 chunks) n'écrase pas les pages PSI. Filtres : `source_types` (+ `sources` dans `POST /ask`), métadonnées `psi_id`, `fuel_category`, `fire_safety_tier`, `section`, `pillars`.
- Question en français : l'embedding Gemini est multilingue ; la branche plein texte est en `english` (peu utile en français, sans effet néfaste).
- Mode mock : plein texte seul, pas de seuil.

### Calibrer le seuil (à faire une fois les vrais embeddings indexés)
```
make calibrate
```
Affiche la similarité du meilleur passage pour les questions avec/sans réponse de `data/eval/questions.json`. Choisir `RETRIEVAL_MIN_SCORE` entre `out_of_corpus_max` et `answerable_min`. S'ils se chevauchent, garder un seuil bas et s'appuyer sur `insufficient_data` du modèle. **Aucune valeur n'est validée scientifiquement tant que cette étape n'est pas faite.**

## 4. Réponses `/ask`
- Le LLM reçoit `[PASSAGE n]` (type de source, id, titre, page ou « not available », contenu) et cite `[PASSAGE n]`.
- Le backend remplace ces références par des citations canoniques `[id, p.N]` ou `[id]` (sans page) et reconstruit `citations[]` depuis la base (id, titre, page, URL, DOI, `source_type`). URL : PDF#page pour NTRS, `source_url` PSI, sinon `https://doi.org/<doi>`, sinon `null`. Rien n'est inventé.
- Références inconnues supprimées. Réponse sans aucune citation valide ⇒ jamais renvoyée : `insufficient_data=true`, `citations=[]`.
- Aucun passage ⇒ le LLM n'est pas appelé : « Les sources indexées ne couvrent pas cette question. » (ou équivalent anglais), `citations=[]`.
- Mode mock : réponse extractive (extraits cités), jamais de citations factices.
- Contrat d'API : routes inchangées. `Citation` gagne `source_type`, `doi` ; `page` et `url` deviennent nullables ; `ntrs_id` porte l'identifiant externe (`PSI-159`). `AskRequest.sources` optionnel. Frontend : `AssistantChat.tsx`, `ui.tsx`, `api-types.ts` adaptés (typecheck + eslint OK).

## 5. Qualité
- `data/eval/questions.json` : 23 questions (SAME, SPICE, ACME BRE, BASS/BASS-II, CFI-G, Apollo 1/13, Mir, propagation, flammes froides, extinction, suie, habitats Lune/Mars, 4 hors corpus). Sources et termes attendus **vérifiés dans le corpus** (`tests/test_eval_set.py`). Deux questions NTRS sont marquées non vérifiées (texte NTRS absent des archives).
- `make eval-retrieval` (embeddings seuls) puis `make eval ARGS="--out report.json"` : recall de la source attendue, pertinence (termes), validité des citations, phrases non sourcées, nombres absents des passages (fidélité), abstention hors corpus, fausses abstentions. Ce sont des **proxys automatiques** : relire des réponses à la main.

## 6. Procédure hackathon
```bash
# 1. Environnement
make install && cp .env.example .env     # renseigner GEMINI_API_KEY, LLM_PROVIDER=gemini
make up                                   # Postgres + pgvector (docker)
# 2. Base
make migrate                              # applique 0001→0004
# 3. Vérifier les clés et les noms de modèles (OBLIGATOIRE)
make check-llm                            # chat JSON, embeddings, taille == EMBEDDING_DIM
# 4. Ingestion
make ingest-psi ARGS="--pause 2"          # 323 chunks, 34 documents
make fetch extract && make ingest-ntrs ARGS="--pause 2"
make ingest-status                        # volumes, dimension OK, embedding unique
# 5. Démarrage
make api                                  # puis: curl localhost:8000/health
curl -s localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"What does the SAME experiment measure?"}'
# 6. Validation
make calibrate && make eval-retrieval && make eval ARGS="--out report.json"
```
Noms de modèles Gemini (vérifiés dans la page officielle des dépréciations le 14/11/2026) : `gemini-embedding-001` n'a pas de date d'arrêt avant 2028 (remplaçant : `gemini-embedding-2`) ; **`gemini-2.5-flash` est déprécié** (plus sélectionnable, routé vers `gemini-3.5-flash-lite` le 01/12/2026). Le défaut du code est `gemini-3.8-flash` ; ces noms évoluent, `make check-llm` fait foi. Surcharge : `LLM_MODEL`, `EMBEDDING_MODEL`.

### Changer la dimension des vecteurs
Changer `EMBEDDING_DIM` ne suffit pas (la colonne est `vector(1536)` + index HNSW). Il faut une migration : drop de l'index HNSW, `ALTER COLUMN embedding TYPE vector(N)` (les vecteurs existants deviennent invalides → `UPDATE chunks SET embedding = NULL, embedding_model = NULL`), recréation de l'index, puis `make ingest`. HNSW pgvector est limité à 2000 dimensions.

## 7. Ce qui a été testé, et avec quoi

| Élément | Mock/fake | PostgreSQL réel | Fournisseur IA réel | Données réelles |
|---|---|---|---|---|
| Migration 0004 up/down/up + backfill | – | **oui** (PG 16, pgvector 0.6.0) | – | – |
| Ingestion PSI (323 chunks, idempotence, reprise, force, prune) | embeddings factices | **oui** | **non** | **oui** (chunks.jsonl régénéré) |
| Ingestion NTRS (pages, exclusion, idempotence) | embeddings factices | **oui** | non | **non** (données NTRS absentes) |
| Retrieval, filtres, seuil, isolation par modèle | embeddings par hachage de mots | **oui** | non | PSI factice réduit |
| `/ask` bout en bout, citations mixtes NTRS+PSI, hors corpus | LLM scripté | **oui** | non | – |
| Gemini / OpenAI / Anthropic | – | – | **non testé** (pas de clé) | – |
| Calibration du seuil, métriques d'évaluation réelles | – | – | **non fait** | – |
| Frontend | – | – | – | typecheck + eslint OK ; `next build` et navigateur non testés |

## 8. Limites restantes
- Extraction automatique de *findings* par LLM : **non livrée** (les 21 findings curés restent la source). Les annotations de l'équipe ne sont jamais des données NASA.
- Tableaux expérimentaux complets (BASS-II 130, CFI-G 1 016, SPICE 470 essais) : **absents** ; seuls des résumés avec lignes d'exemple sont indexés. Ajouter ces CSV demande un nouveau lecteur d'ingestion (même `ChunkSpec`, pas de changement du moteur).
- Données NTRS non fournies : chiffres 37/36 (brief) vs 58/55 (HANDOFF) non vérifiables ici.
- Le fournisseur Anthropic utilise un en-tête bêta (`server-side-fallback-2026-07-01`) non validé.
- Plein texte en anglais uniquement.

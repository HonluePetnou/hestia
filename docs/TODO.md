# Hestia : reste à faire (au 15/11/2026)

L'état complet est dans [HANDOFF.md](HANDOFF.md).

## Indispensable

- [ ] **Pitch** : script, slides, vidéo de démo enregistrée en local, puis soumission.
  - Moments forts à montrer : la flamme qui s'éteint à 2,52 mm dans le simulateur alors que l'essai réel FLEX-086 s'est éteint à 2,56 mm ; la vue Terre / ISS ; une réponse de l'assistant avec ses sources cliquables.
  - Vérifier si Space Apps demande un lien vers une démo en ligne ou si une vidéo suffit.

## Avant la démo

- [ ] Retester `gemini-3.8-flash` (vider `LLM_MODEL` dans `.env`) ; garder `gemini-3.5-flash-lite` si elle renvoie encore des 504.
- [ ] Faire un passage complet de la démo sur la machine qui la présentera.

## Facultatif

- [ ] **CI** : vérifier *Settings → Billing* du compte GitHub (minutes Actions sur dépôt privé).
- [ ] **BASS-II** : télécharger le CSV « Experimental table » sur https://psi.nasa.gov/physci/repo/data/investigations/PSI-25 (PSI bloque les requêtes automatiques), puis ajouter les essais à `data/experiments.json` > `runs`. BASS n'a encore aucun essai.
- [ ] **Relire les findings** (`data/findings.json`) et `data/psi_corpus/docs/psi/annotations_curated.json` en équipe : notes de pertinence et de confiance, jugements de niveau et de piliers.
- [ ] Autres tableaux PSI (CFI-G, SPICE, Flame Design) : même méthode que FLEX, puis un résumé comme `summarize_tests.py`.
- [ ] Supprimer les branches fusionnées : `feat/backend-core`, `feat/ui-design`, `feat/integrate-team`, `feature/data-engineering`, `feat/hestia-rag-integration`.
- [ ] Réponses en streaming pour `/ask`.

## Fait le 14-15/11

Intégration du travail de l'équipe, correction de la CI (`setup-uv`), indexation complète en Gemini avec rotation des clés, calibration, réponses en anglais, repli plein texte, simulateur 3D (chambre ISS, combustion animée, vue Terre / ISS, essai NASA le plus proche), animations, mise en page desktop et mobile, résumé du tableau FLEX, findings ACME.

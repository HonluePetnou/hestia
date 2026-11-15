# Hestia: pitch (NASA Space Apps 2026, « Flame in Freefall »)

Script en anglais pour le jury, environ 3 minutes de parole, suivi du déroulé exact de la démo
et du plan des slides. Les chiffres viennent du projet tel qu'il est sur `main` le 15/11/2026.

---

## 1. Script (≈ 3 min)

### Hook (0:00 – 0:20)
> February 1997. An oxygen canister catches fire aboard the space station Mir. For several
> minutes, a three-foot flame blocks the way to one of the escape capsules and smoke fills
> the station. In space, fire doesn't behave the way our instincts expect, and as we plan
> habitats on the Moon and Mars, getting it wrong is not an option.

### Problem (0:20 – 0:45)
> NASA has spent decades burning things in microgravity: droplets on the ISS, fabrics on
> cargo ships, smoke in gloveboxes. The answers exist, but they are spread across hundreds of
> technical reports and data tables that no mission designer has time to read.

### Solution (0:45 – 1:00)
> Hestia turns that research into answers. It is an assistant, an explorer and a simulator,
> built only on NASA data, and every claim links back to the exact page it came from.

### Demo (1:00 – 2:30) — voir le déroulé en section 2
1. **Ask** a question → cited answer, click a source, the NASA PDF opens at the page.
2. **Simulator** → a methanol droplet at 12 % oxygen burns and goes out. Our model says it
   goes out at 2.52 mm; the real ISS test FLEX-086 went out at 2.56 mm.
3. **Earth vs ISS** → same flame, with and without gravity.
4. **Relevance** → findings ranked for Mars.

### Data & trust (2:30 – 2:50)
> Everything comes from NASA: 55 NTRS reports, 24 Physical Sciences Informatics
> investigations, and 276 droplet tests from the FLEX experiment. The model's burning-rate
> error is 2.3 times smaller than a naive guess, and when the data doesn't cover a
> question, Hestia says so instead of inventing an answer.

### Close (2:50 – 3:00)
> Fire safety beyond Earth starts with the lessons we already paid for. Hestia keeps the
> flame where it belongs.

---

## 2. Déroulé de la démo (à répéter avant d'enregistrer)

Préparation : API et front lancés, `.env` avec Gemini, navigateur en plein écran à 1 440 px,
onglets Assistant et Simulator déjà ouverts, quota Gemini vérifié le jour même.

| # | Écran | Action | Ce qu'on dit / ce qu'on montre |
|---|---|---|---|
| 1 | Overview | Laisser l'animation se jouer 3 s | Le titre, les compteurs (89 rapports, 276 essais) |
| 2 | Assistant | Cliquer la suggestion « How does flame spread change at lunar gravity? » | Réponse citée ; cliquer une citation → le PDF NTRS s'ouvre à la bonne page |
| 3 | Assistant | Taper « Which fuel goes out first in FLEX? » | Réponse issue du tableau d'essais : n-heptane à 84 % du diamètre initial, méthanol à 57 % |
| 4 | Simulator | Choisir **methanol**, oxygène **12 %**, d₀ **3 mm** | La flamme s'allume, la goutte rétrécit, la flamme s'éteint ; carte « Matching NASA test » : FLEX-086, extinction à 2,56 mm |
| 5 | Simulator | Basculer **Earth · 1 g**, puis revenir **ISS** | Flamme étirée et orangée sur Terre, sphérique et bleue en microgravité |
| 6 | Simulator | Monter l'oxygène à **40 %** | L'avertissement « outside the FLEX tests (12 to 34 %) » : l'outil connaît ses limites |
| 7 | Relevance | Basculer sur **Mars** | Finding n° 1 : en Saffire VI, ce sont la fumée et les gaz toxiques, pas la chaleur, le premier danger |

Questions de secours si Gemini est lent : « What happened in the fire aboard Mir in 1997? »
(≈ 5 s, très parlante) ; « What did the SAME experiment learn about smoke particle size? ».

---

## 3. Plan des slides (7 slides)

1. **Titre** : Hestia, « Guard the flame beyond Earth », nom de l'équipe, challenge « Flame in Freefall ».
2. **Le problème** : photo de l'incendie de Mir ou de Saffire ; « des décennies de données, dispersées dans des centaines de rapports ».
3. **La solution** : capture de l'accueil ; trois piliers : Ask, Explore, Simulate.
4. **Démo** : vidéo ou capture du simulateur (FLEX-086 : 2,52 mm prédit, 2,56 mm mesuré).
5. **Les données** : 55 rapports NTRS, 24 investigations PSI, 276 essais FLEX, ressources NASA ; « every claim cites its source ».
6. **Fiabilité** : modèle 2,3 fois meilleur qu'une estimation naïve sur K ; AUC 0,89 pour l'extinction ; seuil de pertinence calibré ; « insufficient data » plutôt que des réponses inventées.
7. **Limites et suite** : modèle limité au n-heptane et au méthanol en microgravité ; vue Terre illustrative ; ensuite : BASS-II, CFI-G et SPICE, matériaux solides, gravité partielle.

---

## 4. Points à vérifier avant l'enregistrement

- [ ] Le quota Gemini du jour (une question test dans l'assistant).
- [ ] `gemini-3.8-flash` à retester ; sinon garder `gemini-3.5-flash-lite`.
- [ ] Le texte « Key differences » de Compare régénéré en anglais (sinon, ne pas montrer Compare).
- [ ] Durée totale de la vidéo selon les règles de soumission Space Apps.

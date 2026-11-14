---
doc_id: psi-62
psi_id: PSI-62
acronym: "BASS FGM modeling"
title: "Concurrent Flame Spread Modeling using Flamelet Generated Manifolds in Microgravity with Comparison to BASS Experiments using Two-Color Tomography"
source_url: https://psi.nasa.gov/physci/repo/data/investigations/PSI-62
doi: 10.60555/e9xp-ex83
source_type: psi_investigation
license: CC0-1.0 (PSI data)
curated_fire_safety_tier: 2
curated_pillars: ['modeling', 'prevention']
---

# PSI-62 — Concurrent Flame Spread Modeling using Flamelet Generated Manifolds in Microgravity with Comparison to BASS Experiments using Two-Color Tomography

## Metadata
- research area: Combustion Science
- sub research area: Spacecraft Fire Safety
- project type: Ground Investigation
- proposal title: Concurrent Flame Spread Modeling using Flamelet Generated Manifolds in Microgravity with Comparison to BASS Experiments using Two-Color Tomography
- start date: 2019-05-01
- end date: 2021-04-30
- dataset size: 9.47 KB
- related: PSI-25, PSI-26
- fuel category: solid (modeling)
- fuels: PMMA sheets, spheres, rods, wax cylinders

## Objectives
The objective of this research was to develop and validate new flamelet generated manifold (FGM) modeling techniques for concurrent flame spread in microgravity. Concurrent flame spread presented one of the greatest modeling challenges in combustion science due to the intricate coupling between heat transfer, mass transport, and chemical kinetics near the solid-vapor interface. Traditional modeling strategies often relied on hybridized turbulence and chemistry models that were not fully consistent and failed to capture important intermediate reaction pathways.
To overcome these shortcomings, this PSI grant advanced the use of an unsteady flamelet generated manifold (UFGM) framework that reduced the complexity of reacting systems by mapping them into lower-dimensional manifolds. The research aimed to leverage this methodology to simulate solid fuel combustion processes with high fidelity, using the NASA Burning and Suppression of Solids (BASS and BASS-II) experiments as benchmarks. Ultimately, the long-term goal was to enable accurate prediction of flammability limits for spacecraft materials and to provide a tool that could also serve as a subgrid-scale model in large-eddy simulations of fires, supporting spacecraft safety and hazard mitigation.

## Approach
The approach combined high-resolution computational modeling with experimental validation to study concurrent flame spread in microgravity. A previously developed computational framework was employed to run fully coupled simulations of fluid–solid responses, focusing on materials subject to charring and ablation. Within this framework, the unsteady FGM method was implemented and tested on various BASS geometries, including flat sheets, spheres, and rod-shaped polymethyl methacrylate (PMMA) samples, as well as wax cylinders.
Experimental imagery found in PSI from the BASS and BASS-II investigations was post-processed using newly developed two-color tomography methods with DSLR cameras, enabling 3D reconstructions of soot and temperature fields for direct comparison to model predictions. The evaluation metrics included flame geometry, temperature distribution, soot volume fraction, and flame spread rate, with special emphasis on reproducing the “Goldilocks” flammability zone reported by Olson and Ferkul. Comparative analyses were also carried out with a parallel NSF-supported terrestrial flame spread project, ensuring that the predictive capabilities of the UFGM approach were assessed across both microgravity and normal-gravity conditions.

## Hypothesis
The unsteady flamelet generated manifold (UFGM) approach was believed to be able to accurately reproduce concurrent flame spread in microgravity, including phenomena such as the “Goldilocks” flammability zone, by coupling near-wall thermal, mass transport, and chemical processes with far-field flow dynamics.

## Research Impacts / Earth Benefits
This research provides predictive tools for screening new materials’ flammability limits, which can lead to the design of safer spacecrafts. The development of Large Eddy Simulation subgrid models is expected to improve hazard assessment capabilities critical for managing fire risks during long-duration space missions and within confined spacecraft habitats. On Earth, these advancements could improve combustion modeling by deepening our understanding of coupled thermal, chemical, and flow processes, which betters fire safety standards. The computational methods being refined have the potential to enable more effective fire prevention and mitigation strategies and foster innovations in diagnostics and simulations applicable across a variety of combustion scenarios. Overall, this research can contribute significantly to safer human exploration in space and improvements to fire safety protocols on Earth.

## Contacts
- Paul DesJardin (PI, University at Buffalo)
- David Urban (Project Scientist, NASA GRC)

## Experimental table (PSI)
- rows: 0

## Publications (all 4 listed on PSI page)
- Microgravity flammability boundary for PMMA rods in axial stagnation flow: Experimental results and energy balance analyses (2017) (Olson, Ferkul) doi:10.1016/j.combustflame.2017.03.001
- Radiative flamelet generated manifolds for solid fuel flame spread in microgravity (2023) (Budzinski, DesJardin) doi:10.1016/j.combustflame.2023.112939
- Theoretical estimates of flammability bounds for thin condensed fuel diffusion flames in microgravity using detailed models of chemistry and radiation (2023) (Budzinski, DesJardin) doi:10.1016/j.combustflame.2023.112910
- Two-color pyrometry based flame to fuel surface radiative heat flux diagnostic using flamelets (Aphale, DesJardin) doi:10.1016/j.combustflame.2021.111395

## Curated annotation (not NASA text)
- fire-safety tier: 2
- pillars: modeling, prevention
- habitat relevance: predictive flammability limits for spacecraft materials from BASS data ('Goldilocks' zone)
- see also: PSI-25, PSI-26

---
doc_id: psi-69
psi_id: PSI-69
acronym: "FLEX"
title: "Flame Extinguishment Experiment (FLEX)"
source_url: https://psi.nasa.gov/physci/repo/data/investigations/PSI-69
doi: 10.60555/mbq8-0451
source_type: psi_investigation
license: CC0-1.0 (PSI data)
curated_fire_safety_tier: 1
curated_pillars: ['suppression', 'prevention']
---

# PSI-69 — Flame Extinguishment Experiment (FLEX)

## Metadata
- research area: Combustion Science
- sub research area: Spacecraft Fire Safety
- project type: Microgravity Investigation
- proposal title: Droplet Flame Extinguishment in Microgravity
- platform: International Space Station (ISS)
- start date: 2007-08-01
- end date: 2016-07-31
- dataset size: 860.39 GB
- hardware: Combustion Integrated Rack (CIR) - Fluids and Combustion Facility (FCF), Multi-user Droplet Combustion Apparatus (MDCA)
- fuel category: liquid droplets
- fuels: methanol, n-heptane, n-octane, n-decane, propanol, alkane/alcohol mixtures
- key conditions: pressure_atm: 0.5-1.5 (LOI tests); droplet_diameter_mm: ~1.6-5 (≈3 mm small droplets); suppressants: CO2, He, SF6; oxygen: varied down to non-ignition to find LOI

## Objectives
The FLEX (Flame Extinguishment Experiment) investigation aims to map the flammability limits of liquid fuels in microgravity environments, measure the effectiveness of various gaseous fire suppressants such as CO2, He, and SF6, and develop reliable predictive models for combustion limits under reduced gravity conditions. The mission seeks to validate and improve simplified models by incorporating detailed chemical reactions, heat transfer, and material movement, using both space-based data and extensive ground-based tests. Key flight experiment goals include obtaining high-resolution measurements of droplet burning rates, flame extinction behavior, heat radiation, soot levels, and temperature profiles, while systematically analyzing the effects of different ambient conditions and suppressant concentrations.

## Approach
The FLEX experiments involve igniting and observing the burning behavior of relatively large droplets. A primary objective of the experiments is to determine the Limiting Oxygen Index (LOI) as a function of ambient pressure and determine how the presence of a suppressant influences the LOI. Procedure: 1. Select the test pressure (0.5 − 1.5 atm) for the LOI tests. 2. Select a smaller droplet size (≈ 3 mm). 3. Select an ambient oxygen mole fraction that, based on ground-based testing, will support droplets burning to completion. 4. Perform a droplet combustion test. 5. Increase the droplet size or repeat the test (if finite extinction diameter at flame extinction observed). 6. Continue steps 4 and 5 until flame exists for only a short time after ignition (radiative extinction). 7. Continue steps 4 thru 6 at a decreased ambient oxygen mole fraction. 8. Continue step 7 to an ambient oxygen mole fraction where the droplet does not ignite. Where extinction droplet sizes were too small to observe, the LOI was found iteratively (burn to completion followed by a no-ignition test) with progressively smaller increments in oxygen mole fraction. In slow-flow tests, near the end of burning the droplet is subjected to a small, sub-buoyant convective flow (by translating the droplet at a slow uniform speed) to see how this flow influences extinction. Many tests involve free (unsupported) droplets, some with a slow drift velocity.

## Hypothesis
The primary hypothesis of the FLEX mission is that microgravity conditions fundamentally alter the combustion and extinction characteristics of liquid fuel droplets due to changes in species and energy transport dynamics, radiative heat loss, and chemical kinetics. Specifically, the lack of buoyant convection in microgravity will lead to significant differences in the flammability limits and suppression efficacy of various fire suppressant agents compared to normal gravity conditions.

## Research Impacts / Earth Benefits
Improved fire safety protocols for future space missions where traditional fire suppression methods may be ineffective. On Earth, insights can advance fire safety in confined and reduced-gravity environments, such as submarines or high-altitude aircraft. Findings on the effectiveness of suppressants (CO2, He, SF6) in microgravity can lead to more efficient and less harmful fire suppression systems, reducing the risk of toxic byproducts. The study of 'cool flames' and low-temperature combustion observed in microgravity can inform the design of advanced combustion engines with improved fuel efficiency and reduced emissions.

## Notable discovery
FLEX revealed quasi-steady droplet burning supported by 'cool flames' (low-temperature chemistry) after radiative extinction of the hot flame for n-alkanes (see Nayagam et al., 'Can cool flames support quasi-steady alkane droplet burning?' 2012).

## Contacts
- Forman A Williams (PI, UC San Diego)
- Benjamin D Shaw (Co-I, UC Davis)
- Michael C Hicks (Co-I, NASA GRC)
- Vedha Nayagam (Co-I, Case Western Reserve University)
- Mun Y Choi (Co-I, University of Missouri)
- Frederick L Dryer (Co-I, University of South Carolina)
- Daniel Dietrich (Project Scientist, NASA GRC)

## Experimental table (PSI)
- rows: 275
- columns: FLEX Test #, FLEX Identifier, Test Date, Test GMT, Fuel, Ambient pressure (mmHg), O2 initial mole fraction, N2 initial mole fraction, CO2 initial mole fraction, He initial mole fraction, Droplet initial diameter (mm), Visible flame extinction diameter (mm), Burning rate (mm2/s), Burn time (s), Test end
- sample: 1 | 20CAL08 | 3/5/2009 | Methanol | 757.7 mmHg | O2 0.21 | N2 0.79 | d0 1.69 mm | dext 0.89 mm | K 0.52 | 4.3 s | Disruption
- sample: 2 | 20CAL10 | Methanol | 762 mmHg | d0 1.86 | dext 0.94 | K 0.6 | 5 s | Extinction
- sample: 5 | 30CAL03 | Methanol | 760 mmHg | d0 1.92 | dext 0.81 | K 0.48 | 6.34 s | Extinction

## Data folders in PSI
Investigation Metadata Files, Experimental table, Engineering Documents, Presentations, Raw Data, Calibration, Science Documents

## Selected publications (partial list; 51 on PSI page)
- Droplet Combustion Experiments Aboard the International Space Station (Dietrich et al.) doi:10.1007/s12217-014-9372-2
- Can cool flames support quasi-steady alkane droplet burning? (Nayagam et al.) doi:10.1016/j.combustflame.2012.07.012
- Cool-flame extinction during n-alkane droplet combustion in microgravity (Nayagam et al.) doi:10.1016/j.combustflame.2015.01.012
- Tethered methanol droplet combustion in carbon-dioxide enriched environment under microgravity conditions (Farouk, Dryer) doi:10.1016/j.combustflame.2011.06.014
- Activation energy asymptotics for methanol droplet extinction in microgravity (Nayagam) doi:10.1016/j.combustflame.2013.05.011
- Ignition and combustion of n-heptane droplets in carbon dioxide enriched environments (Dzik, Nayagam, Williams) doi:10.1016/j.icheatmasstransfer.2009.10.006
- Nonane droplet combustion with and without buoyant convection: flame structure, burning rate and extinction in air and helium (Bae, Avedisian) doi:10.1016/j.proci.2008.06.221
- Detailed results from the flame extinguishment experiment (FLEX) - March 2009 to December 2011 (Dietrich et al.)
- Methanol Droplet Extinction in Oxygen/Carbon-dioxide/Nitrogen Mixtures in Microgravity: Results from the ISS Experiments (Nayagam)

## Curated annotation (not NASA text)
- fire-safety tier: 1
- pillars: suppression, prevention
- habitat relevance: limiting oxygen index of liquid fuels; CO2/He/SF6 suppressant efficacy; cool flames
- see also: PSI-68, PSI-39, PSI-117, PSI-142

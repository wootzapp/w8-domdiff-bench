# Evidence Error Audit: browser_task_009-nasa-mission-lookup-20260909T073151Z

Run: `20260909T_task009_data_new`  
Rubric SHA-256: `d8501aa855b5b07aec67fd374fcfe17455c57c18ab59a631d96ed88fe1d6fe4d`

| Criterion | Screenshot evidence reported | DOM evidence reported | Screenshot points | DOM points | Review | Classification |
|---|---|---|---:|---:|---|---|
| 0: Use NASA’s website as the source of truth | Screenshots 1,3,4,5,6 all show NASA.gov pages (NASA header/logo and nasa.gov search results). Screenshot 6 (latest, mission detail page) shows the Artemis II mission page with mission metadata, confirming NASA’s website was used as the s... | Latest relevant evidence is DOM-model state 5, which shows the agent on nasa.gov at https://www.nasa.gov/mission/artemis-ii/ (official NASA mission page) with mission descriptors. Earlier states (0-4) also show nasa.gov navigation/search... | 3.0/3 | 3.0/3 | not_required | PENDING |
| 1: Identify the next planned Artemis mission | Screenshot 6 (latest) shows the Artemis II page and explicitly labels it “OCCURRED 5 MONTHS AGO,” indicating it is not upcoming/next planned. Screenshots 4 and 5 do not show any explicit ‘next planned mission’ ordering statement. | DOM-model state 4 (Artemis program page) and state 5 (Artemis II mission page) both show an Artemis navigation listing (Artemis I, Artemis II, Artemis III, Artemis IV) implying order. However, neither explicitly labels Artemis II as the ... | 0.0/4 | 3.0/4 | pending | PENDING |
| 2: Report mission name | Screenshot 6 (latest) clearly shows the mission page heading “Artemis II.” | DOM-model state 5 title includes 'Artemis II: NASA’s First Crewed Lunar Flyby in 50 Years' and the page/nav also shows 'Artemis II' and related headers (e.g., 'Our Artemis II Crew'). | 2.0/2 | 2.0/2 | pending | PENDING |
| 3: Report planned launch year | Screenshot 6 (latest) shows a right-side metadata field “LAUNCHED: April 1, 2026,” which contains the year 2026. No screenshot shows an explicitly ‘planned launch year’ field; it is framed as already launched. | Latest relevant evidence is DOM-model state 5, which shows 'LaunchED April 1, 2026' (and also 'splashdown April 10, 2026'). This directly provides the year 2026. Earlier states do not include launch-year info. | 3.0/3 | 3.0/3 | not_required | PENDING |
| 4: Report destination | Screenshot 6 (latest) shows “MISSION TYPE: Crewed Lunar Flyby,” supporting a destination of a lunar flyby around the Moon. | DOM-model state 5 shows 'Mission Type: Crewed Lunar Flyby' and text about venturing around the Moon, supporting a destination of a lunar flyby/around-the-Moon trajectory. | 2.0/2 | 2.0/2 | not_required | PENDING |
| 5: Report primary objective | Screenshot 6 (latest) includes the description: “The first crewed Artemis flight marks a key step toward long-term return to the Moon and future missions to Mars.” | DOM-model state 5 includes objective-style statements such as 'The first crewed Artemis flight marks a key step toward long-term return to the Moon and future missions to Mars,' and language about paving the way for future lunar surface ... | 3.0/3 | 3.0/3 | not_required | PENDING |
| 6: Respect constraints (no sign-in, no registration) and stopping condition | Across screenshots (notably 4–6), there are no sign-in or registration prompts interacted with. Screenshot 6 indicates the agent reached the needed mission page; nothing suggests additional unnecessary steps beyond gathering details. | Action history and DOM states show only search and navigation clicks on nasa.gov; no sign-in/registration flows are shown. The agent stopped after reaching Artemis II and providing the four requested fields. | 3.0/3 | 3.0/3 | pending | PENDING |

## Recovery metrics

- DOM recovery of confirmed screenshot misses: 0/0 (N/A%).
- Screenshot recovery of confirmed DOM misses: 0/0 (N/A%).
- Classified criteria: 0/7.

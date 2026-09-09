# Evidence Error Audit: browser_task_004-museum-film-lookup-20260909T071414Z

Run: `20260909T_task004_data_new`  
Rubric SHA-256: `81ae2fa388b310f12bcd2015339158be8169f748f3fd281893eb5bec3606ab77`

| Criterion | Screenshot evidence reported | DOM evidence reported | Screenshot points | DOM points | Review | Classification |
|---|---|---|---:|---:|---|---|
| 0: Navigate DMNS site to Sturm Infinity Theater 'currently playing' information | Latest screenshot (2 of 2) shows DMNS 'Films & Shows' page with a 'Now Showing' hero and a partially visible 'Sturm Theater' section header, but no visible list of films nor explicit 'Sturm Infinity Theater' listing details. Action histo... | Latest DOM is DOM-model state 1 showing URL https://www.dmns.org/films-and-shows/ with a visible 'Now Showing' heading and text referencing 'Sturm Theater', but no visible film tiles/listings or explicit 'Sturm Infinity Theater' current ... | 1.0/3 | 2.0/3 | pending | PENDING |
| 1: Identify one film currently playing (title) | Both screenshots show no film titles. Latest screenshot (2 of 2) contains only 'Now Showing' and 'Sturm Theater' header, without any film cards/titles. Predicted output contains only an error message and no film title. | Latest DOM is DOM-model state 1 (https://www.dmns.org/films-and-shows/) and it does not display any film titles in the visible content—only 'Now Showing' and general copy. DOM-model state 0 also has no film titles. Agent predicted output... | 0.0/3 | 0.0/3 | pending | PENDING |
| 2: Report what the film is about (description/summary) | Neither screenshot contains a film-specific synopsis/description; latest screenshot (2 of 2) only has generic 'Shows change regularly...' text. Predicted output provides no description, only a timeout error. | Latest DOM is DOM-model state 1 and contains only a generic Sturm Theater description (state-of-the-art giant screen theater), not a film-specific synopsis. No film title is identified in any DOM state, and the agent output contains no d... | 0.0/2 | 0.0/2 | pending | PENDING |
| 3: Report scheduled showtimes for the selected film | No showtimes are visible in either screenshot; latest (2 of 2) shows no schedule module. Predicted output lists no showtimes and only reports a snapshot timeout error. | Latest DOM is DOM-model state 1 and shows no schedule widgets or showtime times (no AM/PM times, no date/time listings). DOM-model state 0 also has no showtimes. Agent output includes only a RunnerError and does not list showtimes or exp... | 0.0/4 | 0.0/4 | pending | PENDING |
| 4: Respect constraints (no sign-in, no purchase, no seat reservation) and stop after one film | Screenshots show 'Login' and 'Buy Tickets' options in the header but no evidence they were used; no sign-in form, checkout, or seat selection is shown. Action history shows only navigation/clicking on Films & Shows. Predicted output is a... | Across DOM-model states 0 and 1 there is navigation including 'Login'/'Buy Tickets'/'Cart', but no evidence of the agent signing in, purchasing, entering checkout, or selecting seats. Action history shows only a click into Films & Shows ... | 3.0/3 | 3.0/3 | pending | PENDING |

## Recovery metrics

- DOM recovery of confirmed screenshot misses: 0/0 (N/A%).
- Screenshot recovery of confirmed DOM misses: 0/0 (N/A%).
- Classified criteria: 0/5.

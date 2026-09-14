# Evidence-Item Audit: browser_task_085-asteroid-record-20260909T091202Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use only the supplied NASA/JPL SBDB response (99942 Apophis, phys-par=1) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: NASA/JPL Small-Body Database (SBDB) API response); verifier caught | Present (dom_model0.txt m0:L1-L1; dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report object.fullname exactly | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: object.fullname); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Report orbit class name and code from object.orbit_class | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: object.orbit_class name and code); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Report orbit.epoch exactly | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: orbit.epoch: 2461200.5); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report absolute magnitude (H) value and uncertainty from phys_par | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot4.png: phys_par entry name H with value and sigma); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Report diameter value, uncertainty, and unit from phys_par | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot4.png: phys_par entry name diameter with value, sigma, and units); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C6 | Report potentially hazardous asteroid flag from object.pha | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: object.pha); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C7 | Output scope: only requested fields; no extra SBDB fields | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: The final answer reports the visibility limitation rather than unrelated SBDB fields); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 3.
- Screenshot catch rate on common evidence: 3/3 (100.0%).
- DOM catch rate on common evidence: 3/3 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).

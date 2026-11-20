# Browser tasks

`tasks.jsonl` contains 40 public, read-only browser tasks: 10 each at easy, medium,
hard and complex difficulty. Each task starts at its `start_url` and ends when its
`stopping_condition` is satisfied.

| Field | Description |
| --- | --- |
| `task_id` | Stable task identifier. |
| `task_name` | Short task title. |
| `category` | Type of research or comparison. |
| `instruction` | Scope, required findings and answer format. |
| `start_url` | Public website entry point. |
| `stopping_condition` | Required deliverables before finishing. |
| `constraints` | Shared browser, access and read-only rules. |
| `difficulty` | Easy, medium, hard or complex, based on the required work. |

Difficulty describes the research scope; every task uses the same configured
turn cap. The turn ranges below are planning guidance, not measured task lengths.

| Difficulty | Scope | Turn guidance |
| --- | --- | --- |
| Easy | One site, one to three pages, a few facts or a simple filter or search. | 5–15 |
| Medium | Filters, sorting or detail pages with several related findings. | 15–40 |
| Hard | Deep navigation or two to three sites with multiple constraints. | 40–100 |
| Complex | Several sites, comparing or calculating across many items. | Generally under 150 |

Report changing values as observed during the run and cite the source
pages used.

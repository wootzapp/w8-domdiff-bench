# Browser tasks

`tasks.jsonl` contains 25 public, read-only browser tasks: 10 medium, 10 hard and
5 complex. Each task starts at its `start_url` and ends when its
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
| `difficulty` | Medium, hard or complex, based on the required work. |

Difficulty describes the research scope; every task uses the same configured
turn cap. Report changing values as observed during the run and cite the source
pages used.

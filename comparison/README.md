# Screenshot and DOM-diff verifier comparison

## Structure

```text
comparison/
├── dom_diff/              # Standalone DOM-evidence verifier package
├── microsoft_verifier/    # Fixed Microsoft screenshot baseline
├── manifests/             # Verifier-package integrity receipts
├── scripts/               # Frozen-rubric and comparison orchestration
├── config/                # Judge endpoint configuration
├── run-comparison         # One-command launcher
└── requirements.txt
```

Paired task inputs live in the repository-level `data/` folder. Generated runs
are written to the repository-level `results/` folder.

## Set up the comparison

Python 3.10 or newer is required. From a fresh clone, enter the comparison
folder, create its virtual environment, and install the pinned dependencies:

```bash
git clone https://github.com/wootzapp/w8-domdiff-bench.git
cd w8-reproducible/comparison

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create the local environment file, then set its API key with your preferred
text editor:

```bash
cp .env.example .env
```

Set the OpenAI API key in `.env`:

```text
OPENAI_API_KEY=your-api-key
```

The launcher reads this file automatically. `.env` is ignored by Git and must
not be committed.

## Run a complete comparison

Task folders are paired by name under `../data/data-ss/` and
`../data/data-dom/`. To evaluate `task_01`, run:

```bash
./run-comparison --task task_01 --execute
```

This command generates one fresh Microsoft rubric, passes that exact frozen
rubric to both verifiers, scores both evidence formats, and writes the final
comparison. It makes paid model calls and submits the supplied task evidence to
the configured API endpoint.

The command automatically resolves:

```text
Screenshot input: ../data/data-ss/task_01
DOM input:        ../data/data-dom/task_01
Judge config:     config/
Run output:       ../results/task_01/<run-id>/
```

To validate configuration and paths without writing results or making paid
calls, omit `--execute`:

```bash
./run-comparison --task task_01
```

Completed runs are stored under `../results/<task>/<run-id>/`. The final
`comparison.json` and `comparison.md` contain only total and criterion-level
scores.
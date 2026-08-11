# Browser Task Recorder

## View the Browser Through an SSH Tunnel

Run this on your local computer:

```bash
ssh -N -L "[::1]:39084:127.0.0.1:16191" ubuntu@static.235.31.55.162.clients.your-server.de
```

Keep the terminal open, then visit:

```text
http://[::1]:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

If `NOVNC_HOST_PORT` differs from its default, replace `16191` in the tunnel command.

## Run Any Task

The CLI accepts any task ID, instruction, and HTTP(S) start URL. It does not depend on stored task folders.

The browser container and its profile persist across tasks. Run a task directly:

```bash
cd /data/aayush/task-recorder-dom-diff

./run-task task17 "example research task" \
    --task "Open the website, find the requested information, report it, and obey all stated constraints." \
    --start-url "https://example.com/" \
    --env-file .env \
    --max-steps 80
```

`run-task` starts the compose browser service with `--no-recreate` when needed. It does not stop or remove the container afterward, so browser cookies, history, and authenticated sessions remain available. At the beginning of every task it:

1. stops any earlier runner and its child processes;
2. creates and activates one fresh browser tab;
3. closes all normal tabs left by earlier tasks; and
4. attaches agent-browser and ChromiumRL capture to the fresh tab.

Starting another task while one is running intentionally interrupts the older run. Its manifest is marked `interrupted`, and verifier trajectory files are not generated from that incomplete run. Ctrl+C performs the same graceful cleanup. The browser container remains running in both cases.

Do not use `docker compose down`, `docker compose rm`, or `--force-recreate` between tasks when you want login sessions to persist. To start the browser manually without running a task, use:

```bash
docker compose --env-file .env up -d --no-recreate --wait wootz-desktop
```

Replace `task17`, the name, instruction, and URL with your own task. The instruction should include the goal, stopping condition, and every constraint. By default the recording is written to a timestamped directory under `fresh-tasks/<task-id>/`; an existing run is never overwritten.

Human intervention is enabled by default. If the runner pauses for a permitted CAPTCHA or browser verification, solve only that visible challenge through noVNC, return to the task terminal, and press Enter. Type `abort` to stop. Use `--no-human-intervention` for unattended runs.

Validate a command without starting the browser task:

```bash
./run-task task17 "example research task" \
    --task "Open the website and report its visible page title." \
    --start-url "https://example.com/" \
    --dry-run
```

## Tasks 1–16 Dataset

These are reference definitions. To rerun one, pass its ID, instruction, and start URL to the generic command above.

| ID | Category | Start URL | Instruction, stopping condition, and constraints |
|---|---|---|---|
| task1 | Reddit ranking | https://www.reddit.com/r/LocalLLaMA/ | In r/LocalLLaMA, sort posts by **Top** for **This Week** and report the exact title and displayed score of the #1 post. Stop after verifying both filters and recording the result. Do not sign in, vote, comment, save, or create a post. If Reddit presents an access block that cannot be resolved without signing in, do not bypass it; report the visible block. |
| task2 | Xbox product research | https://www.xbox.com/ | Find a game listed under **Best sellers**, open its product page, and report its exact title, publisher, developer, and release date. If a candidate lacks any field, return and choose another. Stop after all fields are recorded. Do not sign in, buy, or download anything. |
| task3 | Job listing extraction | https://careers.microsoft.com/ | Search for an **Applied Scientist** position in **Redmond, Washington**. Open a listing whose title contains Applied Scientist and report its exact job number, work-site arrangement, two key responsibilities, and two preferred qualifications from visible evidence. Stop after all fields are recorded. Do not sign in, apply, save, favorite, add the job to a cart, or submit a form. |
| task4 | Museum film lookup | https://www.dmns.org/ | Find one film currently playing at the **Sturm Infinity Theater** and report its exact title, description, and all visible scheduled showtimes. Wait for loading content when necessary and do not loop on an inactive control. Stop after all fields are recorded. Do not sign in, purchase tickets, or reserve seats. |
| task5 | Event lookup | https://www.bush41.org/ | Find the next upcoming event and report its exact title, date, time, and location. Stop after viewing the next event and recording all fields. Do not sign in, register, or purchase tickets. |
| task6 | Earliest article lookup | https://searchengineland.com/ | Find the earliest article available on Search Engine Land and report its exact title, publication date, and author. Verify it using the site archive or oldest reachable ordering. Stop after all fields are recorded. Do not sign in, publish, edit, or comment. |
| task7 | Bestseller and recipe research | https://www.amazon.in/gp/bestsellers/grocery/ | Verify the #2 item in Amazon India Grocery & Gourmet Foods bestsellers, identify its ingredient, then find an AllRecipes recipe using that ingredient. Report the exact bestseller, recipe title, and full ingredient list. Do not sign in, add to cart, or purchase. If a bot check appears, stop and record it rather than bypassing it. |
| task8 | Playwright release research | https://github.com/microsoft/playwright | Open Releases and identify the newest non-preview Playwright release. Report its exact tag, publication date, and three changes, then verify one change using official Playwright documentation. Stop after all release and verification evidence is recorded. Do not sign in or create issues, comments, pull requests, or file changes. |
| task9 | NASA mission lookup | https://www.nasa.gov/ | Find the next planned Artemis mission and report its name, planned launch year, destination, and primary objective. Use NASA as the source of truth and stop after all fields are recorded. Do not sign in or register for updates. |
| task10 | Official Gemini documentation | https://www.google.com/ | Use Google Search to find official Gemini API documentation. Report the page title, domain, Python SDK, and model used in the Python example. Use an official Google domain and stop after all fields are recorded. Do not sign in, create an API key, or run code. |
| task11 | arXiv literature search | https://arxiv.org/search/advanced | Use Advanced Search to find cs.LG papers submitted within the browser's last 30 days whose titles contain the exact phrase **mixture of experts**. Sort newest first and report the three most recent papers with arXiv IDs, titles, and first authors. Verify category, date, and title filters. Do not log in or submit or modify a paper. |
| task12 | arXiv version metadata | https://arxiv.org/abs/1706.03762 | Open arXiv:1706.03762 and report the total version count, version 1 publication date, and latest-version publication date using the exact displayed date strings. Stop after recording them. Do not sign in, download, or edit the paper. |
| task13 | Chess profile lookup | https://www.chess.com/players/magnus-carlsen | Report Magnus Carlsen's current Blitz and Bullet ratings exactly as displayed. Stop after recording both. Do not sign in, challenge, message, or interact with another player. |
| task14 | Reddit post lookup | https://www.reddit.com/r/MachineLearning/ | Sort r/MachineLearning by **Top** for the **past month**, open the highest-ranked post, and report its exact title, author, score, and comment count. Stop after verifying the filters and recording all fields. Do not sign in, vote, comment, save, or create a post. |
| task15 | Reddit community comparison | https://www.reddit.com/r/Python/ | Open r/Python, r/learnpython, and r/django, record each subscriber count, and rank them largest to smallest in a table. Stop after all counts and the ranking are recorded. Do not sign in, join, vote, comment, or post. |
| task16 | Hugging Face model metadata | https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct | Report the visible license name, current likes count, and whether the repository is gated. Do not infer from the model name. Stop after all evidence is recorded. Do not sign in, request access, or download model files. |

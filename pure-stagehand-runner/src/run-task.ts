import "dotenv/config";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import process from "node:process";
import { Stagehand } from "@browserbasehq/stagehand";

type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

type Args = {
  taskId: string;
  task: string;
  maxSteps: number;
  startUrl: string;
  headless: boolean;
  keepOpen: boolean;
};

function parseArgs(): Args {
  const argv = process.argv.slice(2);
  const get = (name: string, fallback?: string): string | undefined => {
    const i = argv.indexOf(name);
    if (i >= 0) return argv[i + 1];
    return fallback;
  };
  const has = (name: string) => argv.includes(name);

  const taskId = get("--task-id");
  const task = get("--task");
  if (!taskId || !task) {
    throw new Error(
      "Usage: tsx src/run-task.ts --task-id <id> --task <prompt> [--max-steps 80]",
    );
  }

  return {
    taskId,
    task,
    maxSteps: Number(get("--max-steps", process.env.STAGEHAND_MAX_STEPS || "80")),
    startUrl: get("--start-url", process.env.START_URL || "about:blank")!,
    headless:
      has("--headless") ||
      String(process.env.HEADLESS || "false").toLowerCase() === "true",
    keepOpen:
      has("--keep-open") ||
      String(process.env.KEEP_OPEN || "false").toLowerCase() === "true",
  };
}

function safeJson(value: unknown, depth = 0): JsonValue {
  if (value === null) return null;
  if (typeof value === "string") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "boolean") return value;
  if (typeof value === "bigint") return value.toString();
  if (typeof value === "undefined") return null;
  if (typeof value === "function") return `[Function ${value.name || "anonymous"}]`;
  if (Buffer.isBuffer(value)) return `[Buffer ${value.length} bytes]`;
  if (depth > 8) return "[MaxDepth]";
  if (Array.isArray(value)) return value.map((v) => safeJson(v, depth + 1));
  if (typeof value === "object") {
    const out: Record<string, JsonValue> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (k === "screenshot" && Buffer.isBuffer(v)) {
        out[k] = `[Buffer ${v.length} bytes]`;
      } else {
        out[k] = safeJson(v, depth + 1);
      }
    }
    return out;
  }
  return String(value);
}

async function writeJson(file: string, value: unknown): Promise<void> {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(safeJson(value), null, 2));
}

async function writeText(file: string, value: string): Promise<void> {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, value);
}

async function appendJsonl(file: string, value: unknown): Promise<void> {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.appendFile(file, JSON.stringify(safeJson(value)) + "\n");
}

function shortJson(value: unknown, max = 900): string {
  const text = JSON.stringify(safeJson(value), null, 2);
  return text.length > max ? text.slice(0, max) + "\n...<truncated>" : text;
}

function modelPromptText(input: unknown): string {
  const messages = Array.isArray(input) ? input : [input];
  return messages
    .map((message, index) => {
      if (message && typeof message === "object") {
        const record = message as Record<string, unknown>;
        const role = typeof record.role === "string" ? record.role : "unknown";
        const content = record.content;
        const contentText =
          typeof content === "string" ? content : JSON.stringify(safeJson(content), null, 2);
        return `--- message ${index + 1} | role: ${role} ---\n${contentText}`;
      }
      return `--- message ${index + 1} | role: unknown ---\n${String(message)}`;
    })
    .join("\n\n");
}

function printStepHeader(step: number, label: string): void {
  console.log("=".repeat(78));
  console.log(`STEP ${String(step).padStart(3, "0")} ${label}`);
  console.log("=".repeat(78));
}

function stepDir(taskDir: string, step: number): string {
  return path.join(taskDir, `step_${String(step).padStart(3, "0")}`);
}

async function pageState(page: any): Promise<Record<string, unknown>> {
  try {
    return await page.evaluate(() => ({
      url: location.href,
      title: document.title,
      readyState: document.readyState,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio,
      },
      bodyTextPreview: document.body?.innerText?.slice(0, 4000) ?? "",
    }));
  } catch (error) {
    return { error: String(error) };
  }
}

async function captureScreenshot(page: any, file: string): Promise<void> {
  try {
    await fs.mkdir(path.dirname(file), { recursive: true });
    await page.screenshot({ path: file, fullPage: false });
  } catch (error) {
    await writeJson(file.replace(/\.png$/, ".error.json"), { error: String(error) });
  }
}

async function main() {
  const args = parseArgs();
  const modelName = process.env.STAGEHAND_MODEL || "openai/gpt-4.1-mini";
  const browserLang = process.env.BROWSER_LANG || "en-US";
  const browserAcceptLanguage =
    process.env.BROWSER_ACCEPT_LANGUAGE || "en-US,en;q=0.9";
  const defaultSystemPrompt =
    "If a cookie consent, privacy dialog, sign-in prompt, ad, newsletter modal, or other overlay blocks the task, handle it first using the visible controls. Prefer the least intrusive option that lets you continue, such as close, reject non-essential cookies, continue without sign-in, or accept only if needed. Do not spend steps on popups that do not block the task.";
  const agentSystemPrompt = process.env.STAGEHAND_SYSTEM_PROMPT || defaultSystemPrompt;

  if (
    process.platform === "linux" &&
    !args.headless &&
    !process.env.DISPLAY &&
    !process.env.WAYLAND_DISPLAY
  ) {
    throw new Error(
      "HEADLESS=false requires a Linux GUI display, but DISPLAY/WAYLAND_DISPLAY is not set. This is not an SSH tunnel problem. Run with HEADLESS=true, or start the task inside a real X11/VNC/Xvfb display.",
    );
  }

  const root = process.cwd();
  const taskDir = path.join(root, "tasks", args.taskId);

  if (fsSync.existsSync(taskDir)) {
    throw new Error(`Task folder already exists: ${taskDir}. Use a new task id.`);
  }

  await fs.mkdir(taskDir, { recursive: true });

  await writeJson(path.join(taskDir, "task.json"), {
    task_id: args.taskId,
    task: args.task,
    runner: "pure-stagehand",
    chromiumrl: false,
    cdp_url: null,
    model: modelName,
    max_steps: args.maxSteps,
    start_url: args.startUrl,
    browser_lang: browserLang,
    browser_accept_language: browserAcceptLanguage,
    stagehand_system_prompt: agentSystemPrompt,
    started_at: new Date().toISOString(),
  });

  const previousCwd = process.cwd();
  process.chdir(taskDir);

  let step = 0;
  let latestScreenshot: Buffer | null = null;
  let latestAriaTree = "";

  const logger = (line: unknown) => {
    void appendJsonl(path.join(taskDir, "stagehand_logs.jsonl"), {
      timestamp: new Date().toISOString(),
      line,
    });
  };

  const stagehand = new Stagehand({
    env: "LOCAL",
    experimental: String(process.env.STAGEHAND_EXPERIMENTAL || "true") === "true",
    verbose: 2,
    logInferenceToFile: true,
    disablePino: true,
    logger,
    localBrowserLaunchOptions: {
      headless: args.headless,
      locale: browserLang,
      args: [`--accept-lang=${browserAcceptLanguage}`],
    },
    model: modelName,
  } as any);

  await stagehand.init();

  const page = stagehand.context.pages()[0];
  if (args.startUrl && args.startUrl !== "about:blank") {
    await page.goto(args.startUrl);
  }

  const agent = stagehand.agent({
    model: modelName,
    executionModel: modelName,
    systemPrompt: agentSystemPrompt,
  } as any);

  console.log(`Pure Stagehand task: ${args.taskId}`);
  console.log(`Prompt: ${args.task}`);
  console.log(`Model: ${modelName}`);
  console.log(`Artifacts: ${taskDir}`);
  console.log(`Start URL: ${args.startUrl}`);
  console.log(`Browser language: ${browserLang}`);
  console.log("Generic blocker handling: enabled");

  try {
    const result: any = await agent.execute({
      instruction: args.task,
      maxSteps: args.maxSteps,
      callbacks: {
        prepareStep: async (prepare: any) => {
          const next = step + 1;
          printStepHeader(next, "MODEL CALL START");
          console.log("Stagehand is preparing the next browser-agent model call...");
          const dir = stepDir(taskDir, next);
          await writeJson(path.join(dir, "agent_input.json"), {
            timestamp: new Date().toISOString(),
            note: "Exact model-step input available to Stagehand before the browser-agent LLM call.",
            prepare_step: prepare,
          });
          return {};
        },
        onStepFinish: async (event: any) => {
          step += 1;
          const dir = stepDir(taskDir, step);

          console.log("Browser-agent step finished.");
          if (event?.finishReason) console.log(`Finish reason: ${event.finishReason}`);
          if (event?.usage) console.log(`Usage: ${shortJson(event.usage, 400)}`);

          await writeJson(path.join(dir, "agent_output.json"), {
            timestamp: new Date().toISOString(),
            note: "Browser-agent LLM output/tool-call result for this Stagehand step.",
            event,
          });

          const modelRequest = event?.request ?? null;
          if (modelRequest) {
            const promptInput = modelRequest?.body?.input ?? null;
            await writeJson(path.join(dir, "model_request.json"), {
              timestamp: new Date().toISOString(),
              note: "Exact browser-agent model request captured from Stagehand/AI SDK for this step.",
              request: modelRequest,
              prompt_input: promptInput,
            });
            await writeText(
              path.join(dir, "model_prompt.txt"),
              modelPromptText(promptInput ?? modelRequest),
            );
          }

          const state = await pageState(page);
          await writeJson(path.join(dir, "page_state.json"), state);
          console.log(`Page: ${String(state.url || "unknown")}`);
          if (state.title) console.log(`Title: ${state.title}`);
          await captureScreenshot(page, path.join(dir, "screenshot.png"));
          if (latestAriaTree) await writeText(path.join(dir, "aria.txt"), latestAriaTree);
          if (latestScreenshot) {
            await fs.writeFile(path.join(dir, "evidence.png"), latestScreenshot);
          }

          await appendJsonl(path.join(taskDir, "trajectory.jsonl"), {
            timestamp: new Date().toISOString(),
            step,
            event: safeJson(event),
          });
        },
        onEvidence: async (event: any) => {
          await appendJsonl(path.join(taskDir, "evidence.jsonl"), {
            timestamp: new Date().toISOString(),
            event,
          });

          if (event?.type === "screenshot" && Buffer.isBuffer(event.screenshot)) {
            latestScreenshot = event.screenshot;
          }

          if (event?.type === "step_observed" && typeof event.ariaTree === "string") {
            latestAriaTree = event.ariaTree;
            console.log(`Observed page: ${event.url || "unknown"}`);
            console.log(`ARIA chars: ${event.ariaTree.length}`);
          }

          if (event?.type === "step_finished") {
            const dir = stepDir(taskDir, step + 1);
            console.log(`Tool/action: ${event.actionName}`);
            console.log(`Arguments: ${shortJson(event.actionArgs, 700)}`);
            if (event.reasoning) console.log(`Reasoning: ${event.reasoning}`);
            console.log(`Tool ok: ${event.toolOutput?.ok}`);
            if (event.toolOutput?.error) console.log(`Tool error: ${event.toolOutput.error}`);
            else console.log(`Tool result: ${shortJson(event.toolOutput?.result, 900)}`);
            await writeJson(path.join(dir, "action.json"), {
              action: event.actionName,
              arguments: event.actionArgs,
              reasoning: event.reasoning,
            });
            await writeJson(path.join(dir, "tool_result.json"), event.toolOutput);
          }

          if (event?.type === "final_answer") {
            console.log("Final answer event:");
            console.log(shortJson(event, 1200));
            await writeJson(path.join(taskDir, "final_answer.json"), event);
          }
        },
      },
    } as any);

    await writeJson(path.join(taskDir, "result.json"), result);
    await writeJson(path.join(taskDir, "final_page_state.json"), await pageState(page));
    await captureScreenshot(page, path.join(taskDir, "final_screenshot.png"));

    console.log(`Run artifacts saved in: ${taskDir}`);
    console.log(JSON.stringify({ success: result.success, completed: result.completed, message: result.message }));
  } finally {
    if (!args.keepOpen) {
      await stagehand.close();
    }
    process.chdir(previousCwd);
  }
}

main().catch((error) => {
  console.error(`ERROR: ${error?.message || String(error)}`);
  process.exit(1);
});

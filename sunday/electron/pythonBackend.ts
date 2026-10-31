import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import path from "node:path";
import { existsSync } from "node:fs";
import type { IntegrationHub } from "./integration";

/** Private child-process pipe: no ports, tokens or shell access in the renderer. */
export class PythonBackend {
  private child: ChildProcessWithoutNullStreams | null = null;
  private unsubscribe: (() => void) | null = null;
  private ready = false;
  private stopping = false;
  private stopped: Promise<void> = Promise.resolve();
  private idleTimer: ReturnType<typeof setTimeout> | undefined;
  private speaking = false;

  constructor(private hub: IntegrationHub) {}

  start(): void {
    const root = process.env.SUNDAY_BACKEND_ROOT || path.resolve(__dirname, "../..");
    if (!existsSync(path.join(root, "backend/runtime.py"))) {
      this.hub.panel.pushMessage({ role: "system", text: "Python backend not found. Start this checkout with python main.py." });
      return;
    }
    const child = spawn(process.env.SUNDAY_PYTHON || "python", ["-u", "-m", "backend.runtime"], {
      cwd: root, windowsHide: true, stdio: "pipe",
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    });
    this.child = child;
    this.stopped = new Promise((resolve) => child.once("close", () => resolve()));
    const lines = createInterface({ input: child.stdout });
    lines.on("line", (line) => {
      try {
        const event = JSON.parse(line);
        if (event.type === "ready" && !this.stopping && !this.ready) {
          this.ready = true;
          this.unsubscribe = this.hub.panel.onUserMessage((text) => this.send({ type: "chat", text }));
          this.hub.panel.pushMessage({ role: "system", text: "Python backend connected. Local commands are ready; AI replies use your configured provider." });
        } else if (event.type === "message" && typeof event.text === "string") {
          if (event.role === "user") this.hub.pushTranscript(event.text);
          else for (let offset = 0; offset < event.text.length; offset += 4000) {
            this.hub.panel.pushMessage({ role: event.role === "sunday" ? "sunday" : "system", text: event.text.slice(offset, offset + 4000) });
          }
          if (event.role === "sunday") {
            this.speaking = true;
            this.hub.dispatchAgentEvent({ type: "speech", payload: { text: event.text } });
          }
        } else if (event.type === "state" && typeof event.status === "string") {
          clearTimeout(this.idleTimer);
          if (event.status === "idle" && this.speaking) {
            this.idleTimer = setTimeout(() => this.hub.controller.setState("idle"), 6000);
          } else this.hub.dispatchAgentEvent({ type: "status_changed", payload: { status: event.status } });
          this.speaking = false;
        }
      } catch { console.warn("[backend] Ignored malformed protocol event"); }
    });
    child.stderr.on("data", (data: Buffer) => process.stderr.write(data));
    child.stdin.on("error", () => this.disconnect());
    child.once("error", () => {
      this.disconnect();
      this.hub.panel.pushMessage({ role: "system", text: "Could not start Python. Run python main.py from the project folder." });
    });
    child.once("close", () => {
      lines.close();
      this.disconnect();
      if (!this.stopping) {
        this.hub.panel.pushMessage({ role: "system", text: "Python backend stopped. Check the terminal and restart python main.py. Requests are not retried automatically." });
        this.hub.controller.setState("error");
      }
    });
  }

  private disconnect(): void {
    clearTimeout(this.idleTimer);
    this.ready = false;
    this.unsubscribe?.();
    this.unsubscribe = null;
  }

  private send(event: object): boolean {
    if (!this.child || this.child.stdin.destroyed || !this.ready || this.stopping) return false;
    this.child.stdin.write(JSON.stringify(event) + "\n");
    return true;
  }

  action(action: unknown): boolean {
    if (action !== "listen" && action !== "settings" && action !== "telegram" && action !== "weather") return false;
    return this.send({ type: action });
  }

  async stop(): Promise<void> {
    if (this.stopping) return this.stopped;
    this.stopping = true;
    this.disconnect();
    if (this.child && !this.child.stdin.destroyed) this.child.stdin.end(JSON.stringify({ type: "shutdown" }) + "\n");
    await this.stopped;
  }
}

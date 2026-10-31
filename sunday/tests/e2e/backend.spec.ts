import { _electron as electron, expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL("../..", import.meta.url));

test("real Python connects, reports provider errors, and keeps pet/panel usable", async ({}, info) => {
  const env: Record<string, string> = { ...Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => typeof entry[1] === "string")), FRIDAY_API_KEY: "", GROQ_ENABLED: "false", TELEGRAM_ENABLED: "false" };
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath: require("electron"), args: [root], env });
  try {
    await expect.poll(() => app.windows().some(w => w.url().endsWith("#panel"))).toBe(true);
    const panel = app.windows().find(w => w.url().endsWith("#panel"))!;
    const pet = app.windows().find(w => w.url().endsWith("#pet"))!;
    await expect(panel.locator(".conn")).toContainText("ready to help", { timeout: 20000 });
    await panel.getByRole("textbox", { name: "Message", exact: true }).fill("Explain stars");
    await panel.getByRole("button", { name: "Send", exact: true }).click();
    await expect(panel.locator(".msg-system").last()).toContainText("Set FRIDAY_API_KEY", { timeout: 15000 });
    await expect(panel.locator(".msg-user")).toHaveCount(1);
    await expect(panel.getByRole("button", { name: "Listen (6s)", exact: true })).toBeEnabled();
    await panel.screenshot({ path: info.outputPath("panel.png") });
    await pet.screenshot({ path: info.outputPath("pet.png") });
    await app.evaluate(({ BrowserWindow }) => {
      BrowserWindow.getAllWindows().find(w => w.webContents.getURL().endsWith("#panel"))!.setSize(340, 420);
    });
    await expect(panel.getByRole("button", { name: "Send", exact: true })).toBeInViewport();
    await panel.screenshot({ path: info.outputPath("panel-compact.png") });
    expect(await panel.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  } finally { await app.close(); }
});

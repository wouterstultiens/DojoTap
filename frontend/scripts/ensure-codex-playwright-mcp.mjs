import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BEGIN_MARKER = "# BEGIN AUTO-MANAGED PLAYWRIGHT MCP";
const END_MARKER = "# END AUTO-MANAGED PLAYWRIGHT MCP";

const PLAYWRIGHT_BLOCK = `${BEGIN_MARKER}
[mcp_servers.playwright]
command = "npx"
args = [
  "@playwright/mcp@latest",
  "--isolated",
  "--save-trace",
  "--output-dir",
  ".artifacts/playwright-mcp",
  "--browser",
  "chromium",
  "--caps",
  "vision",
  "--block-service-workers",
  "--host",
  "127.0.0.1",
  "--port",
  "3000",
]
required = true
startup_timeout_sec = 30
tool_timeout_sec = 120
${END_MARKER}
`;

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function ensureTrailingNewline(value) {
  return value.endsWith("\n") ? value : `${value}\n`;
}

function upsertPlaywrightConfig(existingContent) {
  const existing = existingContent ?? "";
  const markerRegex = new RegExp(
    `${escapeRegExp(BEGIN_MARKER)}[\\s\\S]*?${escapeRegExp(END_MARKER)}`,
    "m",
  );

  if (markerRegex.test(existing)) {
    return ensureTrailingNewline(existing.replace(markerRegex, PLAYWRIGHT_BLOCK));
  }

  if (/\[mcp_servers\.playwright\]/m.test(existing)) {
    return ensureTrailingNewline(existing);
  }

  if (existing.trim().length === 0) {
    return ensureTrailingNewline(PLAYWRIGHT_BLOCK);
  }

  return `${existing.trimEnd()}\n\n${PLAYWRIGHT_BLOCK}`;
}

async function main() {
  const scriptFilePath = fileURLToPath(import.meta.url);
  const scriptDirPath = path.dirname(scriptFilePath);
  const repoRoot = path.resolve(scriptDirPath, "..", "..");
  const codexDir = path.join(repoRoot, ".codex");
  const codexConfigPath = path.join(codexDir, "config.toml");

  await mkdir(codexDir, { recursive: true });

  let current = "";
  try {
    current = await readFile(codexConfigPath, "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") {
      throw error;
    }
  }

  const next = upsertPlaywrightConfig(current);
  if (next === current) {
    console.log("Codex Playwright MCP config already present.");
    return;
  }

  await writeFile(codexConfigPath, next, "utf8");
  console.log("Ensured Codex Playwright MCP config in .codex/config.toml");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

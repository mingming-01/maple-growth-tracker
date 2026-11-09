import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const projectRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const frontendSource = join(projectRoot, "frontend", "src");

function collectSourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const fullPath = join(directory, entry.name);
    if (entry.isDirectory()) return collectSourceFiles(fullPath);
    return /\.(?:js|jsx)$/.test(entry.name) ? [fullPath] : [];
  });
}

const sourceFiles = collectSourceFiles(frontendSource);

test("React API requests stay inside the shared API service", () => {
  const offenders = sourceFiles
    .filter(file => relative(frontendSource, file) !== join("services", "api.js"))
    .filter(file => /\bfetch\s*\(/.test(readFileSync(file, "utf8")))
    .map(file => relative(projectRoot, file).replaceAll("\\", "/"));

  assert.deepEqual(offenders, []);
});

test("React and retained legacy growth calculation modules stay byte-identical", () => {
  const reactModule = readFileSync(join(frontendSource, "lib", "growth.js"), "utf8");
  const legacyModule = readFileSync(join(projectRoot, "static", "js", "growth.js"), "utf8");

  assert.equal(reactModule, legacyModule);
});

test("React browser storage access stays inside the storage module", () => {
  const offenders = sourceFiles
    .filter(file => relative(frontendSource, file) !== join("lib", "storage.js"))
    .filter(file => /\b(?:window\.)?(?:localStorage|sessionStorage)\b/.test(readFileSync(file, "utf8")))
    .map(file => relative(projectRoot, file).replaceAll("\\", "/"));

  assert.deepEqual(offenders, []);
});


test("React JSX legacy class styles remain available in the React compatibility stylesheet", async () => {
  const css = await readFile(new URL("../frontend/src/styles/react-compat.css", import.meta.url), "utf8");
  for (const selector of [
    ".mgt-app-shell .section-title",
    ".mgt-app-shell .growth-goal-card",
    ".mgt-app-shell .game-equipment-layout",
    ".mgt-app-shell .detail-notice",
    ".mgt-app-shell .ai-analysis-card",
    ".mgt-app-shell .history-table",
  ]) {
    assert.ok(css.includes(selector), `Missing React compatibility selector: ${selector}`);
  }
});

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
  const css = readFileSync(join(projectRoot, "frontend", "src", "styles", "react-compat.css"), "utf8");
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


test("React entry and theme import order preserve the legacy boundary", () => {
  const reactHtml = readFileSync(join(projectRoot, "frontend", "index.html"), "utf8");
  const legacyHtml = readFileSync(join(projectRoot, "templates", "index.html"), "utf8");
  const entry = readFileSync(join(frontendSource, "main.jsx"), "utf8");
  const compatibilityIndex = entry.indexOf('import "./styles/react-compat.css";');
  const themeIndex = entry.indexOf('import "./styles.css";');

  assert.equal(reactHtml.includes('href="/static/style.css"'), false);
  assert.ok(legacyHtml.includes("filename='style.css'"));
  assert.ok(compatibilityIndex >= 0, "React compatibility stylesheet must be imported");
  assert.ok(themeIndex > compatibilityIndex, "The React theme must load after compatibility rules");
});

test("Growth route layout selectors match the current React component wrappers", () => {
  const growthHome = readFileSync(join(frontendSource, "features", "home", "GrowthHome.jsx"), "utf8");
  const insight = readFileSync(join(frontendSource, "features", "home", "GrowthInsight.jsx"), "utf8");
  const css = readFileSync(join(frontendSource, "styles.css"), "utf8");

  assert.ok(growthHome.includes('className="mgt-growth-page-content" data-testid="growth-page"'));
  assert.ok(css.includes('.mgt-growth-page-content[data-testid="growth-page"] .growth-dashboard'));
  for (const route of ["details", "analytics", "history", "comparison"]) {
    assert.ok(
      css.includes(`.mgt-growth-page-content[data-testid="${route}-page"]`),
      `Missing layout rules for the ${route} route wrapper`
    );
  }

  for (const className of [
    "mgt-growth-insight-copy",
    "mgt-growth-insight-facts",
    "mgt-insight-link"
  ]) {
    assert.ok(insight.includes(`className="${className}"`), `Missing JSX class ${className}`);
    assert.ok(css.includes(`.${className}`), `Missing CSS selector .${className}`);
  }
});


test("React tracker state persistence is centralized outside state updater callbacks", () => {
  const app = readFileSync(join(frontendSource, "App.jsx"), "utf8");
  const updater = app.match(/const onStatsLoaded = useCallback\(data => \{([\s\S]*?)\n  \},\[\]\);/);

  assert.ok(updater, "The stats-loaded state updater must remain present");
  assert.doesNotMatch(updater[1], /saveTrackerState\s*\(/);
  assert.equal((app.match(/saveTrackerState\s*\(/g) || []).length, 1);
});

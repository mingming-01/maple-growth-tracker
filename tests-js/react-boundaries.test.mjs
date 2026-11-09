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

test("React browser storage access stays inside the storage module", () => {
  const offenders = sourceFiles
    .filter(file => relative(frontendSource, file) !== join("lib", "storage.js"))
    .filter(file => /\b(?:window\.)?(?:localStorage|sessionStorage)\b/.test(readFileSync(file, "utf8")))
    .map(file => relative(projectRoot, file).replaceAll("\\", "/"));

  assert.deepEqual(offenders, []);
});

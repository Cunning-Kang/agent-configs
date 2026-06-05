#!/usr/bin/env bun
// Behavior smoke tests for codebase-memory-gate
// Validates classification logic for read, search, find, ast_grep tool calls.
// NOT E2E: does not spawn OMP or collect stdout/stderr.
// Run: bun behavior-smoke.test.mjs

import {
  isCodePath,
  isCodeDiscoveryCall,
} from "../index.js";

// Test cases: [toolName, input, shouldBlock, description]
const testCases = [
  // === CODE read calls SHOULD be blocked ===
  ["read", { path: "src/main.ts" }, true, "Code file read should block"],
  ["read", { path: "lib/index.ts" }, true, "Nested code file should block"],
  ["read", { path: "src/main.rs:1-5:raw" }, true, "Code file with selector should block"],
  ["read", { path: "src/claude.ts" }, true, "claude.ts should block"],
  ["read", { path: "src/agents.ts" }, true, "agents.ts should block"],
  ["read", { path: "build.gradle" }, true, "Gradle build file should block"],
  ["read", { path: "schema.prisma" }, true, "Prisma schema should block"],
  ["read", { path: "schema.graphql" }, true, "GraphQL schema should block"],

  // === DOCS read calls should NOT be blocked ===
  ["read", { path: "docs/readme.md" }, false, "Markdown in docs/ should NOT block"],
  ["read", { path: "README.md" }, false, "Root README should NOT block"],
  ["read", { path: "CLAUDE.md" }, false, "Root CLAUDE.md should NOT block"],
  ["read", { path: "docs/prd/architecture.md" }, false, "Markdown in nested docs should NOT block"],
  ["read", { path: ".omp/agent/config.yml" }, false, "Config in .omp should NOT block"],
  ["read", { path: ".github/workflows/ci.yml" }, false, "GitHub config should NOT block"],

  // === Internal URIs should NOT be blocked ===
  ["read", { path: "skill://example" }, false, "skill:// URI should NOT block"],
  ["read", { path: "memory://root" }, false, "memory:// URI should NOT block"],

  // === Search/find with code paths should block ===
  ["search", { paths: ["src/**/*.ts"], pattern: "function" }, true, "Search in code dir should block"],
  ["find", { paths: ["src"], pattern: "*.rs" }, true, "Find in code dir should block"],

  // === Search/find with docs should NOT block ===
  ["search", { paths: ["docs/**/*.md"], pattern: "guide" }, false, "Search in docs should NOT block"],
  ["find", { paths: ["."], pattern: "*.md" }, false, "Find md files should NOT block"],

  // === ast_grep tests ===
  ["ast_grep", { paths: ["src/**/*.ts"], pat: "const $X = $Y" }, true, "ast_grep in code dir should block"],
  ["ast_grep", { paths: ["lib"], pat: "function $NAME" }, true, "ast_grep in lib/ should block"],
  ["ast_grep", { paths: ["docs/**/*.md"], pat: "$X" }, false, "ast_grep in docs should NOT block"],

  // === EMPTY INPUT safety-default tests ===
  // Empty input for search/find/ast_grep defaults to BLOCKING (assume code until proven)
  ["search", {}, true, "Empty search input should block (safety default)"],
  ["find", {}, true, "Empty find input should block (safety default)"],
  ["ast_grep", {}, true, "Empty ast_grep input should block (safety default)"],
  // Empty string paths/patterns also default to blocking
  ["search", { paths: [], pattern: "" }, true, "Empty search paths+pattern should block"],
  ["find", { paths: [], pattern: "" }, true, "Empty find paths+pattern should block"],
  ["ast_grep", { paths: [], pat: "" }, true, "Empty ast_grep paths+pattern should block"],
  // Empty string in paths array
  ["search", { paths: [""], pattern: "function" }, true, "Search with empty string path should block"],
  ["find", { paths: [""], pattern: "*.ts" }, true, "Find with empty string path should block"],
  ["ast_grep", { paths: [""], pat: "$X" }, true, "ast_grep with empty string path should block"],
];

// Run tests
let passed = 0;
let failed = 0;
const failures = [];

console.log("OMP Codebase Memory Gate Behavior Smoke Tests");
console.log("===============================================");

for (const [toolName, input, shouldBlock, description] of testCases) {
  const wouldBlock = isCodeDiscoveryCall(toolName, input);
  if (wouldBlock === shouldBlock) {
    console.log(`  PASS: ${description}`);
    passed++;
  } else {
    console.log(`  FAIL: ${description}`);
    console.log(`        Tool: ${toolName}, Input: ${JSON.stringify(input)}`);
    console.log(`        Expected block: ${shouldBlock}, Got: ${wouldBlock}`);
    failures.push({ toolName, input, shouldBlock, wouldBlock, description });
    failed++;
  }
}

console.log("\n=== Summary ===");
console.log(`Passed: ${passed}/${testCases.length}`);
console.log(`Failed: ${failed}/${testCases.length}`);

if (failed > 0) {
  process.exit(1);
} else {
  console.log("\nAll behavior smoke tests passed!");
  console.log("The gate will correctly block code reads while allowing docs reads.");
  process.exit(0);
}
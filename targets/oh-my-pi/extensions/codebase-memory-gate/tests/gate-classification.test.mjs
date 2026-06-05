#!/usr/bin/env bun
// TDD tests for codebase-memory-gate path classification
// Uses production classification logic - no drift risk.
// Run: bun gate-classification.test.mjs

import {
  isCodePath,
  isClearlyNonCodePath,
  isCodeDiscoveryCall,
} from "../index.js";

// Test cases: [path, expectedIsCodePath, description]
const testCases = [
  // === CODE paths that MUST be blocked ===
  // Code extension wins over docs/ directory heuristic
  ["docs/index.ts", true, "docs/index.ts - code ext wins over docs/ dir heuristic"],
  ["doc/api.ts", true, "doc/api.ts - code ext wins over doc/ dir heuristic"],
  ["documentation/api.ts", true, "documentation/api.ts - code ext wins over documentation/ dir"],
  ["src/documentation/generator.ts", true, "src/documentation/generator.ts - code ext wins"],
  ["src/docs/foo.ts", true, "src/docs/foo.ts - code ext wins over src/docs/ dir"],
  // Special Claude/agents files are code regardless of directory
  ["src/claude.ts", true, "src/claude.ts - must be blocked (not root-level)"],
  ["src/agents.ts", true, "src/agents.ts - must be blocked (not root-level)"],
  // Code paths with OMP selectors
  ["src/main.rs:1-5:raw", true, "src/main.rs:1-5:raw - selector stripped, .rs is code"],
  ["src/main.rs:raw", true, "src/main.rs:raw - selector stripped, .rs is code"],
  ["src/main.rs:50:raw", true, "src/main.rs:50:raw - selector stripped"],
  ["src/main.rs:1-5", true, "src/main.rs:1-5 - selector stripped"],
  // Other code files
  ["schema.graphql", true, "schema.graphql - GraphQL is code"],
  ["migrations/001_init.sql", true, "migrations/001_init.sql - SQL is code"],
  ["build.gradle", true, "build.gradle - Gradle is code"],
  ["rules/foo.bzl", true, "rules/foo.bzl - Bazel Starlark is code"],
  // Source root level
  ["src/main.rs", true, "src/main.rs - code file"],
  ["src/index.ts", true, "src/index.ts - code file"],
  // Other code extensions
  ["src/main.zig", true, "src/main.zig - Zig is code"],
  ["src/main.go", true, "src/main.go - Go is code"],
  // Prisma is now code
  ["schema.prisma", true, "schema.prisma - Prisma schema is code"],

  // === NON-CODE paths that MUST pass ===
  // Markdown docs
  ["docs/readme.md", false, "docs/readme.md - markdown passes even in docs/ dir"],
  ["README.md", false, "README.md - root-level README"],
  ["CLAUDE.md", false, "CLAUDE.md - root-level CLAUDE.md"],
  // Config files
  [".omp/agent/config.yml", false, ".omp/agent/config.yml - config in .omp dir"],
  ["config.toml", false, "config.toml - config file"],
  // URLs (must not strip :80 port)
  ["https://example.com/foo.ts", false, "https:// URL - external"],
  ["http://example.com:8080/bar.ts", false, "http:// URL with port - external"],
  // Internal URIs
  ["skill://codebase-memory/SKILL.md", false, "skill:// URI"],
  ["rule://naming-conventions", false, "rule:// URI"],
  ["memory://root", false, "memory:// URI"],
  ["artifact://123", false, "artifact:// URI"],
  ["local://test.md", false, "local:// URI"],
  ["omp://path/to/file.ts", false, "omp:// URI"],
  ["issue://123", false, "issue:// URI"],
  ["pr://456", false, "pr:// URI"],
  ["mcp://tool/call", false, "mcp:// URI"],
  // Root-level agent config (not code because they are configs)
  [".claude/CLAUDE.md", false, ".claude/CLAUDE.md - agent config directory"],
  [".github/workflows/ci.yml", false, ".github/workflows/ci.yml - github config"],
  // Non-code files
  ["docs/prd/agent-loop.md", false, "docs/prd/agent-loop.md - markdown in docs"],
];

// Run tests
let passed = 0;
let failed = 0;
const failures = [];

for (const [path, expected, description] of testCases) {
  const actual = isCodePath(path);
  if (actual === expected) {
    passed++;
  } else {
    failed++;
    failures.push({
      path,
      expected,
      actual,
      description,
    });
  }
}

console.log(`\n=== OMP Codebase Memory Gate Classification Tests ===\n`);
console.log(`Passed: ${passed}/${testCases.length}`);
console.log(`Failed: ${failed}/${testCases.length}`);

if (failures.length > 0) {
  console.log(`\nFAILURES:`);
  for (const f of failures) {
    console.log(`  - ${f.description}`);
    console.log(`    Path: "${f.path}"`);
    console.log(`    Expected isCodePath: ${f.expected}, Got: ${f.actual}`);
  }
  process.exit(1);
} else {
  console.log(`\nAll tests passed!`);
  process.exit(0);
}
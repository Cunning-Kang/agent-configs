#!/usr/bin/env node
/**
 * E2E Smoke Tests for OMP Codebase Memory Gate
 *
 * Verifies:
 * 1. MCP integration works (codebase-memory evidence in /mcp list)
 * 2. Code-read test: gate blocks OR MCP precedes raw code read via logger
 * 3. Docs-read test: succeeds without gate block
 *
 * Run: node e2e-smoke.test.mjs
 */

import { spawn } from "node:child_process";
import { writeFileSync, readFileSync, unlinkSync, existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

const OMP_TIMEOUT_MS = 30000;
// Machine-specific paths. The e2e test exercises the local OMP install and a
// local code fixture; none of these are reusable configuration. Override via
// environment variables for this machine. Defaults are placeholders that
// fail loudly when missing so a clean repo clone cannot accidentally hit a
// user-specific path.
const AGENT_DIR = process.env.OMP_AGENT_DIR || "";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function runOMP(args, options = {}) {
  const { timeout = 90000, env = {} } = options;
  return new Promise((resolve) => {
    const proc = spawn("omp", args, {
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, OMP_MCP_TIMEOUT_MS: String(OMP_TIMEOUT_MS), ...env },
    });
    let stdout = "";
    let stderr = "";
    let exitCode = null;
    let stdoutClosed = false;
    let stderrClosed = false;
    const checkDone = () => {
      if (exitCode !== null && stdoutClosed && stderrClosed) {
        setTimeout(() => resolve({ stdout, stderr, exitCode }), 100);
      }
    };
    proc.stdout?.on("data", (d) => { stdout += d.toString(); });
    proc.stdout?.on("close", () => { stdoutClosed = true; checkDone(); });
    proc.stderr?.on("data", (d) => { stderr += d.toString(); });
    proc.stderr?.on("close", () => { stderrClosed = true; checkDone(); });
    proc.on("exit", (code) => { exitCode = code; checkDone(); });
    setTimeout(() => {
      if (exitCode === null) {
        proc.kill("SIGTERM");
        setTimeout(() => { if (exitCode === null) proc.kill("SIGKILL"); }, 2000);
        resolve({ stdout, stderr, exitCode: -1, killed: true });
      }
    }, timeout);
  });
}

function createToolLoggerExtension() {
  const ts = Date.now();
  const rand = Math.random().toString(36).slice(2, 8);
  const logPath = join(tmpdir(), `e2e-tool-log-${ts}-${rand}.jsonl`);
  const extPath = join(tmpdir(), `e2e-tool-logger-${ts}-${rand}.mjs`);
  const extCode = `
import { appendFileSync } from "node:fs";

const LOG_PATH = process.env.E2E_TOOL_LOG_PATH || "/tmp/e2e-tool-log.jsonl";

export default function toolLogger(pi) {
  if (typeof pi.on === "function") {
    pi.on("tool_call", async (event) => {
      const entry = JSON.stringify({ ts: Date.now(), toolName: event.toolName }) + "\\n";
      try { appendFileSync(LOG_PATH, entry); } catch {}
    });
  }
}
`;
  writeFileSync(extPath, extCode);
  return { extPath, logPath };
}

function cleanupFiles(...paths) {
  for (const p of paths) {
    try { if (existsSync(p)) unlinkSync(p); } catch {}
  }
}

/**
 * True if entry is a raw file read of a code file (extension after selector stripping).
 */
function isCodeRead(entry) {
  const name = entry.toolName;
  if (name !== "read") return false;
  const path = entry.input?.path || entry.input || "";
  // Strip line selector suffix: "foo.rs:50" -> "foo.rs"
  const base = path.split(":")[0].toLowerCase();
  const CODE_EXT_RE = /\.(rs|ts|tsx|js|jsx|go|py|java|c|cpp|h|hpp|cs|rb|swift|kt|scala|php|ex|exs|erl|hs|clj|cljs|fs|fsx|fsi)$/;
  return CODE_EXT_RE.test(base);
}

/**
 * True if entry is a codebase-memory MCP tool.
 */
function isMcp(entry) {
  const name = entry.toolName || "";
  return (
    name.startsWith("mcp__codebase_memory_mcp_") ||
    name.startsWith("mcp__codebase-memory-mcp_") ||
    name.startsWith("mcp__codebase_memory_") ||
    /codebase.memory.mcp/i.test(name)
  );
}

// Gate block message (I3 from gate extension)
const GATE_BLOCK_RE = /code\s*discovery\s*must\s*use\s*codebase[\-\s]*memory[\-\s]*mcp/i;

// ---------------------------------------------------------------------------
// Test 1: MCP Integration
// ---------------------------------------------------------------------------
async function testMCPAvailable() {
  console.log("\n=== Test 1: MCP Integration ===");
  const result = await runOMP(["--print", "/mcp list"], { timeout: 60000 });
  const output = result.stdout.toLowerCase();
  const hasCodebaseMemory = output.includes("codebase-memory-mcp") || output.includes("codebase_memory_mcp");
  const hasTools = output.includes("index_repository") || output.includes("search_graph") || output.includes("get_code_snippet");
  const pass = result.exitCode === 0 && (hasCodebaseMemory || hasTools);
  console.log(`  Exit code: ${result.exitCode}`);
  console.log(`  Has codebase-memory: ${hasCodebaseMemory}`);
  console.log(`  Has tools: ${hasTools}`);
  console.log(`  ${pass ? "PASS" : "FAIL"}`);
  return { pass, stdout: result.stdout, stderr: result.stderr };
}

// ---------------------------------------------------------------------------
// Test 2: Code Read Gate Behavior
// MUST NOT pass because stdout contains code tokens.
// Pass only if: (a) gate blocks OR (b) logger proves MCP before raw code read.
// ---------------------------------------------------------------------------
async function testCodeReadGateBehavior() {
  console.log("\n=== Test 2: Code Read Gate Behavior ===");

  // Machine-specific code fixture. Set E2E_CODE_FIXTURE to the absolute path
  // of a Rust file (or any code file) on this machine before running. The
  // default is an empty string so a clean clone fails loudly rather than
  // accidentally reading a user-specific path.
  const rustFile = process.env.E2E_CODE_FIXTURE || "";
  const { extPath: loggerExt, logPath: loggerLog } = createToolLoggerExtension();

  console.log(`  Testing: Read ${rustFile}`);
  console.log(`  Logger: ${loggerLog}`);

  try {
    const result = await runOMP(
      [
        "--print",
        "--extension", loggerExt,
        `Read the file at ${rustFile} and describe what it does`
      ],
      { timeout: 90000, env: { E2E_TOOL_LOG_PATH: loggerLog } }
    );

    const output = result.stdout;
    const outputLower = output.toLowerCase();

    // I3: robust gate block regex
    const hasGateBlock = GATE_BLOCK_RE.test(output);
    console.log(`  Exit code: ${result.exitCode}`);
    console.log(`  Has gate block: ${hasGateBlock}`);

    // Parse logger
    let entries = [];
    if (existsSync(loggerLog)) {
      try {
        const logContent = readFileSync(loggerLog, "utf-8");
        entries = logContent.split("\n")
          .filter(l => l.trim())
          .map(l => { try { return JSON.parse(l); } catch { return null; } })
          .filter(Boolean);
        console.log(`  Logger entries: ${entries.length}`);
      } catch (e) {
        console.log(`  Logger read error: ${e.message}`);
      }
    } else {
      console.log(`  Logger file not found`);
    }

    // PASS criteria:
    // (a) Gate blocked → always pass
    if (hasGateBlock) {
      console.log("  PASS: Gate blocked raw code read");
      return { pass: true, reason: "gate_block", output, entries };
    }

    // (b) Gate NOT blocked → logger must prove MCP before raw code read
    if (entries.length === 0) {
      console.log("  FAIL: No logger entries — cannot verify sequence");
      return { pass: false, reason: "no_logger", output, entries };
    }

    const mcpIdx = entries.findIndex(isMcp);
    const codeReadIdx = entries.findIndex(isCodeRead);
    console.log(`  MCP index: ${mcpIdx}, code-read index: ${codeReadIdx}`);

    if (mcpIdx >= 0 && (codeReadIdx < 0 || mcpIdx < codeReadIdx)) {
      console.log("  PASS: MCP used before raw code read");
      return { pass: true, reason: "mcp_before_read", output, entries };
    }

    if (codeReadIdx >= 0 && mcpIdx < 0) {
      console.log("  FAIL: Raw code read without prior MCP");
      return { pass: false, reason: "read_without_mcp", output, entries };
    }

    if (codeReadIdx >= 0 && mcpIdx >= 0 && codeReadIdx < mcpIdx) {
      console.log("  FAIL: Raw code read before MCP");
      return { pass: false, reason: "read_before_mcp", output, entries };
    }

    // Edge: no code reads in log, but gate didn't block — suspicious but not failure
    console.log("  FAIL: Gate not blocked, no MCP found, no code read in log");
    return { pass: false, reason: "no_mcp_no_read", output, entries };

  } finally {
    cleanupFiles(loggerExt, loggerLog);
  }
}

// ---------------------------------------------------------------------------
// Test 3: Docs Read — no gate block, must succeed
// ---------------------------------------------------------------------------
async function testDocsReadNoBlock() {
  console.log("\n=== Test 3: Docs Read No Block ===");

  // Machine-specific docs fixture. Set E2E_DOCS_FIXTURE to the absolute path
  // of a docs/markdown file on this machine before running. The default is
  // an empty string so a clean clone fails loudly.
  const readmePath = process.env.E2E_DOCS_FIXTURE || "";

  const result = await runOMP(
    ["--print", `Read the file at ${readmePath} and summarize it`],
    { timeout: 60000 }
  );

  const output = result.stdout;
  const outputLower = output.toLowerCase();

  // Should NOT contain gate block
  const hasGateBlock = GATE_BLOCK_RE.test(output);
  // Should contain actual content
  const hasContent = output.includes("Codebase Memory") ||
                     output.includes("Gate") ||
                     output.includes("proxy") ||
                     output.includes("##");

  console.log(`  Exit code: ${result.exitCode}`);
  console.log(`  Has gate block: ${hasGateBlock}`);
  console.log(`  Has content: ${hasContent}`);

  if (hasGateBlock) {
    console.log("  FAIL: Docs read incorrectly blocked");
    return { pass: false, reason: "incorrectly_blocked", output };
  }

  if (!hasContent) {
    console.log("  FAIL: Docs read missing content");
    return { pass: false, reason: "no_content", output };
  }

  console.log("  PASS: Docs read succeeded without block");
  return { pass: true, reason: "ok", output };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  console.log("=".repeat(60));
  console.log("OMP Codebase Memory Gate - E2E Smoke Tests");
  console.log("=".repeat(60));

  const results = [];

  const r1 = await testMCPAvailable();
  results.push(["MCP Integration", r1.pass]);

  const r2 = await testCodeReadGateBehavior();
  results.push(["Code Read Gate", r2.pass]);

  const r3 = await testDocsReadNoBlock();
  results.push(["Docs Read No Block", r3.pass]);

  console.log("\n" + "=".repeat(60));
  console.log("SUMMARY");
  console.log("=".repeat(60));
  for (const [name, pass] of results) {
    console.log(`  ${name}: ${pass ? "PASS" : "FAIL"}`);
  }

  const failed = results.filter(([, p]) => !p).length;
  console.log(`\nTotal: ${results.length - failed} passed, ${failed} failed`);

  if (failed > 0) {
    process.exit(1);
  } else {
    console.log("\nAll E2E smoke tests passed!");
    process.exit(0);
  }
}

main().catch((err) => {
  console.error("Runner error:", err);
  process.exit(1);
});
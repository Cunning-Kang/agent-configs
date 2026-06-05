/**
 * Classification helpers for codebase-memory-gate.
 * Exported for use in both production (index.ts) and tests.
 */

export const CODE_EXTENSIONS = new Set([
  "c",
  "cc",
  "cpp",
  "cxx",
  "cs",
  "css",
  "dart",
  "ex",
  "exs",
  "go",
  "h",
  "hpp",
  "hs",
  "java",
  "js",
  "jsx",
  "kt",
  "kts",
  "lua",
  "php",
  "py",
  "rb",
  "rs",
  "scala",
  "scss",
  "sh",
  "svelte",
  "swift",
  "tsx",
  "ts",
  "vue",
  // Additional code/schema languages
  "zig",
  "r",
  "m",
  "mm",
  "ml",
  "fs",
  "fsi",
  "clj",
  "erl",
  "pl",
  "sql",
  "graphql",
  "gql",
  "prisma",
  "proto",
  "v",
  "sv",
  "nix",
  "gradle",
  "bazel",
  "bzl",
]);

export const NON_CODE_EXTENSIONS = new Set([
  "adoc",
  "csv",
  "env",
  "ini",
  "json",
  "jsonc",
  "lock",
  "log",
  "md",
  "mdc",
  "pdf",
  "png",
  "rst",
  "svg",
  "toml",
  "txt",
  "xml",
  "yaml",
  "yml",
]);

export function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function normalizePathish(value: string): string {
  return value.split(/[?#]/, 1)[0] ?? value;
}

// Strip OMP path selectors (e.g., :1-5, :raw, :1-5:raw) for extension detection
// But preserve URL schemes and internal URI schemes
export function stripOMPSelector(path: string): string {
  const colonPos = path.lastIndexOf(":");
  if (colonPos < 0) return path;

  const after = path.slice(colonPos + 1);

  if (after === "raw") {
    // Could be :raw or :1-5:raw - check if preceded by range selector
    const before = path.slice(0, colonPos);
    const prevColon = before.lastIndexOf(":");
    if (prevColon >= 0) {
      const prevAfter = before.slice(prevColon + 1);
      // If previous part looks like selector (digits-digits or just digits)
      if (/^\d+(-\d+)?$/.test(prevAfter)) {
        return before.slice(0, prevColon);
      }
    }
    // Simple :raw
    return path.slice(0, colonPos);
  }

  // Check for :N-M or :N pattern
  if (/^\d+(-\d+)?$/.test(after)) {
    return path.slice(0, colonPos);
  }

  // Not a selector (might be URL port like https://example.com:8080)
  return path;
}

export function extensionOf(path: string): string | null {
  const clean = normalizePathish(path).toLowerCase();
  // Strip OMP selectors before extension detection
  const withoutSelector = stripOMPSelector(clean);
  const lastSlash = withoutSelector.lastIndexOf("/");
  const name = lastSlash >= 0 ? withoutSelector.slice(lastSlash + 1) : withoutSelector;
  const lastDot = name.lastIndexOf(".");
  if (lastDot <= 0 || lastDot === name.length - 1) return null;
  return name.slice(lastDot + 1);
}

export function isClearlyNonCodePath(path: string): boolean {
  const clean = normalizePathish(path).toLowerCase();
  // URL or internal URI => non-code
  if (clean.startsWith("http://") || clean.startsWith("https://")) return true;
  if (/^(skill|rule|memory|agent|artifact|local|omp|issue|pr|mcp):\/\//.test(clean)) return true;
  // .omp directory => non-code
  if (/(^|\/)(\.omp)(\/|$)/.test(clean)) return true;
  // .github directory => non-code
  if (/(^|\/)(\.github)(\/|$)/.test(clean)) return true;
  // .claude directory => non-code
  if (/(^|\/)(\.claude)(\/|$)/.test(clean)) return true;

  // Non-code extension check
  const ext = extensionOf(clean);
  if (ext !== null && NON_CODE_EXTENSIONS.has(ext)) return true;

  return false;
}

export function isCodePath(path: string): boolean {
  // URL or internal URI => never code
  const clean = normalizePathish(path).toLowerCase();
  if (clean.startsWith("http://") || clean.startsWith("https://")) return false;
  if (/^(skill|rule|memory|agent|artifact|local|omp|issue|pr|mcp):\/\//.test(clean)) return false;

  // Check code extension (selector already stripped inside extensionOf)
  const ext = extensionOf(clean);
  if (ext !== null && CODE_EXTENSIONS.has(ext)) {
    // Special cases: claude.ts and agents.ts are always code
    const name = path.split("/").pop() || "";
    if (name === "claude.ts" || name === "agents.ts") return true;

    // Code extension wins over directory/name heuristics
    return true;
  }

  return false;
}

export function toolInputText(input: Record<string, unknown>): string {
  const fields = ["path", "paths", "pattern", "query", "command"];
  const parts: string[] = [];
  for (const field of fields) {
    const value = input[field];
    if (typeof value === "string") parts.push(value);
    else if (Array.isArray(value)) {
      for (const item of value) if (typeof item === "string") parts.push(item);
    }
  }
  return parts.join("\n");
}

export function isCodeDiscoveryCall(toolName: string, input: Record<string, unknown>): boolean {
  if (toolName === "read") {
    const path = asString(input.path);
    return path !== "" && isCodePath(path);
  }

  if (toolName === "search" || toolName === "find" || toolName === "ast_grep") {
    const text = toolInputText(input);
    // SAFETY: Empty input defaults to blocking (assume code until proven otherwise)
    if (text === "") return true;
    if (text.split(/\s+/).some(isCodePath)) return true;
    return !text.split(/\s+/).some(isClearlyNonCodePath);
  }

  return false;
}
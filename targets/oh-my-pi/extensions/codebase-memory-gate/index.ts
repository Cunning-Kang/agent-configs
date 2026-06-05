import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

import {
  CODE_EXTENSIONS,
  NON_CODE_EXTENSIONS,
  asString,
  normalizePathish,
  stripOMPSelector,
  extensionOf,
  isClearlyNonCodePath,
  isCodePath,
  toolInputText,
  isCodeDiscoveryCall,
} from "./classification-helpers.js";

const CODEBASE_MEMORY_TOOL_PREFIXES = [
  "mcp__codebase_memory_mcp_",
  "mcp__codebase_memory_",
];

const CODEBASE_MEMORY_TOOLS = [
  "index_repository",
  "search_graph",
  "trace_path",
  "get_code_snippet",
  "query_graph",
  "get_architecture",
  "search_code",
];

function isCodebaseMemoryTool(toolName: string): boolean {
  return CODEBASE_MEMORY_TOOL_PREFIXES.some((prefix) => toolName.startsWith(prefix));
}

function preferredToolNames(pi: ExtensionAPI): string[] {
  try {
    const available = pi
      .getAllTools()
      .map((tool) => tool.name)
      .filter(isCodebaseMemoryTool);
    if (available.length > 0) return available.slice(0, 8);
  } catch {}

  return CODEBASE_MEMORY_TOOL_PREFIXES.flatMap((prefix) =>
    CODEBASE_MEMORY_TOOLS.map((name) => `${prefix}${name}`),
  );
}

function blockReason(pi: ExtensionAPI): string {
  return [
    "Code discovery must use codebase-memory-mcp first.",
    "Use one of:",
    ...preferredToolNames(pi).map((name) => `- ${name}`),
    "If graph is not indexed, call index_repository first.",
    "Read/search/find are allowed for docs, config, and non-code files.",
  ].join("\n");
}

export default function codebaseMemoryGate(pi: ExtensionAPI): void {
  pi.on("tool_call", async (event) => {
    if (isCodebaseMemoryTool(event.toolName)) return;

    const input = event.input as Record<string, unknown>;
    if (!isCodeDiscoveryCall(event.toolName, input)) return;

    return { block: true, reason: blockReason(pi) };
  });
}

// Re-export helpers for testing
export {
  CODE_EXTENSIONS,
  NON_CODE_EXTENSIONS,
  asString,
  normalizePathish,
  stripOMPSelector,
  extensionOf,
  isClearlyNonCodePath,
  isCodePath,
  toolInputText,
  isCodeDiscoveryCall,
};
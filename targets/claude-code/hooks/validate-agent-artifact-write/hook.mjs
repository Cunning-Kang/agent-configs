#!/usr/bin/env node

import { readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(2);
}

function pass() {
  process.exit(0);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function parsePayload() {
  const stdin = readFileSync(0, 'utf8').trim();
  const raw = stdin || process.env.TOOL_INPUT || '';
  if (!raw) fail('Blocked: PreToolUse payload is required.');
  try {
    return JSON.parse(raw);
  } catch {
    fail('Blocked: PreToolUse payload must be valid JSON.');
  }
}

const agent = process.argv[2];
if (!agent || !/^[a-z0-9-]+$/.test(agent)) fail('Blocked: agent name argument is required.');

const payload = parsePayload();
const toolName = payload.tool_name ?? payload.toolName ?? '';
if (toolName && toolName !== 'Write') pass();

const input = payload.tool_input ?? payload.toolInput ?? payload.input ?? payload;
const filePath = input.file_path ?? input.filePath ?? input.path;
if (typeof filePath !== 'string' || filePath.trim() === '') fail('Blocked: Write.file_path is required.');
if (!path.isAbsolute(filePath)) fail('Blocked: artifact Write path must be absolute.');

const tmpBase = process.env.TMPDIR || os.tmpdir();
const allowRoot = path.resolve(tmpBase, 'claude-agent-artifacts');
const target = path.resolve(filePath);
const relative = path.relative(allowRoot, target);
if (relative.startsWith('..') || path.isAbsolute(relative) || relative === '') fail('Blocked: artifact Write path must be under $TMPDIR/claude-agent-artifacts/.');

const base = path.basename(target);
const pattern = new RegExp(`^${escapeRegExp(agent)}-[A-Za-z0-9._-]+\.md$`);
if (!pattern.test(base)) fail(`Blocked: artifact filename must match ${agent}-*.md.`);

pass();

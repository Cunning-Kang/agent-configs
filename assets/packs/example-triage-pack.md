# Pack: example-triage

> See `assets/README.md` for the category contract. A pack is a
> composition note: it **links** to existing assets and never copies
> or inlines them. A pack is not an installable bundle.

## What this pack is for

Triage incoming issues and change requests against this repo's
architecture boundaries. The pack names the role, the skill, the
rules, and the MCP card that travel together for that workflow.

## Composed assets

- **Role**: [`assets/agents/example-code-reviewer.md`](../agents/example-code-reviewer.md)
  — the role that judges whether a diff respects the area
  boundaries and surfaces findings with file paths.
- **Skill**: [`assets/skills/example-repo-triage.md`](../skills/example-repo-triage.md)
  — the standard triage workflow that picks the right area for a
  piece of material.
- **Rules**: [`assets/rules/example-boundary-respect.md`](../rules/example-boundary-respect.md)
  — the behavioural rules the role and the skill apply during
  review.
- **MCP card**: [`assets/mcp-servers/example-github.md`](../mcp-servers/example-github.md)
  — the server the role uses to fetch PR and issue context.

## Rationale

Reviewing a diff for boundary violations, fetching the originating
issue, and reclassifying the material into the right area are the
same workflow from three angles. The pack wires the role, the
skill, the rules, and the server card together so a runtime does
not have to re-derive the composition on every run.

## Boundaries

- The pack adds **no** new content. Every behaviour it describes
  lives in the assets it links to.
- The pack is **not** an installable bundle. A runtime that adopts
  the pack still loads each asset by its own path.
- The pack does **not** override any asset. If a link disagrees
  with the asset it points at, the asset wins; update the pack.

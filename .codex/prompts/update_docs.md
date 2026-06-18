# Update Docs

Use this prompt for documentation-only changes.

Read first:

- `AI_CONTEXT.md`
- `docs/DOC_LIFECYCLE.md`
- `docs/AI_WORKFLOW.md`
- `docs/ai_collaboration.md`
- `docs/AI_HANDOFF.md`

Rules:

- New Markdown files need lifecycle metadata.
- Use `current`, `target`, and `known gap` labels when implementation status matters.
- Do not present target architecture as current behavior.
- Do not move historical `AI_HANDOFF.md` material in bulk unless explicitly requested.
- Keep durable history in `docs/CHANGELOG_AI.md` and bug backlog in `docs/KNOWN_ISSUES.md` over time.

Verification:

- Run `make docs-check`.
- If a feature map changed, ensure all concrete paths exist.

Completion report:

- Docs added/changed.
- Known gaps identified.
- Follow-up docs migration tasks.

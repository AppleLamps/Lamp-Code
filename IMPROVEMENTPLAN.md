## Improvement Plan for Claudable

### Overview
This plan consolidates high‑impact product and UX improvements for Claudable across onboarding, AI workflows, preview, deployment, database, reliability, security, and architecture. Items are prioritized, each with rationale, UX notes, technical hooks, and acceptance criteria.

### Goals and KPIs
- Time to first preview: < 3 minutes from fresh clone
- Successful scaffold rate: > 95% without manual intervention
- Chat-assisted change success: > 85% without manual rollback
- Deployment success rate: > 95% with actionable errors
- Error-free sessions: > 99.5% without fatal crashes
- P95 interactive latencies: Chat < 400ms token-to-token; UI route load < 1s

### Prioritized Roadmap
- Quick wins (1–2 days)
  - [ ] Setup wizard: .env validation, API/WS connectivity checks, key presence checks
  - [ ] Global connection indicators + toast notifications
  - [ ] Live preview panel with health check, restart, and friendly errors
  - [ ] Chat polish: code-block copy buttons, pin messages, resilient streaming
- Near‑term (1–2 weeks)
  - [ ] Scaffold templates gallery + package manager choice (npm/yarn/pnpm)
  - [ ] Chat modes + context panel (files/diffs/logs); apply‑patch confirmation
  - [ ] Typed errors + Sentry; E2E smoke tests (onboarding → preview)
  - [ ] Vercel deploy status UI, logs, and rollback
- Bigger rocks (3–6 weeks)
  - [ ] Alembic migrations + DB designer and seed flows
  - [ ] GitHub integration (repo linking, auto PRs, release mgmt)
  - [ ] Audit log + secrets vault with rotation
  - [ ] Multi‑project dashboard with activity timeline

---

### 1) Onboarding and Setup
- Visual setup wizard
  - Why: Reduce setup friction; catch env/system issues early.
  - UX: Stepper checks Node/Python/ports, validates ANTHROPIC_API_KEY, tests Claude/Cursor connectivity, generates/updates .env.
  - Tech: Use /health, a lightweight WS echo, and a Claude test call; write .env via settings API; port detection.
  - Acceptance:
    - Shows green checks for API/WS; blocks next step until valid key is saved.
    - Generates .env with correct BASE and WS endpoints; persisted to disk.

- In‑app .env editor with validation
  - UX: Form with field-level validation and inline test buttons for API/WS; safe restart prompt after changes.
  - Tech: settings_router + pydantic schema; server restarts or hot-reload on safe fields; write-only secret inputs.
  - Acceptance: Invalid values flagged; saving updates runtime config; tests pass in‑UI.

---

### 2) Project Creation (Scaffolding)
- Templates gallery
  - Why: Faster time-to-value with opinionated presets.
  - UX: Cards for Tailwind/shadcn, auth, Prisma, TS/JS; “View template details” with dependencies and pages.
  - Tech: Pass template params to filesystem service; template manifests in JSON; post-scaffold scripts.
  - Acceptance: Selecting a template yields a working app with those features enabled.

- Package manager choice (npm/yarn/pnpm)
  - UX: Radio selector; persisted per project; displays lockfile type.
  - Tech: Pass correct flags to create-next-app; run matching installer.
  - Acceptance: Lockfile matches selection; install succeeds consistently on Win/macOS/Linux.

- Streaming console + cancel/cleanup
  - UX: Real-time logs (stdout/stderr) with levels; “Cancel” kills process and cleans partial dirs.
  - Tech: Subprocess stdout streaming; cancellation tokens; robust Windows shell handling.
  - Acceptance: Cancelling leaves workspace clean; errors show last 100 lines with copy button.

- Diff preview (“scaffold plan”)
  - UX: Before scaffolding, show file tree and unified diff; confirm to proceed; risk notes (e.g., overwriting existing dir).
  - Tech: Dry-run template manifest; diff renderer.
  - Acceptance: Users can inspect planned changes; applied output matches preview (minus lockfile variability).

- Adaptive timeouts/retries
  - UX: Progress meter; readable stuck-state hints; auto‑retry with backoff.
  - Tech: Tune timeouts by platform/network; retry create-next-app/npm install on transient failures.
  - Acceptance: Stuck installs either recover or fail with actionable guidance.

---

### 3) AI Chat UX
- Mode switches (Generate, Refactor, Tests, Debug, Docs)
  - UX: Mode tabs influence system prompts and tool permissions; quick actions per mode.
  - Tech: Mode param in chat endpoint; prompt templates; stricter tool scopes when needed.
  - Acceptance: Mode changes alter agent behavior with visible differences in outputs.

- Context panel (files/diffs/logs)
  - UX: Right sidebar to pin files, view recent diffs and server logs; pin messages and prompt snippets.
  - Tech: Endpoints for recent diffs; logs tailing; session persistence in DB.
  - Acceptance: Pinned items persist; diffs/logs update live; no UI jank.

- Streaming improvements: partial code blocks and quick actions
  - UX: Code blocks show as they stream; Copy/Insert/Apply buttons.
  - Tech: Chunked rendering; syntax highlighting during stream; patch extraction for apply.
  - Acceptance: Copy works mid-stream; insert opens a target file picker; apply opens confirmation dialog.

- Apply patch preview with rollback
  - UX: Show unified diff; require review acknowledgment; automatic backup and one‑click rollback.
  - Tech: Patch staging; transactional apply; rollback on failure; file locks and conflict detection.
  - Acceptance: Every patch can be rolled back; no half‑applied states.

- Tool transparency
  - UX: Inline “Tool running: <name> …” with parameters (safe) and results; collapsible timeline.
  - Tech: Instrument MCP/tool calls; redaction for secrets; structured logs.
  - Acceptance: All tool actions visible and filterable by type and outcome.

- Persistence/export
  - UX: Sessions auto‑restore; export to Markdown with code fences and timestamps.
  - Tech: Session store; export endpoint; download as .md.
  - Acceptance: Reloading restores last session; export contains full context.

---

### 4) Live Preview Stability
- Embedded preview iframe with health checks
  - UX: Status pill (Starting/Healthy/Error); auto‑reconnect; open in new tab option.
  - Tech: Ping target port; exponential backoff; detect Next build status.
  - Acceptance: Preview stabilizes or shows actionable errors within 5–10s.

- Friendly build error surfaces + “Fix with AI”
  - UX: Error panel with parsed stack and diagnosis; CTA to open a prefilled chat message.
  - Tech: Parse Next build logs; generate fixing prompt; deep link to chat.
  - Acceptance: Clicking CTA creates a chat message with error context; typical build errors resolved in one iteration.

- Restart controls and log tailing
  - UX: Restart dev server; show last N lines; filter logs; copy/share.
  - Tech: Process control in runner script; ring buffer logs.
  - Acceptance: Restart returns preview to healthy state when feasible; logs stay responsive.

- Port conflict UX
  - UX: “Port 3000 busy – Move to 3001?” one-click; auto-update links.
  - Tech: Port probing; env update; preview redirect.
  - Acceptance: Conflicts resolved without manual edits.

---

### 5) Version Control and Deployment
- Auto‑commit + grouped messages
  - UX: Suggested message (e.g., “feat: add auth page”); confirm/skip; link to diff.
  - Tech: Git service; change grouping by feature; conventional commits.
  - Acceptance: Commits appear with readable messages; no noisy churn.

- Draft PR creation
  - UX: Button to open PR; link to GitHub; show diff summary; labels.
  - Tech: GitHub API; branch naming conventions; PR templates.
  - Acceptance: PR created with correct base/head and labels; CI starts.

- Vercel deploy status and logs
  - UX: Card with status, preview URL, build logs, redeploy/rollback.
  - Tech: vercel_router + webhooks; status polling fallback.
  - Acceptance: Status updates near real‑time; rollback switches traffic.

- Optional GitHub during onboarding
  - UX: “Connect GitHub (optional)” step; can skip and add later.
  - Tech: OAuth flow; repo linking persistence.
  - Acceptance: Users onboard without GitHub and add it later seamlessly.

---

### 6) Database Experience
- Supabase wizard
  - UX: Enter project URL/anon key; test connection; seed starter schema.
  - Tech: Secure secret storage; test query; schema apply.
  - Acceptance: Connection verified; schema applied; env vars set.

- Visual schema designer + migration preview
  - UX: Edit tables/columns; see generated SQL; approve apply; migration history.
  - Tech: Alembic migrations; diff generation; safe down scripts.
  - Acceptance: Applying migrations updates DB and produces reversible scripts.

- Seed fixtures and data browser
  - UX: Seed demo data; sortable/filterable grid; inline edits with validation.
  - Tech: Seed scripts; paginated API; optimistic updates.
  - Acceptance: Edits persist; no PII leaks; actions audited.

- Env promotion
  - UX: Promote env vars across dev → preview → prod with guardrails.
  - Tech: Signed ops; audit logs; diff before apply.
  - Acceptance: Prevents accidental overwrites; logs every change.

---

### 7) Error Handling and Observability
- Typed errors and global toasts
  - UX: Consistent, human‑friendly error messages with retry links and diagnostics.
  - Tech: zod on web; pydantic on API; error categories and codes.
  - Acceptance: Network/validation/server errors show distinct, clear messaging.

- Sentry (client + server)
  - UX: Toggle in settings; privacy note and opt‑out.
  - Tech: DSN gated by env; source maps; breadcrumbs with request IDs.
  - Acceptance: Errors appear in Sentry with useful context.

- Logs viewer
  - UX: Tabs for API, Next build, AI calls (PII‑safe); filters by level/component.
  - Tech: Structured logs; redaction; streaming endpoints.
  - Acceptance: Searching by request ID or project ID works reliably.

---

### 8) Performance and Reliability
- AI call queue + rate limit + dedupe
  - Why: Avoid provider 429s; reduce costs and errors.
  - Tech: In‑memory queue with burst control; cache identical prompts; idempotency keys.
  - Acceptance: No 429 storms; UI shows queued/running states.

- Robust WS/API reconnects
  - UX: Banner “Reconnecting…”; retries with backoff/jitter; manual retry.
  - Tech: Heartbeats; exponential backoff; idempotent message IDs.
  - Acceptance: Transient drops recover without manual refresh.

- Process control improvements
  - UX: Show subprocess status; allow kill/retry; safe cleanup.
  - Tech: Graceful termination; cleanup handlers; orphan process detection.
  - Acceptance: No orphan processes; clean state after failures.

- Caching
  - UX: Faster re-runs for unchanged operations.
  - Tech: Disk cache for generated artifacts; ETags for logs; memoize expensive calls.
  - Acceptance: Repeat operations avoid redundant work without staleness bugs.

---

### 9) Accessibility and UI Polish
- Keyboard navigation + ARIA
  - UX: Tab-friendly flows; visible focus; screen‑reader labels on chat, preview, modals.
  - Acceptance: Passes key WCAG checks on onboarding, chat, preview.

- Theming and motion/skeletons
  - UX: Persisted theme; skeleton loaders and progress for long ops; reduced motion setting support.
  - Acceptance: Perceived latency reduced; minimal layout shifts.

- Command palette (Ctrl/Cmd+K)
  - UX: Fuzzy actions: new project, open preview, ask AI, deploy, open logs.
  - Acceptance: Frequent actions reachable in < 1s; keyboard-only.

- Consistent layout/empty states
  - UX: Clear empty-state guidance; consistent spacing/typography and error states.
  - Acceptance: All pages have defined empty/loading/error states.

---

### 10) Security and Secrets
- Encrypt Anthropic key at rest; rotation
  - UX: Rotate button; last used timestamp; copy-to-clipboard timeout.
  - Tech: cryptography lib; KDF; key rotation path; sealed storage.
  - Acceptance: Keys stored encrypted; rotation logs an audit event.

- Service tokens UI (scopes, rotation, revoke)
  - UX: Create/rotate/revoke with scopes; display last used; revoke all.
  - Acceptance: Tokens unusable after revoke; scope enforcement verified in API.

- Audit log
  - UX: Timeline of sensitive actions; filters by actor/resource; export CSV.
  - Tech: Append‑only store; signed entries; retention policy.
  - Acceptance: Every secret/token change recorded with actor and timestamp.

- CORS/CSRF hardening
  - Tech: Strict allowlist; CSRF on state-changing views where relevant.
  - Acceptance: External origins blocked; no CSRF regressions in tests.

---

### 11) Testing and CI
- E2E (Playwright): onboarding → scaffold → chat change → preview → deploy
  - Acceptance: Green run in CI; artifacts include screenshots/videos.

- API tests with pytest/httpx
  - Acceptance: Core routes covered; happy + failure paths; contracts verified.

- Pre‑commit hooks
  - Tech: lint, typecheck, format for web+api; commit message lint.
  - Acceptance: Hooks run locally and in CI; enforce style consistency.

- GitHub Actions CI
  - UX: Status badges; required checks for PR merge.
  - Acceptance: Smoke “npm run dev” starts both servers headlessly; tests pass.

---

### 12) Multi‑Project Management
- Dashboard with search/filters/favorites
  - UX: Sort by last activity; star favorites; quick actions per project.
  - Acceptance: Find and open projects in < 3 clicks; favorites persist.

- Activity timeline and status
  - UX: Show preview up/down, last build/deploy, recent commits.
  - Acceptance: Status reflects real processes with near‑real‑time updates.

- Project duplication and template export/import
  - UX: Clone with options; export template from an existing project.
  - Acceptance: Duplicated project starts correctly without conflicts.

---

### 13) Internationalization
- i18n for UI copy
  - UX: Language switcher; extracted strings; RTL compatibility plan.
  - Tech: next-intl or Next i18n routing; locale files.
  - Acceptance: EN baseline; ready to add locales without code changes.

---

### 14) Architecture Improvements
- Reduce tight coupling
  - Issue: CLI managers directly import WebSocket managers.
  - Fix: Introduce dependency injection and ports/adapters; invert dependencies.
  - Acceptance: No cross-layer imports; services mockable in tests.

- Ports/adapters for external services (Claude, GitHub, Vercel)
  - Tech: Define interfaces; concrete adapters behind DI; clear error boundaries.
  - Acceptance: Swap providers in tests without code changes.

- Stabilize WebSocket protocol
  - Tech: Message IDs, heartbeats, backoff, idempotency; version the protocol.
  - Acceptance: No duplicate actions; reconnection resumes safely.

- Replace Base.metadata.create_all with Alembic
  - UX: Migration commands exposed in UI/CLI; safe upgrades/downgrades.
  - Acceptance: Migrations drive all schema changes; no auto-create on startup.

- Domain boundaries and DTOs
  - Tech: Pydantic models as boundaries; avoid raw dict passing.
  - Acceptance: Type-safe contracts across API; fewer class of runtime errors.

- Observability standards
  - Tech: Structured logs; request IDs; optional OpenTelemetry tracing.
  - Acceptance: Correlate logs across web/api/agent sessions; debug faster.

---

### Dependencies and Risks
- External APIs (Anthropic, GitHub, Vercel, Supabase) can rate limit; use queueing/retries and backoff.
- Windows path/process handling variability; test on win32 and POSIX.
- Use feature flags to roll out risky changes gradually and enable rollback.

### Suggested Sequence
1) Quick wins and setup wizard → 2) Chat guardrails → 3) Preview health + logs → 4) Sentry + typed errors → 5) Templates + package manager → 6) Vercel deploy UI → 7) Alembic + DB designer → 8) GitHub integration → 9) Audit/secrets → 10) Multi‑project dashboard.


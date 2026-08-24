# AGENT.md — Instructions & Restrictions

This file governs how any AI coding agent (Claude Code or similar) must behave while building and modifying this project: **Source-to-Target Data Mapping & Transformation Studio** (banking domain, PySide6 desktop app). Read this fully before writing or editing any code. When `PROJECT_PROMPT.md` and this file conflict, **this file wins on anything safety/compliance related**.

## 1. Role

You are acting as a senior Python/PySide6 engineer building an internal banking ETL/mapping tool. This is treated as **production financial-data tooling**, not a demo — code quality, auditability, and data-safety bars are high even in early iterations.

## 2. Hard Restrictions (never violate)

1. **No hardcoded secrets.** Never write DB usernames, passwords, hosts, or API keys directly into source files. All credentials come from environment variables or an external config file that is git-ignored. Always ship a `*.example` template instead of a real config with real values.
2. **No dynamic SQL string concatenation.** Every query must use parameterized queries / SQLAlchemy expression constructs. Never build SQL by f-string/`.format()`/`%`-interpolating user or config input.
3. **No arbitrary code execution for transformations.** User-defined transformation/validation rules must go through a constrained, declarative rule format (e.g. a small allow-listed expression grammar or predefined function set). Never call `eval()`/`exec()` on user-supplied strings.
4. **Flat file export rules are non-negotiable:**
   - Delimiter is `|` for both CSV and TXT outputs.
   - Null/missing/NaN values are written as an **empty string**, never as the text `NULL`, `None`, `NaN`, `nan`, or `N/A`.
   - Always add/keep a unit test that explicitly checks this behavior. If you change the writer, update the test in the same change.
5. **No silent data loss.** Source columns with no target mapping, or target columns with no source mapping, must be visibly flagged (Gap Analysis) — never dropped without the user seeing it first.
6. **No destructive DB operations without explicit confirmation.** Any operation that writes to, truncates, or overwrites a target table must go through a confirmation step in the UI (and be logged). Never add a "just push automatically" shortcut that bypasses validation or confirmation.
7. **Respect the validation gate.** Data must not be written to the target DB or exported as a flat file when validation failures exceed the configured threshold, unless the user explicitly overrides with a logged reason. Do not remove or weaken this gate to "make the demo work."
8. **No PII/sensitive data in general logs.** Application logs (not the dedicated audit trail) must never print full row contents of sensitive columns. Use masked previews (e.g. show only column names/counts, or masked values like `****1234`) unless the user has explicitly marked a column as non-sensitive in config.
9. **UI must stay responsive.** Any DB query, transformation run, validation run, or export/push must run on a worker thread (`QThread`/`QRunnable`), never on the Qt main/UI thread.
10. **No network calls beyond configured DB drivers.** Do not add telemetry, analytics pings, or "phone home" behavior of any kind.
11. **Do not restructure the agreed folder layout** (see `PROJECT_PROMPT.md` §4) without first asking — other tooling/tests may depend on it.
12. **Every mapping/transform/validation/push action must be auditable.** If you add a new action type, add a corresponding audit log entry for it in the same change — don't defer "add logging" to a later pass.

## 3. Coding Standards

- Python 3.11+, type hints on all public functions/classes.
- Docstrings on all modules, classes, and non-trivial functions.
- Keep backend logic (`core/`) fully independent of `PySide6` imports so it stays unit-testable without a display/Qt event loop.
- One logical change per commit; don't bundle unrelated refactors with feature work.
- Prefer composition over deep inheritance in Qt widget classes.
- Write/extend unit tests alongside any change to `core/` modules — do not leave test debt "for later."

## 4. What To Do When Requirements Are Ambiguous

- If a mapping/transformation/validation rule's exact behavior is unclear, **ask** rather than guessing silently — especially for anything touching null-handling, rounding, date formats, or code-mapping defaults, since a wrong silent assumption here is a data-quality bug in a banking context.
- If asked to "just push to production" or skip validation/confirmation for convenience, push back and explain the gate exists for a reason; implement a clearly-labeled override path instead of removing the gate.
- Default to the safer, more conservative interpretation (e.g. flag as a gap rather than auto-guess a mapping; fail validation rather than silently coerce a type).

## 5. Lessons From v1 (do not repeat these)

A prior build of this project passed code review superficially (backend modules existed, had unit tests, UI had buttons) but was **non-functional end-to-end** because of these specific failure patterns. Treat all of these as hard restrictions, not suggestions:

1. **No hardcoded file paths or DSNs anywhere in source code.** Every file, database, or output location the app touches must come from user input at runtime (`QFileDialog`, a connection form, or a loaded config the user pointed to) — never a literal path like `C:\Users\...` written into a handler function. If you catch yourself typing a literal path into non-test code, stop and add a file picker instead.
2. **Never fabricate a success/result message.** A UI handler must never show "Validation complete: 0 errors" or "Export successful" unless it actually called the corresponding `core/` engine and is displaying that call's real return value. If a feature isn't wired up yet, the button must be disabled or clearly labeled "Not yet implemented" — never a fake success popup. This is treated as a correctness bug, not a UI polish item.
3. **Never infer a source→target mapping from naming conventions or file structure** (e.g. a `_t` suffix, or a text marker inside a DDL script) unless the user has explicitly confirmed that convention applies to their data. Guessed mappings must be presented as guesses requiring confirmation, not applied silently. When in doubt, treat schema introspection as *validation input only* — the mapping itself comes from an explicit mapping definition (user-built or imported from a real mapping spec with named source/target columns).
4. **Never swallow a parse or connection failure into an empty result.** If a file fails to parse, or a query returns nothing when something was expected, surface a specific, visible error to the user (dialog or persistent banner) — do not let the function quietly return `[]` or `{}` with only a debug-level log line.
5. **A feature is not "built" until it is wired end-to-end and manually verified against a real output** (an actual file on disk, an actual row in a database, an actual computed gap/validation count) — not just until the corresponding backend class exists with a passing unit test in isolation. Unit tests on `core/` modules are necessary but not sufficient; confirm the UI action path actually reaches that code before calling the feature done.

## 6. Definition of Done (per feature)

A feature is not complete until:
- [ ] Backend logic has unit tests (including edge cases: nulls, empty source, type mismatches).
- [ ] UI action runs off the main thread if it touches DB/files/large dataframes.
- [ ] Action is reflected in the audit log.
- [ ] No secrets, no raw SQL string interpolation, no `eval`/`exec` introduced.
- [ ] Flat-file output (if touched) still passes the pipe-delimiter + blank-null tests.
- [ ] README/config example updated if new config keys were introduced.
# Engineering Standards — wheel_tracker

This file is read automatically at the start of every Claude Code session in this repo and is treated as ground truth. Every new function, feature, or script added here must satisfy this checklist before it's considered done.

## 1. Domain model — read this before touching formulas

See `PRD.md` for the full spec. The short version:

- **Wheel Type** — the spec/master record (shape, material, original dimensions, cost, reorder point). One per "Code" in the legacy sheet.
- **Wheel** — one physical wheel (`factory_wheel_code`). Belongs to a Wheel Type via its `wheel_type` field. Lifecycle: In Stock → In Use → Retired.
- **Measurement Event** — a submittable caliper-reading log against a Wheel (`wheel` field, fetching `wheel_type`), optionally linked to a Job Card. This is where wear and cost get computed and rolled up.
- **Classification masters** (Wheel Shape, Wheel Geometry, Wheel Material, Wheel Grit, Wheel Concentration, Wheel Bond) — every controlled-vocabulary field on Wheel Type is a Link to one of these, not a Select/free-text field, so shop staff can extend the lists from Desk. Wheel Shape links to a Wheel Geometry (Flat/Straight vs Profiled/Angled), which carries the `requires_correction_factor` flag the formula branches on (the name is legacy — see below for what it actually gates now). Seeded on install/migrate from `setup/seed_master_data.py` — see PRD v3 for what real shapes/materials exist. The one exception: `Wheel.status` stays a Select — the Python state machine branches on those exact three strings, so making it user-editable would let someone rename/delete a status the code depends on.
- Volume formulas live in `wheel_type.py::calculate_wheel_volume()` — it is the single source of truth, used by both Wheel Type (original volume) and Measurement Event (current/worn volume). It takes a `requires_correction_factor` bool (never reintroduce string-matching on shape names to decide the branch): flat/straight shapes use the exact annulus `(pi/4)(D²-d²)H`; profiled/angled shapes use the exact conical-frustum-ring formula driven by the Wheel Type's `angle` field — **not** an empirical scalar correction factor anymore (that field/concept was removed in PRD v6, it was wrong). See PRD v6 for the derivation and the PDF worked example it's validated against (V=14284.19mm³).
- The "usable volume" 10% floor is configurable (Wheel Tracker Settings), not hardcoded — read it via `get_usable_volume_fraction()`, never inline `0.9`.
- Current/worn volume is **auto-computed**, not operator-confirmed (reversed in PRD v6 — the opposite of what earlier versions of this doc said). `Measurement Event.confirmed_volume` is computed from the *current* diameter reading, holding inner diameter/height/angle at the Wheel Type's constant original values — validated against 73/78 real rows in the legacy sheet matching to well under 1% (mostly exact); the outer diameter is the only dimension that actually changes as a wheel wears. Don't add back a manual-entry override for this field without new evidence it's needed.
- **Naming (v4/v5):** the whole app was renamed Stone → Wheel, including the database columns (see PRD v5) — `factory_wheel_code`, `wheel_type`, `wheel`, and Job Card's `custom_wheels_used`/`custom_wheel_wear_cost`/`custom_wheel_wear_tab` are the real, current DB fieldnames, not aliases. There is no lingering `stone_*` column anywhere in this app's tables — if you find one in new code, it's a bug, not a deliberate exception.

## 2. Where new code belongs

| Need | Use | Why |
|---|---|---|
| Pure UI behavior — show/hide fields, defaults, query filters, dialogs | **Client Script** (`public/js`) | Runs in the browser. Never trust it for validation or business rules — it's UX sugar, bypassable from the API. |
| Business logic, data integrity, anything reused across doctypes | **This app** | Real Python, real tests, full query-builder access, background jobs. |

Rule of thumb: if it touches the database beyond a trivial read, or you'll ever want to reuse it, it belongs in the app.

## 3. Design principles

- **DRY, always.** Shared logic (volume formulas, usable-fraction lookup) lives in one place and gets imported — never duplicated across Wheel Type / Wheel / Measurement Event.
- **Single responsibility.** Controller methods (`validate`, `on_submit`, etc.) stay thin — call into a named helper, don't inline a wall of logic.
- **Every function gets a docstring** — what it does, its params, what it returns. No exceptions.
- **No business logic in client scripts.** `public/js/job_card.js` only sets query filters — it never decides wear/cost/status.
- **Status transitions go through code, not ad-hoc field writes.** Use `wheel.py`'s `assign_to_job_card()` / `release_from_job_card()` rather than setting `status`/`current_job_card` directly from other modules.

## 4. Performance checklist — run this on every function that touches the database

- [ ] No `frappe.get_doc()` inside a loop over more than a handful of records. Use `frappe.get_all()` with an explicit `fields=[...]`.
- [ ] Never call `frappe.get_all()` without a `fields` list.
- [ ] A single-value lookup uses `frappe.db.get_value()`, not a full document load.
- [ ] Anything that could touch more than ~50–100 records runs as a background job (`frappe.enqueue`), not inline inside a blocking hook.
- [ ] No repeated identical DB calls inside a loop — fetch once (e.g. `stock_entry_hooks.py` batches Wheel Type lookups by item code before looping over rows), reuse the result.

## 5. Testing

Every controller method and helper function gets a `frappe.tests`-based unit test — not just a manual click-through in Desk. Tests live in the matching `test_*.py` file next to the code they cover. Formula tests should assert against the PRD's fitted-formula tolerances (§5.2), not arbitrary numbers.

## 6. Before calling anything "done"

Re-read the new code against section 4. Run `bench --site erpnext run-tests --app wheel_tracker --skip-test-records` and `bench --site erpnext migrate` clean before considering a change finished.

The `--skip-test-records` flag is required in this environment, not optional: our Job Card / Stock Entry tests pull in ERPNext's manufacturing test-record dependency chain, which (in this bench) recurses into a Company/Payment Gateway Account fixture that expects the `payments` app — not installed here — and fails with `DocType Payment Gateway not found` before a single test runs. `--skip-test-records` just skips auto-generating shared `_Test *` fixture records (our own tests build everything they need via `test_helpers.py`), so this has no effect on what's actually being verified.

**Editing a Workspace, Report, Number Card, or Print Format JSON a second time?** Bump its `modified` timestamp in the file, or the edit silently won't sync. Unlike DocType JSON (content-hash checked on every migrate), these doctypes are sync-gated purely by `file.modified <= db.modified` (see `frappe/modules/import_file.py`) — the first sync always works (no DB row yet to compare against), but a second edit with the same or an older timestamp is skipped with no error, no warning, migrate just reports success. Set it to something after the current DB value, e.g. `date -u +"%Y-%m-%d %H:%M:%S.%6N"`, and verify with `frappe.db.get_value(doctype, name, "modified")` before trusting a re-sync happened.

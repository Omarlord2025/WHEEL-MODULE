# Engineering Standards — wheel_tracker

This file is read automatically at the start of every Claude Code session in this repo and is treated as ground truth. Every new function, feature, or script added here must satisfy this checklist before it's considered done.

## 1. Domain model — read this before touching formulas

See `PRD.md` for the full spec. The short version:

- **Wheel Type** — the spec/master record (shape, material, original dimensions, cost, reorder point). One per "Code" in the legacy sheet.
- **Wheel** — one physical wheel (`factory_wheel_code`). Belongs to a Wheel Type via its `wheel_type` field. Lifecycle: In Stock → In Use → Retired.
- **Measurement Event** — a submittable caliper-reading log against a Wheel (`wheel` field, fetching `wheel_type`), optionally linked to a Job Card. This is where wear and cost get computed and rolled up. Blocked entirely for Wheels whose Type has `requires_measurement` unchecked (P-series — see PRD v9) — those use **Wheel Usability Check** instead: a submittable binary usable/not-usable record that drives retirement directly, no dimensions involved. Both doctypes share the "log an event against a Wheel, submit to apply it, cancel to revert it" shape; don't build a third variant of that pattern without checking whether one of these two already fits.
- **Classification masters** (Wheel Shape, Wheel Geometry, Wheel Material, Wheel Grit, Wheel Concentration, Wheel Bond) — every controlled-vocabulary field on Wheel Type is a Link to one of these, not a Select/free-text field, so shop staff can extend the lists from Desk. Wheel Shape links to a Wheel Geometry (Flat/Straight vs Profiled/Angled), which carries the `requires_correction_factor` flag the formula branches on (the name is legacy — see below for what it actually gates now). Seeded on install/migrate from `setup/seed_master_data.py` — see PRD v3 for what real shapes/materials exist. The one exception: `Wheel.status` stays a Select — the Python state machine branches on those exact three strings, so making it user-editable would let someone rename/delete a status the code depends on.
- Volume formulas live in `wheel_type.py::calculate_wheel_volume()` — it is the single source of truth, used by both Wheel Type (original volume) and Measurement Event (current/worn volume). It takes a `requires_correction_factor` bool (never reintroduce string-matching on shape names to decide the branch): flat/straight shapes use the exact annulus `(pi/4)(D²-d²)H`; profiled/angled shapes walk a `Wheel Type.profile_segments` child table (`Wheel Type Profile Segment`: `angle` + `height` per row) and sum a conical-frustum-ring volume per segment — **not** an empirical scalar correction factor (removed in PRD v6) and **not** a single scalar `angle` field (removed in PRD v7, replaced by the segment table for a possible compound/stepped shape). The schema supports 2+ segments, but every real profiled wheel imported so far (12V9 at 45°, 11V9 at 20°, 1V1 at 45° or 10°) is exactly reproduced by a **single** segment — validated against the real "WHEELS WITH ANGLES" data in PRD v8, all 3 angles solved numerically against real recorded volumes, not assumed. Don't add a second segment to a real Wheel Type without an actual worked example or measurement backing it — the 2-segment path has none yet.
- The "usable volume" 10% floor is configurable (Wheel Tracker Settings), not hardcoded — read it via `get_usable_volume_fraction()`, never inline `0.9`.
- Current/worn volume is **auto-computed**, not operator-confirmed (reversed in PRD v6 — the opposite of what earlier versions of this doc said), via `MeasurementEvent._volume_inputs()` — and the inputs it uses **differ by geometry family** (PRD v8):
  - Flat wheels (1A1/P-series) wear only radially — use the *current* diameter reading with the Wheel Type's constant original inner diameter/height. Validated against 73/78 real FLUTE rows to well under 1%.
  - Single-segment profiled wheels (1V1/12V9/11V9) wear *along the bevel* — diameter, inner diameter, and height all shrink together. Use *this measurement's own* current inner_diameter/diamond_height readings, holding only the Wheel Type's angle constant. Using the flat-wheel model here (Wheel Type constants instead of this event's readings) was tried first and gave 42–68% median error — badly wrong; don't revert to it.
  - Compound/stepped profiles (2+ segments): no real data exists on how current readings map onto a multi-segment chain, so this falls back to the Wheel Type's original segments/height. Known, documented limitation, not a validated model — fix it for real once a real 2-segment Wheel Type exists.
- **Naming (v4/v5):** the whole app was renamed Stone → Wheel, including the database columns (see PRD v5) — `factory_wheel_code`, `wheel_type`, `wheel`, and Job Card's `custom_wheels_used`/`custom_wheel_wear_cost`/`custom_wheel_wear_tab` are the real, current DB fieldnames, not aliases. There is no lingering `stone_*` column anywhere in this app's tables — if you find one in new code, it's a bug, not a deliberate exception.
- **Retirement (v9):** goes through `wheel.py`'s `retire_wheel()`/`reinstate_wheel()` — not just for P-series; either is safe to call on any Wheel from anywhere (both are no-ops if already in the target state). `Wheel.check_auto_retirement()` (consumption ≥100%) still runs on every save regardless and takes priority — don't try to "fix" a wheel that immediately re-retires itself after `reinstate_wheel()`, it means the consumption is still genuinely ≥100%.
- **`mandatory_depends_on` is not reliable for enforcement in this Frappe version** (confirmed on `Wheel Usability Check.retirement_reason` — insert() let a doc through with the condition true and the field empty). Keep the JSON attribute for the UI hint, but also check it explicitly in `validate()`, same as `WheelType.validate_dimensions()` already does for its own fields.

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

# PRD — Resharpening Wheel (Diamond/CBN Wheel) Tracking Module
**App target:** ERPNext v15 / Frappe Framework, hardcoded custom app (code-based doctypes, version-controlled)
**Company:** CNC Leaders
**Status:** Draft v14 — Batch Measurement Entry driven by a date range, not one Job Card

---

## v14 — Batch Measurement Entry finds wheels by date range, not one Job Card at a time

The Batch Measurement Entry page only ever showed Wheels currently In Use on one Job Card you had to already know and pick — awkward for reviewing everything used across several jobs over the last few days, and blind to any Wheel that had already moved on to another Job Card (or been released) by the time someone got around to measuring it.

**`get_job_card_wheels(job_card)` is replaced by `get_wheels_used_between(from_date, to_date)`.** It finds every Job Card whose Posting Date falls in the range, then every Wheel that ever appeared in one of their `Job Card Wheel` rows — reusing the same durable assignment history `MeasurementEvent.derive_job_cards()` already relies on, so a Wheel shows up even if it's since moved to a different Job Card or gone back In Stock. Already-Retired Wheels are dropped (nothing left to measure), and so is any Wheel that already has a submitted Measurement Event on or after `from_date` — that's what makes a just-measured Wheel not come back when the same date range is picked again, without needing any new "already handled" flag or session state.

**The page itself** now asks for From Date/To Date (defaulting to the last 7 days) instead of a Job Card, and each row shows which Job Card(s) that Wheel actually appeared on, since it's no longer implicitly the one Job Card you searched for. `submit_batch_measurements()` dropped its now-meaningless `job_card` parameter entirely — it was already just being ignored in favor of `derive_job_cards()`'s own history lookup since PRD v12; nothing changes about what it submits.

**A pre-existing test-isolation gap got noticeably more exposed by this change, not caused by it:** `make_job_card()`'s Work Order fixture and the Job Cards it creates were never cleaned up between tests (only Wheel/Wheel Type/Measurement Event/Wheel Retirement are, in `cleanup_wheel_tracker_records`) — invisible before, since every prior test scoped its query to one specific Job Card name, but a date-range query naturally picks up any other test's same-day Job Cards too. Worth fixing properly at some point; for now the new tests assert membership (`assertIn`/`assertNotIn`) rather than exact list equality where Job Card names are involved, same way a real user's results page would just show a few extra Job Cards, not break.

84 tests passing (2 new), clean migrate.

---

## v13 — workspace rename, a Desk language toggle, and a combined consumption bar

Three independent, small requests, none touching the wear/cost model.

**Workspace renamed Wheel Tracker → Grinding Wheels.** Cosmetic only — the app's own name, module, and every Python path stayed `wheel_tracker`/`Wheel Tracker`. Renamed via a `pre_model_sync` patch (`rename_wheel_tracker_workspace_to_grinding_wheels.py`, mirroring the v10 doctype-rename patch's own reasoning) rather than editing the Workspace JSON's name in place, since Workspace fixtures are upserted by `name` rather than content-hash-checked and an in-place JSON edit alone would have orphaned the old doc.

**A Language Toggle button on the workspace**, switching the current user's Desk language between Arabic and English. Built on a real, existing Frappe v15 mechanism — **Custom HTML Block** (`html`/`script`/`style` fields rendered into a shadow DOM via `frappe.create_shadow_element`, confirmed by reading `frappe/public/js/frappe/widgets/custom_block_widget.js`) — rather than anything bespoke; the block's script calls a new whitelisted `language_toggle.py::toggle_language()`, which only ever updates `frappe.session.user`'s own `User.language` field. This translates Frappe/ERPNext's own strings and flips RTL layout via their existing language packs (Arabic is already an enabled Language on this site); it does **not** translate this app's own custom field labels — no Arabic translation file exists for those yet, and adding one is separate, larger follow-up work if wanted.

**Consumption % now shows a number, not just a bare bar, in List View.** Frappe's own List View renders a `Percent` fieldtype as an unlabelled progress bar (confirmed by reading `frappe/public/js/frappe/list/list_view.js`) — `Wheel` and `Measurement Event`'s `consumption_percent` both used this by default. A shared formatter (`public/js/consumption_bar.js`, loaded via `app_include_js`) overrides both doctypes' list views (`doctype_list_js`, via `frappe.listview_settings.formatters` — the documented, non-core-patching extension point for this) with a bar that also shows the percentage as text, color-coded green/orange/red by severity.

82 tests passing (unchanged — this version touches no wear/cost logic), clean migrate.

---

## v12 — auto-retirement issues real stock, and one measurement can span several Job Cards

Two gaps surfaced by direct questioning of the v10/v11 design, both closed without touching the wear/cost formulas themselves.

**Crossing 100% consumption now issues the Wheel out of stock automatically, not just in Wheel Tracker's own status.** Previously, `Wheel.check_auto_retirement()` flipped `status = Retired` on save, but nothing created the real Material Issue Stock Entry — a fully-worn Wheel kept showing Active/full-value in ERPNext's own stock ledger until a human noticed and separately filed a Wheel Retirement. `MeasurementEvent.on_submit()`/`on_cancel()` now call new `create_auto_retirement()`/`cancel_auto_retirement()` methods, which create/cancel a real Wheel Retirement — reusing its existing `on_submit`/`on_cancel` (`retire_wheel()` + `create_retirement_stock_entry()`) completely unchanged, not a second implementation of retirement. This has to run *after* `apply_to_wheel()`'s own `wheel.save()` has returned, not from inside `Wheel.check_auto_retirement()` itself, which is still mid-save on the call stack at that point — attempting it there would recurse into that same save. A missing Warehouse on the Wheel still throws (as it always did for a manual Wheel Retirement) rather than being silently swallowed, which would just recreate the same gap.

**A Measurement Event's wear can now be attributed to more than one Job Card.** A Wheel isn't necessarily re-measured after every job — it can be assigned and released across several Job Cards between two measurements — so the single `job_card` Link field was silently misattributing wear to whichever Job Card happened to be open when a measurement was finally taken. `Measurement Event.job_card` is replaced by a `job_cards` child table (`Measurement Event Job Card`: `job_card` + `allocated_cost`), auto-derived in `derive_job_cards()` from the Wheel's real `Job Card Wheel` assignment history since its previous submitted event — no new tracking was needed, since every Job Card a Wheel was ever assigned to already leaves a row there for as long as that assignment isn't explicitly corrected before saving. `job_cost` is split equally across however many distinct Job Cards are found. `job_card_integration.py::update_job_card_wheel_cost()` now sums a Job Card's share from this child table via a join, not `Measurement Event.job_cost` directly. A `pre_model_sync` patch (`migrate_job_card_to_measurement_event_job_cards.py`) backfills existing single-`job_card` data into the new table before the old column drops. The Batch Measurement Entry page keeps its `job_card` parameter only as the "which wheels to show" filter — it no longer writes it onto created events, since `derive_job_cards()` works it out for itself.

82 tests passing (10 new/rewritten), clean migrate.

---

## v11 — batch measurement entry, and a per-Wheel-Type floor override

Two small, independent requests from the shop floor. Recording one Measurement Event at a time against a busy Job Card with several wheels assigned was reported as stressful/error-prone; and the 10% usable-volume floor (Wheel Tracker Settings) turned out not to be a true constant across every Wheel Type.

**Usable Volume Floor % can now be overridden per Wheel Type.** `Wheel Type` gained an optional `usable_volume_floor_percent` (Percent). `get_usable_volume_fraction()` (`wheel_tracker_settings.py`) now takes an optional `floor_percent_override` argument — truthy override wins, otherwise it falls back to the existing global Wheel Tracker Settings value (10% default), unchanged from before. All three call sites (`WheelType.validate()`, `Wheel.recalculate_wear()`, `MeasurementEvent.validate()`) now pass the Wheel Type's own value through, so a blank override is invisible — every existing Wheel Type keeps computing off the global default exactly as before.

**Batch Measurement Entry**, a new Page (`wheel-batch-measurement`, `batch_measurement.py`), following the exact Page + whitelisted-Python shape already established by Bulk Import Wheels rather than inventing a new pattern. An operator picks a Job Card; `get_job_card_wheels()` loads every Wheel currently In Use on it, split into those a Measurement Event can be recorded against and those that can't (Wheel Type `requires_measurement` unchecked — P-series, tracked via Wheel Retirement instead). Each measurable row is pre-filled with its Wheel's current readings and directly editable; `submit_batch_measurements()` then creates and submits one real Measurement Event per row through the *exact same* insert/submit code path as the single-record form — no wear/cost/retirement logic is duplicated for the batch case. Per-row savepoint/rollback (matching `bulk_import.py`'s established convention) means one bad reading is reported as an error without aborting the rest of the batch.

79 tests passing (4 new), clean migrate.

---

## v10 — real Stock/Manufacturing integration, not a parallel bookkeeping system

Wheel Tracker's own counts and ERPNext's real stock ledger had been running as two disconnected systems — confirmed concretely: Item `101546` showed `Bin.actual_qty = 0` in ERPNext's own ledger while Wheel Tracker still counted a Wheel "In Stock" for it, since nothing a Wheel did ever touched a real Stock Ledger Entry. Wheel wear cost also dead-ended in a custom Job Card field, never reaching ERPNext's own Work Order costing. Separately, real data entry doesn't start on Wheel Tracker's own Wheel Type form at all — employees create an Item Template, generate Item Variants across measurement combinations (ERPNext's own native mechanism), and "create wheels from them." This version rebuilds the app around both facts rather than beside them. Three research passes into ERPNext core (`stock/doctype/serial_no`, `stock/serial_batch_bundle.py`, `manufacturing/doctype/work_order`, `controllers/item_variant.py`) grounded every mechanism below in source before it was built, not assumed.

**Item Template + Attributes (new front door).** One universal Item Template (`GRINDING-WHEEL-TEMPLATE`), seeded by `setup/item_variant_setup.py`, with six Item Attributes: `Shape` and `Material` (discrete, matching the existing Wheel Shape/Material codes), `Diameter`/`Inner Diameter`/`Height` (numeric range+increment — ERPNext has no true free-numeric attribute, confirmed via `item_attribute.py::validate_numeric()`), and `Angle` (discrete: 10°/20°/45°, the three real solved angles from v8). Employees use ERPNext's own native "Create Variants" wizard — no custom UI. One real gotcha found empirically, not documented anywhere: a template's own `Item Variant Attribute` rows need `numeric_values`/`from_range`/`to_range`/`increment` copied onto them explicitly (Desk's form does this client-side when an attribute is picked; done here by hand since the template is created programmatically) — without it, `Item.validate_variant()` reads `numeric_values` as unset and validates every numeric attribute against the discrete-value-list path instead, rejecting valid values.

**Wheel Type is now auto-created, not hand-filled.** `item_variant_hooks.py`'s `create_wheel_type_from_variant()` (`Item.after_insert`) reads a new variant's `Item Variant Attribute` rows and builds a matching Wheel Type — flat shapes get `original_diameter`/`original_inner_diameter`/`original_diamond_height` straight from the attributes; profiled shapes get one Profile Segment (`angle` + `height`) instead, with `original_diamond_height` auto-summed by the existing `WheelType.validate()` logic unchanged. No Angle chosen on a profiled variant → the Wheel Type is still created, just with an empty segment table, and the existing "at least one Profile Segment is required" validation surfaces the gap on save rather than guessing. The 63 Wheel Types that existed before this version stay on plain (non-variant) Items — not retrofitted, since their identity already carries the correct data and touching production `item_code`s would be pure risk for no benefit.

**Every Wheel Type's Item is now serialized.** `ensure_item_is_serialized()` (`wheel_type.py`, called from `WheelType.validate()`) sets `has_serial_no=1`, reusing ERPNext's own `Item.cant_change()` guard rather than re-deriving when it's safe. A patch backfills the 63 pre-existing Items the same way.

**Material Receipt attaches real serial numbers, not a bare count.** Once an Item is serialized, ERPNext requires serial numbers as part of a Stock Entry's *submission*, not addable afterward — so `stock_entry_hooks.py` gained a `before_validate` hook (guaranteed to run before core's own mandatory-serial check) that mints `factory_wheel_code`s and attaches them via `erpnext.stock.serial_batch_bundle.SerialBatchCreation` — the same mechanism ERPNext's own test helpers use. One more undocumented gotcha found by testing directly against the real function rather than assuming: `SerialBatchCreation` needs `use_serial_batch_fields=1` and an explicit `batches={}` in its args, or it either refuses to auto-create missing Serial No records or throws `AttributeError: 'SerialBatchCreation' object has no attribute 'batches'` — neither documented, both confirmed empirically. `create_wheels_on_material_receipt` (`on_submit`) now creates one Wheel per *actual* serial, `Wheel.name == Serial No.name` exactly, and is idempotent — a deliberate design choice that let the opening-stock backfill (below) reuse this exact path instead of a separate one.

**A genuine stock movement now changes a Wheel, not just the other way around.** `stock_ledger_hooks.py`'s `sync_wheel_status_from_stock_ledger()`, hooked on `Stock Ledger Entry.on_submit` only — confirmed by reading source that `on_cancel` always `frappe.throw()`s, since SLEs are append-only and a voucher cancellation posts a *new*, sign-reversed SLE that itself goes through `on_submit`, so one handler covers both directions. It reads back `Serial No.status`/`warehouse` (confirmed safe to read synchronously, not a race, by tracing `Document.hook()`'s `compose()` — the controller's own `on_submit`, which updates Serial No inline, runs before any `doc_events` hook for the same event) and calls the existing `retire_wheel()`/`reinstate_wheel()` — never writing status directly. A Material Issue or a Stock Reconciliation zeroing a serial now retires the Wheel for real; a Material Transfer updates its warehouse via a new `sync_wheel_warehouse()` without touching status.

**Wheel Usability Check renamed to Wheel Retirement, and it now does something real.** Per explicit instruction: no more usable/not-usable question — submitting *is* retiring. `on_submit` calls the existing `retire_wheel()` *and* creates+submits a real Material Issue Stock Entry for that Wheel's serial (deliberately redundant with the SLE hook above, which independently arrives at the same conclusion once that Material Issue submits — both are no-ops when already agreeing, and the direct call is what still works for the edge case of a Wheel whose Item somehow isn't serialized). `on_cancel` reinstates and cancels that Stock Entry. Still usable against any Wheel, not just P-series ones.

**Wheel wear cost now reaches Work Order costing.** `job_card_integration.py`'s `sync_wheel_cost_to_work_order()` sums Wheel Wear Cost across a Work Order's Job Cards into `Work Order.additional_operating_cost` — ERPNext's own designed bolt-on-cost extension point, already flowing into `total_operating_cost` and into Stock Entry's FG valuation via `BOM.add_operations_cost()`. Mirrors ERPNext's own `Job Card.update_corrective_in_work_order()` exactly, including `ignore_validate_update_after_submit` before saving a submitted Work Order.

**A real Company and Warehouse now exist.** This site had none — only ERPNext's test/demo fixtures. Created `CNC Leaders` (abbr `CNCL`) and `Main Store - CNCL`, confirmed with the user before creating.

**Opening-stock backfill, the acceptance test for this whole version.** A patch gives all 136 pre-existing Wheels a matching Serial No and an opening Material Receipt (already-retired ones additionally get `create_retirement_stock_entry()` called directly — no real historical "someone submitted this" event to reconstruct, so no fabricated Wheel Retirement documents). Touches only `warehouse`/`source_stock_entry` on the existing Wheel record. Verified directly against the live site after running it: **135 Wheels "In Stock" in Wheel Tracker's own count; 135 units of `actual_qty` in ERPNext's real Bin at Main Store** — the exact number that was mismatched (0 vs 1, on a smaller scale) at the start of this version.

72 tests passing (12 new modules/cases), clean migrate.

---

## v9 — P-series wheels don't get measured; a general manual-retirement workflow

Talked to the shop floor: P-series slitting/cutting-off wheels (P1.5/P1.7/P2) aren't tracked by graduated caliper wear at all — an operator just judges a wheel usable or not usable, no dimensions involved. Measurement Event's whole model (diameter/inner diameter/height readings driving a computed volume) doesn't apply to them; forcing it would mean fabricating precision that was never really measured.

**Wheel Shape gets a new `requires_measurement` field** (Check, default 1), fetched onto Wheel Type the same way `requires_correction_factor` already is. Seeded 0 for P1.5/P1.7/P2, 1 for everything else (1A1/12V9/11V9/1V1). A patch (`set_p_series_requires_measurement`) fixes the flag on the P-series Wheel Shape *and* Wheel Type records already live in the system, since `fetch_from` only refreshes on save and `seed_master_data`'s get-or-create doesn't touch existing rows.

**Measurement Event refuses to be created against a Wheel whose Type has `requires_measurement` unchecked** — enforced in `validate()` (real guard) and mirrored client-side by filtering the Wheel picker to measurable wheels only (`measurable_wheel_query`, UX only). Existing historical baseline events for the 7 real P-series wheels (created by the original FLUTE backfill, before this rule existed) are untouched — the rule only blocks *new* ones.

**New doctype: Wheel Usability Check** — the P-series replacement for Measurement Event, and, more generally, a manual retirement/reinstatement record usable against *any* Wheel (not just P-series) for a reason unrelated to consumption %, e.g. a diamond wheel that's physically cracked well before its volume runs out. Submittable, mirrors Measurement Event's shape: `wheel`, `wheel_type` (fetched), an optional `job_card` for traceability, `check_date`/`checked_by`, and a `usable` checkbox with a required `retirement_reason` when unchecked. On submit: usable → `reinstate_wheel()`; not usable → `retire_wheel()`. On cancel: reapplies whatever the next-most-recent submitted check for that Wheel said, or reinstates if none is left. (`mandatory_depends_on` on `retirement_reason` didn't actually enforce at insert time in this Frappe version — reason required is checked explicitly in `validate()` instead, matching how `WheelType.validate_dimensions()` already does its own explicit checks rather than leaning on JSON-only validation.)

**Two new whitelisted functions on `wheel.py`**, alongside the existing `assign_to_job_card`/`release_from_job_card` pair: `retire_wheel(wheel, reason)` and `reinstate_wheel(wheel)` — both no-ops if the Wheel's already in the target state, both centralizing the status/retirement-field writes (per this file's existing rule: status transitions go through code, not ad-hoc field writes). `check_auto_retirement()` on `Wheel.validate()` is unchanged and still runs on every save — a wheel manually reinstated while genuinely still at ≥100% consumption immediately re-retires itself in the same save, which is correct (can't override a measurement-driven retirement that's still factually true), and doesn't apply to P-series wheels anyway since their `current_volume` never changes without a Measurement Event to update it.

Added to the workspace under Operations, next to Measurement Event. 60 tests passing (12 new), clean migrate.

---

## v8 — backfilled the real profiled-wheel data; found profiled wheels wear differently than flat ones

`Main data and flow.xlsx` turned out to have a second sheet ("Sheet1") pasted in as plain values from a linked external workbook, with no header row and an unfamiliar 20-column layout — 59 real 12V9/11V9/1V1 wheels (the "WHEELS WITH ANGLES" data referenced back in the original v1 correction, never actually imported). Reconstructing its column meanings by arithmetic alone only got to ~5% median error — not trustworthy for production import, especially right after the v6/v7 formula work. The external link named its source file directly; found it on the Desktop, password-protected ("ملف جرد حجارة المصنع و استهلاكه2-8-2026.xlsx" — the same file a prior formula-reference document had flagged as needing confirmation). User supplied the password; decrypted it (`msoffcrypto-tool`) to get the sheet's real headers and an Excel Table definition — no more guessing.

**Validated the original-volume formula against real recorded volumes, per shape:**
- **12V9**: angle = 45°, exact match (0.00% error, all 3 real wheels) — single Ring Frustum segment, same formula as v6.
- **1V1**: angle = 45° or 10° depending on spec (parsed from a `-vNN-` token in the legacy name — the name's `-sNN-`/`-vNN-` tokens turned out to be genuine, shape-specific angle encodings). 15/19 wheels matched to <2% (many exact); 4 outliers are the same kind of source data-entry errors found in v6 (see below).
- **11V9**: the name's `-s70-` token is *not* the geometric angle (using it gave 25–35% systematic error) — solved for the angle numerically against the real recorded volumes instead, independently across two different dimension families, and both converged to the same clean **20.00000°**. Confirms this is a real, single, shape-level constant, not a per-wheel value.

This directly tests the compound/stepped-profile question from v7: the recorded historical volumes for 11V9 are reproduced *exactly* by a single Ring Frustum segment at 20°, not the two-segment chamfer+cone model the physical wheels apparently have. Read as: the shop's own spreadsheet has always used a single-segment simplification (the chamfer's volume contribution is evidently small enough to ignore), and matching that simplification is what "exactly like the Excel file" requires here. The 2-segment schema from v7 stays in the code for whenever a case actually needs it, but isn't used by anything real today.

**New finding — profiled wheels wear differently than flat ones.** v6 established that flat wheels (1A1/P-series) wear *only* radially — bore and layer height stay constant, only the outer diameter reading matters for current volume. Testing that same assumption against the real 11V9/12V9/1V1 current-volume numbers gave 42–68% median error — badly wrong. The fix: profiled wheels wear *along the bevel*, so diameter, inner diameter, and layer height all shrink together; recomputing current volume from *this measurement's own* current inner-diameter/height readings (not the Wheel Type's original constants), holding only the angle fixed, reproduced the real recorded current volumes essentially exactly (median error back to 0.00%). `MeasurementEvent._volume_inputs()` now branches on geometry family: flat wheels still use the Wheel Type's constant inner diameter/height (v6, unchanged); single-segment profiled wheels use this event's own readings; compound/stepped profiles (no real data to validate against) fall back to the Wheel Type's original segments, documented as an unvalidated limitation.

**Data-quality issues found and handled, not silently guessed around** (same pattern as the v6 FLUTE anomalies):
- Spec code 102302 (2 wheels, `SL-B-1V1-100-T4-0247/0248`): recorded inner diameter (104.9mm) larger than its recorded outer diameter (100mm) — physically impossible. **Excluded from the import.**
- One row (`SL-B-1v1-100-T5-0189`) had its spec `Code` cell showing `5.08` — a stray copy of its own height value, not a real code. Its dimensions/shape/material/volume exactly matched 5 other wheels filed under code 101552, so it was corrected to join that spec rather than becoming its own bogus one-wheel type.
- A handful of individual rows (e.g. `SH-D-12V9-100-T20-0063`, `SH-D-1V1-125-T4-0085`) have recorded volumes the formula can't reproduce even with the right angle — inconsistent with their own sibling rows, so left as imported (the formula-driven `confirmed_volume` going forward is trusted over that one stale historical number, same call made for the 5 FLUTE outliers in v6).

**Result:** 19 new Wheel Types, 57 new Wheels, 57 new submitted baseline Measurement Events, all through the same `Wheel`/`Measurement Event` code path as a live measurement (no separate import logic duplicating the wear math). Combined with the v6 FLUTE backfill: 62 Wheel Types, 136 Wheels, 135 submitted Measurement Events. Full test suite (48 tests) passing, clean migrate.

---

## v7 — reconciling a second formula reference; 11V9/12V9 are a stepped profile, not a single bevel

Handed a second document — `resharpening-stone-shapes-volume-reference.md` — alongside the same PDF from v6, with an explicit "go think harder" to reconcile them. It disagreed with v6 on two points; one was rejected, the other was real and is now fixed.

**Rejected: its 1V1/11V9/12V9 geometry.** It models these as a wedge whose abrasive band narrows to a knife edge as you move *radially* outward (Pappus's centroid theorem over a trapezoid parametrized by two radii and two band-widths). v6's model — a band of *constant* radial width that shifts position as you move *axially* along the wheel — is a different, incompatible shape: plugging the PDF's own worked numbers into this document's formula gives ~7,262mm³, not the PDF's 14,284.19mm³. Kept v6's model, for three reasons: (1) the PDF's own prose says outright which diameter is "the variable that changes with wear" and which are "ثابت" (constant) — that's a direct statement of the physical model, not something inferred from the numbers; (2) the PDF's parametrization needs exactly the three measurements the legacy sheet already has (diameter, inner diameter, height) plus an angle — this document's needs a different measurement (band width at two separate points) nobody at CNC Leaders currently records; (3) this document repeatedly flags itself as unverified web research ("please confirm this against the physical stones," "worth a sanity check") — the PDF gives a concrete worked example.

**Rejected: its "P2/P1.7/P1.5 are flat rectangular plates" theory.** Also self-flagged as an unconfirmed guess. Contradicted by data already live in the system: these have real circular diameter/inner-diameter values (125mm, 104.9mm — same family as every 1A1) and the annulus formula already matches them closely. They're thin flat wheels, not plates — no change from v3/v6.

**Adopted: 11V9/12V9 are a compound/stepped profile, not a single bevel like 1V1.** This document raised the possibility (a main cone plus a separate chamfer near the bore, each with its own angle); confirmed against the real physical wheels. Neither reference document gives a worked numerical example for this case (the PDF only covers 1V1/45), so unlike the single-segment formula, this one has no external number to verify against — flagged as such everywhere it appears in code and docs.

**Schema change:** `Wheel Type.angle` (a single scalar Float, added in v6) is replaced by `Wheel Type.profile_segments`, a child table (`Wheel Type Profile Segment`: `angle` + `height` per row). `calculate_wheel_volume()` walks the rows in order, chaining each segment's outer/inner diameters from where the previous one ended, and sums a Ring Frustum volume per segment (see v6 for that formula) — one row reproduces the exact v6/1V1 behavior; two rows handle 11V9/12V9. `original_diamond_height` is now read-only and auto-set to the sum of segment heights for profiled shapes (still directly editable for flat shapes, which have no segments). Verified the chaining logic is internally consistent: splitting one segment's total taper into two identical half-segments reproduces the exact same volume as a single segment (same net geometry, two integration steps) — see `test_wheel_type.py::test_stepped_profiled_wheel_sums_two_segments`.

**Also added — a metric this document didn't touch but a fresh re-read of the PDF caught was missing:** "نسبة الخسارة" (loss ratio) — `(Wheel Type.Original Diameter − Measurement Event.Diameter) ÷ 2`, the radial wear in mm. It's one of the PDF's five documented calculation steps and had never been implemented; it's a simple caliper-only cross-check independent of the volume formula, now on Measurement Event as `radial_wear`.

No real Wheel Type has ever used a profiled shape (all 43 are 1A1/P-series flat), so none of this touches live data — purely forward-looking, same as v6.

---

## v6 — volume formula correction (profiled shapes) + current volume auto-computed

§5.2 (below, preserved as history) turned out to be wrong in two ways, caught after being handed an authoritative reference — "معادلات حساب الـVolume في أحجار التجليخ (Grinding Wheels)", a formula sheet the team actually calculates against — plus a closer re-read of `Main data and flow.xlsx`.

**1. Profiled/angled shapes (12V9, 11V9, 1V1) don't use an empirical correction factor — there's an exact formula.** The abrasive band on a profiled wheel is a conical frustum ring, not an annulus scaled by a fudge factor. Its geometry: the band's outer and inner boundaries both taper at the wheel's angle, so each has a "big" (specified/measured) diameter and a "small" one derived from it:

```
D_small = D_big − 2 × Height × tan(Angle)         (applied to both outer and inner diameters —
                                                     assumes a uniform-thickness band, i.e. inner
                                                     and outer boundaries taper in parallel)

Volume = (π × Height / 12) × [(D_out_big² + D_out_big·D_out_small + D_out_small²)
                              − (D_in_big² + D_in_big·D_in_small + D_in_small²)]
```

Exact match to the reference's own worked example (1V1/45 "Gash": D_out_big=100, D_in_big=78.4, Angle=45°, Height=5 → **V = 14,284.19 mm³**, reproduced exactly). The old `default_correction_factor` field (≈0.73, fitted against too little data) is removed — `Wheel Type.angle` is now a required numeric field for profiled shapes and is used directly in the formula, not just encoded informationally in the shape name.

**2. Current/worn volume was wrongly treated as impossible to compute reliably — that conclusion in the original §5.2 was a misread of my own numbers, not a real geometric limit.** Re-running the flat-wheel formula against the real 78-row dataset, but correctly holding inner diameter and height at the Wheel Type's *original* constant values and only substituting the *current* outer-diameter reading (a bore doesn't wear; only the ground face does), 73 of 78 rows match the sheet's own recorded current volume to well under 1% — most exactly. The mean error is dragged to ~13% (matching the old "13% average, up to 220%" finding almost exactly) entirely by 5 rows with bad source data in the sheet itself:
- `SL-D-1A1-125-T4-0086`: recorded current diameter (100mm) is *smaller* than the bore (104.9mm) — physically impossible, a data-entry error.
- Five `...T25...` rows (`SH-D-1A1-125-T25-0158/0036`, `SH-B-1A1-125-T25-0052/0039/0065`): the sheet's own "current height" column shows 25mm (unchanged from original) but its own current-volume figure is only reproducible using height=12mm — an inconsistency inside the sheet's own cells, not a formula mismatch.

These 5 rows' `confirmed_volume` values were already backfilled from the sheet as-is and are left alone (submitted historical records, not silently rewritten) — flagged here as a known data-quality gap in the source file, not an app bug.

**Consequence — reverses the §5.2 design decision:** `Measurement Event.confirmed_volume` is now **auto-computed**, not operator-entered. The `estimated_volume` "reference only" field is removed (there's no longer a separate estimate vs. confirmed value — one formula, used directly). The three caliper readings (diameter, inner diameter, diamond layer height) are still logged every measurement for audit purposes, but only `diameter` actually drives the volume calculation now; inner diameter/height/angle come from the Wheel Type's constant original spec. `wheel_type.py::calculate_annulus_volume()` is renamed `calculate_wheel_volume()` to reflect that it's no longer just an annulus formula.

All 43 real Wheel Types / 78 Wheels / 78 submitted Measurement Events are flat-family (1A1/P-series) — none are profiled, so the Ring Frustum formula is additive/forward-looking for this dataset, not a retroactive change to any existing wear numbers. Full app test suite (46 tests) re-passes; `bench migrate` clean.

---

## v5 — the database columns too

v4 (below) deliberately left the underlying column names (`stone_type`, `stone`, `factory_stone_code`, `custom_stones_used`, `custom_stone_wear_cost`) unrenamed, reasoning that a fieldname is purely an internal key nobody sees. Asked to go further, since fully renamed:

- `frappe.db.rename_column()` (a real `ALTER TABLE ... CHANGE COLUMN`, not add-and-copy) on `tabWheel` (`factory_stone_code`→`factory_wheel_code`, `stone_type`→`wheel_type`), `tabMeasurement Event` (`stone`→`wheel`, `stone_type`→`wheel_type`), and `tabJob Card Wheel` (`stone`→`wheel`, `stone_type`→`wheel_type`) — all 78 real Wheels and 78 Measurement Events preserved exactly, verified row-by-row after.
- Job Card's custom fieldnames, via Frappe's own `rename_fieldname()` API (the same code path the Desk "rename field" UI uses): `custom_stones_used`→`custom_wheels_used`, `custom_stone_wear_cost`→`custom_wheel_wear_cost`, `custom_stone_wear_tab`→`custom_wheel_wear_tab`. (These fields are marked `is_system_generated` since they're created by `create_custom_fields()`, which blocks the rename API as a UI-safety guard against accidental edits — lifted only for this one controlled call, then restored.)
- Every Python/JS reference across the app updated to match in the same pass (`wheel.py`, `measurement_event.py`, `job_card_integration.py`, `stock_entry_hooks.py`, `reorder_alerts.py`, `bulk_import.py`, the Wheel Cost Summary report, `job_card.js`, `test_helpers.py`, all test files) — including one real latent bug caught along the way: `reorder_alerts.py`'s stock-count query was still filtering `Wheel` on `"stone_type"`, which would have silently returned zero rows (and never alerted) the moment the column was renamed, had it not been fixed in the same pass.

No further "internal-only, safe to skip" exceptions remain — this really is Wheel end to end now.

---

## v4 — "Stone" renamed to "Wheel" (display layer)

The whole app was originally built using "Stone" as the domain term (matching "Factory Stone Code" in the legacy data), but the physical objects being tracked are resharpening **wheels**, and that's what the business actually calls them. Renamed at every level a user or developer would see:

- App: `stone_tracker` → `wheel_tracker` (package, folders, `sites/apps.txt`, installed-apps registry — a real Frappe app-folder move, not just a find/replace).
- Doctypes (via `frappe.rename_doc`, so all 78 already-backfilled real records carried over untouched): Stone → **Wheel**, Stone Type → **Wheel Type**, Stone Shape → **Wheel Shape**, Stone Material → **Wheel Material**, Stone Grit/Concentration/Bond → **Wheel** equivalents, Job Card Stone → **Job Card Wheel**, Stone Tracker Settings → **Wheel Tracker Settings**. Module/Workspace: Stone Tracker → **Wheel Tracker**.
- Job Card's custom field *labels*: "Stones Used" → "Wheels Used", "Stone Wear Cost" → "Wheel Wear Cost", "Stone Wear" (tab) → "Wheel Wear".

---

## v3 — findings from `Main data and flow.xlsx` (the file employees actually use)

This is a different file from the one v1/v2 were based on: one sheet ("Sheet1"), one Excel Table ("Table2"), 18 Arabic-labeled columns, 78 data rows, dated Dec 2024–Aug 2026. The good news: its formulas match §5.1 exactly, column-for-column (`*0.9`, `usable_orig - usable_cur`, `consumed / usable_orig`) — that part of the design holds up exactly as built. Three things don't, and change the schema:

1. **A third wheel shape shows up: thin slitting/cutting wheels (`P1.5`, `P1.7`, `P2`).** 7 rows have factory codes like `SH-D-P2-125-T8-0074` and names containing `شرشرة` ("sawing/slitting") — a flat disc, just much thinner (1.7–2.13mm) than a 1A1 flute wheel (4–30mm), described by width (`W`) instead of height. Geometrically it's still a flat annulus, so the *same exact* §5.2 flat formula applies — `(π/4)(D²−d²)×W` — no new formula needed, but it means "Flat (1A1)" was too narrow a label: the real driver is whether a shape needs the profiled correction factor at all, not "is it specifically 1A1." Renamed the concept accordingly (see schema change below) — a **Wheel Geometry** (Flat/Straight vs Profiled/Angled) now carries that flag, and a separate **Stone Shape** master (1A1, P1.5, P1.7, P2, 12V9, 11V9, 1V1, ...) carries the per-shape default correction factor, since the PRD always intended that to be tunable "per shape as more data comes in" — it just wasn't a real doctype yet.
2. **Factory Stone Code's material letter is `B` for CBN, not `C`.** v2's auto-generator assumed `D`/`C`; the real codes use `D` (diamond grit series) / `B` (CBN/borazon grit series) — a standard superabrasives convention, not arbitrary. One row (spec `100972`, factory code `SH-B-1A1-125-T8-0170`) has Material=Diamond with a `B`-series code — likely a data-entry slip in the legacy sheet, flagged here rather than silently trusted. Fixed in code; the letter now comes from the new Stone Material master instead of a hardcoded ternary.
3. **The `SH-`/`SL-` code prefix is unresolved** — roughly even split (43 vs 35 rows), no correlation found with material, shape, warehouse, or date. Left as free text; `SH-` kept as this app's auto-generation default since there's no clear reason to prefer one. **Non-blocking, worth asking the team** what it originally meant, if anyone still knows.

**Data-quality note, not replicated:** the 7 slitting-wheel rows also have blank "usable/current/consumed/%" columns in the legacy sheet itself (formula not dragged down for that batch) and an identical Original Volume (7819.42) copy-pasted across three different widths (2.13/2/1.7mm) rather than recomputed per row. The new module computes these correctly per-row instead of carrying the gap forward — flagging it here so it's not mistaken for an app bug if the backfilled numbers don't match the old sheet exactly for those 7 wheels.

**Dropdown-to-doctype change (requested separately, applied at the same time):** every classification field that's a controlled vocabulary — Material, Wheel Geometry, Stone Shape, Grit, Concentration, Bond — is now a Link to its own master doctype instead of a Select/free-text field, so shop staff can extend the lists from Desk without a code change. Stone's lifecycle `status` (In Stock/In Use/Retired) stays a Select — the app's Python logic branches on those exact three strings, so making it editable would let someone rename/delete a status the code depends on.

---

## Correction from v1

v1 assumed consumption was tracked as simple thickness loss (mm). Having decrypted and read the actual spreadsheet, that's wrong — I want to flag that clearly rather than quietly patch it in.

Your file tracks **diamond/CBN layer volume (mm³)**, not thickness, across two wheel families with different geometry:

- **"WHEELS WITH ANGLES"** (60 wheels) — profiled shapes (`12V9`, `11V9`, `1V1`, etc., encoded in the name/spec string) where the diamond layer's height differs from the wheel's total body height.
- **"FLUTE"** (98 wheels) — flat-face `1A1` wheels used for flute grinding, where the diamond layer height equals the total wheel height (simpler geometry).

Every wheel has a **Factory Stone Code** (e.g. `SH-D-12V9-100-T20-0063`) that uniquely identifies one physical wheel, and a shared **Code** (e.g. `100642`) that identifies the spec/type — multiple physical wheels share the same Code. This maps exactly onto the Stone Type / Stone split from v1 — good, that part holds up.

## 1. Problem Statement

CNC Leaders resharpens saw blades and cutting tools using diamond/CBN grinding wheels. Wheel wear is currently tracked in a spreadsheet via periodic caliper measurements (diameter, inner diameter, diamond-layer height), from which remaining volume and consumption % are calculated. This works as a physical record but has no connection to:

- Which job(s) consumed how much of a wheel's life
- Cost of wheel wear per job/order
- Stock levels or automatic reordering
- A system of record instead of a spreadsheet someone has to remember to update and password-protect

## 2. Goals

1. Every physical wheel tracked from receipt to retirement, with full measurement history.
2. Every resharpening job (Job Card) records which wheel(s) were used and how much volume was consumed.
3. Wheel wear cost calculated and allocated to the Job Card / Work Order.
4. Automatic alerts: a wheel crossing its usable-life threshold (retirement), or a Stone Type's in-stock count dropping below its reorder point.
5. New wheel stock is received through ERPNext's standard **Material Receipt** (Stock Entry) flow, which also creates the tracked Stone records — no separate "add stones" step outside normal stock movements.
6. Fully replace the spreadsheet.

## 3. Non-Goals (v1)

- Not modeling wheel manufacturing — CNC Leaders buys these, doesn't make them.
- Not a generic wear-tracking framework for other consumables — scoped to resharpening wheels specifically (reasonably extensible, not generalized now).
- Not touching non-resharpening Job Card flows.
- No GL/accounting depreciation postings — wear cost is operational/reporting visibility, not a fixed-asset ledger entry (confirm in Open Questions if that's actually wanted).
- **Not computing wheel volume from first-principles geometry in v1** — see the blocking open question in §7. This is the one piece I'm not willing to guess at.

## 4. Domain Concepts

| Term | Meaning |
|---|---|
| **Stone Type** | Spec/master record — shape code (1A1, 12V9, 11V9, 1V1...), material (Diamond/CBN), original dimensions, grit/bond spec, unit cost, linked ERPNext Item, reorder point. |
| **Stone** | One physical wheel of a Stone Type. Own identity (Factory Stone Code), current dimensions, current volume, status, full measurement history. |
| **Measurement Event** | A caliper reading logged against a Stone — diameter, inner diameter, diamond-layer height — at a point in time, optionally linked to the Job Card it followed. |
| **Usable Volume** | Volume after excluding a 10% floor that's never counted as usable (matches your existing sheet's "minus 10%" columns — the last 10% of the diamond layer isn't treated as consumable). |
| **Consumption %** | How much of the *usable* volume has been ground away since new. |

## 5. Volume Formulas

### 5.1 Confirmed derived-column formulas (exact — read from the live Excel formulas in your file)

```
Usable Original Volume = Original Volume × 0.9
Usable Current Volume  = Current Volume × 0.9
Consumed Volume        = Usable Original Volume − Usable Current Volume
Consumption %          = Consumed Volume ÷ Usable Original Volume
                        (this simplifies to (Original Volume − Current Volume) ÷ Original Volume —
                         the 0.9 factor cancels out of the percentage, but still shapes the
                         absolute "Consumed Volume" number, so it's kept explicit below)
```

### 5.2 Volume-from-dimensions formulas (derived by fitting your actual data — not from an external standard, since none was available)

**Superseded by v6 above** — the profiled-shape formula here (empirical 0.73 factor) and the "current volume can't be reliably computed" conclusion were both wrong; kept below only as a historical record of what shipped and why it was revisited.

You didn't have the underlying geometry formula, so I fit one against your own recorded values across all ~158 wheels. Results differ meaningfully by wheel family and by new-vs-worn state — shown honestly below rather than presented as one universal formula.

**Flat wheels (1A1 — FLUTE sheet):**
```
Volume = (π/4) × (Diameter² − Inner Diameter²) × Height
```
Verified against your data: matches **original/new volume** within ~2% on 94 of 98 rows. Four rows (one repeated spec) sit at a consistent ~25% gap — likely a distinct product variant or a spec entry worth double-checking, not a formula problem.

**Profiled wheels (12V9 / 11V9 / 1V1 — WHEELS WITH ANGLES sheet):**
```
Volume ≈ 0.73 × (π/4) × (Diameter² − Inner Diameter²) × Diamond Height
```
The 0.73 is an empirical correction factor (their abrasive band is a taper/bevel, not a straight annulus) fitted against your data — held within ±5% across 12V9, 11V9, and 1V1 for **original/new volume**. Stored as a configurable field per Stone Type, not hardcoded, so it can be tuned per shape as more data comes in.

**Important limit — this does NOT reliably extend to current (worn) volume, for either wheel family.** Running the same formulas against your recorded *current* dimensions instead of original dimensions gives 13% average error and up to 220% on some rows. That's not a tuning problem — a worn wheel's abrasive layer wears irregularly (chipping, uneven grinding), so three caliper readings alone can't reconstruct its true remaining volume. Your existing current-volume numbers likely already include staff judgment beyond pure geometry.

**Design consequence:**
- **New stone volume** (Step 1/2 below): auto-calculated by the module using the formulas above, with a manual override field for exceptions like the 25%-gap spec.
- **Current/worn stone volume** (Step 4 below): the module shows the formula estimate as a reference, but a person enters/confirms the actual value — same as your current process. Auto-computing this from geometry alone would silently feed numbers wrong by up to 2x into cost allocation, which is worse than the manual step it would replace.

**Cost allocation (new — not in your current sheet, since the sheet has no cost data at all today):**

```
Cost per mm³ (usable) = Stone Type Unit Cost ÷ Usable Original Volume
Job Cost              = Incremental Consumed Volume (this job) × Cost per mm³ (usable)
```

Where "Incremental Consumed Volume" = Consumed Volume at this measurement − Consumed Volume at the previous measurement for that Stone. This is a new field your sheet doesn't need (it's a periodic snapshot, not a per-job ledger) but the module does, to allocate cost per job rather than just per measurement.

**Retirement trigger:**
```
Retire the Stone when Usable Current Volume ≤ 0  (i.e. Consumption % ≥ 100%)
```

## 6. End-to-End App Flow

### Step 1 — Set up a Stone Type (one-time, per spec)
**Input:** shape code (1A1 / 12V9 / 11V9 / 1V1), material (Diamond/CBN), original diameter, original inner diameter, original diamond-layer height, angle (if applicable), grit/concentration/bond code, unit cost, linked ERPNext Item, reorder point, reorder qty.
**System calculates:** Original Volume, using the §5.2 formula matching the shape code (exact for 1A1, ×0.73 correction for 12V9/11V9/1V1). Shown as an editable field — override if the manufacturer spec sheet says otherwise.
**Output:** Stone Type record with Original Volume set.

### Step 2 — Receive stock (Material Receipt)
**Input:** A Stock Entry in ERPNext, **Purpose = Material Receipt**, against the Stone Type's linked Item, qty = number of new wheels, target warehouse.
**System action on submit:** creates that many `Stone` records automatically —
- status = In Stock
- current diameter / inner diameter / diamond height = Stone Type's original values
- current volume = original volume (0% consumed)
- source document = this Stock Entry (traceability)
- Factory Stone Code = auto-generated (matching your existing `SH-D-<shape>-<diameter>-T<height>-####` pattern) or entered manually if you want to keep numbering continuous with your current physical stones.
**Output:** N new Stone records, all In Stock.

### Step 3 — Assign a Stone to a job
**Input:** Job Card for a resharpening job; operator selects an In Stock Stone of the right Stone Type.
**System action:** Stone status → In Use, linked to that Job Card.
**Output:** Stone marked as in use on that job.

### Step 4 — Log a measurement (after the job, or at a periodic check)
**Input:** new caliper readings — current diameter, current inner diameter, current diamond-layer height (same three numbers you already record today) — plus the **confirmed current volume** (system shows the §5.2 formula's estimate alongside the input as a reference, but the operator enters/confirms the real value, per the §5.2 reliability limit on worn-volume formulas).
**System calculates, using the formulas in §5.1:**
- Usable Current Volume (from the confirmed Current Volume)
- Consumed Volume (cumulative)
- Consumption %
- Incremental Consumed Volume since the last measurement
- Job Cost for this job (Incremental Consumed Volume × Cost per mm³)
**System action:** updates the Stone's current dimensions/volume, appends this Measurement Event, updates the Job Card's rolled-up "Stone Cost" field, and auto-retires the Stone if Consumption % ≥ 100%.
**Output:** updated Stone record, Measurement Event logged, Job Card cost updated.

### Step 5 — Reorder check (daily scheduled job)
**Input:** none (runs automatically).
**System action:** for each Stone Type, count Stones with status = In Stock. If below reorder point, raise a Notification (+ optional email), deduplicated so it doesn't re-alert every day once already flagged.
**Output:** alert to the configured recipient/role.

### Step 6 — Retirement
**Triggers:** automatic (Consumption % ≥ 100% at Step 4) or manual (user marks a Stone scrapped, e.g. it cracked).
**System action:** status → Retired. Removed from the pool available for job assignment; stays in the system for historical cost/audit reporting.

## 7. Open Questions

- **[Resolved]** Volume formula — derived empirically from your own data, see §5.2. Exact for 1A1, ~±5% for profiled shapes on new-wheel volume. Current/worn volume stays a manually-confirmed field by design, not a formula limitation to fix later.
- **[Worth a spot-check]** Four rows in FLUTE, all the same spec (`1a1-d100-h20-t6-x10-d91 C100-saili`, F=6/G=100/H=79.2), show a consistent ~25% gap between the formula estimate and the recorded original volume (23,419.69 vs. a computed ~17,564.8). Every other spec matches within a couple percent. Worth checking whether that spec's recorded volume is right, since it's an outlier against everything else in the file.
- **[Non-blocking]** Should wear cost post to accounting (GL) at all, or stay reporting-only? Assumed reporting-only (see Non-Goals).
- **[Non-blocking]** Is a Stone reused across multiple jobs until retired (current design assumption), or assigned to one job only?
- **[Non-blocking]** Who receives reorder alerts — a role, specific users, or both?
- **[Non-blocking]** Purchase Receipt (PO-based buying) isn't in scope for v1 per your Material Receipt instruction — confirm that's intentional and wheels are received without a Purchase Order, not that Material Receipt was just the more familiar term.

## 8. Requirements

**Must-Have (P0)**
- [ ] Stone Type + Stone doctypes with status lifecycle (In Stock → In Use → Retired)
- [ ] Original-volume auto-calculation per §5.2 (shape-aware, with the 0.73-style correction factor stored per Stone Type, editable, not hardcoded) plus manual override
- [ ] Material Receipt (Stock Entry) hook → auto-creates Stone records
- [ ] Measurement Event logging: formula estimate shown as reference, confirmed current volume entered by operator, §5.1 formulas applied from there, linked to Job Card
- [ ] Auto-retirement at Consumption % ≥ 100%
- [ ] Cost allocation rollup to Job Card
- [ ] Reorder alert (daily scheduled job)

**Nice-to-Have (P1)**
- [ ] Dashboard: wheels nearing retirement, stock by type, cost-per-job trend
- [ ] Bulk import to backfill your current ~158 tracked wheels from the spreadsheet
- [ ] QR/barcode label per Stone for shop-floor lookup

**Future Considerations (P2)**
- [ ] Same wear-tracking pattern for other consumable tooling
- [ ] Predictive reorder based on consumption rate rather than a static reorder point

## 9. Plan

1. Stone Type + Stone doctypes, status lifecycle
2. Material Receipt → Stone auto-generation hook
3. Measurement Event doctype + formulas + Job Card link
4. Cost allocation rollup
5. Reorder alert scheduled job
6. Backfill tooling for the existing ~158 wheels

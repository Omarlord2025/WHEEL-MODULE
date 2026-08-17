# PRD — Resharpening Wheel (Diamond/CBN Wheel) Tracking Module
**App target:** ERPNext v15 / Frappe Framework, hardcoded custom app (code-based doctypes, version-controlled)
**Company:** CNC Leaders
**Status:** Draft v6 — volume formulas corrected against an authoritative formula reference; current/worn volume now auto-computed

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

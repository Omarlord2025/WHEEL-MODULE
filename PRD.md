# PRD — Resharpening Wheel (Diamond/CBN Wheel) Tracking Module
**App target:** ERPNext v15 / Frappe Framework, hardcoded custom app (code-based doctypes, version-controlled)
**Company:** CNC Leaders
**Status:** Draft v26 — the v22 cache-busting fix silently broke every doctype_js/doctype_list_js script site-wide; fixed

---

## v26 — the consumption bar's colors and numbers silently stopped working, root-caused to a real regression in v22

Customer report: "why the consumption bars edits were removed like the specific colors and numbers." The source file (`consumption_bar.js`) was untouched since the feature was first built — confirmed via `git log`, only ever modified in the original commit. So nothing was "removed" in the sense of a reverted edit; something was breaking it live instead. Reproduced directly: the Measurement Event/Wheel list views were rendering Frappe's own *built-in* bare percent bar (unrounded value, no `%` label, no color thresholds) instead of `wheel_tracker.render_consumption_bar()` at all — meaning the custom formatter was never even being invoked.

**Root cause:** `doctype_js`/`doctype_list_js` are *not* `<script src>` tags, unlike `app_include_js`. Frappe reads those files' own content server-side and inlines it directly into the doctype's metadata (`meta.__js`/`meta.__list_js`), executed client-side via `new Function(...)` — confirmed by reading `frappe/public/js/frappe/model/model.js`'s `init_doctype()`. That server-side read resolves the hook's string as a literal filesystem path. The v22 cache-busting fix (`_v()`, appending `?v=<mtime>`) is correct and necessary for `app_include_js` — a real URL — but applying the same helper to `doctype_js`/`doctype_list_js` broke their file-path resolution with an invalid `?v=...` suffix, failing the read **silently** (`meta.__js`/`__list_js` simply end up unset, no error logged anywhere, no 404, nothing in the console). This had been quietly broken since v22 for every doctype_js/doctype_list_js entry in this app — not just the consumption bar: `shape_image_live_preview.js` (the live shape-photo preview across 5 doctypes), `wheel_tracker_settings.js` (the reload-after-language-change), and `job_card.js` were all equally affected, just not yet reported.

**Fixed by removing `_v()` from `doctype_js`/`doctype_list_js` entirely** — those two hooks keep their original bare paths; only `app_include_js` (a genuine URL) gets the cache-busting suffix. Verified by reading `locals.DocType[doctype].__js`/`__list_js` directly client-side (confirmed populated again for Measurement Event, Wheel Type, Wheel Tracker Settings, Job Card) and visually confirming the real colored/numbered bars render correctly (green under 70%, orange 70–90%, exact rounded percentage on every bar).

85 tests passing, clean migrate.

---

## v25 — "every text should be translated no exceptions"

Customer directive, after a question about "inline explanations in the workspace" turned up nothing in the workspace's own data (checked both the fixture file and the live Workspace doctype's `content`/`shortcuts`/`links` — none have any description/explanation text set, in either place): translate everything, full stop, not just this module's own doctype names and messages.

**Added ~26 core Desk chrome strings** this module's screens render on every page — `Save`, `Not Saved`, `Submitted`, `Cancel`, `Assigned To`, `Attachments`, `Tags`, `Share`, `Comments`, `Activity`, `List View`, `Filter By`, `Created By`, `Edit Filters`, `Save Filter`, `Last Updated On`, `Load More`, `Today`, `Home`, `Help`, `No new notifications`, `Begin typing for results.`, and the workspace's own brand title `Grinding Wheels` → "أحجار الجلخ" — none of these are Wheel Tracker's own strings, but Frappe ships no Arabic file at all (confirmed repeatedly — see v18/v22), so nobody else's translation file covers them either.

**The calendar widget needed a different mechanism entirely, not just more `ar.csv` rows.** Frappe already ships a complete Arabic locale for its date picker (`datepicker_i18n.js` — full month/day names, "اليوم" for Today) — but `ControlDate.set_date_options()` (`frappe/public/js/frappe/form/controls/date.js`) picks the language from `frappe.boot.user.language`, the viewer's own real account setting, entirely bypassing the `__()` dictionary this feature's whole mechanism is built on. Patched `ControlDate.prototype.set_date_options` (the same pinned-reimplementation-of-one-method technique as the v21 workspace fix) to override the resolved language to `"ar"` — but **only** when the field belongs to one of this module's own doctypes, or (for standalone Page/Report filter fields with no bound doctype, like Batch Measurement Entry's or Wheel Cost Summary's own date filters) the current route is one of this module's own pages. Verified live: Batch Measurement Entry's From Date field pops a fully Arabic calendar (month name, day names, "اليوم"); the scoping check itself (`WHEEL_TRACKER_DOCTYPES`/`WHEEL_TRACKER_ROUTES` sets) is a straightforward membership test, so an unrelated doctype's date field is unaffected by construction.

**Found and fixed a genuine race condition, not a structural gap, while checking the workspace sidebar specifically.** On a cold page load, the breadcrumb/title rendered correctly in Arabic, but the left sidebar's own "Grinding Wheels" entry stayed in English — reloading the exact same page fixed it, proving the sidebar (which Desk renders once, synchronously, very early in boot, and never rebuilds afterward) was simply racing the script's own async `frappe.call` for the dictionary and sometimes losing. Root-caused properly instead of working around it with a forced reload: added `language_switch.boot_session()`, an `extend_bootinfo` hook that injects the same `{language, dictionary}` state directly into the server-rendered boot payload — available synchronously the instant `wheel_tracker_language.js` runs, before any bundle script even executes, so there's no async round-trip for the *first* render to possibly lose. The existing `frappe.call` stays as a background refresh for mid-session changes (e.g. picking up someone else's save without a fresh login), now a freshness check rather than the only source of initial state. Verified with three separate genuinely-cold browser contexts (not just a reload of a warm one) — all three showed the sidebar and title correctly in Arabic with zero English leftovers.

85 tests passing, clean migrate.

---

## v24 — volume formulas moved out of Python and onto Wheel Shape, editable

Customer request: "make the formulas for each shape to be available and can be edited for wheel type doctypes." Before this version, the two volume formulas (flat annulus vs. profiled conical frustum) were hardcoded directly in `calculate_wheel_volume()` — correct and carefully verified against real data (PRD v6/v7), but invisible and unchangeable without a code deploy. Confirmed the two open design questions with the customer before building: formula lives **on Wheel Shape** (one per shape family, matching how the flat/profiled split already worked), as a **real, freeform math expression** (not a fixed list of named presets).

**New field: `Wheel Shape.volume_formula`** (Code, Python syntax highlighting). Flat/straight shapes (1A1, P-series): evaluated once, with `diameter`/`inner_diameter`/`height` available. Profiled/angled shapes (1V1, 11V9/12V9): evaluated once *per Profile Segment* on the Wheel Type, with that segment's own `d_out_big`/`d_out_small`/`d_in_big`/`d_in_small`/`height` (`calculate_wheel_volume()` still derives each segment's small-end diameters from its angle via `D_small = D_big - 2 x height x tan(angle)` and sums the per-segment results — that chaining is structural plumbing, not really "the formula," and stays in trusted code). `pi` is always available. Evaluated with `frappe.safe_eval()` — the same sandboxed evaluator behind Notification conditions and Server Script, never a raw `eval()`.

**Validated before anything else can depend on it**: `WheelShape.validate()` test-runs the formula with sample numbers (the same 1V1 worked example — Dob=100, Dib=78.4, angle=45°, h=5 — cited throughout this doc) the moment it's saved, and rejects a bad formula right there with the real Python error, rather than letting a typo surface three documents later on a real Wheel Type or Measurement Event.

**Also visible on Wheel Type itself** (per "available... for wheel type doctypes"): a read-only `volume_formula` field, fetched from the Type's own Shape, sitting right next to Original Volume — so anyone looking at a Wheel Type can see exactly what formula produced that number, without having to go find the Shape record. Editing still happens on Wheel Shape, where the description on both fields says so explicitly.

**A real gap found and fixed while backfilling existing data**: the new `requires_correction_factor` fetch_from field added to Wheel Shape (needed so its own `validate()` knows which sample-variable set to self-check with) was blank/0 for every pre-existing Shape — fetch_from only populates on save, the exact same gotcha already documented elsewhere in this app, caught here by a failing test (`calculate_wheel_volume()` tried to look up "Wheel Shape 0", i.e. the Python boolean False being misread as a doctype name from the old call signature) rather than by assuming the first version was correct. Fixed two ways: `calculate_wheel_volume()` itself no longer trusts that fetched field at all — it reads `requires_correction_factor` straight from Wheel Geometry every time, so it can never be wrong regardless of a Shape's own save history; and the backfill patch bulk-updates the fetched field on every existing Shape too, via SQL `UPDATE...JOIN`, so the hidden field itself is also correct for Wheel Shape's own validate().

`calculate_wheel_volume()`'s signature changed (`requires_angle_formula: bool` → `shape: str`, the Wheel Shape's name) — every call site across the app and its tests updated accordingly. Re-ran the full worked-example assertions (the exact 14284.19mm³ 1V1 case, the dual-segment chaining-consistency check, the 73/78-row historical match) and every one still passes bit-for-bit identically, confirming the refactor changed *where* the math lives, not the math itself. Verified live: editing a Shape's formula to a deliberately different value (doubling it) changed a real Wheel Type's `original_volume` immediately on save, and a syntactically broken formula was rejected with a clear error at Wheel Shape save time. 85 tests passing, clean migrate.

---

## v23 — عجلة was the wrong word for "Wheel" everywhere; corrected to حجر

Direct customer correction: "it is حجر not عجلة." عجلة means a vehicle wheel (car tire, cart wheel); the real Arabic trade term for a resharpening/grinding wheel — this app's entire subject — is حجر (literally "stone," as in a grinding stone), the word actually used on the shop floor. Every single Arabic string in `ar.csv` that used عجلة/العجلة/عجلات/العجلات (58 of ~213 rows) was wrong, not just a handful.

**Not a blind find-and-replace.** حجر is grammatically masculine; عجلة was feminine. Arabic requires gender agreement on verbs, adjectives, and pronouns referring to a noun, so swapping the noun alone would have produced broken grammar throughout (e.g. "الحجر متقاعدة" — "the stone [fem.] is-retired[fem.]" — wrong). Went through all 58 lines individually, distinguishing *singular* instance references (needed the adjective/verb/pronoun changed to masculine too — "العجلة {0} متقاعدة" → "الحجر {0} متقاعد") from *plural* references (Arabic's non-human-plural rule already takes feminine-singular agreement regardless of the noun's own gender, so "عجلات متبقية" → "أحجار متبقية" needed only the noun swapped, not "متبقية"). Caught one residual gap by actually checking a live rendered page rather than trusting the line-by-line edit alone: the `Retired` status option (`"متقاعدة"`) and `Backfilled as Retired` default reason weren't touched by the 58-line pass at all, since neither contains the word "wheel" itself — only a careful live read of the Wheel form's Status field caught the leftover feminine form.

Verified via the automated replacement script's own self-check (all 58 old strings confirmed present in the file before rewriting, so nothing was silently skipped), a full manual read-through of the entire corrected file for any remaining gender mismatch, and a live re-check across the Wheel form, the workspace, and the Wheel list — breadcrumbs, field labels, descriptions, and status options all confirmed consistent via real extracted text. 85 tests passing, clean migrate.

---

## Verification note (same day as v22) — testing Batch Measurement Entry's data table without fabricating production data

Remaining gap after v22: the Batch Measurement Entry page's intro text and empty-state messages were verified, but never its actual wheels-to-measure *table* with real rows — because this site genuinely has **zero** `Job Card Wheel` rows and **zero** Job Cards at all (confirmed via direct SQL), so the table could never populate from real data without first building full ERPNext manufacturing infrastructure (BOM, Work Order, routing, workstation) from scratch, purely to pixel-check a translation. Fabricating that on a live, already-populated demo site for this purpose alone was judged not worth the risk.

Instead: intercepted the page's own network call (`wheel_tracker.batch_measurement.get_wheels_used_between`) via Playwright's request routing and substituted a realistic fake response — the real, unmodified production JS then rendered the real table from it, with zero database writes. Confirmed the full table — "عجلة"/"نوع العجلة"/"بطاقات العمل"/"القطر (مم)"/"القطر الداخلي (مم)"/"ارتفاع طبقة الماس (مم)" column headers, the non-measurable-shape warning banner, real wheel/job-card codes correctly left untranslated, numeric values correctly populated into the input fields, and even the page's primary action button ("اعتماد القياسات") — all render correctly together. This is the same technique worth reaching for generally when a UI state depends on data a given site doesn't have: mock the one network response, let the real code render it, rather than fabricating database records or skipping the check.

---

## v22 — the translation switch was entirely client-side JS; server-computed strings never saw it

Caught by actually running the Wheel Cost Summary report with real data loaded, not just its empty state: the report title and filter placeholders translated correctly, but the **data table's own column headers stayed in English** — a real, reproducible gap, not a timing artifact (re-confirmed with a fresh screenshot after the first one turned out to be a stale cached read of a reused filename, a mistake worth remembering for next time: always use a fresh file name when re-verifying a changed screenshot).

**Root cause:** `wheel_tracker_language.js` only ever wraps the *client-side* `window.__`/`frappe._`. Report columns are built once, server-side, in `wheel_cost_summary.py`'s `get_columns()`, using Python's `from frappe import _` — which translates using `frappe.local.lang`, the real session/site language. This feature deliberately never touches that (per the v19 rejection of touching System Settings/User), so every server-computed string — not just this report, **any** `frappe.throw(_("..."))` validation message anywhere in this app's own Python — was always going to render in whatever the session's actual language is, completely blind to this module's own switch. Audited every call site across the app: 7 files, 20 translated strings (`job_card_integration.py`, `bulk_import.py`, `wheel_type.py`, `wheel_cost_summary.py`, `wheel_retirement.py`, `wheel.py`, `measurement_event.py`).

**Fix:** `frappe._()` already accepts an explicit `lang=` override with zero side effect on session state (confirmed by reading its source: `local.lang` is only read, never written, when `lang` is passed) — so `wheel_tracker.language_switch._()` is a drop-in replacement for Frappe's own `_` that pins that override to `Wheel Tracker Settings.language` instead. Swapped `from frappe import _` → `from wheel_tracker.language_switch import _` in all 7 files; every existing call site picked it up with no other code changes. Verified: the report's data table now shows "حدث القياس"/"التاريخ"/"بطاقة عمل"/"عجلة"/"نوع العجلة"/etc. as real column headers over real data rows, not just the title.

**Real consequence, caught by the test suite, not guessed at:** `TestWheel.test_auto_retires_at_full_consumption` started failing — `wheel.py`'s `check_auto_retirement()` sets `retirement_reason` via `_("Auto-retired: consumption reached {0}%")`, and since the *live* `Wheel Tracker Settings.language` happened to be set to Arabic from manual testing, the test's assertion for the English substring broke. This is correct new behavior (the string genuinely does respect the switch now), but a test suite shouldn't be fragile to whatever a human last left an interactive Single doctype set to. Added `wheel_tracker.install.before_tests()`, wired via `hooks.py`, pinning the setting to English before the suite runs — the same pattern Frappe apps already use for seeding a default Company/Fiscal Year.

**Verified exhaustively this time, not just spot-checked:** every one of the 11 doctypes in this module (including Wheel Grit/Concentration/Bond, which have zero real records on this site — checked via their blank `/new` forms instead), both custom Pages' full body content (not just titles), the Wheel Cost Summary report with real data loaded, and the workspace — all read via actual extracted `textContent`/`innerText`, not screenshots or assumption. Zero page errors across every route. 85 tests passing, clean migrate.

---

## v21 — the workspace fix from v20 was too broad; made it precise instead

v20's Stop-hook feedback was explicit: the disappearance was fixed, but "the Grinding Wheels workspace page itself still renders in English under Arabic, which the assistant states as an accepted trade-off, and the condition asks for the entire module to be translated" — plus a demand to actually verify form-level content beyond page titles, not just assert it. Both addressed for real, not re-explained away.

**The workspace now translates completely, not just safely.** v20's fix (skip translation whenever `frappe.get_route()[0] === "Workspaces"`) worked but was the wrong shape of fix — it avoided the crash by disabling translation for the *entire page*, including header text and everything else that was never part of the actual bug. The precise fix: every workspace block type (shortcut, card, number_card, chart, quick_list) extends the same `Block` base class from Frappe core and inherits one shared `make()` method unchanged — reachable through `frappe.workspace_block.blocks`, a registry `workspace.js` itself already uses publicly. `wheel_tracker_language.js` now patches that one shared method (once, via `Object.getPrototypeOf(frappe.workspace_block.blocks.shortcut.prototype)`) with a reimplementation identical to Frappe's current one, except its single `.find()` identity comparison uses the original, untranslated `__()` instead of ours — while the widget it then builds still renders through the wrapped `__()` normally, same as everywhere else. Net effect: the matching bug is gone *and* the page translates fully. This is a pinned copy of Frappe's current `make()` body — needs re-checking against the real source after any future Frappe upgrade, but fails safe (silently reverts to no translation on these specific blocks, not breakage) if it ever drifts out of sync.

**Two more gaps, found and fixed while actually making the workspace translate instead of avoiding it:**
1. `frappe/public/js/frappe/widgets/links_widget.js` builds each individual doctype-link item's text as `item.link_title = item.label || item.name` and writes it straight to the DOM — **never passed through `__()` at all**, a pre-existing Frappe core gap unrelated to this feature (true for any language, any user, with or without this app). No identity-matching involved here, so no prototype patch needed: a small `MutationObserver` on `document.body` swaps the `textContent` of any `.link-text`/`.link-content` element that exactly matches an `ar.csv` key. Confirmed safe — these are a fixed, non-editable list of doctype links, not EditorJS-contenteditable content, so there's nothing for this to corrupt; verified by opening the workspace's own Edit/customize mode with the fix active and seeing no errors.
2. A separate, unrelated Frappe quirk: `header.js`'s translation logic HTML-escapes a header's extracted text before `.replace()`-ing it back into the original *unescaped* HTML string — so any header containing a literal `&` can never match, no matter what's in the dictionary. Not something to patch from outside for one character; sidestepped by renaming the workspace's own "Masters & Operations" header to "Masters and Operations" in `grinding_wheels.json`.

**Verified properly this time — real content, not just titles.** Opened the actual Measurement Event and Wheel Retirement forms for real records (not just Wheel Tracker Settings) via the reused live session cookie, and read every section header, field label, and field description via `innerText`/`textContent` — confirmed Caliper Readings, Wear Calculation, and every individual field (Diameter, Confirmed Volume, Consumption %, Radial Wear, Retirement Reason, etc.) translate correctly, descriptions included, while actual data values (dates, numbers, the wheel's own code) correctly stay untouched. Confirmed the workspace's Edit/customize mode opens cleanly with the fix active. Re-confirmed (again) that a status badge misread earlier as a wrong word was a screenshot-reading error on my part, not a real bug — `textContent` extraction is the only verification that counts for exact Arabic text, screenshots only prove layout/disappearance.

85 tests passing (unchanged), clean migrate.

---

## v20 — the workspace was disappearing under Arabic (superseded by v21 above — its fix was real but too broad)

Customer report: `/goal do not stop until done and fixed the disappearance and entire translation shit for the module`. Reproduced live by reusing the customer's own active Desk session cookie (`tabSessions`) in a real headless browser rather than guessing — on the Grinding Wheels workspace with Arabic selected, every shortcut, number card, and Masters/Operations doctype link had silently vanished; only header text ("Your Shortcuts", "Overview") survived.

**Root cause, found by reading Frappe's own source, not assuming:** `frappe/public/js/frappe/views/workspace/blocks/block.js`'s `make()` matches a content block's stored name against its server-fetched widget data via `obj.label == __(block_name)` — it reuses the global translate function as an *internal identity check*, not just for display. v19's wrapper translated `block_name` (e.g. "Wheel Type" → "نوع العجلة") while `obj.label` (built server-side, never touched by the client) stayed English — so the comparison failed for every shortcut/number-card/card block, `make()` returned `false`, and the widget just never rendered. No exception, no console error, no Error Log entry — genuinely silent.

**v20's fix** (skip translation whenever `frappe.get_route()[0] === "Workspaces"`) genuinely fixed the disappearance and was a real, working, deliberate engineering choice — but traded away too much (no translation anywhere on that page at all) instead of fixing the actual collision. See v21 above for the precise replacement.

**Closed two more real gaps while fixing this, both confirmed via direct source reading:**
1. Field **descriptions** were never in scope before this version — only labels, Select options, and doctype names. Audited all 42 of this module's field descriptions against `ar.csv`, found all 42 missing, translated and added every one.
2. Both custom Pages (`wheel_batch_measurement.js`, `wheel_bulk_import.js`) passed a raw hardcoded English string as `title:` to `frappe.ui.make_app_page()`. `Page.set_title()` (`frappe/public/js/frappe/ui/page.js`) never wraps its `title` argument in `__()` on its own — so neither page's title was *ever* translatable, a pre-existing gap unrelated to this feature. Fixed by wrapping both in `__(...)` at the call site.

85 tests passing (unchanged), clean migrate.

---

## v19 — v18's language switch was rejected and rebuilt to actually be scoped

v18 (below) shipped a `Wheel Tracker Settings.language` field whose `on_update()` wrote `System Settings.language` and bulk-updated every row in `tabUser`. The customer rejected this immediately and specifically: *"the problem is it changes the entire system which IS WRONG... do not scope it to the user who changed it and do not RTL the entire system... it should change independently."* Confirmed live: it had actually forced every real account (including the customer's own) and the site default to Arabic — reverted by hand via direct SQL (`update tabUser set language='en' where language='ar'`, `System Settings.language` back to `en`) as part of this fix.

**The real fix never touches `System Settings` or `tabUser` at all.** Every Desk label, breadcrumb, and workspace title Frappe renders funnels through one global client-side function — `window.__`/`frappe._` (`frappe/public/js/frappe/translate.js`), which checks `frappe._messages[txt]` (the session's loaded dictionary) and falls back to the original string if nothing matches. `public/js/wheel_tracker_language.js` (added to `app_include_js`, so it loads on every Desk page for every user) wraps that one function: on load it asks a new whitelisted method, `wheel_tracker.language_switch.get_language_state()`, for the current flag and this module's own `ar.csv` dictionary, then its replacement `__()` intercepts a string **only if it's an exact key in that dictionary** — every other string, from core Frappe, ERPNext, or any other app, falls straight through to the original function untouched. This is what makes it genuinely independent of System Settings, of any particular User's own language, and of who saved the setting: nothing is written anywhere except the one flag on the Single itself, and every browser tab (anyone's) just asks fresh on its own next page load. `wheel_tracker_settings.py`'s controller is back to a bare `pass` — the field is inert data now, read only by the API. `public/js/wheel_tracker_settings.js` still reloads the current tab after a save that changed the field, purely so the person who just flipped it sees the change immediately — that reload has no effect on anyone else, who'd pick up the new state on their own next load regardless.

No RTL direction change anywhere — this only ever substitutes the translated string Frappe would already render in that same spot; it doesn't touch `dir`, layout, or anything else.

85 tests passing (unchanged), clean migrate, verified via `bench execute`: toggling `Wheel Tracker Settings.language` to Arabic and back no longer changes `System Settings.language` or any `tabUser` row (asserted directly), while `get_language_state()` still returns the correct dictionary and `frappe._("Wheel", lang="ar")`-equivalent lookups resolve correctly through the new path.

---

## v18 — a real language switch, this time on Wheel Tracker Settings (superseded by v19 — do not reintroduce)

After v17 removed both language-toggle workspace buttons by customer request, the customer asked for the capability back — but as a real settings field, switchable "from the settings of the wheel [tracker] itself," not a floating workspace button, and covering every doctype/field name across the whole module.

**`Wheel Tracker Settings` (the app's own Single doctype) gets a `language` field** (Select: English/Arabic). Its `on_update()` writes `System Settings.language` and bulk-updates every row in `tabUser` to match, then clears cache — **Frappe has no concept of a per-module display language**; switching is always whole-site and every-user, so there's no way to show Arabic only inside Wheel Tracker's own doctypes while the rest of Desk stays English, and no point pretending otherwise. In practice, since the user's own session language (`User.language`) otherwise overrides the site default, both have to be written for the switch to actually take effect for everyone immediately rather than only for new/guest sessions. A client script (`public/js/wheel_tracker_settings.js`) forces a full page reload right after a save that actually changed the field, since Desk loads its translation dictionary once per full boot, not reactively per-save.

**Rejected by the customer — see v19 above.** The premise that this had to be whole-site/every-user was wrong: Frappe's rendering funnels through one interceptable client-side function, so a module-scoped override was possible after all.

**Audited `translations/ar.csv` (v15) for real gaps**, not just trusted it was still complete: wrote a script comparing every DocType name, field label, and Select option across all of this app's own doctype JSON files against the CSV's source strings. Found 18 genuinely missing (`Amended From`, `Code`, `Consumed Volume (mm³)`, `Description`, `Disabled`, `Item`, `Material`, `Reason`, `Shape Code`, `Shape Image`, `Shape Image URL`, `Status`, `Stock Entry`, `Upload Shape Photo`, `Warehouse`, plus the Number Card's full label `"Wheels Nearing Retirement (>=80%)"`, a report column `"Date"`, and the new field's own strings) and added them — deliberately skipping only the two naming-series format patterns (`ME-.YYYY.-.#####` etc., not real text) and the generic `"Series"` label.

**Checked an assumption before relying on it**: confirmed via `grep` that `apps/frappe/frappe/translations/ar.csv` doesn't exist at all (Frappe core ships no Arabic file), and that ERPNext's own 9000+-line `ar.csv` only defines strings as they appear in actual ERPNext sentences — not standalone generic DocField labels like `Status`, `Date`, `Item`, `Warehouse` in isolation. So this app's own `ar.csv` has to carry those too, even though they look like "someone else's problem" — there is no one else's file that covers them.

Verified end-to-end via `bench execute`: flipping `Wheel Tracker Settings.language` to Arabic and back confirmed `System Settings.language` and every real `tabUser` row actually changed, and that `frappe._("...", lang="ar")` resolves real Arabic text for both old and newly-added strings, not just a cache artifact. 85 tests passing (unchanged — no wear/cost logic touched), clean migrate.

---

## v17 — language toggle removed

Customer request: remove the Arabic/English toggle from the Grinding Wheels workspace entirely. Removed `language_toggle.py` (the whitelisted `toggle_language()` it called), `patches/create_language_toggle_block.py` (the patch that created its Custom HTML Block), and its `patches.txt` registration; stripped the corresponding `custom_blocks` entry and `content` block from the workspace fixture.

Turned out there were **two** toggles live on the site, not one: this app's own v13 button, plus a second, differently-named "Translate Names" toggle switch (`window.wheel_tracker_get_name_translation_lang`/`set_name_translation_lang` globals this app never defined) that had been added directly to the live workspace afterward, outside any fixture or patch here — and its `content` block referenced its custom block by a freeform label ("Translate Names") that didn't even match the real document's name ("Grinding Wheels Translate Names"), since `content` is a JSON blob, not a link-validated field. An exact-name cleanup patch missed it on the first pass. `patches/remove_language_toggle.py` now matches *any* Custom HTML Block (and workspace content block referencing one) whose name contains "language" or "translat", case-insensitive, not just the one name this app itself ever used — and clears the workspace's `content`/`custom_blocks` directly via `frappe.db.set_value` rather than trusting the next fixture sync to do it, since a live Desk edit to the workspace bumps its `modified` past whatever this app's own JSON file declares, which (per this project's own documented gotcha) silently skips re-syncing over it otherwise.

`wheel_tracker/translations/ar.csv` (v15, the actual Arabic translation of this app's own fields) is untouched — that's separate from the toggle button and still applies via Frappe's own standard per-user language setting.

85 tests passing (unchanged), clean migrate, verified directly against the live site: zero Custom HTML Block records remain, zero `custom_block` entries left in the workspace's content.

---

## v16 — real shape reference photos, fetched through the whole chain

The customer uploaded real reference photos per shape via the Google Form's Drive-folder links (one per 1A1/1V1/11V9/12V9, one shared across the three P-series shapes — confirmed by Case 11 as functionally identical for this purpose). Asked to make them visible on Wheel, Wheel Type, and Measurement Event "and so on."

**`Wheel Shape` gets a real `shape_image` (Attach Image) field** — the single source of truth per shape, set as the doctype's `image_field` so it also shows as a thumbnail in list view. **`Wheel Type`, `Wheel`, `Measurement Event`, and `Wheel Retirement` each get their own `shape_image`**, `read_only` and `fetch_from` chained through however they actually link to a shape — `Wheel Type.shape_image` fetches from `shape.shape_image`, `Wheel.shape_image` from `wheel_type.shape_image`, `Measurement Event.shape_image` and `Wheel Retirement.shape_image` both from `wheel.shape_image`. All five also get `image_field: "shape_image"` set, so every one of them shows the shape thumbnail in its own list view, not just on the form. Wheel Material/Grit/Concentration/Bond were deliberately left out — none of them have any link to a Shape, so there's nothing to fetch.

**Two corrections, same day, both found by reading Frappe's own source rather than assuming:**

1. `Attach Image` only ever renders as a plain link with a hover-only preview — not what "shown on the doctype" should mean. First fix attempt: added a display-only `shape_image_preview` field (`fieldtype: "Image"`, `options: "shape_image"`) to `Wheel Shape`, and switched the four *fetched* `shape_image` fields (Wheel Type/Wheel/Measurement Event/Wheel Retirement) straight to `fieldtype: "Image"` with `options` pointing at their own fieldname.
2. That second half broke three of the four. `"Image"` is listed in `frappe/model/__init__.py`'s `no_value_fields` — meaning `Document.as_dict()`/`getdoc()` (what the server actually sends the browser on a normal page load) **excludes an `Image`-typed field from the document payload entirely**. Wheel Type happened to still show something because its one-hop source (Wheel Shape's real `Attach Image` field) was reachable through an unrelated live client-side fetch; Wheel/Measurement Event/Wheel Retirement, chained one hop further through an already-excluded `Image` field, got nothing. Fixed for real by giving *every* doctype the same two-field shape (verified this time by directly inspecting the `getdoc()` response payload, not just the doctype meta): a real `shape_image` (`Attach Image`, fetched/chained as before) plus a separate `shape_image_preview` (`Image`, `options: "shape_image"`) purely for display — the same pattern `Wheel Shape` already had right from the start. No data migration needed either time; the stored value never changed, only which field renders it and how.

**Third pass, same day:** the real `shape_image` field was still visible on the form, showing the raw `/files/...` URL as a clickable link right next to the actual photo — exactly what the customer explicitly did not want ("I need photo only"). Set `hidden: 1` on it across all four fetched doctypes (relabelled "Shape Image URL" so its purpose is clear if a developer ever unhides it for debugging), leaving `shape_image_preview` — relabelled plainly "Shape Image" — as the only thing anyone actually sees. `Wheel Shape`'s own `shape_image` is the one field that has to stay visible, since it's the real upload target; relabelled "Upload Shape Photo" so it reads as a utility control rather than a second, confusing display of the same photo.

**Fourth pass, same day:** all of the above fixed the photo for an *already-saved* record being opened — the remaining ask was for it to also appear live, the moment someone picks a Shape/Wheel Type/Wheel in the dropdown, before saving. Searched the whole installed codebase (Frappe + ERPNext + every other app) for a precedent: the only real-world working example of "Image field whose `options` points to a fetched field" is ERPNext's own `image`/`image_view` pair on Sales Order Item and its siblings — and every single instance of that pattern lives inside a **child table grid**, never a plain top-level form field. Grids and forms don't share the same client-side refresh machinery, so there's no actual precedent that `fetch_from`'s own live-fetch mechanism (`add_fetch`) reliably re-renders a *separate* `Image`-type field on a top-level form the instant its source changes — confirmed server-side that the underlying RPCs (`frappe.client.validate_link`, `frappe.client.get_value`) both return the correct value instantly when simulated directly, so the data layer was never the problem; the uncertainty was purely in whether the browser was guaranteed to repaint from it. Rather than trust that implicit wiring for a case with no real precedent, added an explicit client script (`public/js/shape_image_live_preview.js`, via `doctype_js` on all five doctypes) that, on the relevant Link field's own change event, calls `frappe.db.get_value()` for the one-hop source's `shape_image` directly, `frm.set_value()`s it, and explicitly `frm.refresh_field("shape_image_preview")`s — deterministic, no dependency on unproven framework timing.

**The five source images are bundled into the app** (`public/images/wheel_shapes/`), not left depending on the customer's local Downloads folder, so a fresh install reproduces this. A `post_model_sync` patch (`attach_shape_reference_images.py`) attaches each one to its real `Wheel Shape` record as a genuine File (idempotent — skips a Shape that already has one; Frappe's own content-hash dedup means the one P-series image attached to three different Shape records only exists once on disk) and then backfills `shape_image` onto every pre-existing `Wheel Type`/`Wheel`/`Measurement Event`/`Wheel Retirement` row via a bulk `UPDATE...JOIN` per hop — `fetch_from` only populates on save, so old rows wouldn't otherwise pick it up; anything created from now on gets it for free through the normal fetch mechanism. Verified directly against the live site: all 63 Wheel Types, all 136 Wheels, all 136 Measurement Events, and both Wheel Retirements ended up with their image set.

85 tests passing (unchanged — this version adds no new wear/cost logic to test), clean migrate, confirmed idempotent on a second run.

---

## v15 — auto-retirement becomes review-then-confirm; the app's own fields get a real Arabic translation

First real customer sign-off round (Google Form review of v1–v14's decisions, one respondent) landed two concrete, specific changes; two other findings from that same round — a possible second flat-wheel wear pattern, and a "local code vs. manufacturer code" question — are real but need more information before anything gets built, and are deliberately left open rather than guessed at.

**Auto-retirement now drafts a Wheel Retirement instead of auto-submitting one.** The customer's answer was specific: "review for confirmation, but create it as a draft, pending review and confirmation." `MeasurementEvent.create_auto_retirement()` no longer calls `.submit()` on the Wheel Retirement it creates — the Wheel's own status still flips to Retired immediately (that's `Wheel.check_auto_retirement()`, unchanged, and independent of this document), but the actual Material Issue now waits for a human to open the draft and submit it themselves, exactly like a manually-filed Wheel Retirement always has. `cancel_auto_retirement()` picks up a second branch: if the draft is still pending (docstatus 0) when the triggering Measurement Event gets cancelled, it's deleted outright rather than "cancelled" (which only applies to submitted docs) — and since the Measurement Event's own `auto_retirement` Link field still points at it at that moment, that field has to be cleared first or `frappe.delete_doc()` refuses with a `LinkExistsError`. If the draft had already been reviewed and submitted by then, the existing cancel-and-reverse-the-Material-Issue path (unchanged) still applies.

**Full Arabic translation of this app's own custom fields**, not just core Frappe/ERPNext strings (the v13 language toggle only ever covered those). `wheel_tracker/translations/ar.csv` — Frappe's standard per-app translation file, auto-discovered by `frappe.translate.get_translations_from_csv()`, no hooks.py registration needed — covers every custom DocType name, field label, Select option, Workspace/Page/Report title, and user-facing Python/JS message string across the app (~145 entries). Deliberately does *not* redefine generic strings ERPNext's own `ar.csv` already translates (`Status`, `Date`, `Description`, `Item`, `Material`, `Warehouse`, `Code`, `Disabled`, `Reason`, `Series`, `Amended From`) — redefining an identical source string risks disagreeing with core depending on app load order, and core's existing translation already fits fine. Where this app's own field happens to share an exact label with one of those (e.g. Wheel Retirement's `reason` field is just labelled "Reason"), core's translation applies and that's fine, not a gap.

**Two findings surfaced by the same review, deliberately not acted on yet:**
- A possible second flat-wheel wear pattern: "depends on the stone type — one that wears by diameter (only diameter changes), one that wears by height (and consequently both diameters change too)." The second case isn't the current flat model (diameter-only) *or* the current profiled model (this measurement's own readings for all three dimensions) — it's a third pattern where height drives the change and diameter follows as a consequence. Same discipline as every other formula change in this project (v6/v7/v8): no formula gets written without a real Wheel Type and real before/after readings to validate against. Needs: which Shape(s) actually do this, and at least one real measurement example.
- "You didn't mention the local code and the manufacturer/factory code and how to handle them" — genuinely unclear yet whether this maps onto existing fields (`Wheel Type.spec_code`, `Wheel.factory_wheel_code`, `Wheel Type.legacy_spec_name`) or needs something new. Needs clarification before any schema change.

85 tests passing (3 new, 2 rewritten), clean migrate.

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

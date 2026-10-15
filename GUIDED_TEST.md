# Wheel Tracker — Guided Test

A step-by-step walkthrough to verify the whole app works, end to end, on a real site.
Check each box as you go. If a step doesn't match its expected result, stop and note
exactly what you saw instead — that's a real bug report, not a guess.

Each section is independent where possible, but Sections 2–9 build on each other in
order (you're following one wheel's life from arrival to retirement), and Sections 10
and 11 check the accounting trail those same actions should have left behind — do them
right after Section 9, not later. You can skip Section 1 if master data already
exists, and Sections 12–17 can be done in any order once Section 1 is done.

Where to find everything: Desk → **Grinding Wheels** workspace.

---

## 0. Before You Start

- [ ] You can log in to Desk and see the **Grinding Wheels** workspace in the left
      sidebar, with four sections: Your Shortcuts, Overview, Masters & Operations.
- [ ] The four "Overview" number cards (Wheels In Stock / In Use / Nearing Retirement /
      Types Below Reorder Point) show real numbers, not blank or "Error".
- [ ] You have (or can create) a System Manager or Stock Manager account — several
      steps below need write access to master data.

---

## 1. Master Data (skip if it already exists)

Each of these is its own doctype under **Masters** / **Classification** on the
workspace. You only need one of each to run the rest of this test.

- [ ] **Wheel Geometry**: open or create one named `Flat / Straight` with **Requires
      Correction Factor** unchecked, and one named `Profiled / Angled` with it checked.
- [ ] **Wheel Shape**: open an existing flat shape (e.g. `1A1`) and a profiled one
      (e.g. `1V1`). Confirm each has:
  - [ ] A **Wheel Geometry** link set (flat → `Flat / Straight`, profiled → `Profiled / Angled`).
  - [ ] A **Volume Formula** field with real Python text in it (not blank) — see
        Section 14 for what this does and how to test editing it.
  - [ ] A reference photo showing under **Shape Image** (not a raw link/URL).
- [ ] **Wheel Material**, **Wheel Grit**, **Wheel Concentration**, **Wheel Bond**: at
      least one record each exists (these feed the Spec Codes section of Wheel Type).

---

## 2. Create a Wheel Type

Wheel Types are normally auto-created from an ERPNext Item Variant, but creating one
directly also exercises the same validation and formula logic.

- [ ] Open **Wheel Type** → New.
- [ ] Set **Shape** to a *flat* shape (e.g. `1A1`), a **Material**, an **Item** (any
      stock Item, or let it create one), **Original Diameter** = `100`, **Original
      Inner Diameter** = `60`, **Original Diamond Layer Height** = `6`, **Unit Cost** =
      `900`.
- [ ] Save. Expected:
  - [ ] **Original Volume** auto-fills to a real number (~`30159.29` mm³ for these
        exact numbers — the annulus formula, (π/4)×(100²−60²)×6).
  - [ ] **Usable Original Volume** and **Cost per mm³** also auto-fill (non-zero).
  - [ ] **Volume Formula** shows the same read-only formula text as the Shape's own,
        right next to Original Volume.
- [ ] Repeat with a **profiled** shape (e.g. `1V1`): set **Original Diameter** = `100`,
      **Original Inner Diameter** = `78.4`, add one **Profile Segment** row with
      **Angle** = `45`, **Height** = `5`. Save. Expected:
  - [ ] **Original Diamond Layer Height** auto-fills to `5` (sum of segment heights).
  - [ ] **Original Volume** comes out to ~`14284.19` mm³ — this is a known worked
        example; if it's off, something is genuinely wrong with the formula.
- [ ] Try saving a profiled Wheel Type with **Original Inner Diameter** ≥ **Original
      Diameter**, or with Angle/Height left at 0 in a Profile Segment. Expected: a
      clear validation error, not a silent save or a server error page.

---

## 3. Receive Wheels Into Stock

- [ ] Go to **Stock Entry** (core ERPNext) → New → **Purpose: Material Receipt**.
- [ ] Add the Item linked to your Wheel Type from Section 2, **Qty = 3**, a real
      Warehouse. Submit.
- [ ] Go back to **Wheel** list, filtered by that Wheel Type. Expected:
  - [ ] Exactly 3 new **Wheel** records exist, each with a real **Factory Wheel Code**
        auto-generated (not blank).
  - [ ] Each one's **Status** = `In Stock`.
  - [ ] Each has a **Source Stock Entry** pointing back to the Material Receipt you
        just submitted.

---

## 4. Put a Wheel on a Job

This needs a real Job Card — if your site has no manufacturing data set up yet
(no Work Orders), this step needs a Work Order created first (core ERPNext,
Manufacturing module); skip this whole section if that's out of scope for your test
and note it as skipped, not failed.

- [ ] Open a Job Card (new or existing, docstatus doesn't matter for this test).
- [ ] Under **Wheels Used**, add one of your 3 new Wheels.
- [ ] Save. Expected:
  - [ ] That Wheel's own **Status** flips to `In Use` and **Current Job Card** shows
        this Job Card — check the Wheel record directly, don't just trust the Job Card
        side.
  - [ ] Trying to add the *same* Wheel to a *different* Job Card now fails with a
        clear "already In Use" error.
- [ ] Remove the Wheel from **Wheels Used** and save again. Expected: the Wheel's
      **Status** goes back to `In Stock`, **Current Job Card** clears.
- [ ] Re-add it (you'll need it In Use again for Section 5).

---

## 5. Log Wear — One Wheel at a Time

- [ ] Open **Measurement Event** → New. Pick the In-Use Wheel from Section 4.
- [ ] Enter a **Diameter** reading slightly smaller than the Wheel Type's Original
      Diameter (e.g. `95` if original was `100`).
- [ ] Submit. Expected:
  - [ ] **Confirmed Volume**, **Consumed Volume**, **Consumption %**, **Job Cost** all
        auto-compute (none blank or zero unless the math genuinely says zero).
  - [ ] **Job Cards** table shows the Job Card from Section 4, with its full
        **Allocated Cost** (100%, since only one Job Card is involved yet).
  - [ ] Open that Job Card: its own **Wheel Wear Cost** field reflects this same cost.
- [ ] Cancel the Measurement Event. Expected: the Wheel's dimensions/status revert to
      what they were before (check the Wheel record), and the Job Card's wear cost
      goes back to its prior value (likely 0).
- [ ] Re-submit it (you'll need it for later sections).

---

## 6. Log Wear — Several Wheels at Once

- [ ] Go to the **Batch Measurement Entry** page (under Operations on the workspace).
- [ ] Set **From Date** to a date before your Job Card's posting date, **To Date** to
      today.
- [ ] Expected: every Wheel used on a Job Card in that window appears in a table, each
      row pre-filled with its current readings, column headers Wheel / Wheel Type /
      Job Cards / Diameter / Inner Diameter / Diamond Layer Height.
- [ ] Edit one row's Diameter to a smaller value, click **Submit Measurements**.
      Expected:
  - [ ] A success summary shows the count of Measurement Events created.
  - [ ] A real, submitted Measurement Event now exists for that Wheel (check the
        Measurement Event list) — same wear/cost math as Section 5, not a different
        shortcut path.
  - [ ] Reloading the same date range no longer lists that Wheel (already measured
        since From Date).
- [ ] If any Wheel in range belongs to a Wheel Type with **Requires Measurement**
      unchecked (a P-series-style shape), confirm it's listed separately with a
      "use Wheel Retirement instead" message, not mixed into the measurable table.

---

## 7. Wear Split Across More Than One Job Card

- [ ] Take one In-Stock Wheel. Assign it to Job Card A (see Section 4), then remove it
      (back to In Stock), then assign it to a *different* Job Card B.
- [ ] Submit one Measurement Event against it with a real diameter change.
- [ ] Expected: the **Job Cards** table on that Measurement Event shows *both* Job
      Card A and Job Card B, each with **half** the total Job Cost (equal split) — not
      just the most recent one.

---

## 8. Auto-Retirement at 100% Consumption

- [ ] Take any In-Use Wheel (any Shape is fine) and submit a Measurement Event with
      **Diameter** set equal to the Wheel Type's **Original Inner Diameter** (i.e.
      fully worn — Consumption % should land at/near 100%).
- [ ] Expected immediately on submit:
  - [ ] The Wheel's own **Status** flips to `Retired` right away.
  - [ ] The Measurement Event's **Auto-Created Wheel Retirement** field now links to a
        real Wheel Retirement record.
  - [ ] Open that Wheel Retirement: it exists as a **draft** (docstatus 0, not yet
        submitted) — the Wheel is already Retired, but nothing has left the stock
        ledger yet. This is deliberate, not a bug.
- [ ] Submit that draft Wheel Retirement. Expected: a real, submitted **Material
      Issue** Stock Entry now exists, linked via its **Stock Entry** field, and the
      Wheel's Bin quantity in its Warehouse drops by 1.
- [ ] Cancel the Measurement Event that triggered all this. Expected: the Wheel
      Retirement (now submitted) gets cancelled too, its Material Issue reverses, and
      the Wheel goes back to `In Use` (or whatever it was before) with its prior
      dimensions restored.

---

## 9. Retire a Wheel Early (Damage, Not Wear)

- [ ] Open **Wheel Retirement** → New directly (not auto-created this time). Pick a
      real In-Stock or In-Use Wheel, fill **Retirement Reason** (e.g. "chipped edge"),
      submit.
- [ ] Expected: Wheel's Status → `Retired`, a real submitted Material Issue exists,
      Bin quantity drops by 1 — same outcome as Section 8's reviewed draft, just
      triggered directly instead of automatically.
- [ ] Cancel it. Expected: Wheel back to its prior status, Material Issue reversed.

---

## 10. Checking the Accounting Side (Stock Ledger & General Ledger)

Wheel Tracker deliberately builds on real ERPNext Stock Entries — a wheel's arrival and
retirement are supposed to be genuine accounting events, not just field changes inside
this app. This section only applies if your Company has **Enable Perpetual Inventory**
checked (Company → Accounts tab); if it's off, skip to Section 12 and note why. Do this
section right after Sections 3–9, while that Stock Entry and GL trail is still fresh.

- [ ] Open the Material Receipt Stock Entry from Section 3. Confirm:
  - [ ] Its **GL Entries** (Stock Entry → View → Accounting Ledger) show a debit to
        **Stock In Hand** and a matching credit to **Stock Adjustment** (or to a
        Purchase document's own payable-side account, if one was behind it instead of
        a bare Material Receipt), for Qty × the Wheel Type's **Unit Cost**.
  - [ ] Each new Wheel's backing **Serial No** record (Stock → Serial No) shows a
        **Purchase Rate** matching that same Unit Cost — check one of the 3 Wheels
        from Section 3 directly, not just the Stock Entry total.
- [ ] Open the submitted Wheel Retirement / Material Issue from Section 8 or 9.
      Confirm:
  - [ ] Its GL Entries are the mirror image — a credit to **Stock In Hand**, a debit
        to **Stock Adjustment** — at the *same* valuation as the matching receipt
        (ERPNext's own valuation method decides this; check the actual number instead
        of assuming it matches).
  - [ ] **Stock → Bin** for that Item/Warehouse shows **actual_qty** down by exactly 1
        since Section 3, and **Stock Value** down by the same valuation amount.
- [ ] Run core ERPNext's **Stock Balance** report, filtered to the Wheel Type's Item
      and your test Warehouse. Confirm the running qty/value after your Section 3/8/9
      actions matches what you'd expect by hand (received 3, issued however many you
      retired).
- [ ] Run **General Ledger**, filtered to the **Stock In Hand** account, for this same
      date range. Confirm every Wheel Tracker-driven Material Receipt/Material Issue
      from this test shows up as its own real GL Entry, and that these numbers
      reconcile with the Stock Balance report above — a mismatch here is a real
      accounting bug, not a Wheel Tracker display issue.
- [ ] If Section 4/7 involved a real Work Order (not skipped), confirm the wheel's
      wear cost actually reached the manufacturing side, not just the Job Card:
  - [ ] Open that **Work Order** — its **Additional Operating Cost** should equal the
        sum of **Wheel Wear Cost** across all its non-cancelled Job Cards; check the
        actual arithmetic, don't just confirm it's non-zero.
  - [ ] If that Work Order's own Manufacture Stock Entry has been submitted, the
        Finished Good's resulting valuation rate should reflect this cost — compare it
        against (BOM cost + normal operating cost + this additional operating cost) ÷
        manufactured quantity.

---

## 11. Sell Scrap From a Retired Wheel

Some retired wheels have real scrap value (e.g. a recovered aluminum hub). This needs
**Wheel Tracker Settings → Scrap Sales Account** set to a real Income account first —
set one now if it's blank.

- [ ] Open **Wheel Scrap Sale** → New. Set **Company**, **Payment Account** (a real
      Cash or Bank account), and under **Wheels** add one row: the Retired Wheel from
      Section 8 or 9, an **Amount**.
- [ ] Submit. Expected:
  - [ ] **Total Amount** equals the row's Amount.
  - [ ] **Journal Entry** now links to a real, submitted Journal Entry — open it and
        confirm it debits your **Payment Account** and credits the **Scrap Sales
        Account** from Settings, both for the exact same amount.
- [ ] Try creating a *second* Wheel Scrap Sale for the *same* Wheel. Expected: a clear
      "already sold" error naming the first sale — the same wheel's scrap can't be
      sold twice.
- [ ] Try adding a Wheel that's still **In Stock** or **In Use** (not Retired) to a new
      Wheel Scrap Sale. Expected: a clear validation error, nothing saves.
- [ ] **Bulk case**: retire a second Wheel (Section 9), create one more Wheel Scrap
      Sale with *both* Retired Wheels as separate rows, different Amounts each.
      Submit. Expected: **Total Amount** is the sum of both rows, and the resulting
      Journal Entry's debit/credit both equal that same sum — one JE for the whole
      bulk sale, not one per wheel.
- [ ] Cancel one of your submitted Wheel Scrap Sales. Expected: its Journal Entry gets
      cancelled too (check the JE's own docstatus), and that Wheel can now be put into
      a *new* Wheel Scrap Sale again (the "already sold" block only applies to
      non-cancelled sales).
- [ ] Temporarily clear **Scrap Sales Account** on Wheel Tracker Settings, try creating
      a new Wheel Scrap Sale. Expected: blocked immediately with a clear error, not a
      silent save or a post to the wrong account. Put the account back afterward.

---

## 12. Reorder Alerts

- [ ] Open a Wheel Type, set **Reorder Point** higher than its current In-Stock count
      (check the real count first).
- [ ] Run the daily reorder check manually (don't wait for the scheduled job):
      `bench --site <site> execute wheel_tracker.reorder_alerts.check_reorder_levels`
- [ ] Expected: a Notification Log entry appears for the configured **Reorder Notify
      Role** (Wheel Tracker Settings), and — if **Also Send Email Alerts** is
      checked — a real email goes out. The Wheel Type's own **Reorder Alert Active**
      flips on, **Last Reorder Alert On** gets a timestamp.
- [ ] Bring the In-Stock count back above the Reorder Point (receive more stock).
      Expected: next check run clears **Reorder Alert Active**.

---

## 13. Wheel Cost Summary Report

- [ ] Open the **Wheel Cost Summary** report (under Reports on the workspace).
- [ ] Set a wide date range covering the Measurement Events you've submitted above.
- [ ] Expected: one row per submitted Measurement Event, columns Measurement Event /
      Date / Job Card / Wheel / Wheel Type / Incremental Consumed Volume / Job Cost /
      Consumption %, with a **Total** row summing Job Cost and averaging Consumption %.
- [ ] Filter by a specific Wheel Type / Wheel / Job Card and confirm the row count
      narrows correctly.

---

## 14. Edit a Volume Formula (and See It Actually Change Numbers)

- [ ] Open the **Wheel Shape** you used in Section 2 (the flat one). Note its current
      **Volume Formula** text and the resulting Original Volume on your Wheel Type.
- [ ] Change the formula to something deliberately different but still valid, e.g.
      wrap the existing expression in `2 * (...)` to double it. Save.
- [ ] Expected:
  - [ ] It saves successfully (a valid formula is accepted).
  - [ ] Re-open the Wheel Type from Section 2 and re-save it (or just check
        **Original Volume** after any save) — it's now exactly double what it was.
- [ ] Now break it deliberately: replace the formula with nonsense, e.g.
      `diameter / 0 +++`. Save. Expected: a clear error naming the real problem
      (invalid syntax / can't evaluate), the bad formula is rejected, nothing saves.
- [ ] Put the original formula back and save.

---

## 15. Bulk Import

- [ ] Open **Bulk Import Wheels** (under Operations on the workspace).
- [ ] Click **Download CSV Template**, confirm it downloads a real CSV with the
      expected columns (shape, material, spec_code, item, ...).
- [ ] Fill in 2–3 rows with real Shape/Material codes that already exist, upload it.
- [ ] Expected: a success summary (Wheel Types created/reused, Wheels created), and
      the new Wheel Type(s)/Wheel(s) actually exist afterward with sensible values.
- [ ] Try uploading a row with a Shape or Material code that doesn't exist. Expected:
      that row is reported as an error (with its row number), not silently guessed at
      or skipped without mention.

---

## 16. Language Switch (English ⇄ Arabic)

- [ ] Open **Wheel Tracker Settings**, set **Language** to `Arabic`, save.
- [ ] Expected: the page reloads itself automatically, and:
  - [ ] Every doctype name, field label, and field description across Wheel/Wheel
        Type/Wheel Shape/Measurement Event/Wheel Retirement/etc. shows in Arabic.
  - [ ] The **Grinding Wheels** workspace — shortcuts, number cards, section headers,
        every card's doctype links — all show Arabic, and still work (click through
        a few, nothing is broken or missing).
  - [ ] Core Desk chrome on these screens (Save, Assigned To, Comments, breadcrumbs,
        the sidebar's own "Grinding Wheels" entry) shows Arabic too — check this on a
        **freshly loaded** tab, not just a page you were already on.
  - [ ] Open any date field (e.g. Batch Measurement Entry's From Date) — the calendar
        popup shows Arabic month/day names.
  - [ ] Open an *unrelated* doctype (e.g. core **User** or **ToDo**) — its own date
        field calendar and labels stay in whatever language they were in before; this
        switch must not leak outside Wheel Tracker.
  - [ ] "Wheel" itself shows as **حجر**, not **عجلة**, everywhere.
- [ ] Set **Language** back to `English`, save, confirm everything reverts.

---

## 17. Consumption % Bar (List Views)

- [ ] Open the **Measurement Event** or **Wheel** list view.
- [ ] Expected: the **Consumption %** column shows an actual colored progress bar with
      the exact percentage printed on it (e.g. "68.96%"), not a plain number and not
      Frappe's bare built-in bar (no label, raw unrounded value).
- [ ] Confirm the color rule: green under 70%, orange 70–90%, red 90% and above —
      find or create rows spanning these ranges to check all three colors actually
      appear, not just green.

---

## Sign-Off

- [ ] All sections above are checked, or explicitly marked "skipped" with a reason.
- [ ] Any step whose actual result didn't match its expected result is written up
      separately with: the exact step, what you expected, what you actually saw, and
      (if you can) a screenshot.

Tested by: ______________________  Date: ______________________

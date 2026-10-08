# Wheel Tracker — Stores & Shop Floor Guide

This is a plain-language walkthrough of using Wheel Tracker in Desk day to day — you'll
find it in Desk under the **Grinding Wheels** workspace. If you're a developer, see
`CLAUDE.md`. If you want the full spec/formula history, see `PRD.md` — neither is
needed for normal day-to-day use.

## 1. What This App Tracks

Every diamond/CBN resharpening wheel in the shop, from the moment it's received until
it's fully worn out or damaged. It tracks how much of a wheel's abrasive material has
been used, what that wear cost, and which jobs it was used on.

## 2. The Five Things You'll See in Desk

- **Wheel** — one physical wheel, identified by its Factory Wheel Code. Its status is
  always one of In Stock, In Use, or Retired.
- **Wheel Type** — the spec a Wheel belongs to (shape, material, size, cost).
- **Job Card's "Wheels Used"** — the list of Wheels assigned to a specific job.
- **Measurement Event** — a caliper reading logged against a Wheel, showing how much
  wear happened since the last reading.
- **Wheel Retirement** — the record of a Wheel being taken permanently out of service.

Every one of these shows a reference photo of the wheel's shape (1A1, 1V1, 11V9, 12V9,
or P-series) right on the form and in its list view — set once on **Wheel Shape**, it
carries through automatically wherever that shape shows up.

## 3. Receiving New Wheels

When new wheels arrive, they're brought into stock with a **Material Receipt** Stock
Entry against the Wheel Type's Item, same as any other stock item. You don't need to
create Wheel records by hand — submitting that Stock Entry automatically creates one
Wheel per unit received, In Stock, with a Factory Wheel Code already assigned.

## 4. Putting a Wheel on a Job

Open the Job Card and add a row under **Wheels Used**. Only Wheels currently In Stock
show up in the picker. Saving the Job Card marks the Wheel In Use and links it to that
job — no separate step needed.

## 5. Logging Wear

### 5.1 One Wheel at a Time — the Measurement Event Form

Create a new Measurement Event, pick the Wheel, and enter its current caliper readings
(diameter, and for profiled wheels, inner diameter and layer height). Submitting it
calculates the wear and cost automatically and updates the Wheel.

### 5.2 Several Wheels at Once — the Batch Measurement Entry Page

Instead of filling out the single-record form repeatedly, use the **Batch Measurement
Entry** page. Pick a From Date and To Date, and every Wheel that was used on a Job Card
posted in that window is listed for you to enter readings against in one go — each row
shows which Job Card(s) it came from. Once you submit a reading for a Wheel, it won't
be listed again if you pick the same date range afterward.

### 5.3 When a Wheel Was Used on More Than One Job

If a wheel hasn't been measured since it was used on more than one job, its next
Measurement Event automatically works out every Job Card it sat on since the last
reading and splits the wear cost evenly between them — you don't need to measure after
every single job to keep costs accurate per job.

## 6. When a Wheel Retires Itself (Auto-Retirement)

If a measurement shows a wheel has reached 100% consumption, the Wheel is marked
Retired immediately — but it doesn't leave stock on its own. A **Wheel Retirement** is
drafted for you automatically, sitting there until someone opens it and submits it. Only
that submission actually removes the wheel from stock with a genuine Material Issue —
so there's always a review step between "this wheel ran out" and "it's really gone from
the ledger."

## 7. Retiring a Wheel Early (Damage, Chips, Cracks)

If a wheel needs to come out of service before it's fully worn — cracked, chipped, or
otherwise unsafe — file a **Wheel Retirement** for it directly, with a reason. This is
now specifically the path for early/damage retirement; a wheel that simply ran out
handles itself (see above).

## 8. Undoing a Mistake

- **Cancelling a Measurement Event** reverses everything it did: the Wheel's
  dimensions and status go back to what they were before. If it auto-retired the Wheel
  and that draft Wheel Retirement is still pending review, the draft is simply removed;
  if someone already reviewed and submitted it, that retirement (and its Stock Entry)
  is cancelled instead.
- **Cancelling a Wheel Retirement** directly brings the Wheel back to In Stock and
  cancels its Material Issue.

## 9. Reorder Alerts

Once a day, the system checks every Wheel Type's In Stock count against its Reorder
Point. If it's fallen below that, an alert goes out (Notification Log, and email if
enabled) until stock is replenished.

## 10. Common Questions

**"Why is this Wheel Retired and I didn't retire it?"**
Check the Measurement Event that caused it — it has an **Auto-Created Wheel
Retirement** field linking straight to the record that was drafted automatically when
consumption hit 100%. If it's still a draft, nothing has actually left stock yet —
review it and submit it to confirm.

**"Why can't I log a measurement for this wheel?"**
Its Wheel Type doesn't Require Measurement — some shapes (like thin slitting wheels)
are tracked as simply usable/not-usable instead. Use Wheel Retirement for those.

## 11. Switching Between English and Arabic

Open **Wheel Tracker Settings** and set **Language** to English or Arabic, then save —
your own page reloads right away to show it. This only switches Wheel Tracker's own
field names, doctype names, and messages; it does not touch System Settings or anyone's
personal language preference, and the rest of Desk (Sales Orders, Customers, everything
outside this module) is completely unaffected. Everyone sees the same choice the next
time they load a page, regardless of their own language setting elsewhere in the system.

## 12. Reading the Consumption % Bar

Wherever you see a Consumption % bar in a list (Wheel, Measurement Event), it now shows
the percentage as a number on the bar itself, colored green under 70%, orange from
70–90%, and red at 90% and above — a quick visual read on which wheels are closest to
retiring.

## 13. Where to Go Next

- `CLAUDE.md` — engineering rules and design principles, for developers.
- `PRD.md` — the full spec and formula history, if you need the "why" behind a number.

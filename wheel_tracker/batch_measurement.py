# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Batch measurement entry for the "Batch Measurement Entry" Page — recording a
Measurement Event per Wheel one at a time is slow, so this lets an operator pick a date
range, load every Wheel used on a Job Card whose Posting Date falls in it, and submit
all of their new caliper readings in one action. Each Wheel still gets a real,
individually submitted Measurement Event through the exact same insert/submit code path
as the single-record form — no wear/cost/retirement logic is duplicated here.

Since PRD v14, the range replaces picking a single Job Card: a Wheel isn't necessarily
still on (or even In Use on) the Job Card it was measured against, and one operator
session often covers several Job Cards' wheels at once. A Wheel that already has a
submitted Measurement Event on or after the range's start date is left off the list, so
submitting once means it doesn't come back when the same range is picked again."""

import frappe
from frappe.utils import cint, flt, now_datetime

from wheel_tracker.job_card_integration import WHEEL_ROWS_FILTERS

WHEEL_FIELDS = ["name as wheel", "wheel_type", "current_diameter", "current_inner_diameter", "current_diamond_height"]


@frappe.whitelist()
def get_wheels_used_between(from_date: str, to_date: str) -> dict:
	"""Every Wheel used on a Job Card whose Posting Date falls in [from_date, to_date],
	split into those a Measurement Event can be recorded against (their Wheel Type has
	requires_measurement checked) and those that can't (e.g. P-series — tracked via
	Wheel Retirement instead, see PRD v9). Already-Retired Wheels are left out
	entirely — nothing left to measure. A Wheel already measured on or after
	`from_date` is also left out, so it doesn't reappear once handled.

	Args:
		from_date: earliest Job Card Posting Date to include.
		to_date: latest Job Card Posting Date to include.

	Returns:
		dict with "job_cards" (matched Job Card names) and "measurable"/
		"non_measurable" lists of {wheel, wheel_type, job_cards, current_diameter,
		current_inner_diameter, current_diamond_height} — `job_cards` on each row is
		the list of matched Job Cards that Wheel actually appeared on.
	"""
	job_cards = frappe.get_all(
		"Job Card", filters={"posting_date": ["between", [from_date, to_date]]}, pluck="name"
	)
	if not job_cards:
		return {"job_cards": [], "measurable": [], "non_measurable": []}

	wheel_job_cards = get_wheels_by_job_card(job_cards)
	if not wheel_job_cards:
		return {"job_cards": job_cards, "measurable": [], "non_measurable": []}

	already_measured = get_wheels_measured_since(list(wheel_job_cards), from_date)
	wheel_names = [wheel for wheel in wheel_job_cards if wheel not in already_measured]
	if not wheel_names:
		return {"job_cards": job_cards, "measurable": [], "non_measurable": []}

	rows = frappe.get_all(
		"Wheel",
		filters={"name": ["in", wheel_names], "status": ["!=", "Retired"]},
		fields=WHEEL_FIELDS,
		order_by="wheel_type, name",
	)
	if not rows:
		return {"job_cards": job_cards, "measurable": [], "non_measurable": []}

	wheel_types = {row.wheel_type for row in rows}
	requires_measurement = dict(
		frappe.get_all(
			"Wheel Type",
			filters={"name": ["in", list(wheel_types)]},
			fields=["name", "requires_measurement"],
			as_list=True,
		)
	)

	measurable, non_measurable = [], []
	for row in rows:
		row["job_cards"] = wheel_job_cards.get(row.wheel, [])
		bucket = measurable if cint(requires_measurement.get(row.wheel_type)) else non_measurable
		bucket.append(row)

	return {"job_cards": job_cards, "measurable": measurable, "non_measurable": non_measurable}


def get_wheels_by_job_card(job_cards: list) -> dict:
	"""{wheel: [job_card, ...]} for every Job Card Wheel row against any of these Job
	Cards, however that Wheel's assignment stands today — a completed or since-released
	Job Card still counts, same as MeasurementEvent.derive_job_cards()'s own history
	lookup relies on."""
	rows = frappe.get_all(
		"Job Card Wheel",
		filters={"parent": ["in", job_cards], **WHEEL_ROWS_FILTERS},
		fields=["wheel", "parent as job_card"],
	)
	wheel_job_cards = {}
	for row in rows:
		wheel_job_cards.setdefault(row.wheel, []).append(row.job_card)
	return wheel_job_cards


def get_wheels_measured_since(wheel_names: list, from_date: str) -> set:
	"""Wheels among wheel_names that already have a submitted Measurement Event on or
	after from_date — excluded from get_wheels_used_between() so a just-measured Wheel
	doesn't reappear when the same date range is picked again."""
	if not wheel_names:
		return set()
	rows = frappe.get_all(
		"Measurement Event",
		filters={"wheel": ["in", wheel_names], "docstatus": 1, "measurement_date": [">=", from_date]},
		pluck="wheel",
	)
	return set(rows)


@frappe.whitelist()
def submit_batch_measurements(readings) -> dict:
	"""Create and submit one Measurement Event per reading.

	Args:
		readings: list of {wheel, diameter, inner_diameter, diamond_height} dicts
			(JSON-encoded when called over the wire). Each created event derives its
			own real set of linked Job Cards from assignment history (see
			MeasurementEvent.derive_job_cards) — nothing here decides that.

	Returns:
		dict summary: count created and any per-wheel errors (processing continues
		past a bad row instead of aborting the whole batch, matching bulk_import.py's
		convention).
	"""
	readings = frappe.parse_json(readings)
	summary = {"created": 0, "errors": []}

	for i, reading in enumerate(readings):
		wheel = reading.get("wheel")
		savepoint = f"batch_measurement_row_{i}"
		frappe.db.savepoint(savepoint)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Measurement Event",
					"wheel": wheel,
					"measurement_date": now_datetime(),
					"measured_by": frappe.session.user,
					"diameter": flt(reading.get("diameter")),
					"inner_diameter": flt(reading.get("inner_diameter")),
					"diamond_height": flt(reading.get("diamond_height")),
				}
			).insert(ignore_permissions=True)
			doc.submit()
			summary["created"] += 1
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			summary["errors"].append({"wheel": wheel, "message": str(e)})

	return summary

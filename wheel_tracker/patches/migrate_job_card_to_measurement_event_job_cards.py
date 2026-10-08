# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Backfills the new Measurement Event Job Card child table from the old single
`job_card` Link field before it's dropped from the DocType JSON (see PRD v12 — a
Measurement Event's wear can span several Job Cards a Wheel sat on since its last
measurement, not just one). Must run pre_model_sync, while the old `job_card` column
still exists in the DB, same reasoning as
rename_wheel_usability_check_to_wheel_retirement. Idempotent: skips any Measurement
Event that already has rows in job_cards, and no-ops entirely on a fresh site that
never had the old column."""

import frappe


def execute():
	if not frappe.db.has_column("Measurement Event", "job_card"):
		return

	rows = frappe.db.sql(
		"""
		select name, job_card, job_cost
		from `tabMeasurement Event`
		where job_card is not null and job_card != ''
		""",
		as_dict=True,
	)

	for row in rows:
		if frappe.db.exists(
			"Measurement Event Job Card", {"parent": row.name, "parenttype": "Measurement Event"}
		):
			continue

		child = frappe.get_doc(
			{
				"doctype": "Measurement Event Job Card",
				"parenttype": "Measurement Event",
				"parentfield": "job_cards",
				"parent": row.name,
				"job_card": row.job_card,
				"allocated_cost": row.job_cost,
				"idx": 1,
			}
		)
		child.db_insert()

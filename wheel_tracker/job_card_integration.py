# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from wheel_tracker.wheel_tracker.doctype.wheel.wheel import assign_to_job_card, release_from_job_card

WHEEL_ROWS_FILTERS = {"parenttype": "Job Card", "parentfield": "custom_wheels_used"}


def validate_wheel_assignments(doc, method=None):
	"""Job Card validate hook: snapshot the previously-saved Wheel rows and reject bad new ones early."""
	if doc.is_new():
		doc.flags.previous_wheels = set()
	else:
		doc.flags.previous_wheels = set(
			frappe.get_all(
				"Job Card Wheel", filters={"parent": doc.name, **WHEEL_ROWS_FILTERS}, pluck="wheel"
			)
		)

	current_wheels = {row.wheel for row in (doc.get("custom_wheels_used") or []) if row.wheel}

	for wheel_name in current_wheels - doc.flags.previous_wheels:
		status, current_job = frappe.db.get_value("Wheel", wheel_name, ["status", "current_job_card"])
		if status == "In Use" and current_job and current_job != doc.name:
			frappe.throw(
				_("Wheel {0} is already In Use on Job Card {1}.").format(wheel_name, current_job)
			)
		if status == "Retired":
			frappe.throw(_("Wheel {0} is Retired and cannot be assigned to a job.").format(wheel_name))


def sync_wheel_assignments(doc, method=None):
	"""Job Card on_update hook: apply the Wheel assign/release side-effects validated above."""
	current_wheels = {row.wheel for row in (doc.get("custom_wheels_used") or []) if row.wheel}
	previous_wheels = doc.flags.previous_wheels or set()

	for wheel_name in current_wheels - previous_wheels:
		if frappe.db.get_value("Wheel", wheel_name, "status") == "In Stock":
			assign_to_job_card(wheel_name, doc.name)

	for wheel_name in previous_wheels - current_wheels:
		status, current_job = frappe.db.get_value("Wheel", wheel_name, ["status", "current_job_card"])
		if status == "In Use" and current_job == doc.name:
			release_from_job_card(wheel_name)

	if doc.status == "Completed":
		release_all_wheels_for_job(doc.name)


def release_wheels_on_trash(doc, method=None):
	"""Job Card on_trash hook: return any still-assigned Wheels to the pool."""
	release_all_wheels_for_job(doc.name)


def release_all_wheels_for_job(job_card: str):
	wheels = frappe.get_all(
		"Wheel", filters={"current_job_card": job_card, "status": "In Use"}, pluck="name"
	)
	for wheel_name in wheels:
		release_from_job_card(wheel_name)


def update_job_card_wheel_cost(job_card: str):
	"""Recompute the Job Card's rolled-up wear cost from its submitted Measurement Events."""
	total = frappe.db.get_value("Measurement Event", {"job_card": job_card, "docstatus": 1}, "sum(job_cost)")
	frappe.db.set_value("Job Card", job_card, "custom_wheel_wear_cost", flt(total))

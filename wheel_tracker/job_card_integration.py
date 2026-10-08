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
	"""Recompute the Job Card's rolled-up wear cost from its share of every submitted
	Measurement Event linked to it (see Measurement Event Job Card — a Wheel's wear
	between two measurements can be split across several Job Cards, PRD v12), then roll
	that up into its Work Order (see PRD v10)."""
	total = frappe.db.sql(
		"""
		select sum(mejc.allocated_cost)
		from `tabMeasurement Event Job Card` mejc
		inner join `tabMeasurement Event` me on me.name = mejc.parent
		where mejc.job_card = %(job_card)s
			and me.docstatus = 1
		""",
		{"job_card": job_card},
	)[0][0]
	frappe.db.set_value("Job Card", job_card, "custom_wheel_wear_cost", flt(total))

	work_order = frappe.db.get_value("Job Card", job_card, "work_order")
	if work_order:
		sync_wheel_cost_to_work_order(work_order)


def sync_wheel_cost_to_work_order(work_order: str):
	"""Sum Wheel Wear Cost across every non-cancelled Job Card on a Work Order into
	Work Order.additional_operating_cost — ERPNext's own bolt-on operating-cost
	extension point (work_order.py's calculate_operating_cost(): total_operating_cost =
	additional_operating_cost + ... + corrective_operation_cost — already read by
	BOM.add_operations_cost() into Stock Entry's own FG valuation). Mirrors Job Card's
	own update_corrective_in_work_order(), which does exactly this shape for
	corrective_operation_cost."""
	total = frappe.db.get_value(
		"Job Card", {"work_order": work_order, "docstatus": ["!=", 2]}, "sum(custom_wheel_wear_cost)"
	)

	wo = frappe.get_doc("Work Order", work_order)
	if wo.docstatus == 2:
		return
	wo.additional_operating_cost = flt(total)
	wo.calculate_operating_cost()
	wo.flags.ignore_validate_update_after_submit = True
	wo.save(ignore_permissions=True)

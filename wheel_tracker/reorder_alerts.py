# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime

IN_STOCK = "In Stock"


def check_reorder_levels():
	"""Daily scheduled job: alert when a Wheel Type's In Stock count drops below its reorder point.

	Deduplicated via Wheel Type.reorder_alert_active — only fires once per dip below the
	reorder point; clears automatically once stock is replenished, so the next dip alerts again.
	"""
	settings = frappe.get_single("Wheel Tracker Settings")
	wheel_types = frappe.get_all(
		"Wheel Type",
		filters={"disabled": 0, "reorder_point": [">", 0]},
		fields=["name", "spec_code", "shape", "reorder_point", "reorder_alert_active"],
	)
	if not wheel_types:
		return

	stock_counts = frappe.get_all(
		"Wheel",
		filters={"status": IN_STOCK, "wheel_type": ["in", [row.name for row in wheel_types]]},
		group_by="wheel_type",
		fields=["wheel_type", "count(name) as qty"],
	)
	count_by_type = {row.wheel_type: row.qty for row in stock_counts}

	for wheel_type in wheel_types:
		in_stock = count_by_type.get(wheel_type.name, 0)
		below_reorder = in_stock < wheel_type.reorder_point

		if below_reorder and not wheel_type.reorder_alert_active:
			send_reorder_alert(wheel_type, in_stock, settings)
			frappe.db.set_value(
				"Wheel Type",
				wheel_type.name,
				{"reorder_alert_active": 1, "last_reorder_alert_on": now_datetime()},
			)
		elif not below_reorder and wheel_type.reorder_alert_active:
			frappe.db.set_value("Wheel Type", wheel_type.name, "reorder_alert_active", 0)


def send_reorder_alert(wheel_type, in_stock: int, settings):
	"""Raise a Notification Log (+ optional email) to every enabled user with the notify role."""
	users = frappe.get_all(
		"Has Role", filters={"role": settings.reorder_notify_role, "parenttype": "User"}, pluck="parent"
	)
	users = frappe.get_all(
		"User", filters={"name": ["in", users], "enabled": 1}, pluck="name"
	)
	if not users:
		return

	subject = _("Reorder Alert: {0} ({1}) below reorder point").format(
		wheel_type.spec_code, wheel_type.shape
	)
	message = _("Wheel Type {0} has {1} wheel(s) In Stock, below its reorder point of {2}.").format(
		wheel_type.spec_code, in_stock, wheel_type.reorder_point
	)

	for user in users:
		notification = frappe.new_doc("Notification Log")
		notification.subject = subject
		notification.for_user = user
		notification.type = "Alert"
		notification.document_type = "Wheel Type"
		notification.document_name = wheel_type.name
		notification.email_content = message
		notification.insert(ignore_permissions=True)

	if settings.send_email_alerts:
		emails = frappe.get_all("User", filters={"name": ["in", users]}, pluck="email")
		try:
			frappe.sendmail(recipients=emails, subject=subject, message=message)
		except Exception:
			# A missing/misconfigured Email Account shouldn't lose the Notification Log
			# above or abort the rest of the reorder check for other Wheel Types.
			frappe.log_error(
				title=_("Wheel Tracker reorder email failed"),
				message=frappe.get_traceback(),
			)

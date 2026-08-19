# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from wheel_tracker.wheel_tracker.doctype.wheel.wheel import reinstate_wheel, retire_wheel


class WheelUsabilityCheck(Document):
	def validate(self):
		wheel_type = frappe.db.get_value("Wheel", self.wheel, "wheel_type")
		if not wheel_type:
			frappe.throw(_("Wheel {0} does not exist.").format(self.wheel))
		self.wheel_type = wheel_type

		if not self.usable and not self.retirement_reason:
			frappe.throw(_("Reason is required when marking a Wheel not usable."), frappe.MandatoryError)

	def on_submit(self):
		if self.usable:
			reinstate_wheel(self.wheel)
		else:
			retire_wheel(self.wheel, self.retirement_reason)

	def on_cancel(self):
		previous = get_previous_submitted_check(self.wheel, exclude=self.name)
		if not previous:
			reinstate_wheel(self.wheel)
		elif previous.usable:
			reinstate_wheel(self.wheel)
		else:
			retire_wheel(self.wheel, previous.retirement_reason)


def get_previous_submitted_check(wheel: str, exclude: str | None = None):
	"""Most recent submitted Wheel Usability Check for a Wheel (verdict + reason), or None."""
	filters = {"wheel": wheel, "docstatus": 1}
	if exclude:
		filters["name"] = ["!=", exclude]
	rows = frappe.get_all(
		"Wheel Usability Check",
		filters=filters,
		fields=["usable", "retirement_reason"],
		order_by="check_date desc, creation desc",
		limit=1,
	)
	return rows[0] if rows else None

# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from wheel_tracker.language_switch import _
from frappe.model.document import Document

from wheel_tracker.wheel_tracker.doctype.wheel.wheel import reinstate_wheel, retire_wheel


class WheelRetirement(Document):
	def validate(self):
		wheel_type = frappe.db.get_value("Wheel", self.wheel, "wheel_type")
		if not wheel_type:
			frappe.throw(_("Wheel {0} does not exist.").format(self.wheel))
		self.wheel_type = wheel_type

	def on_submit(self):
		retire_wheel(self.wheel, self.retirement_reason)
		se_name = create_retirement_stock_entry(self.wheel)
		self.db_set("stock_entry", se_name)

	def on_cancel(self):
		reinstate_wheel(self.wheel)
		if self.stock_entry:
			frappe.get_doc("Stock Entry", self.stock_entry).cancel()


def create_retirement_stock_entry(wheel_name: str) -> str:
	"""Create+submit a real Material Issue Stock Entry consuming this Wheel's serial
	number out of its current warehouse — the concrete stock action Wheel Retirement
	represents, not just a Wheel.status flip. See PRD v10.

	Deliberately redundant with the Stock Ledger Entry hook this Material Issue's own
	submission will independently trigger (stock_ledger_hooks.py, which will also call
	retire_wheel() once the Serial No's status settles) — retire_wheel() is a no-op when
	already retired, so the two paths agreeing costs nothing, and this direct call is
	the only one that fires if the Wheel's Item somehow isn't serialized."""
	wheel = frappe.db.get_value("Wheel", wheel_name, ["wheel_type", "warehouse"], as_dict=True)
	if not wheel.warehouse:
		frappe.throw(_("Wheel {0} has no Warehouse set — can't issue it out of stock.").format(wheel_name))

	item_code = frappe.db.get_value("Wheel Type", wheel.wheel_type, "item")
	company = frappe.db.get_value("Warehouse", wheel.warehouse, "company")

	se = frappe.new_doc("Stock Entry")
	se.purpose = "Material Issue"
	se.stock_entry_type = "Material Issue"
	se.company = company
	se.append("items", {"item_code": item_code, "s_warehouse": wheel.warehouse, "qty": 1})
	se.flags.wheel_serial_no = wheel_name
	se.insert(ignore_permissions=True)
	se.submit()
	return se.name

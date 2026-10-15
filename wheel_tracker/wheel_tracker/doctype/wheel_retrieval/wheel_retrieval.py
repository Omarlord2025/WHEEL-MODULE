# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint
from wheel_tracker.language_switch import _


class WheelRetrieval(Document):
	def validate(self):
		self.validate_items()
		self.total_qty = sum(cint(row.qty_to_create) for row in self.items)

	def validate_items(self):
		if not self.items:
			frappe.throw(_("Add at least one Wheel Type to retrieve."))

		seen = set()
		for row in self.items:
			if row.wheel_type in seen:
				frappe.throw(
					_("Row {0}: Wheel Type {1} is listed more than once.").format(row.idx, row.wheel_type)
				)
			seen.add(row.wheel_type)

			if cint(row.qty_to_create) <= 0:
				frappe.throw(_("Row {0}: Quantity to Create must be greater than zero.").format(row.idx))

	def on_submit(self):
		se = self.create_material_receipt()
		self.db_set("stock_entry", se.name)

	def on_cancel(self):
		if self.stock_entry and frappe.db.exists("Stock Entry", self.stock_entry):
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()

	def create_material_receipt(self):
		"""One real Material Receipt Stock Entry for every row — the existing
		assign_serial_numbers_for_wheel_receipt / create_wheels_on_material_receipt
		hooks (stock_entry_hooks.py) mint a matching Wheel per unit received, same as
		any other Material Receipt against a Wheel Type's Item. Reuses that machinery
		rather than creating Wheel records directly, so this stays a real ERPNext
		document and Bin.actual_qty stays correct (PRD v10's own principle)."""
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Receipt"
		se.stock_entry_type = "Material Receipt"
		se.company = self.company
		se.posting_date = self.posting_date

		for row in self.items:
			item_code, unit_cost = frappe.db.get_value("Wheel Type", row.wheel_type, ["item", "unit_cost"])
			se.append(
				"items",
				{
					"item_code": item_code,
					"qty": row.qty_to_create,
					"t_warehouse": self.warehouse,
					"basic_rate": unit_cost,
				},
			)

		se.insert(ignore_permissions=True)
		se.submit()
		return se


@frappe.whitelist()
def get_items_by_group(item_group: str | None = None, warehouse: str | None = None):
	"""Every enabled Wheel Type (optionally filtered to one Item Group), with the
	target Warehouse's current Bin qty for reference — powers the "Get Items" button."""
	filters = {"disabled": 0}
	if item_group:
		item_codes = frappe.get_all("Item", filters={"item_group": item_group}, pluck="name")
		filters["item"] = ["in", item_codes or [""]]

	wheel_types = frappe.get_all(
		"Wheel Type", filters=filters, fields=["name as wheel_type", "item"], order_by="name"
	)
	for row in wheel_types:
		row["item_name"] = frappe.db.get_value("Item", row.item, "item_name")
		row["current_stock_qty"] = get_bin_qty(row.item, warehouse)
	return wheel_types


@frappe.whitelist()
def get_current_stock_qty(wheel_type: str, warehouse: str | None = None):
	item = frappe.db.get_value("Wheel Type", wheel_type, "item")
	return get_bin_qty(item, warehouse)


def get_bin_qty(item_code: str, warehouse: str | None) -> int:
	if not item_code or not warehouse:
		return 0
	return cint(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0)

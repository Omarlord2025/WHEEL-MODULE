# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

MATERIAL_RECEIPT = "Material Receipt"


def create_wheels_on_material_receipt(doc, method=None):
	"""Stock Entry on_submit hook: a Material Receipt against a Wheel Type's Item
	auto-creates that many Wheel records, new-wheel dimensions, In Stock."""
	if doc.purpose != MATERIAL_RECEIPT:
		return

	item_codes = list({row.item_code for row in doc.items})
	if not item_codes:
		return

	wheel_types = frappe.get_all(
		"Wheel Type",
		filters={"item": ["in", item_codes]},
		fields=[
			"name",
			"item",
			"original_diameter",
			"original_inner_diameter",
			"original_diamond_height",
			"original_volume",
		],
	)
	if not wheel_types:
		return

	wheel_type_by_item = {row.item: row for row in wheel_types}

	for row in doc.items:
		wheel_type = wheel_type_by_item.get(row.item_code)
		if not wheel_type:
			continue

		for _ in range(cint(row.qty)):
			wheel = frappe.new_doc("Wheel")
			wheel.wheel_type = wheel_type.name
			wheel.status = "In Stock"
			wheel.warehouse = row.t_warehouse
			wheel.current_diameter = wheel_type.original_diameter
			wheel.current_inner_diameter = wheel_type.original_inner_diameter
			wheel.current_diamond_height = wheel_type.original_diamond_height
			wheel.current_volume = wheel_type.original_volume
			wheel.source_stock_entry = doc.name
			wheel.received_on = doc.posting_date
			wheel.insert(ignore_permissions=True)

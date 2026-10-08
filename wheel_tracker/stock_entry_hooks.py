# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

from wheel_tracker.serial_stock_utils import build_serial_bundle, get_row_or_sle_serial_nos

MATERIAL_RECEIPT = "Material Receipt"
MATERIAL_ISSUE = "Material Issue"


def assign_serial_numbers_for_wheel_receipt(doc, method=None):
	"""Stock Entry before_validate hook: auto-generate factory_wheel_codes and attach
	them as a Serial and Batch Bundle before core validation requires serial numbers to
	be present for a serialized Item — before_validate always runs before validate()
	(frappe.model.document.Document's own _validate() ordering), so this beats core's
	own mandatory-serial check. See PRD v10."""
	if doc.purpose not in (MATERIAL_RECEIPT, MATERIAL_ISSUE):
		return

	from wheel_tracker.wheel_tracker.doctype.wheel.wheel import generate_factory_wheel_code

	wheel_type_by_item = get_wheel_types_by_item({row.item_code for row in doc.items})

	for row in doc.items:
		wheel_type = wheel_type_by_item.get(row.item_code)
		if not wheel_type or row.serial_and_batch_bundle or row.serial_no:
			continue  # not ours, or already populated (idempotent re-save / backfill guard)
		if not frappe.db.get_value("Item", row.item_code, "has_serial_no"):
			continue  # defensive: an item Phase 3 couldn't serialize

		if doc.purpose == MATERIAL_RECEIPT:
			# The opening-stock backfill patch reuses this hook to attach an existing
			# Wheel's own factory_wheel_code (always a single-serial, qty=1 receipt)
			# instead of minting a new one — everything else generates fresh codes.
			forced_serial = doc.flags.get("wheel_serial_no")
			if forced_serial:
				codes = [forced_serial]
			else:
				codes = [generate_factory_wheel_code(wheel_type.name) for _ in range(cint(row.qty))]
			bundle = build_serial_bundle(row.item_code, row.t_warehouse, codes, "Inward", doc.company)
		else:  # Material Issue — the specific Wheel being retired, passed by the caller
			target_serial = doc.flags.wheel_serial_no
			if not target_serial:
				continue
			bundle = build_serial_bundle(row.item_code, row.s_warehouse, [target_serial], "Outward", doc.company)

		row.serial_and_batch_bundle = bundle.name
		row.use_serial_batch_fields = 0


def create_wheels_on_material_receipt(doc, method=None):
	"""Stock Entry on_submit hook: a Material Receipt against a Wheel Type's Item
	auto-creates a matching Wheel per actual serial number received, In Stock.
	Idempotent — skips serials that already have a Wheel (needed by the opening-stock
	backfill patch, which reuses this same path)."""
	if doc.purpose != MATERIAL_RECEIPT:
		return

	wheel_type_by_item = get_wheel_types_by_item({row.item_code for row in doc.items})

	for row in doc.items:
		wheel_type = wheel_type_by_item.get(row.item_code)
		if not wheel_type:
			continue

		for serial_no in get_row_or_sle_serial_nos(row):
			if frappe.db.exists("Wheel", serial_no):
				continue

			wheel = frappe.new_doc("Wheel")
			wheel.factory_wheel_code = serial_no
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


def get_wheel_types_by_item(item_codes: set) -> dict:
	item_codes = list(item_codes)
	if not item_codes:
		return {}
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
	return {row.item: row for row in wheel_types}

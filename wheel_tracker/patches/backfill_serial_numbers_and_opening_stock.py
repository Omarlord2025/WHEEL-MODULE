# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""One-time backfill: gives every Wheel that existed before real ERPNext stock
integration (see PRD v10) a matching Serial No and an opening Stock Entry, so
Bin.actual_qty genuinely reflects them going forward — no permanent split between
"real" and "legacy" wheels. Idempotent (skips any Wheel that already has a Serial No),
per-wheel savepoint/rollback on failure, matching bulk_import.py's own convention.

Touches only `warehouse` and `source_stock_entry` on the existing Wheel record —
nothing else about its history is rewritten."""

import frappe

from wheel_tracker.wheel_tracker.doctype.wheel_retirement.wheel_retirement import create_retirement_stock_entry

MAIN_STORE = "Main Store - CNCL"


def execute():
	wheels = frappe.get_all(
		"Wheel",
		filters={"status": ["in", ["In Stock", "In Use", "Retired"]]},
		fields=["name", "wheel_type", "status", "received_on"],
	)

	failures = []
	for wheel in wheels:
		if frappe.db.exists("Serial No", wheel.name):
			continue
		savepoint = f"wt_backfill_{wheel.name.replace('-', '_').replace('.', '_')}"
		frappe.db.savepoint(savepoint)
		try:
			backfill_one_wheel(wheel)
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			failures.append((wheel.name, str(e)))

	if failures:
		frappe.log_error(
			title="wheel_tracker: opening-stock backfill failures",
			message=f"{len(failures)} Wheel(s) could not be backfilled: {failures}",
		)


def backfill_one_wheel(wheel):
	item_code, unit_cost = frappe.db.get_value("Wheel Type", wheel.wheel_type, ["item", "unit_cost"])
	company = frappe.db.get_value("Warehouse", MAIN_STORE, "company")

	se = frappe.new_doc("Stock Entry")
	se.purpose = "Material Receipt"
	se.stock_entry_type = "Material Receipt"
	se.posting_date = wheel.received_on or frappe.utils.nowdate()
	se.company = company
	se.append("items", {"item_code": item_code, "t_warehouse": MAIN_STORE, "qty": 1, "basic_rate": unit_cost})
	se.flags.wheel_serial_no = wheel.name
	se.insert(ignore_permissions=True)
	se.submit()

	frappe.db.set_value("Wheel", wheel.name, {"warehouse": MAIN_STORE, "source_stock_entry": se.name})

	if wheel.status == "Retired":
		create_retirement_stock_entry(wheel.name)

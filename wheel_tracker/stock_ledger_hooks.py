# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""The real bidirectional link between ERPNext's stock ledger and Wheel.status — a
genuine stock movement against a Wheel's serial number now retires/reinstates/moves it,
same as the app's own Wheel Retirement/Job Card flows. See PRD v10."""

import frappe

from wheel_tracker.serial_stock_utils import get_row_or_sle_serial_nos
from wheel_tracker.wheel_tracker.doctype.wheel.wheel import reinstate_wheel, retire_wheel, sync_wheel_warehouse

# Serial No.status values ERPNext itself computes (get_serial_no_status,
# erpnext/stock/serial_batch_bundle.py) for an outward/no-longer-in-this-warehouse
# movement — Material Issue/Manufacture/Repack -> Consumed, Disassemble/cancelled
# receipt -> Inactive, Delivery Note/Sales Invoice -> Delivered.
RETIRING_STATUSES = ("Consumed", "Delivered", "Inactive")


def sync_wheel_status_from_stock_ledger(doc, method=None):
	"""Stock Ledger Entry on_submit hook — fires for every SLE in the system, so bail
	out cheaply for anything that isn't a serialized Wheel Type Item. Deliberately NOT
	hooked on on_cancel: Stock Ledger Entry.on_cancel() always frappe.throw()s (SLEs are
	append-only) — cancelling a voucher posts a *new*, sign-reversed SLE that itself
	goes through on_submit, so this one handler already covers reversal."""
	if not doc.serial_and_batch_bundle and not doc.serial_no:
		return
	if not frappe.db.exists("Wheel Type", {"item": doc.item_code}):
		return

	for serial_no in get_row_or_sle_serial_nos(doc):
		if not frappe.db.exists("Wheel", serial_no):
			continue

		status, warehouse = frappe.db.get_value("Serial No", serial_no, ["status", "warehouse"])
		apply_serial_status_to_wheel(serial_no, status, warehouse)


def apply_serial_status_to_wheel(serial_no: str, status: str, warehouse: str | None):
	"""Map a Serial No's real ERPNext status back onto Wheel.status/warehouse, reusing
	wheel.py's own transition functions — never write status/warehouse directly here."""
	if status in RETIRING_STATUSES:
		retire_wheel(serial_no, f"Removed from stock via a {status.lower()} stock transaction.")
	elif status == "Active":
		reinstate_wheel(serial_no)
		sync_wheel_warehouse(serial_no, warehouse)

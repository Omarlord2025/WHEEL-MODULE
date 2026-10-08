# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Shared helpers for attaching real ERPNext serial numbers to a Stock Entry row —
used by the Material Receipt hook (stock_entry_hooks.py), Wheel Retirement's Material
Issue, and the opening-stock backfill patch. See PRD v10."""

import frappe


def build_serial_bundle(item_code: str, warehouse: str, serial_nos: list[str], type_of_transaction: str, company: str, voucher_type: str = "Stock Entry"):
	"""Build (but don't submit) a Serial and Batch Bundle for the given serial numbers,
	via ERPNext's own erpnext.stock.serial_batch_bundle.SerialBatchCreation — the same
	mechanism erpnext's own stock_entry_utils.make_stock_entry test helper uses.
	Auto-creates the underlying Serial No documents for any code that doesn't exist yet.

	type_of_transaction: "Inward" (Material Receipt) or "Outward" (Material Issue).
	Returns the unsubmitted Serial and Batch Bundle document.
	"""
	from erpnext.stock.serial_batch_bundle import SerialBatchCreation

	qty = len(serial_nos) * (1 if type_of_transaction == "Inward" else -1)
	creation = SerialBatchCreation(
		{
			"item_code": item_code,
			"warehouse": warehouse,
			"voucher_type": voucher_type,
			"total_qty": qty,
			"type_of_transaction": type_of_transaction,
			"company": company,
			"do_not_submit": True,
			# Required so SerialBatchCreation.make_serial_nos() actually creates the
			# Serial No docs for codes that don't exist yet, rather than throwing
			# LinkValidationError — confirmed empirically, not documented behavior.
			"use_serial_batch_fields": 1,
			"batches": {},
		}
	)
	return creation.make_serial_and_batch_bundle(serial_nos=serial_nos)


def get_row_or_sle_serial_nos(doc) -> list[str]:
	"""Serial numbers on a Stock Entry Detail row or a Stock Ledger Entry, covering
	both the Serial and Batch Bundle path and the legacy serial_no text-field path."""
	if doc.serial_and_batch_bundle:
		return frappe.get_all(
			"Serial and Batch Entry", filters={"parent": doc.serial_and_batch_bundle}, pluck="serial_no"
		)
	if doc.serial_no:
		from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos

		return get_serial_nos(doc.serial_no)
	return []

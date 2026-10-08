# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Renames the doctype (table, Link options everywhere it's referenced) before migrate's
own DocType JSON sync runs — see PRD v10 for why Wheel Usability Check became Wheel
Retirement. No real records exist under the old name in production, but this stays
guarded/idempotent regardless."""

import frappe


def execute():
	if frappe.db.exists("DocType", "Wheel Usability Check") and not frappe.db.exists(
		"DocType", "Wheel Retirement"
	):
		frappe.rename_doc("DocType", "Wheel Usability Check", "Wheel Retirement", force=True)
		frappe.clear_cache(doctype="Wheel Retirement")

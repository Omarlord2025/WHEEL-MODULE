# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Renames the Workspace before migrate's own fixture sync runs — see PRD v13. Workspace
JSON isn't content-hash-checked like DocType JSON; it's upserted by `name`, so editing
the JSON's name/label alone would leave the old "Wheel Tracker" workspace behind as an
orphan and create a new "Grinding Wheels" one instead of renaming in place. Mirrors
rename_wheel_usability_check_to_wheel_retirement's pre_model_sync placement and
idempotency guard."""

import frappe


def execute():
	if frappe.db.exists("Workspace", "Wheel Tracker") and not frappe.db.exists(
		"Workspace", "Grinding Wheels"
	):
		frappe.rename_doc("Workspace", "Wheel Tracker", "Grinding Wheels", force=True)
		frappe.clear_cache(doctype="Workspace")

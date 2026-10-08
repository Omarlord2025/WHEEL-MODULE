# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Backs the Language Toggle button on the Grinding Wheels workspace (see PRD v13) — a
Custom HTML Block, created by patches/create_language_toggle_block.py, whose script
calls toggle_language() below."""

import frappe

ARABIC = "ar"
ENGLISH = "en"


@frappe.whitelist()
def toggle_language() -> str:
	"""Flip the current session user's own Desk language between Arabic and English.
	Only ever touches frappe.session.user's own record — safe to call from any
	logged-in user, no special permission needed. Returns the new language code."""
	current = frappe.db.get_value("User", frappe.session.user, "language") or ENGLISH
	new_language = ENGLISH if current == ARABIC else ARABIC
	frappe.db.set_value("User", frappe.session.user, "language", new_language)
	return new_language

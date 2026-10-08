# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.translate import get_translations_from_csv


@frappe.whitelist()
def get_language_state():
	"""Backs `public/js/wheel_tracker_language.js`, which wraps the client's own global
	`__()` to intercept *only* the exact strings this module defines in
	`translations/ar.csv` — nothing else. Deliberately doesn't touch System Settings or
	any User's own `language` field: those are whole-site/every-user settings, and
	switching Arabic on for Wheel Tracker specifically must not flip either, per explicit
	customer rejection of an earlier version that did. Every Desk session asks this fresh
	on load, so there's nothing cached server-side to go stale, and no RTL/system-wide
	effect of any kind — a user with their own language already set to something else is
	completely unaffected outside of this module's own strings."""
	language = frappe.db.get_single_value("Wheel Tracker Settings", "language") or "English"
	dictionary = get_translations_from_csv("ar", "wheel_tracker") if language == "Arabic" else {}
	return {"language": language, "dictionary": dictionary}

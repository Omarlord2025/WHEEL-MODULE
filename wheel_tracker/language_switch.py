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


def get_current_lang_code() -> str:
	"""`"ar"`/`"en"` matching this module's own `Wheel Tracker Settings.language` flag —
	deliberately independent of `frappe.local.lang` (session/System Settings), same as
	`get_language_state()` above. `frappe.db.get_single_value` is itself cache-backed, so
	calling this once per `_()` call within a request (`get_columns()` does it ~8 times)
	isn't a fresh query each time."""
	language = frappe.db.get_single_value("Wheel Tracker Settings", "language") or "English"
	return "ar" if language == "Arabic" else "en"


def _(msg: str, context: str | None = None) -> str:
	"""Drop-in replacement for `from frappe import _` throughout this app's own Python
	code. Plain `frappe._()` translates using `frappe.local.lang` — the real session/site
	language, which this feature deliberately never touches — so every server-computed
	string (report column labels built in `get_columns()`, any `frappe.throw(_("..."))`
	validation message) would otherwise always render in whatever the session's actual
	language is, completely ignoring this module's own switch. `frappe._()` accepts an
	explicit `lang=` override with no side effect on session state at all (confirmed:
	`local.lang` is only read, never written, when `lang` is passed) — so this just pins
	that override to our own flag instead. Import this instead of Frappe's own `_` in any
	new file that throws/prints/labels user-facing text; `from frappe import _` silently
	skips this module's language switch entirely."""
	return frappe._(msg, lang=get_current_lang_code(), context=context)

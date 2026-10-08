# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

LANGUAGE_CODES = {"English": "en", "Arabic": "ar"}


class WheelTrackerSettings(Document):
	def on_update(self):
		self.apply_language()

	def apply_language(self):
		"""Frappe has no concept of a per-module display language — switching it is
		always a whole-site, every-user setting. This Single is just where staff are
		meant to flip that switch instead of leaving it buried in System Settings, so
		flipping it here deliberately touches System Settings and every User row.
		Re-applied on every save (idempotent) rather than only when self.language looks
		changed, so a save interrupted partway through a prior rollout still finishes."""
		lang_code = LANGUAGE_CODES.get(self.language)
		if not lang_code:
			return
		frappe.db.set_single_value("System Settings", "language", lang_code)
		frappe.db.sql("update `tabUser` set language = %s", lang_code)
		frappe.clear_cache()


def get_usable_volume_fraction(floor_percent_override: float | None = None) -> float:
	"""Fraction of volume treated as usable, after excluding the usable volume floor.

	Pass a Wheel Type's own `usable_volume_floor_percent` (if it has one set) as
	`floor_percent_override` to use that instead of the global Wheel Tracker Settings
	default (10% if neither is set) — see Wheel Type for where that override lives."""
	floor_percent = flt(floor_percent_override) or (
		frappe.db.get_single_value("Wheel Tracker Settings", "usable_volume_floor_percent") or 10
	)
	return (100 - floor_percent) / 100

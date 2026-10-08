# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class WheelTrackerSettings(Document):
	pass


def get_usable_volume_fraction(floor_percent_override: float | None = None) -> float:
	"""Fraction of volume treated as usable, after excluding the usable volume floor.

	Pass a Wheel Type's own `usable_volume_floor_percent` (if it has one set) as
	`floor_percent_override` to use that instead of the global Wheel Tracker Settings
	default (10% if neither is set) — see Wheel Type for where that override lives."""
	floor_percent = flt(floor_percent_override) or (
		frappe.db.get_single_value("Wheel Tracker Settings", "usable_volume_floor_percent") or 10
	)
	return (100 - floor_percent) / 100

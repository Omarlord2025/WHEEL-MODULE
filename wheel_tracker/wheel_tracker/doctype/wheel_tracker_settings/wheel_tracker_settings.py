# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WheelTrackerSettings(Document):
	pass


def get_usable_volume_fraction() -> float:
	"""Fraction of volume treated as usable, after excluding the configured floor (default 10%)."""
	floor_percent = (
		frappe.db.get_single_value("Wheel Tracker Settings", "usable_volume_floor_percent") or 10
	)
	return (100 - floor_percent) / 100

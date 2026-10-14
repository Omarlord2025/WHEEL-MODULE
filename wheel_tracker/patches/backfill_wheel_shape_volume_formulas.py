# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Fills Wheel Shape.volume_formula (PRD v24) on every pre-existing Wheel Shape record,
using the same default formula text calculate_wheel_volume() always used in Python
before this version — so nothing changes behaviorally for existing shapes until
someone deliberately edits one. New shapes created after this patch get their
default from WheelShape.validate() itself; this only covers rows that predate the
field existing at all. Also backfills the new requires_correction_factor fetch_from
field on the same rows — fetch_from only populates on save, so every pre-existing
Shape would otherwise read it as blank/0 regardless of its real Wheel Geometry
(calculate_wheel_volume() itself no longer trusts this field for that reason, reading
Wheel Geometry directly instead — but Wheel Shape's own validate() still uses it to
self-check a newly-entered formula, so it has to be correct too). Idempotent — skips
any row that already has a formula."""

import frappe

from wheel_tracker.wheel_tracker.doctype.wheel_shape.wheel_shape import (
	DEFAULT_FLAT_FORMULA,
	DEFAULT_SEGMENT_FORMULA,
)


def execute():
	frappe.db.sql(
		"""
		update `tabWheel Shape` ws
		inner join `tabWheel Geometry` wg on wg.name = ws.wheel_geometry
		set ws.requires_correction_factor = wg.requires_correction_factor
		"""
	)

	for shape in frappe.get_all(
		"Wheel Shape", fields=["name", "volume_formula", "requires_correction_factor"]
	):
		if shape.volume_formula:
			continue
		formula = (
			DEFAULT_SEGMENT_FORMULA if shape.requires_correction_factor else DEFAULT_FLAT_FORMULA
		)
		frappe.db.set_value("Wheel Shape", shape.name, "volume_formula", formula)

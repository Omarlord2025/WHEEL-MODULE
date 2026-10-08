# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Seeds the classification master doctypes with the values actually found in
`Main data and flow.xlsx` (see PRD v3), so a fresh install already has a working
set of dropdowns instead of an empty list on every Wheel Type field."""

import frappe

WHEEL_GEOMETRIES = [
	{"geometry_name": "Flat / Straight", "requires_correction_factor": 0},
	{"geometry_name": "Profiled / Angled", "requires_correction_factor": 1},
]

WHEEL_MATERIALS = [
	{"material_name": "Diamond", "factory_code_letter": "D"},
	{"material_name": "CBN", "factory_code_letter": "B"},
]

WHEEL_SHAPES = [
	# Flat/straight — exact annulus formula.
	{"shape_code": "1A1", "wheel_geometry": "Flat / Straight"},
	# P-series slitting/cutting-off wheels aren't tracked by graduated caliper wear at
	# all per the shop floor (see PRD v9) — they're simply usable or not usable, so
	# Measurement Event is blocked for them; Wheel Retirement is used instead.
	{
		"shape_code": "P1.5",
		"wheel_geometry": "Flat / Straight",
		"requires_measurement": 0,
		"description": "Thin slitting/cutting-off wheel, ~1.5mm width. Tracked usable/not-usable, not by measurement.",
	},
	{
		"shape_code": "P1.7",
		"wheel_geometry": "Flat / Straight",
		"requires_measurement": 0,
		"description": "Thin slitting/cutting-off wheel, ~1.7mm width. Tracked usable/not-usable, not by measurement.",
	},
	{
		"shape_code": "P2",
		"wheel_geometry": "Flat / Straight",
		"requires_measurement": 0,
		"description": "Thin slitting/cutting-off wheel, ~2mm width. Tracked usable/not-usable, not by measurement.",
	},
	# Profiled — conical-frustum-ring formula, driven by each Wheel Type's own Angle
	# (the same base shape can be cut at different angles, e.g. 1V1/45 vs 1V1/60 — see PRD v6).
	{"shape_code": "12V9", "wheel_geometry": "Profiled / Angled"},
	{"shape_code": "11V9", "wheel_geometry": "Profiled / Angled"},
	{"shape_code": "1V1", "wheel_geometry": "Profiled / Angled"},
]


def seed_master_data():
	for row in WHEEL_GEOMETRIES:
		get_or_create("Wheel Geometry", row)
	for row in WHEEL_MATERIALS:
		get_or_create("Wheel Material", row)
	for row in WHEEL_SHAPES:
		get_or_create("Wheel Shape", row)


def get_or_create(doctype: str, values: dict):
	name_field = frappe.get_meta(doctype).autoname.split(":")[1]
	if frappe.db.exists(doctype, values[name_field]):
		return
	frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)

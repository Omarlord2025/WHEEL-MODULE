# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""One-time fix-up for sites where P1.5/P1.7/P2 were seeded before Requires Measurement
existed (default 1, per the new field) — get_or_create in seed_master_data.py only
touches new records, so already-seeded P-series rows need setting explicitly. See PRD v9."""

import frappe

P_SERIES_SHAPES = ("P1.5", "P1.7", "P2")


def execute():
	for shape in P_SERIES_SHAPES:
		if frappe.db.exists("Wheel Shape", shape):
			frappe.db.set_value("Wheel Shape", shape, "requires_measurement", 0)

	# Wheel Type.requires_measurement is fetch_from shape — but fetch_from only refreshes
	# when a Wheel Type record is itself saved, which won't happen automatically for
	# already-imported records, so set it directly here too.
	frappe.db.set_value(
		"Wheel Type", {"shape": ["in", P_SERIES_SHAPES]}, "requires_measurement", 0
	)

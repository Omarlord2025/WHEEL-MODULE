# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Fills the new Wheel Type.item_name fetch_from field (for easier reading than the
raw Item code) on every pre-existing Wheel Type — fetch_from only populates on save,
so every row that predates this field would otherwise show blank regardless of its
real Item's name."""

import frappe


def execute():
	frappe.db.sql(
		"""
		update `tabWheel Type` wt
		inner join `tabItem` i on i.name = wt.item
		set wt.item_name = i.item_name
		"""
	)

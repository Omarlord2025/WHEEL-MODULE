# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Fills the new Wheel Type.start_numbering_from field (now reqd: 1) on every
pre-existing Wheel Type with 1 — today's existing auto-numbering behavior, so
nothing changes for a Wheel Type until someone deliberately raises it."""

import frappe


def execute():
	frappe.db.sql(
		"""
		update `tabWheel Type`
		set start_numbering_from = 1
		where start_numbering_from is null or start_numbering_from = 0
		"""
	)

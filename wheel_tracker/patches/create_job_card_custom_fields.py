# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe

from wheel_tracker.setup.custom_fields import create_wheel_tracker_custom_fields


def execute():
	create_wheel_tracker_custom_fields()
	# Persist the JSON defaults to tabSingles so db.get_single_value() sees them
	# immediately, instead of only after someone opens and saves the settings page.
	frappe.get_single("Wheel Tracker Settings").save()

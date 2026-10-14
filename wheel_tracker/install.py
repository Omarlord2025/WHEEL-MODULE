# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe

from wheel_tracker.setup.custom_fields import create_wheel_tracker_custom_fields
from wheel_tracker.setup.seed_master_data import seed_master_data


def after_install():
	create_wheel_tracker_custom_fields()
	# Persist the JSON defaults to tabSingles so db.get_single_value() sees them
	# immediately, instead of only after someone opens and saves the settings page.
	frappe.get_single("Wheel Tracker Settings").save()
	seed_master_data()


def before_tests():
	"""Pin Wheel Tracker Settings.language to English before the suite runs. Since v21,
	every server-side `_()` call in this app's own code (wheel_tracker.language_switch._)
	respects this Single's value, independent of frappe.local.lang/System Settings —
	so a test asserting a literal English string (e.g. retirement_reason containing
	"Auto-retired") would otherwise pass or fail depending on whatever a human last left
	this set to interactively on this site, which is exactly the kind of ambient global
	state a test suite shouldn't depend on."""
	frappe.db.set_single_value("Wheel Tracker Settings", "language", "English")

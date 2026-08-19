# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel, make_wheel_type


class TestWheelUsabilityCheck(FrappeTestCase):
	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(
				shape="P2", original_diameter=125, original_inner_diameter=104.9, original_diamond_height=2
			)
		)
		self.wheel = make_wheel(self.wheel_type.name)

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def make_check(self, **kwargs):
		values = {
			"doctype": "Wheel Usability Check",
			"wheel": self.wheel.name,
			"check_date": frappe.utils.now_datetime(),
			"checked_by": frappe.session.user,
			"usable": 1,
		}
		values.update(kwargs)
		doc = frappe.get_doc(values).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def test_not_usable_retires_the_wheel(self):
		self.make_check(usable=0, retirement_reason="Chipped edge")
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")
		self.assertEqual(self.wheel.retirement_reason, "Chipped edge")

	def test_reason_required_when_not_usable(self):
		self.assertRaises(frappe.MandatoryError, self.make_check, usable=0)

	def test_usable_reinstates_a_previously_retired_wheel(self):
		self.make_check(usable=0, retirement_reason="Looked worn")
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")

		self.make_check(usable=1)
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")

	def test_cancel_reapplies_previous_checks_verdict(self):
		self.make_check(usable=1)
		second = self.make_check(usable=0, retirement_reason="Cracked")
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")

		second.cancel()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")

	def test_cancel_with_no_history_left_reinstates(self):
		check = self.make_check(usable=0, retirement_reason="Cracked")
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")

		check.cancel()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")

	def test_measurement_event_still_rejected_after_a_usable_check(self):
		from wheel_tracker.test_helpers import make_measurement_event

		self.make_check(usable=1)
		self.assertRaises(frappe.ValidationError, make_measurement_event, self.wheel.name)

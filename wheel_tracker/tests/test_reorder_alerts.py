# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.reorder_alerts import check_reorder_levels
from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel, make_wheel_type


class TestReorderAlerts(FrappeTestCase):
	def setUp(self):
		self._created = []

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)
		frappe.db.delete("Notification Log", {"document_type": "Wheel Type", "document_name": ["in", self._created]})

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def test_alert_raised_and_flagged_when_below_reorder_point(self):
		wheel_type = self.track(
			make_wheel_type(
				original_diameter=100, original_inner_diameter=60, original_diamond_height=6, reorder_point=2
			)
		)
		make_wheel(wheel_type.name)  # only 1 In Stock, below the reorder point of 2

		check_reorder_levels()

		wheel_type.reload()
		self.assertTrue(wheel_type.reorder_alert_active)
		self.assertTrue(wheel_type.last_reorder_alert_on)
		notifications = frappe.get_all(
			"Notification Log", filters={"document_type": "Wheel Type", "document_name": wheel_type.name}
		)
		self.assertTrue(notifications)

	def test_no_alert_when_above_reorder_point(self):
		wheel_type = self.track(
			make_wheel_type(
				original_diameter=100, original_inner_diameter=60, original_diamond_height=6, reorder_point=1
			)
		)
		make_wheel(wheel_type.name)
		make_wheel(wheel_type.name)  # 2 In Stock, at/above the reorder point of 1

		check_reorder_levels()

		wheel_type.reload()
		self.assertFalse(wheel_type.reorder_alert_active)

	def test_alert_flag_clears_once_restocked(self):
		wheel_type = self.track(
			make_wheel_type(
				original_diameter=100, original_inner_diameter=60, original_diamond_height=6, reorder_point=2
			)
		)
		make_wheel(wheel_type.name)
		check_reorder_levels()
		wheel_type.reload()
		self.assertTrue(wheel_type.reorder_alert_active)

		make_wheel(wheel_type.name)
		make_wheel(wheel_type.name)
		check_reorder_levels()
		wheel_type.reload()
		self.assertFalse(wheel_type.reorder_alert_active)

	def test_dedupe_does_not_recreate_notifications_while_still_active(self):
		wheel_type = self.track(
			make_wheel_type(
				original_diameter=100, original_inner_diameter=60, original_diamond_height=6, reorder_point=2
			)
		)
		make_wheel(wheel_type.name)

		check_reorder_levels()
		first_count = frappe.db.count(
			"Notification Log", {"document_type": "Wheel Type", "document_name": wheel_type.name}
		)
		check_reorder_levels()
		second_count = frappe.db.count(
			"Notification Log", {"document_type": "Wheel Type", "document_name": wheel_type.name}
		)
		self.assertEqual(first_count, second_count)

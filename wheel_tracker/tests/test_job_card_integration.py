# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.job_card_integration import release_all_wheels_for_job, sync_wheel_assignments
from wheel_tracker.test_helpers import (
	cleanup_wheel_tracker_records,
	make_job_card,
	make_measurement_event,
	make_wheel,
	make_wheel_type,
)


class TestJobCardIntegration(FrappeTestCase):
	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6)
		)

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def test_adding_a_row_assigns_the_wheel(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()

		job_card.append("custom_wheels_used", {"wheel": wheel.name})
		job_card.save()

		wheel.reload()
		self.assertEqual(wheel.status, "In Use")
		self.assertEqual(wheel.current_job_card, job_card.name)

	def test_removing_a_row_releases_the_wheel(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": wheel.name})
		job_card.save()

		job_card.custom_wheels_used = []
		job_card.save()

		wheel.reload()
		self.assertEqual(wheel.status, "In Stock")
		self.assertFalse(wheel.current_job_card)

	def test_cannot_assign_a_wheel_already_in_use_elsewhere(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card_1 = make_job_card()
		job_card_2 = make_job_card()

		job_card_1.append("custom_wheels_used", {"wheel": wheel.name})
		job_card_1.save()

		job_card_2.append("custom_wheels_used", {"wheel": wheel.name})
		self.assertRaises(frappe.ValidationError, job_card_2.save)

	def test_retired_wheel_cannot_be_assigned(self):
		wheel = make_wheel(self.wheel_type.name, status="Retired")
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": wheel.name})
		self.assertRaises(frappe.ValidationError, job_card.save)

	def test_release_all_wheels_for_job_returns_them_to_stock(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": wheel.name})
		job_card.save()

		release_all_wheels_for_job(job_card.name)

		wheel.reload()
		self.assertEqual(wheel.status, "In Stock")

	def test_wheel_wear_cost_rolls_up_into_work_order_additional_operating_cost(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": wheel.name})
		job_card.save()
		event = make_measurement_event(wheel.name, diameter=90)

		work_order = frappe.db.get_value("Job Card", job_card.name, "work_order")
		additional_operating_cost, total_operating_cost = frappe.db.get_value(
			"Work Order", work_order, ["additional_operating_cost", "total_operating_cost"]
		)
		self.assertAlmostEqual(additional_operating_cost, event.job_cost, places=4)
		self.assertGreaterEqual(total_operating_cost, additional_operating_cost)

	def test_cancelling_measurement_event_reduces_work_order_cost(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": wheel.name})
		job_card.save()
		event = make_measurement_event(wheel.name, diameter=90)
		work_order = frappe.db.get_value("Job Card", job_card.name, "work_order")

		event.cancel()

		additional_operating_cost = frappe.db.get_value("Work Order", work_order, "additional_operating_cost")
		self.assertAlmostEqual(additional_operating_cost, 0, places=4)

	def test_sync_hook_releases_wheels_when_status_is_completed(self):
		"""Job Card's own controller drives status through set_status() based on real
		completion state, which is heavy to reproduce here — so this exercises the
		on_update hook function directly with a Completed status, the same way Frappe
		calls it, rather than fighting ERPNext's manufacturing validation to get there."""
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": wheel.name})
		job_card.save()

		fake_doc = frappe.new_doc("Job Card")
		fake_doc.name = job_card.name
		fake_doc.status = "Completed"
		sync_wheel_assignments(fake_doc)

		wheel.reload()
		self.assertEqual(wheel.status, "In Stock")

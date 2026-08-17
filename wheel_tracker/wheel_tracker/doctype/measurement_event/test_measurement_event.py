# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import (
	cleanup_wheel_tracker_records,
	make_job_card,
	make_measurement_event,
	make_wheel,
	make_wheel_type,
)
from wheel_tracker.wheel_tracker.doctype.wheel_type.wheel_type import calculate_wheel_volume


class TestMeasurementEvent(FrappeTestCase):
	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6)
		)
		self.wheel = make_wheel(self.wheel_type.name)

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def expected_volume(self, diameter):
		"""confirmed_volume is computed from `diameter` alone — inner diameter/height/angle
		stay at the Wheel Type's constant original values (see PRD v6)."""
		return calculate_wheel_volume(
			diameter,
			self.wheel_type.original_inner_diameter,
			self.wheel_type.original_diamond_height,
			self.wheel_type.requires_correction_factor,
			self.wheel_type.angle,
		)

	def test_confirmed_volume_is_computed_from_diameter(self):
		event = make_measurement_event(self.wheel.name, diameter=90)
		self.assertAlmostEqual(event.confirmed_volume, self.expected_volume(90), places=2)

	def test_first_event_incremental_equals_consumed(self):
		event = make_measurement_event(self.wheel.name, diameter=90)
		self.assertAlmostEqual(event.consumed_volume, event.incremental_consumed_volume, places=3)
		self.assertAlmostEqual(event.previous_consumed_volume, 0, places=3)

	def test_incremental_is_delta_since_last_measurement(self):
		make_measurement_event(self.wheel.name, diameter=95)
		second = make_measurement_event(self.wheel.name, diameter=85)
		expected_incremental = second.consumed_volume - second.previous_consumed_volume
		self.assertAlmostEqual(second.incremental_consumed_volume, expected_incremental, places=3)
		self.assertGreater(second.incremental_consumed_volume, 0)

	def test_job_cost_uses_wheel_type_cost_per_mm3(self):
		event = make_measurement_event(self.wheel.name, diameter=90)
		# Compare against the DB-rounded cost_per_mm3 (what the controller itself reads via
		# get_cached_doc), not self.wheel_type's raw in-memory value from before its round-trip.
		cost_per_mm3 = frappe.db.get_value("Wheel Type", self.wheel_type.name, "cost_per_mm3")
		expected = event.incremental_consumed_volume * cost_per_mm3
		self.assertAlmostEqual(event.job_cost, expected, places=2)

	def test_submit_applies_readings_to_wheel(self):
		event = make_measurement_event(
			self.wheel.name,
			diameter=95,
			inner_diameter=60,
			diamond_height=5,
		)
		self.wheel.reload()
		self.assertEqual(self.wheel.current_diameter, 95)
		self.assertAlmostEqual(self.wheel.current_volume, event.confirmed_volume, places=2)

	def test_submit_triggers_retirement_and_cancel_reverts_it(self):
		# diameter == inner diameter -> exact-annulus volume is 0.
		event = make_measurement_event(self.wheel.name, diameter=60)
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")
		self.assertTrue(event.triggered_retirement)

		event.cancel()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")
		self.assertAlmostEqual(self.wheel.current_volume, self.wheel_type.original_volume, places=2)

	def test_cancel_reverts_to_previous_measurement_not_original(self):
		first = make_measurement_event(self.wheel.name, diameter=92)
		second = make_measurement_event(self.wheel.name, diameter=80)

		second.cancel()
		self.wheel.reload()
		self.assertAlmostEqual(self.wheel.current_volume, first.confirmed_volume, places=2)

	def test_job_card_rollup_updates_on_submit_and_cancel(self):
		job_card = make_job_card()
		event = make_measurement_event(self.wheel.name, job_card=job_card.name, diameter=90)
		self.assertAlmostEqual(
			frappe.db.get_value("Job Card", job_card.name, "custom_wheel_wear_cost"), event.job_cost, places=4
		)

		event.cancel()
		self.assertAlmostEqual(frappe.db.get_value("Job Card", job_card.name, "custom_wheel_wear_cost"), 0, places=4)

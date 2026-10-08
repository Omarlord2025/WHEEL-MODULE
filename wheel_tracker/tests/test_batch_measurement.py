# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from wheel_tracker.batch_measurement import get_wheels_used_between, submit_batch_measurements
from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_job_card, make_wheel, make_wheel_type


class TestBatchMeasurement(FrappeTestCase):
	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6)
		)
		self.from_date = add_days(today(), -7)
		self.to_date = today()

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def assign(self, job_card, wheel_name, posting_date=None):
		job_card.reload()
		job_card.append("custom_wheels_used", {"wheel": wheel_name})
		job_card.save()
		if posting_date:
			frappe.db.set_value("Job Card", job_card.name, "posting_date", posting_date)

	def test_get_wheels_used_between_splits_measurable_and_non_measurable(self):
		p_series_type = self.track(
			make_wheel_type(
				shape="P1.5", original_diameter=100, original_inner_diameter=60, original_diamond_height=2
			)
		)
		measurable_wheel = make_wheel(self.wheel_type.name)
		non_measurable_wheel = make_wheel(p_series_type.name)
		job_card = make_job_card()
		self.assign(job_card, measurable_wheel.name, self.to_date)
		self.assign(job_card, non_measurable_wheel.name, self.to_date)

		result = get_wheels_used_between(self.from_date, self.to_date)

		# Membership, not exact-list equality, for job_cards: make_job_card()'s
		# Work Order fixture and Job Card aren't cleaned up between tests (a known,
		# pre-existing gap — cleanup_wheel_tracker_records only handles Wheel/Wheel
		# Type/Measurement Event/Wheel Retirement), so other tests' Job Cards dated
		# "today" can legitimately also fall in this range. Wheel names are always
		# unique per test, so the measurable/non_measurable lists stay exact.
		self.assertIn(job_card.name, result["job_cards"])
		self.assertEqual([r.wheel for r in result["measurable"]], [measurable_wheel.name])
		self.assertEqual([r.wheel for r in result["non_measurable"]], [non_measurable_wheel.name])

	def test_get_wheels_used_between_returns_empty_outside_the_job_cards_own_dates(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		self.assign(job_card, wheel.name, add_days(self.from_date, -30))

		result = get_wheels_used_between(self.from_date, self.to_date)

		self.assertNotIn(job_card.name, result["job_cards"])
		all_wheels = [r.wheel for r in result["measurable"] + result["non_measurable"]]
		self.assertNotIn(wheel.name, all_wheels)

	def test_get_wheels_used_between_excludes_already_measured_wheels(self):
		from wheel_tracker.test_helpers import make_measurement_event

		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		self.assign(job_card, wheel.name, self.to_date)

		make_measurement_event(wheel.name, diameter=95)

		result = get_wheels_used_between(self.from_date, self.to_date)

		self.assertIn(job_card.name, result["job_cards"])
		all_wheels = [r.wheel for r in result["measurable"] + result["non_measurable"]]
		self.assertNotIn(wheel.name, all_wheels)

	def test_get_wheels_used_between_excludes_retired_wheels(self):
		from wheel_tracker.wheel_tracker.doctype.wheel.wheel import retire_wheel

		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		self.assign(job_card, wheel.name, self.to_date)

		retire_wheel(wheel.name, "Chipped edge")

		result = get_wheels_used_between(self.from_date, self.to_date)

		self.assertIn(job_card.name, result["job_cards"])
		all_wheels = [r.wheel for r in result["measurable"] + result["non_measurable"]]
		self.assertNotIn(wheel.name, all_wheels)

	def test_submit_batch_measurements_creates_and_submits_events(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		self.assign(job_card, wheel.name)

		summary = submit_batch_measurements(
			[
				{
					"wheel": wheel.name,
					"diameter": 90,
					"inner_diameter": wheel.current_inner_diameter,
					"diamond_height": wheel.current_diamond_height,
				}
			],
		)

		self.assertEqual(summary["created"], 1)
		self.assertEqual(summary["errors"], [])

		wheel.reload()
		self.assertAlmostEqual(wheel.current_diameter, 90, places=3)

		event = frappe.get_all("Measurement Event", filters={"wheel": wheel.name}, fields=["docstatus", "name"])
		self.assertEqual(len(event), 1)
		self.assertEqual(event[0].docstatus, 1)

		linked_job_cards = frappe.get_all(
			"Measurement Event Job Card", filters={"parent": event[0].name}, pluck="job_card"
		)
		self.assertEqual(linked_job_cards, [job_card.name])

	def test_submit_batch_measurements_continues_past_bad_row(self):
		wheel = make_wheel(self.wheel_type.name)
		job_card = make_job_card()
		self.assign(job_card, wheel.name)

		summary = submit_batch_measurements(
			[
				{"wheel": "NONEXISTENT-WHEEL", "diameter": 90, "inner_diameter": 60, "diamond_height": 6},
				{
					"wheel": wheel.name,
					"diameter": 90,
					"inner_diameter": wheel.current_inner_diameter,
					"diamond_height": wheel.current_diamond_height,
				},
			],
		)

		self.assertEqual(summary["created"], 1)
		self.assertEqual(len(summary["errors"]), 1)
		self.assertEqual(summary["errors"][0]["wheel"], "NONEXISTENT-WHEEL")

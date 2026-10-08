# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from wheel_tracker.test_helpers import (
	cleanup_wheel_tracker_records,
	make_job_card,
	make_measurement_event,
	make_wheel,
	make_wheel_type,
	receive_wheel_via_material_receipt,
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
		"""confirmed_volume is computed from `diameter` alone — inner diameter/segments
		stay at the Wheel Type's constant original values (see PRD v6/v7)."""
		return calculate_wheel_volume(
			diameter,
			self.wheel_type.original_inner_diameter,
			self.wheel_type.original_diamond_height,
			self.wheel_type.requires_correction_factor,
			self.wheel_type.profile_segments,
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

	def test_cancel_reverts_to_previous_measurement_not_original(self):
		first = make_measurement_event(self.wheel.name, diameter=92)
		second = make_measurement_event(self.wheel.name, diameter=80)

		second.cancel()
		self.wheel.reload()
		self.assertAlmostEqual(self.wheel.current_volume, first.confirmed_volume, places=2)

	def test_job_card_rollup_updates_on_submit_and_cancel(self):
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": self.wheel.name})
		job_card.save()

		event = make_measurement_event(self.wheel.name, diameter=90)
		self.assertEqual(len(event.job_cards), 1)
		self.assertEqual(event.job_cards[0].job_card, job_card.name)
		self.assertAlmostEqual(
			frappe.db.get_value("Job Card", job_card.name, "custom_wheel_wear_cost"), event.job_cost, places=4
		)

		event.cancel()
		self.assertAlmostEqual(frappe.db.get_value("Job Card", job_card.name, "custom_wheel_wear_cost"), 0, places=4)

	def test_single_job_card_still_gets_full_allocation(self):
		job_card = make_job_card()
		job_card.append("custom_wheels_used", {"wheel": self.wheel.name})
		job_card.save()

		event = make_measurement_event(self.wheel.name, diameter=90)

		self.assertEqual(len(event.job_cards), 1)
		self.assertEqual(event.job_cards[0].job_card, job_card.name)
		self.assertAlmostEqual(event.job_cards[0].allocated_cost, event.job_cost, places=4)
		self.assertAlmostEqual(
			frappe.db.get_value("Job Card", job_card.name, "custom_wheel_wear_cost"), event.job_cost, places=4
		)

	def test_job_cards_split_equally_across_assignment_history(self):
		from wheel_tracker.wheel_tracker.doctype.wheel.wheel import release_from_job_card

		job_card_a = make_job_card()
		job_card_b = make_job_card()

		# Assign to Job Card A, then release it as a completed Job Card would (see
		# release_all_wheels_for_job) — releasing this way, rather than removing the row
		# from Job Card A's own grid and saving, leaves that Job Card Wheel row intact,
		# which is what makes it real assignment history and not a corrected mistake.
		job_card_a.append("custom_wheels_used", {"wheel": self.wheel.name})
		job_card_a.save()
		self.wheel.reload()
		self.assertEqual(self.wheel.current_job_card, job_card_a.name)

		release_from_job_card(self.wheel.name)
		self.wheel.reload()
		self.assertFalse(self.wheel.current_job_card)

		# Reassign to Job Card B.
		job_card_b.append("custom_wheels_used", {"wheel": self.wheel.name})
		job_card_b.save()

		event = make_measurement_event(self.wheel.name, diameter=90)

		linked = {row.job_card: row.allocated_cost for row in event.job_cards}
		self.assertEqual(set(linked), {job_card_a.name, job_card_b.name})
		half = flt(event.job_cost) / 2
		for cost in linked.values():
			self.assertAlmostEqual(cost, half, places=4)

		self.assertAlmostEqual(
			frappe.db.get_value("Job Card", job_card_a.name, "custom_wheel_wear_cost"), half, places=4
		)
		self.assertAlmostEqual(
			frappe.db.get_value("Job Card", job_card_b.name, "custom_wheel_wear_cost"), half, places=4
		)


class TestMeasurementEventBlockedForNonMeasuredShapes(FrappeTestCase):
	"""P-series slitting wheels are tracked usable/not-usable (Wheel Retirement),
	not by caliper measurement — Requires Measurement is unchecked on their Wheel Shape
	(seeded), so Measurement Event must refuse to be created against them. See PRD v9."""

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

	def test_measurement_event_is_rejected(self):
		self.assertRaises(frappe.ValidationError, make_measurement_event, self.wheel.name)


class TestMeasurementEventProfiled(FrappeTestCase):
	"""Single-bevel profiled wheels wear along the slope — unlike flat wheels, this
	measurement's own inner_diameter/diamond_height readings drive the volume, not the
	Wheel Type's original constants. Real-data ground truth from the decrypted "WHEELS
	WITH ANGLES" sheet (see PRD v8): a 1V1/45 wheel type (D=100, d=78.4, T=5, angle=45,
	original_volume=14284.19) measured later at diameter=84.45/inner=78.4/height=5 has a
	recorded current volume of 3631.46 — reproduced by this model to within 0.01%."""

	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(
				shape="1V1",
				original_diameter=100,
				original_inner_diameter=78.4,
				profile_segments=[{"angle": 45, "height": 5}],
			)
		)
		self.wheel = make_wheel(self.wheel_type.name)

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def test_confirmed_volume_uses_this_events_own_readings(self):
		event = make_measurement_event(
			self.wheel.name, diameter=84.45, inner_diameter=78.4, diamond_height=5
		)
		self.assertAlmostEqual(event.confirmed_volume, 3631.46, delta=1)


class TestMeasurementEventAutoRetirement(FrappeTestCase):
	"""Auto-retirement must now do more than flip Wheel.status — it has to create and
	submit a real Wheel Retirement + Material Issue, and reverse both on cancel. Needs a
	Wheel with a genuine Warehouse/Bin quantity (not the bare make_wheel() fixture used
	elsewhere in this file), since Wheel Retirement's Material Issue draws down real
	stock. See PRD v12."""

	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6)
		)
		self.wheel = receive_wheel_via_material_receipt(self.wheel_type.name)

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def test_submit_auto_creates_retirement_and_issues_stock(self):
		# diameter == inner diameter -> exact-annulus volume is 0 -> 100% consumption.
		event = make_measurement_event(self.wheel.name, diameter=60)

		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")
		self.assertTrue(event.triggered_retirement)
		self.assertTrue(event.auto_retirement)

		retirement = frappe.get_doc("Wheel Retirement", event.auto_retirement)
		self.assertEqual(retirement.docstatus, 1)
		self.assertEqual(retirement.wheel, self.wheel.name)
		self.assertTrue(retirement.stock_entry)
		self.assertEqual(frappe.db.get_value("Stock Entry", retirement.stock_entry, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Stock Entry", retirement.stock_entry, "purpose"), "Material Issue")

		bin_qty = frappe.db.get_value(
			"Bin", {"item_code": self.wheel_type.item, "warehouse": "_Test Warehouse - _TC"}, "actual_qty"
		)
		self.assertEqual(bin_qty, 0)

	def test_cancel_reverses_retirement_and_stock_entry(self):
		event = make_measurement_event(self.wheel.name, diameter=60)
		retirement_name = event.auto_retirement
		stock_entry_name = frappe.db.get_value("Wheel Retirement", retirement_name, "stock_entry")

		event.cancel()

		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")
		self.assertAlmostEqual(self.wheel.current_volume, self.wheel_type.original_volume, places=2)
		self.assertEqual(frappe.db.get_value("Wheel Retirement", retirement_name, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Stock Entry", stock_entry_name, "docstatus"), 2)

		bin_qty = frappe.db.get_value(
			"Bin", {"item_code": self.wheel_type.item, "warehouse": "_Test Warehouse - _TC"}, "actual_qty"
		)
		self.assertEqual(bin_qty, 1)

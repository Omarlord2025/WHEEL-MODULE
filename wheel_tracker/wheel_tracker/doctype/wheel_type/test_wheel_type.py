# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import math
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel_type
from wheel_tracker.wheel_tracker.doctype.wheel_type.wheel_type import calculate_wheel_volume


def _segments(angle_height_pairs):
	"""Plain stand-ins for Wheel Type Profile Segment rows — calculate_wheel_volume only
	reads .angle/.height, so a real child-table doc isn't needed for a pure-function test."""
	return [SimpleNamespace(angle=a, height=h) for a, h in angle_height_pairs]


class TestWheelType(FrappeTestCase):
	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def setUp(self):
		self._created = []

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def test_flat_wheel_volume_is_exact_annulus(self):
		st = self.track(
			make_wheel_type(
				shape="1A1", original_diameter=100, original_inner_diameter=60, original_diamond_height=6
			)
		)
		expected = (math.pi / 4) * (100**2 - 60**2) * 6
		self.assertAlmostEqual(st.original_volume, expected, places=2)
		self.assertFalse(st.requires_correction_factor)

	def test_slitting_wheel_shape_uses_the_same_flat_formula(self):
		"""P-series slitting/cutting wheels are geometrically flat annuli too (see PRD v3) —
		same exact formula as 1A1, just parameterized by width instead of height."""
		st = self.track(
			make_wheel_type(
				shape="P2", original_diameter=125, original_inner_diameter=104.9, original_diamond_height=2
			)
		)
		expected = (math.pi / 4) * (125**2 - 104.9**2) * 2
		self.assertAlmostEqual(st.original_volume, expected, places=1)

	def test_single_bevel_profiled_wheel_uses_ring_frustum_formula(self):
		"""Exact worked example from the "Volume equations for grinding wheels" PDF
		(1V1/45 Gash): Dob=100, Dib=78.4, angle=45deg, H=5 -> V=14284.19mm3 (see PRD v6).
		Confirms the Ring Frustum formula, not the old empirical correction factor."""
		st = self.track(
			make_wheel_type(
				shape="1V1",
				original_diameter=100,
				original_inner_diameter=78.4,
				profile_segments=[{"angle": 45, "height": 5}],
			)
		)
		self.assertTrue(st.requires_correction_factor)
		self.assertAlmostEqual(st.original_volume, 14284.19, places=1)
		self.assertAlmostEqual(st.original_diamond_height, 5, places=3)

	def test_stepped_profiled_wheel_sums_two_segments(self):
		"""11V9/12V9 are a compound/stepped profile — a main cone plus a separate chamfer
		near the bore, each with its own angle (confirmed against the physical wheels,
		see PRD v7). No independent worked example exists for this case (unlike 1V1
		above), so this checks internal consistency instead: splitting one segment's
		total taper into two identical half-segments must reproduce the exact same
		volume as computing it as a single segment (same net geometry, two integration
		steps) — proving the segment-chaining logic itself is sound."""
		one_segment = calculate_wheel_volume(100, 78.4, 5, "1V1", _segments([(45, 5)]))
		two_half_segments = calculate_wheel_volume(100, 78.4, 5, "1V1", _segments([(45, 2.5), (45, 2.5)]))
		self.assertAlmostEqual(one_segment, two_half_segments, places=6)

		st = self.track(
			make_wheel_type(
				shape="12V9",
				original_diameter=100,
				original_inner_diameter=60,
				profile_segments=[{"angle": 30, "height": 3}, {"angle": 20, "height": 4}],
			)
		)
		self.assertTrue(st.requires_correction_factor)
		self.assertAlmostEqual(st.original_diamond_height, 7, places=3)
		self.assertGreater(st.original_volume, 0)

	def test_profiled_wheel_requires_at_least_one_segment(self):
		self.assertRaises(
			frappe.ValidationError,
			make_wheel_type,
			shape="12V9",
			original_diameter=100,
			original_inner_diameter=60,
			original_diamond_height=20,
			profile_segments=[],
		)

	def test_usable_original_volume_applies_configured_floor(self):
		st = self.track(make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6))
		fraction = (
			100 - frappe.db.get_single_value("Wheel Tracker Settings", "usable_volume_floor_percent")
		) / 100
		self.assertAlmostEqual(st.usable_original_volume, st.original_volume * fraction, places=2)

	def test_usable_original_volume_uses_own_floor_override_when_set(self):
		global_floor = frappe.db.get_single_value("Wheel Tracker Settings", "usable_volume_floor_percent")
		override_floor = flt(global_floor) + 15  # deliberately different from the global default
		st = self.track(
			make_wheel_type(
				original_diameter=100,
				original_inner_diameter=60,
				original_diamond_height=6,
				usable_volume_floor_percent=override_floor,
			)
		)
		expected = st.original_volume * (100 - override_floor) / 100
		self.assertAlmostEqual(st.usable_original_volume, expected, places=2)
		self.assertNotAlmostEqual(
			st.usable_original_volume,
			st.original_volume * (100 - flt(global_floor)) / 100,
			places=2,
		)

	def test_usable_original_volume_falls_back_to_global_floor_when_blank(self):
		st = self.track(
			make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6)
		)
		fraction = (
			100 - frappe.db.get_single_value("Wheel Tracker Settings", "usable_volume_floor_percent")
		) / 100
		self.assertAlmostEqual(st.usable_original_volume, st.original_volume * fraction, places=2)

	def test_cost_per_mm3_derived_from_unit_cost(self):
		st = self.track(
			make_wheel_type(
				original_diameter=100, original_inner_diameter=60, original_diamond_height=6, unit_cost=900
			)
		)
		self.assertAlmostEqual(st.cost_per_mm3, 900 / st.usable_original_volume, places=6)

	def test_manual_override_skips_auto_calc(self):
		st = self.track(
			make_wheel_type(
				original_diameter=100,
				original_inner_diameter=60,
				original_diamond_height=6,
				auto_calc_volume=0,
				original_volume=12345,
			)
		)
		self.assertEqual(st.original_volume, 12345)

	def test_inner_diameter_must_be_smaller_than_diameter(self):
		self.assertRaises(
			frappe.ValidationError,
			make_wheel_type,
			original_diameter=60,
			original_inner_diameter=100,
			original_diamond_height=6,
		)

	def test_new_wheel_type_serializes_its_item(self):
		st = self.track(make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6))
		self.assertTrue(frappe.db.get_value("Item", st.item, "has_serial_no"))

	def test_throws_if_item_has_submitted_stock_and_cant_be_serialized(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		from wheel_tracker.test_helpers import make_item

		item_code = make_item()
		frappe.db.set_value("Item", item_code, "has_serial_no", 0)
		make_stock_entry(item_code=item_code, qty=1, to_warehouse="_Test Warehouse - _TC", purpose="Material Receipt")

		self.assertRaises(
			frappe.ValidationError,
			make_wheel_type,
			item=item_code,
			original_diameter=100,
			original_inner_diameter=60,
			original_diamond_height=6,
		)

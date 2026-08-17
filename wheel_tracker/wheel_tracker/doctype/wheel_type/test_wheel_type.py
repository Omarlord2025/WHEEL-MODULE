# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import math

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel_type


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

	def test_profiled_wheel_uses_ring_frustum_formula(self):
		"""Exact worked example from the "Volume equations for grinding wheels" PDF
		(1V1/45 Gash): Dob=100, Dib=78.4, angle=45deg, H=5 -> V=14284.19mm3 (see PRD v6).
		Confirms the Ring Frustum formula, not the old empirical correction factor."""
		st = self.track(
			make_wheel_type(
				shape="1V1",
				original_diameter=100,
				original_inner_diameter=78.4,
				original_diamond_height=5,
				angle=45,
			)
		)
		self.assertTrue(st.requires_correction_factor)
		self.assertAlmostEqual(st.original_volume, 14284.19, places=1)

	def test_profiled_wheel_requires_angle(self):
		self.assertRaises(
			frappe.ValidationError,
			make_wheel_type,
			shape="12V9",
			original_diameter=100,
			original_inner_diameter=60,
			original_diamond_height=20,
		)

	def test_usable_original_volume_applies_configured_floor(self):
		st = self.track(make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6))
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

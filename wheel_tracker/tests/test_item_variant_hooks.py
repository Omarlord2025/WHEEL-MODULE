# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records


class TestItemVariantHooks(FrappeTestCase):
	def setUp(self):
		self._created_types = []
		self._created_items = []

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created_types)
		for item_code in self._created_items:
			frappe.delete_doc("Item", item_code, force=True, ignore_permissions=True)

	def make_variant(self, args):
		from erpnext.controllers.item_variant import create_variant

		variant = create_variant("GRINDING-WHEEL-TEMPLATE", args)
		variant.item_group = "All Item Groups"
		variant.insert(ignore_permissions=True)
		self._created_items.append(variant.name)
		return variant

	def test_flat_variant_auto_creates_matching_wheel_type(self):
		variant = self.make_variant(
			{"Shape": "1A1", "Material": "Diamond", "Diameter": "100", "Inner Diameter": "60", "Height": "6"}
		)
		self._created_types.append(variant.name)

		wheel_type = frappe.get_doc("Wheel Type", variant.name)
		self.assertEqual(wheel_type.item, variant.name)
		self.assertEqual(wheel_type.shape, "1A1")
		self.assertEqual(wheel_type.material, "Diamond")
		self.assertAlmostEqual(wheel_type.original_diameter, 100, places=2)
		self.assertAlmostEqual(wheel_type.original_inner_diameter, 60, places=2)
		self.assertAlmostEqual(wheel_type.original_diamond_height, 6, places=2)
		self.assertFalse(wheel_type.requires_correction_factor)

	def test_profiled_variant_auto_creates_a_profile_segment(self):
		variant = self.make_variant(
			{
				"Shape": "1V1",
				"Material": "Diamond",
				"Diameter": "100",
				"Inner Diameter": "78.4",
				"Height": "5",
				"Angle": "45",
			}
		)
		self._created_types.append(variant.name)

		wheel_type = frappe.get_doc("Wheel Type", variant.name)
		self.assertTrue(wheel_type.requires_correction_factor)
		self.assertEqual(len(wheel_type.profile_segments), 1)
		self.assertAlmostEqual(wheel_type.profile_segments[0].angle, 45, places=2)
		self.assertAlmostEqual(wheel_type.original_volume, 14284.19, places=1)

	def test_unrelated_item_is_ignored(self):
		item_code = "_Test Wheel Tracker Unrelated Item"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert(ignore_permissions=True)
		self._created_items.append(item_code)

		self.assertFalse(frappe.db.exists("Wheel Type", {"item": item_code}))

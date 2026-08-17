# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel_type


class TestStockEntryHooks(FrappeTestCase):
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

	def test_material_receipt_creates_matching_number_of_wheels(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		make_stock_entry(
			item_code=self.wheel_type.item,
			qty=3,
			to_warehouse="_Test Warehouse - _TC",
			purpose="Material Receipt",
		)

		wheels = frappe.get_all("Wheel", filters={"wheel_type": self.wheel_type.name})
		self.assertEqual(len(wheels), 3)

	def test_created_wheels_start_in_stock_at_original_dimensions(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		se = make_stock_entry(
			item_code=self.wheel_type.item,
			qty=1,
			to_warehouse="_Test Warehouse - _TC",
			purpose="Material Receipt",
		)

		wheel = frappe.get_last_doc("Wheel", filters={"wheel_type": self.wheel_type.name})
		self.assertEqual(wheel.status, "In Stock")
		self.assertAlmostEqual(wheel.current_volume, self.wheel_type.original_volume, places=2)
		self.assertEqual(wheel.source_stock_entry, se.name)
		self.assertEqual(wheel.warehouse, "_Test Warehouse - _TC")

	def test_non_material_receipt_purpose_creates_no_wheels(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		# Material Transfer needs stock to already exist at the source warehouse.
		make_stock_entry(
			item_code=self.wheel_type.item,
			qty=2,
			to_warehouse="_Test Warehouse - _TC",
			purpose="Material Receipt",
		)
		before = frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name})

		make_stock_entry(
			item_code=self.wheel_type.item,
			qty=1,
			from_warehouse="_Test Warehouse - _TC",
			to_warehouse="_Test Warehouse 1 - _TC",
			purpose="Material Transfer",
		)

		after = frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name})
		self.assertEqual(before, after)

	def test_unrelated_item_is_ignored(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		make_stock_entry(
			item_code="_Test Item",
			qty=5,
			to_warehouse="_Test Warehouse - _TC",
			purpose="Material Receipt",
		)
		self.assertEqual(frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name}), 0)

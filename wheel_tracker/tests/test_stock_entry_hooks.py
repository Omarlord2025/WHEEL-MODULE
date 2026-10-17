# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_item, make_wheel_type


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

		make_stock_entry(
			item_code=self.wheel_type.item,
			qty=2,
			to_warehouse="_Test Warehouse - _TC",
			purpose="Material Receipt",
		)
		before = frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name})
		wheel_name = frappe.db.get_value("Wheel", {"wheel_type": self.wheel_type.name}, "name")

		# Once the Item is serialized (every Wheel Type's Item now is — see PRD v10), a
		# Material Transfer needs an explicit serial, same as any other movement.
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"purpose": "Material Transfer",
				"stock_entry_type": "Material Transfer",
				"company": "_Test Company",
				"items": [
					{
						"item_code": self.wheel_type.item,
						"s_warehouse": "_Test Warehouse - _TC",
						"t_warehouse": "_Test Warehouse 1 - _TC",
						"qty": 1,
						"serial_no": wheel_name,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

		after = frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name})
		self.assertEqual(before, after)

	def test_wheel_name_equals_serial_no_name(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		make_stock_entry(
			item_code=self.wheel_type.item, qty=1, to_warehouse="_Test Warehouse - _TC", purpose="Material Receipt"
		)
		wheel = frappe.get_last_doc("Wheel", filters={"wheel_type": self.wheel_type.name})
		self.assertTrue(frappe.db.exists("Serial No", wheel.name))
		self.assertEqual(frappe.db.get_value("Serial No", wheel.name, "item_code"), self.wheel_type.item)

	def test_bin_actual_qty_matches_wheels_in_stock_count(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		make_stock_entry(
			item_code=self.wheel_type.item, qty=4, to_warehouse="_Test Warehouse - _TC", purpose="Material Receipt"
		)
		wheels_in_stock = frappe.db.count(
			"Wheel", {"wheel_type": self.wheel_type.name, "status": "In Stock"}
		)
		bin_qty = frappe.db.get_value(
			"Bin", {"item_code": self.wheel_type.item, "warehouse": "_Test Warehouse - _TC"}, "actual_qty"
		)
		self.assertEqual(wheels_in_stock, 4)
		self.assertEqual(bin_qty, 4)

	def test_unrelated_item_is_ignored(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		plain_item = make_item()
		make_stock_entry(
			item_code=plain_item,
			qty=5,
			to_warehouse="_Test Warehouse - _TC",
			purpose="Material Receipt",
		)
		self.assertEqual(frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name}), 0)


DEFAULT_WAREHOUSE = "_Test Warehouse 1 - _TC"


class TestDefaultWarehouse(FrappeTestCase):
	def setUp(self):
		self._created = []
		self._original_default_warehouse = frappe.db.get_single_value(
			"Wheel Tracker Settings", "default_warehouse"
		)
		frappe.db.set_single_value("Wheel Tracker Settings", "default_warehouse", DEFAULT_WAREHOUSE)
		self.wheel_type = self.track(
			make_wheel_type(original_diameter=200, original_inner_diameter=60, original_diamond_height=20)
		)

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)
		frappe.db.set_single_value(
			"Wheel Tracker Settings", "default_warehouse", self._original_default_warehouse
		)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def test_blocks_an_item_with_no_wheel_type_entering_the_default_warehouse(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		plain_item = make_item()
		self.assertRaises(
			frappe.ValidationError,
			make_stock_entry,
			item_code=plain_item,
			qty=1,
			to_warehouse=DEFAULT_WAREHOUSE,
			purpose="Material Receipt",
		)

	def test_does_not_block_the_same_item_entering_a_different_warehouse(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		make_stock_entry(
			item_code=self.wheel_type.item, qty=1, to_warehouse="_Test Warehouse - _TC", purpose="Material Receipt"
		)
		self.assertEqual(frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name}), 1)

	def test_allows_and_creates_wheels_for_an_item_that_has_a_wheel_type(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		make_stock_entry(
			item_code=self.wheel_type.item, qty=2, to_warehouse=DEFAULT_WAREHOUSE, purpose="Material Receipt"
		)
		self.assertEqual(frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name}), 2)

	def test_non_material_receipt_entering_default_warehouse_also_mints_wheels(self):
		"""The Default Warehouse rule applies to any purely-inward row, not just a
		Material Receipt purpose — a Repack row producing a Wheel Type's Item straight
		into the Default Warehouse mints new Wheels the same way, beating core's
		mandatory-serial check exactly like a receipt does. (A Material Transfer row
		doesn't qualify — see row_is_inward_wheel_receipt's own docstring: a transfer
		leg must already carry real serials, it can't mint fresh ones.)"""
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		raw_item = make_item()
		make_stock_entry(item_code=raw_item, qty=1, to_warehouse="_Test Warehouse - _TC", purpose="Material Receipt")

		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"purpose": "Repack",
				"stock_entry_type": "Repack",
				"company": "_Test Company",
				"items": [
					{"item_code": raw_item, "s_warehouse": "_Test Warehouse - _TC", "qty": 1},
					{"item_code": self.wheel_type.item, "t_warehouse": DEFAULT_WAREHOUSE, "qty": 1},
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

		self.assertEqual(frappe.db.count("Wheel", {"wheel_type": self.wheel_type.name}), 1)

	def test_blank_default_warehouse_disables_all_of_this(self):
		frappe.db.set_single_value("Wheel Tracker Settings", "default_warehouse", None)
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		# No longer blocked, and Material Receipt into any warehouse keeps working as before.
		plain_item = make_item()
		make_stock_entry(item_code=plain_item, qty=1, to_warehouse=DEFAULT_WAREHOUSE, purpose="Material Receipt")

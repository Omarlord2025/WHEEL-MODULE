# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel_type
from wheel_tracker.wheel_tracker.doctype.wheel_retrieval.wheel_retrieval import (
	get_current_stock_qty,
	get_items_by_group,
)

WAREHOUSE = "_Test Warehouse - _TC"


class TestWheelRetrieval(FrappeTestCase):
	def setUp(self):
		self._created = []

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, wheel_type):
		self._created.append(wheel_type.name)
		return wheel_type

	def make_retrieval(self, rows, **kwargs):
		values = {
			"doctype": "Wheel Retrieval",
			"posting_date": frappe.utils.today(),
			"company": "_Test Company",
			"warehouse": WAREHOUSE,
			"items": [{"wheel_type": wt, "qty_to_create": qty} for wt, qty in rows],
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def test_single_item_retrieval_creates_wheels_via_material_receipt(self):
		wt = self.track(make_wheel_type())
		retrieval = self.make_retrieval([(wt.name, 3)])
		retrieval.submit()

		self.assertEqual(retrieval.total_qty, 3)
		self.assertTrue(retrieval.stock_entry)

		se = frappe.get_doc("Stock Entry", retrieval.stock_entry)
		self.assertEqual(se.docstatus, 1)
		self.assertEqual(se.purpose, "Material Receipt")

		wheels = frappe.get_all("Wheel", filters={"wheel_type": wt.name})
		self.assertEqual(len(wheels), 3)
		for w in frappe.get_all("Wheel", filters={"wheel_type": wt.name}, fields=["status", "warehouse"]):
			self.assertEqual(w.status, "In Stock")
			self.assertEqual(w.warehouse, WAREHOUSE)

		bin_qty = frappe.db.get_value("Bin", {"item_code": wt.item, "warehouse": WAREHOUSE}, "actual_qty")
		self.assertEqual(bin_qty, 3)

	def test_bulk_multiple_wheel_types_in_one_retrieval(self):
		wt_a = self.track(make_wheel_type())
		wt_b = self.track(make_wheel_type())
		retrieval = self.make_retrieval([(wt_a.name, 2), (wt_b.name, 5)])
		retrieval.submit()

		self.assertEqual(retrieval.total_qty, 7)
		se = frappe.get_doc("Stock Entry", retrieval.stock_entry)
		self.assertEqual(len(se.items), 2)
		self.assertEqual(len(frappe.get_all("Wheel", filters={"wheel_type": wt_a.name})), 2)
		self.assertEqual(len(frappe.get_all("Wheel", filters={"wheel_type": wt_b.name})), 5)

	def test_cancel_reverses_the_material_receipt(self):
		wt = self.track(make_wheel_type())
		retrieval = self.make_retrieval([(wt.name, 1)])
		retrieval.submit()
		se_name = retrieval.stock_entry

		retrieval.cancel()
		se = frappe.get_doc("Stock Entry", se_name)
		self.assertEqual(se.docstatus, 2)

	def test_rejects_duplicate_wheel_type_within_same_retrieval(self):
		wt = self.track(make_wheel_type())
		self.assertRaises(
			frappe.ValidationError,
			self.make_retrieval,
			[(wt.name, 1), (wt.name, 2)],
		)

	def test_rejects_zero_quantity(self):
		wt = self.track(make_wheel_type())
		self.assertRaises(frappe.ValidationError, self.make_retrieval, [(wt.name, 0)])

	def test_get_items_by_group_filters_by_item_group(self):
		wt = self.track(make_wheel_type())
		item_group = frappe.db.get_value("Item", wt.item, "item_group")

		matching = get_items_by_group(item_group=item_group, warehouse=WAREHOUSE)
		self.assertIn(wt.name, [row["wheel_type"] for row in matching])

		other_group = "Products"
		self.assertNotEqual(item_group, other_group)
		not_matching = get_items_by_group(item_group=other_group, warehouse=WAREHOUSE)
		self.assertNotIn(wt.name, [row["wheel_type"] for row in not_matching])

	def test_get_current_stock_qty_reflects_bin_after_retrieval(self):
		wt = self.track(make_wheel_type())
		self.assertEqual(get_current_stock_qty(wt.name, WAREHOUSE), 0)

		retrieval = self.make_retrieval([(wt.name, 4)])
		retrieval.submit()

		self.assertEqual(get_current_stock_qty(wt.name, WAREHOUSE), 4)

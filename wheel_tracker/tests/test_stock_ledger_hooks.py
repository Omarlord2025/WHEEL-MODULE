# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel_type


class TestStockLedgerHooks(FrappeTestCase):
	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(original_diameter=100, original_inner_diameter=60, original_diamond_height=6)
		)
		self.wheel = self.receive_one_wheel()

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def receive_one_wheel(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		make_stock_entry(
			item_code=self.wheel_type.item, qty=1, to_warehouse="_Test Warehouse - _TC", purpose="Material Receipt"
		)
		return frappe.get_last_doc("Wheel", filters={"wheel_type": self.wheel_type.name})

	def issue_the_wheel(self):
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"purpose": "Material Issue",
				"stock_entry_type": "Material Issue",
				"company": "_Test Company",
				"items": [
					{
						"item_code": self.wheel_type.item,
						"s_warehouse": "_Test Warehouse - _TC",
						"qty": 1,
						"serial_no": self.wheel.name,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()
		return se

	def test_material_issue_retires_the_wheel(self):
		self.issue_the_wheel()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")

	def test_cancelling_material_issue_reinstates_the_wheel(self):
		se = self.issue_the_wheel()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")

		se.cancel()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")

	def test_stock_reconciliation_zero_qty_retires_the_wheel(self):
		sr = frappe.get_doc(
			{
				"doctype": "Stock Reconciliation",
				"company": "_Test Company",
				"purpose": "Stock Reconciliation",
				"items": [
					{
						"item_code": self.wheel_type.item,
						"warehouse": "_Test Warehouse - _TC",
						"reconcile_all_serial_batch": 1,
						"qty": 0,
						"valuation_rate": 0,
					}
				],
			}
		)
		sr.insert(ignore_permissions=True)
		sr.submit()

		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")

	def test_material_transfer_updates_wheel_warehouse_without_changing_status(self):
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
						"serial_no": self.wheel.name,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")
		self.assertEqual(self.wheel.warehouse, "_Test Warehouse 1 - _TC")

	def test_hook_ignores_unrelated_items(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		# _Test Item is not serialized and not a Wheel Type Item -- must not error.
		make_stock_entry(item_code="_Test Item", qty=5, to_warehouse="_Test Warehouse - _TC", purpose="Material Receipt")
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")

# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.test_helpers import (
	cleanup_wheel_tracker_records,
	make_wheel_type,
	receive_wheel_via_material_receipt,
)


class TestWheelRetirement(FrappeTestCase):
	def setUp(self):
		self._created = []
		self.wheel_type = self.track(
			make_wheel_type(
				shape="P2", original_diameter=125, original_inner_diameter=104.9, original_diamond_height=2
			)
		)
		self.wheel = self.receive_one_wheel()

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def receive_one_wheel(self):
		return receive_wheel_via_material_receipt(self.wheel_type.name)

	def make_retirement(self, **kwargs):
		values = {
			"doctype": "Wheel Retirement",
			"wheel": self.wheel.name,
			"check_date": frappe.utils.now_datetime(),
			"checked_by": frappe.session.user,
			"retirement_reason": "Chipped edge",
		}
		values.update(kwargs)
		doc = frappe.get_doc(values).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def test_submit_retires_the_wheel_and_issues_it_out_of_stock(self):
		retirement = self.make_retirement()

		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")
		self.assertEqual(self.wheel.retirement_reason, "Chipped edge")

		self.assertTrue(retirement.stock_entry)
		self.assertEqual(frappe.db.get_value("Stock Entry", retirement.stock_entry, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Stock Entry", retirement.stock_entry, "purpose"), "Material Issue")

		bin_qty = frappe.db.get_value(
			"Bin", {"item_code": self.wheel_type.item, "warehouse": "_Test Warehouse - _TC"}, "actual_qty"
		)
		self.assertEqual(bin_qty, 0)

	def test_reason_is_required(self):
		self.assertRaises(frappe.MandatoryError, self.make_retirement, retirement_reason="")

	def test_cancel_reinstates_the_wheel_and_cancels_the_stock_entry(self):
		retirement = self.make_retirement()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "Retired")

		retirement.cancel()
		self.wheel.reload()
		self.assertEqual(self.wheel.status, "In Stock")
		self.assertEqual(frappe.db.get_value("Stock Entry", retirement.stock_entry, "docstatus"), 2)

	def test_measurement_event_still_rejected_after_reinstatement(self):
		from wheel_tracker.test_helpers import make_measurement_event

		retirement = self.make_retirement()
		retirement.cancel()
		self.assertRaises(frappe.ValidationError, make_measurement_event, self.wheel.name)

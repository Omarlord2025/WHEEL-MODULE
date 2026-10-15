# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_wheel, make_wheel_type
from wheel_tracker.wheel_tracker.doctype.wheel_scrap_sale.wheel_scrap_sale import (
	get_retired_wheels_with_unsold_scrap,
	retired_wheel_query,
)

CASH_ACCOUNT = "Cash - _TC"
SCRAP_ACCOUNT = "Sales - _TC"
BUYER = "_Test Wheel Scrap Buyer"


class TestWheelScrapSale(FrappeTestCase):
	def setUp(self):
		self._created = []
		self._original_scrap_account = frappe.db.get_single_value(
			"Wheel Tracker Settings", "scrap_sales_account"
		)
		frappe.db.set_single_value("Wheel Tracker Settings", "scrap_sales_account", SCRAP_ACCOUNT)
		if not frappe.db.exists("Customer", BUYER):
			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": BUYER,
					"customer_group": "_Test Customer Group",
					"territory": "_Test Territory",
				}
			)
			customer.flags.ignore_mandatory = True
			customer.insert(ignore_permissions=True)

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)
		frappe.db.set_single_value(
			"Wheel Tracker Settings", "scrap_sales_account", self._original_scrap_account
		)

	def track(self, doc):
		self._created.append(doc.name)
		return doc

	def make_retired_wheel(self):
		wt = self.track(make_wheel_type())
		wheel = make_wheel(wt.name, status="Retired")
		return wheel

	def make_sale(self, wheels_and_amounts, **kwargs):
		values = {
			"doctype": "Wheel Scrap Sale",
			"posting_date": frappe.utils.today(),
			"company": "_Test Company",
			"buyer": BUYER,
			"payment_account": CASH_ACCOUNT,
			"wheels": [{"wheel": w, "amount": a} for w, a in wheels_and_amounts],
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def test_single_wheel_scrap_sale_creates_and_submits_a_journal_entry(self):
		wheel = self.make_retired_wheel()
		sale = self.make_sale([(wheel.name, 150)])
		sale.submit()

		self.assertEqual(sale.total_amount, 150)
		self.assertTrue(sale.journal_entry)

		je = frappe.get_doc("Journal Entry", sale.journal_entry)
		self.assertEqual(je.docstatus, 1)
		accounts = {row.account: row for row in je.accounts}
		self.assertAlmostEqual(flt(accounts[CASH_ACCOUNT].debit_in_account_currency), 150, places=2)
		self.assertAlmostEqual(flt(accounts[SCRAP_ACCOUNT].credit_in_account_currency), 150, places=2)

	def test_bulk_scrap_sale_sums_multiple_wheels_into_one_journal_entry(self):
		wheel_a = self.make_retired_wheel()
		wheel_b = self.make_retired_wheel()
		sale = self.make_sale([(wheel_a.name, 100), (wheel_b.name, 75)])
		sale.submit()

		self.assertEqual(sale.total_amount, 175)
		je = frappe.get_doc("Journal Entry", sale.journal_entry)
		accounts = {row.account: row for row in je.accounts}
		self.assertAlmostEqual(flt(accounts[CASH_ACCOUNT].debit_in_account_currency), 175, places=2)
		self.assertAlmostEqual(flt(accounts[SCRAP_ACCOUNT].credit_in_account_currency), 175, places=2)

	def test_cancel_reverses_the_journal_entry(self):
		wheel = self.make_retired_wheel()
		sale = self.make_sale([(wheel.name, 200)])
		sale.submit()
		je_name = sale.journal_entry

		sale.cancel()
		je = frappe.get_doc("Journal Entry", je_name)
		self.assertEqual(je.docstatus, 2)

	def test_rejects_a_wheel_that_is_not_retired(self):
		wt = self.track(make_wheel_type())
		in_stock_wheel = make_wheel(wt.name, status="In Stock")
		self.assertRaises(frappe.ValidationError, self.make_sale, [(in_stock_wheel.name, 50)])

	def test_rejects_selling_the_same_wheels_scrap_twice(self):
		wheel = self.make_retired_wheel()
		first = self.make_sale([(wheel.name, 80)])
		first.submit()

		self.assertRaises(frappe.ValidationError, self.make_sale, [(wheel.name, 20)])

	def test_rejects_duplicate_wheel_within_the_same_sale(self):
		wheel = self.make_retired_wheel()
		self.assertRaises(
			frappe.ValidationError,
			self.make_sale,
			[(wheel.name, 50), (wheel.name, 30)],
		)

	def test_blocked_without_a_configured_scrap_sales_account(self):
		frappe.db.set_single_value("Wheel Tracker Settings", "scrap_sales_account", None)
		wheel = self.make_retired_wheel()
		self.assertRaises(frappe.ValidationError, self.make_sale, [(wheel.name, 50)])

	def test_retired_wheel_query_excludes_already_sold_scrap(self):
		unsold = self.make_retired_wheel()
		sold = self.make_retired_wheel()
		sale = self.make_sale([(sold.name, 60)])
		sale.submit()

		names = {row[0] for row in retired_wheel_query("Wheel", "", "name", 0, 20, {})}
		self.assertIn(unsold.name, names)
		self.assertNotIn(sold.name, names)

	def test_retired_wheel_query_excludes_wheels_not_retired(self):
		wt = self.track(make_wheel_type())
		in_stock_wheel = make_wheel(wt.name, status="In Stock")

		names = {row[0] for row in retired_wheel_query("Wheel", "", "name", 0, 20, {})}
		self.assertNotIn(in_stock_wheel.name, names)

	def test_get_retired_wheels_with_unsold_scrap_excludes_already_sold(self):
		unsold = self.make_retired_wheel()
		sold = self.make_retired_wheel()
		sale = self.make_sale([(sold.name, 60)])
		sale.submit()

		names = {row.wheel for row in get_retired_wheels_with_unsold_scrap()}
		self.assertIn(unsold.name, names)
		self.assertNotIn(sold.name, names)

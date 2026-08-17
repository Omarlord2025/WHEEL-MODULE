# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import csv
import io
import math

import frappe
from frappe.tests.utils import FrappeTestCase

from wheel_tracker.bulk_import import TEMPLATE_COLUMNS, import_wheels_from_csv
from wheel_tracker.test_helpers import cleanup_wheel_tracker_records, make_item


class TestBulkImport(FrappeTestCase):
	def setUp(self):
		self._created = []
		self._files = []
		self.item = make_item()

	def tearDown(self):
		cleanup_wheel_tracker_records(self._created)
		for file_name in self._files:
			frappe.delete_doc("File", file_name, force=True)

	def make_csv_file(self, rows: list[dict]) -> str:
		buf = io.StringIO()
		writer = csv.DictWriter(buf, fieldnames=TEMPLATE_COLUMNS)
		writer.writeheader()
		for row in rows:
			full_row = dict.fromkeys(TEMPLATE_COLUMNS, "")
			full_row.update(row)
			writer.writerow(full_row)

		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "test_bulk_import.csv", "content": buf.getvalue(), "is_private": 1}
		).insert(ignore_permissions=True)
		self._files.append(file_doc.name)
		return file_doc.file_url

	def base_row(self, **overrides) -> dict:
		row = {
			"shape": "1A1",
			"material": "Diamond",
			"spec_code": "_TEST-BULK-100642",
			"item": self.item,
			"original_diameter": "100",
			"original_inner_diameter": "60",
			"original_diamond_height": "6",
			"unit_cost": "500",
			"factory_wheel_code": "",
			"current_diameter": "98",
			"current_inner_diameter": "60",
			"current_diamond_height": "5.5",
			"status": "In Stock",
		}
		row.update(overrides)
		return row

	def test_two_rows_same_spec_share_one_wheel_type(self):
		file_url = self.make_csv_file([self.base_row(), self.base_row(current_diameter="90")])
		self._created.append("_TEST-BULK-100642")

		summary = import_wheels_from_csv(file_url)

		self.assertEqual(summary["wheel_types_created"], 1)
		self.assertEqual(summary["wheels_created"], 2)
		self.assertFalse(summary["errors"])
		self.assertEqual(frappe.db.count("Wheel", {"wheel_type": "_TEST-BULK-100642"}), 2)

	def test_bad_row_is_captured_without_aborting_the_batch(self):
		rows = [
			self.base_row(),
			self.base_row(original_diamond_height="0", spec_code="_TEST-BULK-BAD"),
		]
		file_url = self.make_csv_file(rows)
		self._created.append("_TEST-BULK-100642")

		summary = import_wheels_from_csv(file_url)

		self.assertEqual(summary["wheels_created"], 1)
		self.assertEqual(len(summary["errors"]), 1)
		self.assertFalse(frappe.db.exists("Wheel Type", "_TEST-BULK-BAD"))

	def test_blank_item_auto_creates_one_keyed_on_spec_code(self):
		file_url = self.make_csv_file([self.base_row(item="")])
		self._created.append("_TEST-BULK-100642")
		self.addCleanup(frappe.delete_doc, "Item", "_TEST-BULK-100642", force=True, ignore_missing=True)

		import_wheels_from_csv(file_url)

		wheel_type = frappe.get_doc("Wheel Type", "_TEST-BULK-100642")
		self.assertEqual(wheel_type.item, "_TEST-BULK-100642")
		self.assertTrue(frappe.db.exists("Item", "_TEST-BULK-100642"))

	def test_baseline_measurement_event_reflects_current_reading(self):
		file_url = self.make_csv_file([self.base_row()])
		self._created.append("_TEST-BULK-100642")

		import_wheels_from_csv(file_url)

		wheel_name = frappe.db.get_value("Wheel", {"wheel_type": "_TEST-BULK-100642"})
		events = frappe.get_all("Measurement Event", filters={"wheel": wheel_name, "docstatus": 1})
		self.assertEqual(len(events), 1)
		wheel = frappe.get_doc("Wheel", wheel_name)
		# confirmed_volume is computed from current_diameter (98) against the Wheel Type's
		# constant original inner diameter (60) and height (6) — see PRD v6.
		expected = (math.pi / 4) * (98**2 - 60**2) * 6
		self.assertAlmostEqual(wheel.current_volume, expected, places=2)

	def test_unknown_shape_is_reported_not_guessed(self):
		file_url = self.make_csv_file([self.base_row(shape="DOES-NOT-EXIST")])

		summary = import_wheels_from_csv(file_url)

		self.assertEqual(summary["wheels_created"], 0)
		self.assertEqual(len(summary["errors"]), 1)
		self.assertFalse(frappe.db.exists("Wheel Type", "_TEST-BULK-100642"))

	def test_original_volume_override_skips_auto_calc(self):
		file_url = self.make_csv_file(
			[self.base_row(original_volume_override="99999", legacy_spec_name="1a1-d100-h20-t6-x10-SAILI")]
		)
		self._created.append("_TEST-BULK-100642")

		import_wheels_from_csv(file_url)

		wheel_type = frappe.get_doc("Wheel Type", "_TEST-BULK-100642")
		self.assertEqual(wheel_type.auto_calc_volume, 0)
		self.assertEqual(wheel_type.original_volume, 99999)
		self.assertEqual(wheel_type.legacy_spec_name, "1a1-d100-h20-t6-x10-SAILI")

	def test_grit_concentration_bond_are_auto_created(self):
		grit, concentration, bond = "_TEST-D91", "_TEST-C100", "_TEST-B127"
		file_url = self.make_csv_file(
			[self.base_row(grit=grit, concentration=concentration, bond=bond)]
		)
		self._created.append("_TEST-BULK-100642")
		self.addCleanup(frappe.delete_doc, "Wheel Grit", grit, force=True)
		self.addCleanup(frappe.delete_doc, "Wheel Concentration", concentration, force=True)
		self.addCleanup(frappe.delete_doc, "Wheel Bond", bond, force=True)

		import_wheels_from_csv(file_url)

		wheel_type = frappe.get_doc("Wheel Type", "_TEST-BULK-100642")
		self.assertEqual(wheel_type.grit, grit)
		self.assertEqual(wheel_type.concentration, concentration)
		self.assertEqual(wheel_type.bond, bond)

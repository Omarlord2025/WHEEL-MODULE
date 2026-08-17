# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Shared fixture builders for wheel_tracker tests. Keep test setup here, not
duplicated across test_*.py files, per CLAUDE.md's DRY rule."""

import frappe
from frappe.utils import random_string


def make_item(item_code: str | None = None) -> str:
	"""Create (or reuse) a minimal stock Item and return its item_code."""
	item_code = item_code or f"_Test Wheel Item {random_string(8)}"
	if frappe.db.exists("Item", item_code):
		return item_code

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
	return item_code


def make_wheel_type(**kwargs) -> "frappe.model.document.Document":
	"""Create a Wheel Type with sensible flat 1A1/Diamond defaults, overridable via kwargs.
	Relies on the seeded "1A1" Wheel Shape and "Diamond" Wheel Material (see
	wheel_tracker.setup.seed_master_data) already existing on the site."""
	values = {
		"doctype": "Wheel Type",
		"spec_code": f"_TEST-{random_string(8)}",
		"shape": "1A1",
		"material": "Diamond",
		"item": make_item(),
		"original_diameter": 100,
		"original_inner_diameter": 60,
		"original_diamond_height": 20,
		"unit_cost": 1000,
		"reorder_point": 0,
		"reorder_qty": 0,
	}
	values.update(kwargs)
	return frappe.get_doc(values).insert(ignore_permissions=True)


def make_wheel(wheel_type_name: str, **kwargs) -> "frappe.model.document.Document":
	"""Create a Wheel at its Wheel Type's new-wheel dimensions, overridable via kwargs."""
	wheel_type = frappe.get_doc("Wheel Type", wheel_type_name)
	values = {
		"doctype": "Wheel",
		"wheel_type": wheel_type_name,
		"status": "In Stock",
		"current_diameter": wheel_type.original_diameter,
		"current_inner_diameter": wheel_type.original_inner_diameter,
		"current_diamond_height": wheel_type.original_diamond_height,
		"current_volume": wheel_type.original_volume,
	}
	values.update(kwargs)
	return frappe.get_doc(values).insert(ignore_permissions=True)


def make_measurement_event(wheel_name: str, submit: bool = True, **kwargs) -> "frappe.model.document.Document":
	"""Create a Measurement Event against a Wheel, submitted by default. confirmed_volume
	is computed automatically from `diameter` (see PRD v6) — pass `diameter` to control it,
	not confirmed_volume directly."""
	wheel = frappe.get_doc("Wheel", wheel_name)
	values = {
		"doctype": "Measurement Event",
		"wheel": wheel_name,
		"measurement_date": frappe.utils.now_datetime(),
		"measured_by": frappe.session.user,
		"diameter": wheel.current_diameter,
		"inner_diameter": wheel.current_inner_diameter,
		"diamond_height": wheel.current_diamond_height,
	}
	values.update(kwargs)
	doc = frappe.get_doc(values).insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def make_job_card() -> "frappe.model.document.Document":
	"""Build a real, fully valid Job Card via ERPNext's own manufacturing test fixtures
	(BOM -> Work Order -> auto-created Job Card). Heavier than a fake doc, but Job Card
	has hard-required links (work_order, workstation, operation, wip_warehouse) that
	only a real Work Order satisfies without fighting ERPNext's own validation."""
	from erpnext.manufacturing.doctype.job_card.test_job_card import make_bom_for_jc_tests
	from erpnext.manufacturing.doctype.work_order.test_work_order import make_wo_order_test_record

	make_bom_for_jc_tests()
	work_order = make_wo_order_test_record(item="_Test FG Item 2", qty=2)
	job_card_name = frappe.db.get_value("Job Card", {"work_order": work_order.name})
	return frappe.get_doc("Job Card", job_card_name)


def cleanup_wheel_tracker_records(wheel_type_names: list[str]):
	"""Delete Measurement Events, Wheels, and Wheel Types created for a test, in FK order."""
	for wheel_type_name in wheel_type_names:
		for wheel_name in frappe.get_all("Wheel", filters={"wheel_type": wheel_type_name}, pluck="name"):
			for event_name in frappe.get_all(
				"Measurement Event", filters={"wheel": wheel_name}, pluck="name"
			):
				event = frappe.get_doc("Measurement Event", event_name)
				if event.docstatus == 1:
					event.cancel()
				frappe.delete_doc("Measurement Event", event_name, force=True)
			frappe.delete_doc("Wheel", wheel_name, force=True)
		frappe.delete_doc("Wheel Type", wheel_type_name, force=True)

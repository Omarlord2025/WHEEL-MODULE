# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""One-time serialization of every existing Wheel Type's Item, so physical Wheels map
to real ERPNext Serial Nos going forward (see PRD v10). New Wheel Types serialize their
own Item automatically via WheelType.validate() -> ensure_item_is_serialized(); this
patch only needs to catch the ones that already existed before that existed."""

import frappe

from wheel_tracker.wheel_tracker.doctype.wheel_type.wheel_type import ensure_item_is_serialized


def execute():
	failures = []
	for item_code in frappe.get_all("Wheel Type", pluck="item", distinct=True):
		try:
			ensure_item_is_serialized(item_code)
		except frappe.ValidationError as e:
			failures.append((item_code, str(e)))

	if failures:
		frappe.log_error(
			title="wheel_tracker: could not serialize Item(s)",
			message=f"{len(failures)} Item(s) could not be serialized (likely have submitted stock "
			f"transactions already): {failures}",
		)

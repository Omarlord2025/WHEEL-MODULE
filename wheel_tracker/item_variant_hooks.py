# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Turns "generate an Item Variant" into a fully working Wheel Type automatically —
employees never touch the Wheel Type form directly. See setup/item_variant_setup.py
for the template/attributes this reacts to, and PRD v10 for why."""

import frappe

from wheel_tracker.setup.item_variant_setup import TEMPLATE_ITEM_CODE


def create_wheel_type_from_variant(doc, method=None):
	"""Item after_insert hook: a new variant of the Grinding Wheel template becomes a
	Wheel Type, dimensions read straight off its Item Variant Attribute values —
	nothing for an employee to re-type."""
	if doc.variant_of != TEMPLATE_ITEM_CODE:
		return
	if frappe.db.exists("Wheel Type", {"item": doc.name}):
		return

	values = get_attribute_values(doc.name)
	shape = values.get("Shape")
	material = values.get("Material")
	if not shape or not material:
		frappe.throw(
			frappe._("Wheel variant {0} is missing a Shape or Material attribute value.").format(doc.name)
		)

	requires_correction_factor = frappe.db.get_value(
		"Wheel Geometry",
		frappe.db.get_value("Wheel Shape", shape, "wheel_geometry"),
		"requires_correction_factor",
	)

	wheel_type = frappe.new_doc("Wheel Type")
	wheel_type.spec_code = doc.name
	wheel_type.shape = shape
	wheel_type.material = material
	wheel_type.item = doc.name
	wheel_type.legacy_spec_name = doc.item_name
	wheel_type.original_diameter = values.get("Diameter") or 0
	wheel_type.original_inner_diameter = values.get("Inner Diameter") or 0

	if requires_correction_factor:
		angle = values.get("Angle")
		height = values.get("Height") or 0
		if angle:
			wheel_type.append("profile_segments", {"angle": angle, "height": height})
		# No Angle chosen on the variant: leave profile_segments empty. WheelType's own
		# validate_dimensions() already throws a clear "at least one Profile Segment is
		# required" error on save — surfaced on the Wheel Type form, not guessed here.
	else:
		wheel_type.original_diamond_height = values.get("Height") or 0

	wheel_type.unit_cost = 0
	wheel_type.reorder_point = 0
	wheel_type.reorder_qty = 0
	wheel_type.insert(ignore_permissions=True)


def get_attribute_values(item_code: str) -> dict:
	"""{attribute: attribute_value} for one variant Item — see PRD v10, confirmed
	queryable this way against erpnext.utilities.product.get_item_codes_by_attributes."""
	rows = frappe.get_all(
		"Item Variant Attribute", filters={"parent": item_code}, fields=["attribute", "attribute_value"]
	)
	return {row.attribute: row.attribute_value for row in rows}

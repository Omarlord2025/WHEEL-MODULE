# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Seeds the ERPNext Item Attributes and Item Template that back the real data-entry
workflow: employees generate Item Variants from this template (ERPNext's own
"Create Variants" wizard, no custom UI needed) with one attribute-value combination
per real wheel spec, and Wheel Tracker auto-creates a matching Wheel Type from each
new variant (see item_variant_hooks.py). See PRD v10."""

import frappe

TEMPLATE_ITEM_CODE = "GRINDING-WHEEL-TEMPLATE"

DISCRETE_ATTRIBUTES = {
	# Abbreviations feed directly into ERPNext's own variant item_code generation
	# (make_variant_item_code) — kept identical to the existing Wheel Shape/Material
	# codes so a variant's auto-generated item_code stays legible against them.
	"Shape": [
		{"attribute_value": "1A1", "abbr": "1A1"},
		{"attribute_value": "P1.5", "abbr": "P1.5"},
		{"attribute_value": "P1.7", "abbr": "P1.7"},
		{"attribute_value": "P2", "abbr": "P2"},
		{"attribute_value": "12V9", "abbr": "12V9"},
		{"attribute_value": "11V9", "abbr": "11V9"},
		{"attribute_value": "1V1", "abbr": "1V1"},
	],
	"Material": [
		{"attribute_value": "Diamond", "abbr": "D"},
		{"attribute_value": "CBN", "abbr": "B"},
	],
	# The three real solved angles validated this session (see PRD v8) — add more
	# rows here if a genuinely new angle is ever confirmed the same way, never guessed.
	"Angle": [
		{"attribute_value": "10", "abbr": "A10"},
		{"attribute_value": "20", "abbr": "A20"},
		{"attribute_value": "45", "abbr": "A45"},
	],
}

# Wide enough to cover any real spec without a maintained discrete list; ERPNext has
# no true free-numeric attribute (see PRD v10) — ranged+increment is the closest fit.
NUMERIC_ATTRIBUTES = {
	"Diameter": {"from_range": 10, "to_range": 300, "increment": 0.01},
	"Inner Diameter": {"from_range": 5, "to_range": 300, "increment": 0.01},
	"Height": {"from_range": 0.5, "to_range": 60, "increment": 0.01},
}


def setup_item_variants():
	for attribute_name, values in DISCRETE_ATTRIBUTES.items():
		get_or_create_discrete_attribute(attribute_name, values)
	for attribute_name, range_values in NUMERIC_ATTRIBUTES.items():
		get_or_create_numeric_attribute(attribute_name, range_values)
	get_or_create_template()


def get_or_create_discrete_attribute(attribute_name: str, values: list[dict]):
	if frappe.db.exists("Item Attribute", attribute_name):
		return
	frappe.get_doc(
		{
			"doctype": "Item Attribute",
			"attribute_name": attribute_name,
			"numeric_values": 0,
			"item_attribute_values": values,
		}
	).insert(ignore_permissions=True)


def get_or_create_numeric_attribute(attribute_name: str, range_values: dict):
	if frappe.db.exists("Item Attribute", attribute_name):
		return
	frappe.get_doc(
		{
			"doctype": "Item Attribute",
			"attribute_name": attribute_name,
			"numeric_values": 1,
			**range_values,
		}
	).insert(ignore_permissions=True)


def get_or_create_template():
	if frappe.db.exists("Item", TEMPLATE_ITEM_CODE):
		return

	attribute_rows = []
	for name in ("Shape", "Material", "Diameter", "Inner Diameter", "Height", "Angle"):
		# Item.validate_variant() reads numeric_values/from_range/to_range/increment off
		# the TEMPLATE's own Item Variant Attribute row, not the Item Attribute master —
		# Desk's own form copies these client-side when an attribute is picked; done here
		# by hand since this is created programmatically, not through the Item form.
		numeric_values, from_range, to_range, increment = frappe.db.get_value(
			"Item Attribute", name, ["numeric_values", "from_range", "to_range", "increment"]
		)
		attribute_rows.append(
			{
				"attribute": name,
				"numeric_values": numeric_values,
				"from_range": from_range,
				"to_range": to_range,
				"increment": increment,
			}
		)

	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": TEMPLATE_ITEM_CODE,
			"item_name": "Grinding Wheel",
			"item_group": "All Item Groups",
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"has_variants": 1,
			"variant_based_on": "Item Attribute",
			"attributes": attribute_rows,
		}
	).insert(ignore_permissions=True)

# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

JOB_CARD_CUSTOM_FIELDS = {
	"Job Card": [
		{
			"fieldname": "custom_wheel_wear_tab",
			"fieldtype": "Tab Break",
			"insert_after": "amended_from",
			"label": "Wheel Wear",
		},
		{
			"description": "Diamond/CBN wheels assigned to this job. Adding an In Stock Wheel here marks it In Use.",
			"fieldname": "custom_wheels_used",
			"fieldtype": "Table",
			"insert_after": "custom_wheel_wear_tab",
			"label": "Wheels Used",
			"options": "Job Card Wheel",
		},
		{
			"description": "Sum of Job Cost across submitted Measurement Events logged against this Job Card.",
			"fieldname": "custom_wheel_wear_cost",
			"fieldtype": "Currency",
			"insert_after": "custom_wheels_used",
			"label": "Wheel Wear Cost",
			"read_only": 1,
		},
	]
}


def create_wheel_tracker_custom_fields():
	create_custom_fields(JOB_CARD_CUSTOM_FIELDS, update=True)

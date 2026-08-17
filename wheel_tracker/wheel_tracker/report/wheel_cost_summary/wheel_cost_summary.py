# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Wear-cost trend over submitted Measurement Events — the per-job cost ledger
the legacy spreadsheet never had. Filterable by date range, Wheel Type, and Job Card."""

import frappe
from frappe import _


def execute(filters=None):
	"""Report entry point required by the Script Report framework.

	Args:
		filters (dict | None): report filters from wheel_cost_summary.js.

	Returns:
		tuple[list[dict], list[dict]]: (columns, data) for the report grid.
	"""
	columns = get_columns()
	data = get_data(filters or {})
	return columns, data


def get_columns():
	"""Define the report's column layout."""
	return [
		{
			"label": _("Measurement Event"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Measurement Event",
			"width": 130,
		},
		{"label": _("Date"), "fieldname": "measurement_date", "fieldtype": "Datetime", "width": 160},
		{"label": _("Job Card"), "fieldname": "job_card", "fieldtype": "Link", "options": "Job Card", "width": 130},
		{"label": _("Wheel"), "fieldname": "wheel", "fieldtype": "Link", "options": "Wheel", "width": 160},
		{
			"label": _("Wheel Type"),
			"fieldname": "wheel_type",
			"fieldtype": "Link",
			"options": "Wheel Type",
			"width": 110,
		},
		{
			"label": _("Incremental Consumed Volume (mm³)"),
			"fieldname": "incremental_consumed_volume",
			"fieldtype": "Float",
			"precision": 3,
			"width": 160,
		},
		{"label": _("Job Cost"), "fieldname": "job_cost", "fieldtype": "Currency", "width": 110},
		{
			"label": _("Consumption %"),
			"fieldname": "consumption_percent",
			"fieldtype": "Percent",
			"width": 110,
		},
	]


def get_data(filters: dict):
	"""Fetch submitted Measurement Events matching the given filters."""
	conditions, values = get_conditions(filters)
	return frappe.db.sql(
		f"""
		select
			name, measurement_date, job_card, wheel, wheel_type,
			incremental_consumed_volume, job_cost, consumption_percent
		from `tabMeasurement Event`
		where docstatus = 1 {conditions}
		order by measurement_date desc
		""",
		values,
		as_dict=True,
	)


def get_conditions(filters: dict):
	"""Build a SQL WHERE fragment and its bind values from report filters."""
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("measurement_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("measurement_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("wheel_type"):
		conditions.append("wheel_type = %(wheel_type)s")
		values["wheel_type"] = filters["wheel_type"]
	if filters.get("job_card"):
		conditions.append("job_card = %(job_card)s")
		values["job_card"] = filters["job_card"]
	if filters.get("wheel"):
		conditions.append("wheel = %(wheel)s")
		values["wheel"] = filters["wheel"]

	return ("and " + " and ".join(conditions) if conditions else "", values)

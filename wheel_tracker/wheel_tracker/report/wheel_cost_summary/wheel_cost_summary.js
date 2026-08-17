frappe.query_reports["Wheel Cost Summary"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "wheel_type",
			label: __("Wheel Type"),
			fieldtype: "Link",
			options: "Wheel Type",
		},
		{
			fieldname: "wheel",
			label: __("Wheel"),
			fieldtype: "Link",
			options: "Wheel",
		},
		{
			fieldname: "job_card",
			label: __("Job Card"),
			fieldtype: "Link",
			options: "Job Card",
		},
	],
};

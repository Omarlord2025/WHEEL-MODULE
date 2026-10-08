frappe.listview_settings["Measurement Event"] = {
	formatters: {
		consumption_percent(value) {
			return wheel_tracker.render_consumption_bar(value);
		},
	},
};

frappe.listview_settings["Wheel"] = {
	formatters: {
		consumption_percent(value) {
			return wheel_tracker.render_consumption_bar(value);
		},
	},
};

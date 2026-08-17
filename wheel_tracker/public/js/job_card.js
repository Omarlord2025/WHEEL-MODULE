frappe.ui.form.on("Job Card", {
	refresh(frm) {
		frm.set_query("wheel", "custom_wheels_used", () => ({
			filters: { status: "In Stock" },
		}));
	},
});

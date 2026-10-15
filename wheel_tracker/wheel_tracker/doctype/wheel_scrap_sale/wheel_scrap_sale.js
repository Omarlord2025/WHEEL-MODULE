// Copyright (c) 2026, CNC Leaders and contributors
// For license information, please see license.txt

frappe.ui.form.on("Wheel Scrap Sale", {
	setup(frm) {
		frm.set_query("wheel", "wheels", () => ({
			query: "wheel_tracker.wheel_tracker.doctype.wheel_scrap_sale.wheel_scrap_sale.retired_wheel_query",
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Retired Wheels"), () => frm.events.get_retired_wheels(frm));
		}
	},

	get_retired_wheels(frm) {
		frappe.call({
			method: "wheel_tracker.wheel_tracker.doctype.wheel_scrap_sale.wheel_scrap_sale.get_retired_wheels_with_unsold_scrap",
			callback: (r) => {
				const already_listed = new Set((frm.doc.wheels || []).map((row) => row.wheel));
				const to_add = (r.message || []).filter((row) => !already_listed.has(row.wheel));

				if (!to_add.length) {
					frappe.msgprint(__("Every Retired Wheel with unsold scrap is already in this table."));
					return;
				}

				to_add.forEach((row) => {
					const child = frm.add_child("wheels");
					child.wheel = row.wheel;
				});
				frm.refresh_field("wheels");
			},
		});
	},
});

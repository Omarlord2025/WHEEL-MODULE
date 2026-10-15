// Copyright (c) 2026, CNC Leaders and contributors
// For license information, please see license.txt

frappe.ui.form.on("Wheel Retrieval", {
	get_items_button(frm) {
		if (!frm.doc.warehouse) {
			frappe.msgprint(__("Set a Warehouse first — it's used to look up each Item's current stock."));
			return;
		}
		frappe.call({
			method: "wheel_tracker.wheel_tracker.doctype.wheel_retrieval.wheel_retrieval.get_items_by_group",
			args: { item_group: frm.doc.item_group, warehouse: frm.doc.warehouse },
			callback: (r) => {
				const matches = r.message || [];
				if (!matches.length) {
					frappe.msgprint(
						frm.doc.item_group
							? __("No enabled Wheel Type was found under Item Group {0}.", [frm.doc.item_group])
							: __("No enabled Wheel Type exists yet — create one first.")
					);
					return;
				}

				const already_listed = new Set((frm.doc.items || []).map((row) => row.wheel_type));
				const to_add = matches.filter((row) => !already_listed.has(row.wheel_type));

				if (!to_add.length) {
					frappe.msgprint(__("Every matching Wheel Type is already in this table."));
					return;
				}

				to_add.forEach((row) => {
					const child = frm.add_child("items");
					child.wheel_type = row.wheel_type;
					child.current_stock_qty = row.current_stock_qty;
					child.qty_to_create = row.current_stock_qty || 0;
				});
				frm.refresh_field("items");
			},
		});
	},
});

frappe.ui.form.on("Wheel Retrieval Item", {
	wheel_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.wheel_type || !frm.doc.warehouse) return;
		frappe.call({
			method: "wheel_tracker.wheel_tracker.doctype.wheel_retrieval.wheel_retrieval.get_current_stock_qty",
			args: { wheel_type: row.wheel_type, warehouse: frm.doc.warehouse },
			callback: (r) => {
				frappe.model.set_value(cdt, cdn, "current_stock_qty", r.message || 0);
				if (!row.qty_to_create) {
					frappe.model.set_value(cdt, cdn, "qty_to_create", r.message || 0);
				}
			},
		});
	},
});

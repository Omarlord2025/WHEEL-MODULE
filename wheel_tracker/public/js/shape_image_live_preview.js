/**
 * Forces the Shape Image preview to update the moment a user picks/changes the Link
 * field it ultimately depends on — Wheel Type.shape, Wheel.wheel_type, Measurement
 * Event.wheel, Wheel Retirement.wheel. Deliberately explicit rather than relying on
 * fetch_from's own live add_fetch mechanism: that mechanism is only proven, in the
 * whole Frappe/ERPNext codebase, for Image-type fields living inside a child table
 * grid (e.g. Sales Order Item's image/image_view) — there's no precedent anywhere for
 * it on a top-level form field, which is what shape_image/shape_image_preview are
 * here, and grids and forms don't share the same refresh machinery. This reuses the
 * exact one-hop source every doctype's own `shape_image` fetch_from already points
 * at, so it never drifts from the real backfill/fetch chain.
 */

function apply_shape_image(frm, source_doctype, source_name) {
	if (!source_name) {
		frm.set_value("shape_image", "");
		frm.refresh_field("shape_image_preview");
		return;
	}
	frappe.db.get_value(source_doctype, source_name, "shape_image").then((r) => {
		frm.set_value("shape_image", (r.message && r.message.shape_image) || "");
		frm.refresh_field("shape_image_preview");
	});
}

frappe.ui.form.on("Wheel Type", {
	shape(frm) {
		apply_shape_image(frm, "Wheel Shape", frm.doc.shape);
	},
});

frappe.ui.form.on("Wheel", {
	wheel_type(frm) {
		apply_shape_image(frm, "Wheel Type", frm.doc.wheel_type);
	},
});

frappe.ui.form.on("Measurement Event", {
	wheel(frm) {
		apply_shape_image(frm, "Wheel", frm.doc.wheel);
	},
});

frappe.ui.form.on("Wheel Retirement", {
	wheel(frm) {
		apply_shape_image(frm, "Wheel", frm.doc.wheel);
	},
});

frappe.ui.form.on("Wheel Shape", {
	shape_image(frm) {
		// The user just uploaded/changed the real photo on the master itself —
		// refresh its own preview immediately rather than waiting for a save+reload.
		frm.refresh_field("shape_image_preview");
	},
});

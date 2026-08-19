// Copyright (c) 2026, Omar Sabry and contributors
// For license information, please see license.txt

frappe.ui.form.on("Measurement Event", {
	onload(frm) {
		// Wheels of a shape that doesn't Require Measurement (see Wheel Shape) can't
		// actually be saved here — server-side validate() enforces it — this just keeps
		// them out of the picker. Use Wheel Usability Check for those instead.
		frm.set_query("wheel", () => ({
			query: "wheel_tracker.wheel_tracker.doctype.measurement_event.measurement_event.measurable_wheel_query",
		}));
	},
});

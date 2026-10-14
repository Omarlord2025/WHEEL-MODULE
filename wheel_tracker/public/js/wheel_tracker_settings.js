// Reloads only this browser tab after a real language change, so the person who just
// flipped it sees Wheel Tracker's own strings switch immediately. wheel_tracker_language.js
// re-fetches the flag fresh on every page load for everyone else too — no shared state
// to push, nothing else to notify.
frappe.ui.form.on("Wheel Tracker Settings", {
	onload(frm) {
		frm._language_before_save = frm.doc.language;
	},
	after_save(frm) {
		if (frm.doc.language && frm.doc.language !== frm._language_before_save) {
			frappe.show_alert({ message: __("Language updated — reloading the page..."), indicator: "green" });
			setTimeout(() => window.location.reload(), 1000);
		}
		frm._language_before_save = frm.doc.language;
	},
});

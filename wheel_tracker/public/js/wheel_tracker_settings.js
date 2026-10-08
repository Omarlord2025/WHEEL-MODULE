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

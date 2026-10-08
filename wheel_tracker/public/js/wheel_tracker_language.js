(function () {
	// Scoped, session-independent translation override for Wheel Tracker's own
	// strings only. Wraps the global `__()` Frappe already routes every label,
	// breadcrumb, and workspace title through — but only ever answers for the exact
	// strings in this module's own translations/ar.csv; every other string (any core
	// or other app string) falls straight through to the original, untouched. This
	// never writes to System Settings or any User's `language` field, so it has zero
	// effect outside Wheel Tracker's own doctypes/pages, regardless of who's viewing
	// or what their own language is set to.
	const original_translate = window.__;
	let wt_language = "English";
	let wt_dictionary = {};

	function refresh_state() {
		frappe.call({
			method: "wheel_tracker.language_switch.get_language_state",
			callback(r) {
				if (r.message) {
					wt_language = r.message.language;
					wt_dictionary = r.message.dictionary || {};
				}
			},
		});
	}

	window.__ = frappe._ = function (txt, replace, context) {
		if (wt_language === "Arabic" && typeof txt === "string" && wt_dictionary[txt]) {
			let translated = wt_dictionary[txt];
			if (replace && typeof replace === "object") {
				translated = $.format(translated, replace);
			}
			return translated;
		}
		return original_translate(txt, replace, context);
	};

	frappe.wheel_tracker_refresh_language = refresh_state;
	refresh_state();
})();

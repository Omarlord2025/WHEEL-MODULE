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

	function on_workspace_page() {
		// Frappe's own workspace renderer (frappe/public/js/.../blocks/block.js, make())
		// matches a shortcut/card/number-card block's stored name against its pre-fetched
		// data via `obj.label == __(block_name)` — reusing the *same* translate function
		// for an internal identity check, not just display. If we translate block_name
		// here but the other side of that comparison (obj.label, built server-side) stays
		// English, the match silently fails and the widget never renders — no error, it
		// just vanishes. Confirmed live: every shortcut/number-card/card-link on the
		// Grinding Wheels workspace disappeared under Arabic before this guard existed.
		// Skipping translation specifically on the Workspaces route sidesteps the entire
		// bug class (chart/quick_list/links blocks use the same pattern) without having to
		// enumerate and exclude every doctype/shortcut/card name one at a time — it has no
		// effect on breadcrumbs or list/report titles, which render on their own separate
		// routes and never hit this comparison.
		return typeof frappe !== "undefined" && frappe.get_route && frappe.get_route()[0] === "Workspaces";
	}

	window.__ = frappe._ = function (txt, replace, context) {
		if (
			wt_language === "Arabic" &&
			typeof txt === "string" &&
			wt_dictionary[txt] &&
			!on_workspace_page()
		) {
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

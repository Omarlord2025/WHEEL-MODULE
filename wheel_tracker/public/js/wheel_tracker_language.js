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
	// Read synchronously from frappe.boot first (populated server-side by
	// language_switch.boot_session(), inline in the page HTML before any bundle script
	// even runs) instead of starting from "English" and waiting on an async frappe.call
	// — Desk's own sidebar renders once, synchronously, very early in boot and is never
	// rebuilt afterward, so a cold page load reliably lost that race under the old
	// async-only version: the breadcrumb/title (rendered later, after boot settles)
	// came out correctly in Arabic while the sidebar entry for the same workspace,
	// rendered earlier, stayed in English — confirmed live, fixed only by a reload. The
	// boot payload removes the race instead of working around it.
	const boot_state = (frappe.boot && frappe.boot.wheel_tracker_language_state) || {};
	let wt_language = boot_state.language || "English";
	let wt_dictionary = boot_state.dictionary || {};

	function refresh_state() {
		// Re-checks after boot — picks up a language change saved from another tab/
		// session without needing a fresh login; the first paint never depends on this.
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

	// --- Workspace shortcut/card/number-card/chart/quick-list fix -------------------
	// Frappe's own workspace renderer (frappe/public/js/frappe/views/workspace/blocks/
	// block.js, make()) matches a block's stored name against its server-fetched data
	// via `obj.label == __(block_name)` — reusing the translate function as an
	// *internal identity check*, not just for display. `obj.label` comes straight from
	// the server and is always English (this feature never touches server-side
	// language), so once block_name is translated the comparison fails every time and
	// the widget silently never renders — confirmed live: every shortcut/number-card/
	// card-link on the Grinding Wheels workspace vanished under Arabic, no error
	// anywhere. A route-wide "don't translate on the Workspaces page" fix was tried
	// first and worked, but it's too broad: it also blocked legitimate, safe
	// translation of header text and anything else on that page. The precise fix:
	// patch just the shared `make()` method (every workspace block type — shortcut,
	// card, number_card, chart, quick_list — extends the same `Block` base and
	// inherits it unchanged, reachable via the public `frappe.workspace_block.blocks`
	// registry) so *only* its internal matching uses the original, untranslated
	// `__()`, while the widget it then builds still renders through our wrapped
	// `__()` normally, same as everywhere else. This is a pinned reimplementation of
	// Frappe's current `make()` body (same file/line as cited above) — if a Frappe
	// upgrade changes that method, this silently stops helping (falls back to Frappe's
	// own current behavior, i.e. no translation on these blocks — not breakage), but
	// should be re-checked against the new source after any framework upgrade.
	function patch_workspace_block_matching() {
		if (!frappe.workspace_block || !frappe.workspace_block.blocks) return;
		const sample = frappe.workspace_block.blocks.shortcut;
		if (!sample || !sample.prototype) return;
		const block_proto = Object.getPrototypeOf(sample.prototype);
		if (!block_proto || typeof block_proto.make !== "function" || block_proto.__wt_patched) return;

		block_proto.make = function (block, block_name, widget_type = block) {
			let block_data = this.config.page_data[block + "s"].items.find((obj) => {
				return (
					frappe.utils.unescape_html(obj.label) ==
					frappe.utils.unescape_html(original_translate(block_name))
				);
			});
			if (!block_data) return false;
			this.wrapper.innerHTML = "";
			block_data.in_customize_mode = !this.readOnly;
			this.block_widget = new frappe.widget.SingleWidgetGroup({
				container: this.wrapper,
				type: widget_type,
				class_name: block == "chart" ? "widget-charts" : "",
				options: this.options,
				widgets: block_data,
				api: this.api,
				block: this.block,
			});
			this.wrapper.setAttribute(block + "_name", block_name);
			if (!this.readOnly) {
				this.block_widget.customize();
			}
			return true;
		};
		block_proto.__wt_patched = true;
	}

	patch_workspace_block_matching();

	// --- Links-card individual doctype items -----------------------------------------
	// Separate, unrelated gap: frappe/public/js/frappe/widgets/links_widget.js builds
	// each doctype link's visible text as `item.link_title = item.label || item.name`
	// and inserts it straight into the DOM — never passed through `__()` at all, by
	// Frappe itself, for anyone, in any language (confirmed by reading the file; this
	// is a pre-existing core gap, not something this feature introduced or can trigger
	// the make()-matching bug through, since no identity comparison is involved here).
	// Fixed with a plain, additive DOM text swap instead of another prototype patch:
	// safe because it runs after Frappe's own rendering, only ever replaces whole,
	// exact-match text nodes inside `.link-text`/`.link-content` elements, and a
	// MutationObserver reacting to added nodes rather than clobbering editable content.
	function translate_link_item_text(el) {
		const original = el.textContent;
		const trimmed = original.trim();
		if (!trimmed) return;
		const translated = wt_dictionary[trimmed];
		if (translated && translated !== trimmed) {
			el.textContent = original.replace(trimmed, translated);
		}
	}

	function scan_for_link_items(root) {
		if (wt_language !== "Arabic") return;
		root.querySelectorAll &&
			root.querySelectorAll(".link-text, .link-content").forEach(translate_link_item_text);
	}

	function observe_workspace_links() {
		// document.body, not a specific workspace container captured once at script
		// load: the workspace's own `.layout-main-section` is torn down and rebuilt on
		// every SPA navigation back to it, which would silently disconnect an observer
		// bound to the old element. body persists for the whole Desk session.
		const observer = new MutationObserver((mutations) => {
			if (wt_language !== "Arabic") return;
			for (const mutation of mutations) {
				mutation.addedNodes.forEach((node) => {
					if (node.nodeType !== 1) return;
					if (node.matches && node.matches(".link-text, .link-content")) {
						translate_link_item_text(node);
					}
					scan_for_link_items(node);
				});
			}
		});
		observer.observe(document.body, { childList: true, subtree: true });
		scan_for_link_items(document.body);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", observe_workspace_links);
	} else {
		observe_workspace_links();
	}

	// --- Date picker month/day names --------------------------------------------------
	// A separate gap from everything above: the calendar popup's month/day names come
	// from Frappe's own bundled air-datepicker locale files (confirmed: a full Arabic
	// one already ships, frappe/public/js/frappe/form/controls/datepicker_i18n.js), but
	// ControlDate.set_date_options() (frappe/public/js/frappe/form/controls/date.js)
	// picks the language from `frappe.boot.user.language` — the viewer's own real
	// account setting, not our `__()` dictionary, and not something this feature
	// touches (see the v19/v20 PRD entries on why not). So the calendar would otherwise
	// always render in whatever the viewer's own language already is, regardless of
	// this module's switch. Patches the one method that picks it, scoped to only this
	// module's own doctypes/pages (checked via the control's own `doctype`, when bound
	// to a form, or the current route for standalone Page/Report filter fields like
	// Batch Measurement Entry's or Wheel Cost Summary's own date filters) — every date
	// field on every other doctype keeps using the viewer's own language untouched.
	const WHEEL_TRACKER_DOCTYPES = new Set([
		"Wheel", "Wheel Type", "Wheel Shape", "Wheel Geometry", "Wheel Material",
		"Wheel Grit", "Wheel Concentration", "Wheel Bond", "Measurement Event",
		"Measurement Event Job Card", "Wheel Retirement", "Wheel Tracker Settings",
		"Job Card Wheel", "Wheel Type Profile Segment",
	]);
	const WHEEL_TRACKER_ROUTES = new Set([
		"wheel-batch-measurement", "wheel-bulk-import", "Wheel Cost Summary",
	]);

	function is_wheel_tracker_context(control) {
		if (control.doctype && WHEEL_TRACKER_DOCTYPES.has(control.doctype)) return true;
		if (control.doctype) return false;
		const route = frappe.get_route ? frappe.get_route() : [];
		return route.some((part) => WHEEL_TRACKER_ROUTES.has(part));
	}

	function patch_datepicker_language() {
		const ControlDate = frappe.ui.form && frappe.ui.form.ControlDate;
		if (!ControlDate || !ControlDate.prototype || ControlDate.prototype.__wt_patched) return;

		const original_set_date_options = ControlDate.prototype.set_date_options;
		ControlDate.prototype.set_date_options = function (...args) {
			original_set_date_options.apply(this, args);
			if (
				wt_language === "Arabic" &&
				$.fn.datepicker.language["ar"] &&
				is_wheel_tracker_context(this)
			) {
				this.datepicker_options.language = "ar";
			}
		};
		ControlDate.prototype.__wt_patched = true;
	}

	patch_datepicker_language();

	frappe.wheel_tracker_refresh_language = refresh_state;
	refresh_state();
})();

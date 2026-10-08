frappe.provide("wheel_tracker");

/**
 * Combined progress-bar + percentage label for a Consumption % (Percent fieldtype)
 * value — Frappe's own List View renders a Percent field as a bare bar with no number
 * on it (see frappe/public/js/frappe/list/list_view.js), so this is used as a
 * `listview_settings.formatters` override wherever that's not enough on its own.
 * Shared by Wheel and Measurement Event's list views — both list the same field with
 * the same meaning, so the formatter lives here once rather than being duplicated.
 */
wheel_tracker.render_consumption_bar = function (value) {
	const pct = Math.max(0, Math.min(100, Math.round((Number(value) || 0) * 100) / 100));
	const color = pct >= 90 ? "progress-bar-danger" : pct >= 70 ? "progress-bar-warning" : "progress-bar-success";

	return `
		<div class="progress" style="margin: 0; height: 14px; position: relative;" title="${pct}%">
			<div class="progress-bar ${color}" role="progressbar"
				aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"
				style="width: ${pct}%;"></div>
			<span style="position: absolute; inset: 0; text-align: center; font-size: 11px; line-height: 14px; color: #333;">
				${pct}%
			</span>
		</div>
	`;
};

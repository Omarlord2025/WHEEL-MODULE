frappe.pages["wheel-batch-measurement"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Batch Measurement Entry",
		single_column: true,
	});

	new WheelBatchMeasurement(page);
};

class WheelBatchMeasurement {
	constructor(page) {
		this.page = page;
		this.setup_date_fields();
		this.render_intro();
	}

	setup_date_fields() {
		this.from_date_field = this.page.add_field({
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
			change: () => this.load_wheels(),
		});
		this.to_date_field = this.page.add_field({
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			change: () => this.load_wheels(),
		});
	}

	render_intro() {
		this.$body = $(`
			<div class="wheel-batch-measurement">
				<div class="alert alert-info">
					${__(
						"Pick a date range to load every Wheel used on a Job Card posted in it, enter each Wheel's new caliper reading, then submit once. One real Measurement Event is created and submitted per Wheel — same wear/cost/retirement logic as entering them one at a time. A Wheel already measured since the From Date won't be listed again."
					)}
				</div>
				<div class="wheel-batch-measurement-wheels"></div>
				<div class="wheel-batch-measurement-results" style="margin-top: 20px;"></div>
			</div>
		`).appendTo(this.page.main);
	}

	load_wheels() {
		const from_date = this.from_date_field.get_value();
		const to_date = this.to_date_field.get_value();
		const $wheels = this.$body.find(".wheel-batch-measurement-wheels");
		const $results = this.$body.find(".wheel-batch-measurement-results");
		$results.empty();
		this.page.clear_primary_action();

		if (!from_date || !to_date) {
			$wheels.empty();
			return;
		}

		$wheels.html(`<div class="text-muted">${__("Loading...")}</div>`);

		frappe.call({
			method: "wheel_tracker.batch_measurement.get_wheels_used_between",
			args: { from_date, to_date },
			callback: (r) => this.render_wheels(r.message || {}, $wheels),
		});
	}

	render_wheels(data, $wheels) {
		const job_cards = data.job_cards || [];
		const measurable = data.measurable || [];
		const non_measurable = data.non_measurable || [];

		if (!job_cards.length) {
			$wheels.html(
				`<div class="text-muted">${__("No Job Cards were posted in this date range.")}</div>`
			);
			return;
		}

		if (!measurable.length && !non_measurable.length) {
			$wheels.html(
				`<div class="text-muted">${__(
					"No Wheels left to measure for this date range — either none were used on these Job Cards, or they've already been measured."
				)}</div>`
			);
			return;
		}

		let html = "";
		if (non_measurable.length) {
			html += `
				<div class="alert alert-warning">
					${__("Not measured by caliper reading — use Wheel Retirement instead")}:
					${non_measurable.map((w) => frappe.utils.escape_html(w.wheel)).join(", ")}
				</div>
			`;
		}

		if (measurable.length) {
			html += `
				<table class="table table-bordered wheel-batch-measurement-table">
					<thead>
						<tr>
							<th>${__("Wheel")}</th>
							<th>${__("Wheel Type")}</th>
							<th>${__("Job Cards")}</th>
							<th>${__("Diameter (mm)")}</th>
							<th>${__("Inner Diameter (mm)")}</th>
							<th>${__("Diamond Layer Height (mm)")}</th>
						</tr>
					</thead>
					<tbody>
						${measurable
							.map(
								(w) => `
							<tr data-wheel="${frappe.utils.escape_html(w.wheel)}">
								<td>${frappe.utils.escape_html(w.wheel)}</td>
								<td>${frappe.utils.escape_html(w.wheel_type)}</td>
								<td>${(w.job_cards || []).map((jc) => frappe.utils.escape_html(jc)).join(", ")}</td>
								<td><input type="number" step="any" class="form-control input-sm batch-diameter" value="${w.current_diameter}"></td>
								<td><input type="number" step="any" class="form-control input-sm batch-inner-diameter" value="${w.current_inner_diameter}"></td>
								<td><input type="number" step="any" class="form-control input-sm batch-diamond-height" value="${w.current_diamond_height}"></td>
							</tr>
						`
							)
							.join("")}
					</tbody>
				</table>
			`;
		}

		$wheels.html(html);

		if (measurable.length) {
			this.page.set_primary_action(__("Submit Measurements"), () => this.submit(), "upload");
		}
	}

	submit() {
		const readings = [];
		this.$body.find(".wheel-batch-measurement-table tbody tr").each(function () {
			const $row = $(this);
			readings.push({
				wheel: $row.attr("data-wheel"),
				diameter: flt($row.find(".batch-diameter").val()),
				inner_diameter: flt($row.find(".batch-inner-diameter").val()),
				diamond_height: flt($row.find(".batch-diamond-height").val()),
			});
		});

		if (!readings.length) return;

		const $results = this.$body.find(".wheel-batch-measurement-results");
		$results.html(`<div class="text-muted">${__("Submitting...")}</div>`);

		frappe.call({
			method: "wheel_tracker.batch_measurement.submit_batch_measurements",
			args: { readings },
			freeze: true,
			freeze_message: __("Submitting measurements..."),
			callback: (r) => this.render_results(r.message || {}, $results),
			error: () => {
				$results.html(
					`<div class="alert alert-danger">${__("Batch submission failed. Check the Error Log for details.")}</div>`
				);
			},
		});
	}

	render_results(summary, $results) {
		const errors = summary.errors || [];
		const has_errors = errors.length > 0;

		let html = `
			<div class="alert alert-success">
				${__("Measurement Events created")}: <b>${summary.created || 0}</b> &nbsp;|&nbsp;
				${__("Errors")}: <b>${errors.length}</b>
			</div>
		`;

		if (has_errors) {
			html += `
				<table class="table table-bordered">
					<thead><tr><th>${__("Wheel")}</th><th>${__("Error")}</th></tr></thead>
					<tbody>
						${errors
							.map(
								(e) =>
									`<tr><td>${frappe.utils.escape_html(e.wheel)}</td><td>${frappe.utils.escape_html(e.message)}</td></tr>`
							)
							.join("")}
					</tbody>
				</table>
			`;
		}

		$results.html(html);
		this.load_wheels();
	}
}

frappe.pages["wheel-bulk-import"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Bulk Import Wheels",
		single_column: true,
	});

	new WheelBulkImport(page);
};

class WheelBulkImport {
	constructor(page) {
		this.page = page;
		this.setup_actions();
		this.render_intro();
	}

	setup_actions() {
		this.page.set_primary_action(__("Upload CSV & Import"), () => this.pick_file(), "upload");
		this.page.add_menu_item(__("Download CSV Template"), () => this.download_template());
	}

	render_intro() {
		this.$body = $(`
			<div class="wheel-bulk-import">
				<div class="alert alert-info">
					${__(
						"Backfills Wheel Type + Wheel + a baseline Measurement Event per row from a CSV — the same importer used to load the real ~78-wheel backfill. Each row's <b>shape</b> and <b>material</b> must already exist as a Wheel Shape / Wheel Material record; rows with an unknown one are reported as an error rather than guessed at. Grit, Concentration, and Bond are created automatically if new."
					)}
				</div>
				<div class="wheel-bulk-import-columns"></div>
				<div class="wheel-bulk-import-results" style="margin-top: 20px;"></div>
			</div>
		`).appendTo(this.page.main);

		this.render_columns();
	}

	render_columns() {
		frappe.call({
			method: "wheel_tracker.bulk_import.get_import_template",
			callback: (r) => {
				this.template_header = r.message;
				const columns = r.message.split(",");
				const $wrapper = this.$body.find(".wheel-bulk-import-columns");
				$wrapper.html(`
					<p class="text-muted">${__("Expected CSV columns, in order:")}</p>
					<code style="display: block; white-space: pre-wrap; word-break: break-all;">${frappe.utils.escape_html(
						columns.join(", ")
					)}</code>
				`);
			},
		});
	}

	download_template() {
		frappe.call({
			method: "wheel_tracker.bulk_import.get_import_template",
			callback: (r) => {
				const blob = new Blob([r.message + "\n"], { type: "text/csv" });
				const url = window.URL.createObjectURL(blob);
				const link = document.createElement("a");
				link.href = url;
				link.download = "wheel_bulk_import_template.csv";
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
				window.URL.revokeObjectURL(url);
			},
		});
	}

	pick_file() {
		new frappe.ui.FileUploader({
			folder: "Home",
			restrictions: {
				allowed_file_types: [".csv", "text/csv"],
			},
			on_success: (file_doc) => this.run_import(file_doc.file_url),
		});
	}

	run_import(file_url) {
		const $results = this.$body.find(".wheel-bulk-import-results");
		$results.html(`<div class="text-muted">${__("Importing...")}</div>`);

		frappe.call({
			method: "wheel_tracker.bulk_import.import_wheels_from_csv",
			args: { file_url },
			freeze: true,
			freeze_message: __("Importing wheels..."),
			callback: (r) => this.render_results(r.message, $results),
			error: () => {
				$results.html(`<div class="alert alert-danger">${__("Import failed. Check the Error Log for details.")}</div>`);
			},
		});
	}

	render_results(summary, $results) {
		const has_errors = summary.errors && summary.errors.length;

		let html = `
			<div class="alert alert-success">
				${__("Wheel Types created")}: <b>${summary.wheel_types_created}</b> &nbsp;|&nbsp;
				${__("Wheel Types reused")}: <b>${summary.wheel_types_reused}</b> &nbsp;|&nbsp;
				${__("Wheels created")}: <b>${summary.wheels_created}</b> &nbsp;|&nbsp;
				${__("Errors")}: <b>${summary.errors.length}</b>
			</div>
		`;

		if (has_errors) {
			html += `
				<table class="table table-bordered">
					<thead><tr><th>${__("CSV Row")}</th><th>${__("Error")}</th></tr></thead>
					<tbody>
						${summary.errors
							.map(
								(e) =>
									`<tr><td>${e.row}</td><td>${frappe.utils.escape_html(e.message)}</td></tr>`
							)
							.join("")}
					</tbody>
				</table>
			`;
		}

		$results.html(html);
	}
}

# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Creates the Custom HTML Block backing the Grinding Wheels workspace's Language
Toggle button (see PRD v13). Idempotent — a Custom HTML Block is a plain document, not
DocType JSON, so it has to be created via a patch rather than synced from a fixture
file. Content lives here, in Python, rather than a separate .html/.js file, since it's
this one record's field values, not a reusable asset."""

import frappe

BLOCK_NAME = "Grinding Wheels Language Toggle"

HTML = """
<div style="display:flex; justify-content:center; padding: 6px 0;">
	<button class="btn btn-sm btn-default wt-language-toggle-btn">
		🌐 العربية / English
	</button>
</div>
"""

SCRIPT = """
let btn = root_element.querySelector(".wt-language-toggle-btn");
btn.addEventListener("click", () => {
	btn.disabled = true;
	frappe.call({
		method: "wheel_tracker.language_toggle.toggle_language",
		callback: () => window.location.reload(),
	});
});
"""


def execute():
	if frappe.db.exists("Custom HTML Block", BLOCK_NAME):
		return

	frappe.get_doc(
		{
			"doctype": "Custom HTML Block",
			"name": BLOCK_NAME,
			"private": 0,
			"html": HTML,
			"script": SCRIPT,
		}
	).insert(ignore_permissions=True)

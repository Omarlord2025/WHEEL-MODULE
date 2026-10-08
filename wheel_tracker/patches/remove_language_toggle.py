# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Removes every language/name-translation toggle block from the Grinding Wheels
workspace (PRD v13's own "Language Toggle" button, plus a second, differently-named
"Translate Names" toggle switch that was added directly on the live site afterwards,
outside this app's own fixtures/patches) — both removed by customer request. Idempotent.

Clears the Workspace's own `content`/`custom_blocks` directly via frappe.db.set_value
rather than relying on the next fixture sync to do it: a Workspace JSON fixture only
re-syncs when its file's `modified` is newer than the DB's (see CLAUDE.md) — a
Desk-UI edit to the live workspace (like the ad-hoc "Translate Names" block) bumps the
DB's `modified` past whatever this app's own fixture file declares, which would
silently skip overwriting it on the very next migrate otherwise."""

import json

import frappe

# Matched case-insensitively as a substring, not an exact name, deliberately: the
# Workspace's own `content` JSON blob isn't link-validated against a real Custom HTML
# Block name, so a block added/relabelled by hand on the live site (confirmed found:
# a "Translate Names" toggle referencing `custom_block_name: "Translate Names"` in
# `content`, with no "Grinding Wheels " prefix, distinct from the real
# "Grinding Wheels Translate Names" doc it was presumably meant to point at) can drift
# from the actual document name. An exact-match list already missed this once.
NAME_FRAGMENTS = ("language", "translat")


def _is_toggle_name(name: str) -> bool:
	name = (name or "").lower()
	return any(fragment in name for fragment in NAME_FRAGMENTS)


def execute():
	remove_custom_html_blocks()
	strip_workspace_references()


def remove_custom_html_blocks():
	for name in frappe.get_all("Custom HTML Block", pluck="name"):
		if _is_toggle_name(name):
			frappe.delete_doc("Custom HTML Block", name, ignore_permissions=True, force=True)


def strip_workspace_references():
	if not frappe.db.exists("Workspace", "Grinding Wheels"):
		return

	content = frappe.db.get_value("Workspace", "Grinding Wheels", "content")
	if content:
		blocks = json.loads(content)
		blocks = [
			b
			for b in blocks
			if not (
				b.get("type") == "custom_block"
				and _is_toggle_name(b.get("data", {}).get("custom_block_name"))
			)
		]
		frappe.db.set_value("Workspace", "Grinding Wheels", "content", json.dumps(blocks))

	for row_name in frappe.get_all(
		"Workspace Custom Block", filters={"parent": "Grinding Wheels"}, pluck="custom_block_name"
	):
		if _is_toggle_name(row_name):
			frappe.db.delete(
				"Workspace Custom Block",
				{"parent": "Grinding Wheels", "custom_block_name": row_name},
			)

	frappe.clear_cache(doctype="Workspace")

# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Attaches the real reference photos the customer uploaded (via the Google Form's
Drive-folder upload links, see CUSTOMER_DECISION_FORM.gs) to each real Wheel Shape
record, then backfills the new `shape_image` fetched field (see PRD v16) onto every
existing Wheel Type/Wheel/Measurement Event/Wheel Retirement — fetch_from only
populates on save, so pre-existing rows need this one-time backfill; anything created
from now on gets it automatically through the normal fetch mechanism. Idempotent:
skips a Wheel Shape that already has an image, and the backfill UPDATEs only ever
touch rows whose source image is actually set."""

import frappe
from frappe.utils.file_manager import save_file

# P-series shares one representative image across all three real Shape records —
# confirmed by the shop floor (Google Form, Case 11) as visually/functionally
# identical for this purpose; everything else is shape-specific.
SHAPE_IMAGES = {
	"1A1": "1a1.jpg",
	"1V1": "1v1.png",
	"11V9": "11v9.jpg",
	"12V9": "12v9.jpg",
	"P1.5": "p-series.jpeg",
	"P1.7": "p-series.jpeg",
	"P2": "p-series.jpeg",
}


def execute():
	attach_shape_images()
	backfill_fetched_shape_images()


def attach_shape_images():
	"""Create a real File attachment on each Wheel Shape from the bundled image, and
	set its shape_image field to the resulting file_url."""
	for shape_code, filename in SHAPE_IMAGES.items():
		if not frappe.db.exists("Wheel Shape", shape_code):
			continue
		if frappe.db.get_value("Wheel Shape", shape_code, "shape_image"):
			continue  # already attached — idempotent

		path = frappe.get_app_path("wheel_tracker", "public", "images", "wheel_shapes", filename)
		with open(path, "rb") as f:
			content = f.read()

		file_doc = save_file(filename, content, "Wheel Shape", shape_code, is_private=0)
		frappe.db.set_value("Wheel Shape", shape_code, "shape_image", file_doc.file_url)


def backfill_fetched_shape_images():
	"""fetch_from only fires on save, so every Wheel Type/Wheel/Measurement
	Event/Wheel Retirement row that existed before this patch needs its
	shape_image backfilled directly — a bulk UPDATE...JOIN per hop, not a
	frappe.get_doc() loop (see CLAUDE.md's performance checklist), chained in the
	same order the fetch_from chain itself resolves (Shape -> Type -> Wheel ->
	Measurement Event / Wheel Retirement)."""
	frappe.db.sql(
		"""
		update `tabWheel Type` wt
		inner join `tabWheel Shape` ws on ws.name = wt.shape
		set wt.shape_image = ws.shape_image
		where ws.shape_image is not null and ws.shape_image != ''
		"""
	)
	frappe.db.sql(
		"""
		update `tabWheel` w
		inner join `tabWheel Type` wt on wt.name = w.wheel_type
		set w.shape_image = wt.shape_image
		where wt.shape_image is not null and wt.shape_image != ''
		"""
	)
	frappe.db.sql(
		"""
		update `tabMeasurement Event` me
		inner join `tabWheel` w on w.name = me.wheel
		set me.shape_image = w.shape_image
		where w.shape_image is not null and w.shape_image != ''
		"""
	)
	frappe.db.sql(
		"""
		update `tabWheel Retirement` wr
		inner join `tabWheel` w on w.name = wr.wheel
		set wr.shape_image = w.shape_image
		where w.shape_image is not null and w.shape_image != ''
		"""
	)

# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

"""Backfill tooling for the wheels tracked in the legacy spreadsheet(s) — both the
original 158-wheel FLUTE/WHEELS WITH ANGLES file and `Main data and flow.xlsx`, the
single-table Arabic-header file the team actually keeps up to date (see PRD v3).
Neither is in a shape a straight Data Import can produce Wheel Types + Wheels +
history from directly, so this importer works off a documented, generic CSV schema
instead — see TEMPLATE_COLUMNS below for the exact headers.

Each row creates (or reuses, by spec_code) a Wheel Type, a Wheel at that Wheel Type's
new-wheel dimensions, and one submitted "Backfill baseline" Measurement Event carrying
the row's current readings — so the wear math and any auto-retirement run through the
exact same code path as a live measurement, instead of being duplicated here. The
baseline event's confirmed_volume is computed automatically from current_diameter,
same as any other Measurement Event — see PRD v6.

shape and material must already exist as Wheel Shape / Wheel Material records (the
seeded set covers everything found in Main data and flow.xlsx — 1A1, P1.5, P1.7, P2,
12V9, 11V9, 1V1 / Diamond, CBN); a row referencing an unknown one is reported as an
error rather than guessed at, since that choice drives which volume formula applies.
grit/concentration/bond are looser spec codes with no formula impact, so those are
auto-created on the fly if a row's value doesn't exist yet.
"""

import csv
import io

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

TEMPLATE_COLUMNS = [
	"shape",  # existing Wheel Shape, e.g. 1A1, P2, 12V9, 11V9, 1V1
	"material",  # existing Wheel Material, e.g. Diamond, CBN
	"spec_code",  # shared "Code", e.g. 100642
	"item",  # ERPNext Item code; blank = auto-created using spec_code as the item_code
	"legacy_spec_name",  # optional; the original free-text spec string, preserved as-is
	"original_diameter",
	"original_inner_diameter",
	"original_diamond_height",
	"total_body_height",  # optional
	"angle",  # single-bevel profiled shapes only (e.g. 45 for 1V1/45), degrees; compound/
	          # stepped shapes (11V9/12V9) need a second Profile Segment added via Desk after import
	"original_volume_override",  # optional; blank = auto-calculated from dimensions
	"unit_cost",
	"reorder_point",  # optional, default 0
	"reorder_qty",  # optional, default 0
	"grit",  # optional; auto-created if new
	"concentration",  # optional; auto-created if new
	"bond",  # optional; auto-created if new
	"factory_wheel_code",  # unique per physical wheel; blank = auto-generated
	"current_diameter",
	"current_inner_diameter",
	"current_diamond_height",
	"warehouse",  # optional
	"received_on",  # optional date, defaults to today
	"status",  # optional: In Stock / In Use / Retired, default In Stock
	"retirement_reason",  # optional, only used if status = Retired
]

SIMPLE_MASTER_DOCTYPES = {
	"grit": ("Wheel Grit", "grit_code"),
	"concentration": ("Wheel Concentration", "concentration_code"),
	"bond": ("Wheel Bond", "bond_code"),
}


@frappe.whitelist()
def get_import_template() -> str:
	"""CSV header row for the backfill import, as text."""
	return ",".join(TEMPLATE_COLUMNS)


@frappe.whitelist()
def import_wheels_from_csv(file_url: str) -> dict:
	"""Backfill Wheel Type + Wheel + baseline Measurement Event records from a CSV.

	Args:
		file_url: file_url of an already-uploaded File document, matching TEMPLATE_COLUMNS.

	Returns:
		dict summary: counts of created/reused records and any per-row errors
		(processing continues past a bad row instead of aborting the whole batch).
	"""
	content = frappe.get_doc("File", {"file_url": file_url}).get_content()
	if isinstance(content, bytes):
		content = content.decode("utf-8-sig")
	rows = list(csv.DictReader(io.StringIO(content)))

	summary = {
		"wheel_types_created": 0,
		"wheel_types_reused": 0,
		"wheels_created": 0,
		"errors": [],
	}
	wheel_type_cache = {}

	for i, row in enumerate(rows, start=2):  # row 1 is the header
		savepoint = f"bulk_import_row_{i}"
		frappe.db.savepoint(savepoint)
		try:
			wheel_type_name = get_or_create_wheel_type(row, wheel_type_cache, summary)
			create_wheel_with_baseline(row, wheel_type_name)
			summary["wheels_created"] += 1
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			summary["errors"].append({"row": i, "message": str(e)})

	return summary


def get_or_create_wheel_type(row: dict, cache: dict, summary: dict) -> str:
	"""Find an existing Wheel Type by spec_code, or create one from the row's spec columns."""
	spec_code = row["spec_code"].strip()
	if spec_code in cache:
		return cache[spec_code]

	existing = frappe.db.get_value("Wheel Type", {"spec_code": spec_code})
	if existing:
		cache[spec_code] = existing
		summary["wheel_types_reused"] += 1
		return existing

	shape = row["shape"].strip()
	material = row["material"].strip()
	if not frappe.db.exists("Wheel Shape", shape):
		frappe.throw(_("Wheel Shape {0} does not exist — create it first.").format(shape))
	if not frappe.db.exists("Wheel Material", material):
		frappe.throw(_("Wheel Material {0} does not exist — create it first.").format(material))

	item = get_or_create_item((row.get("item") or "").strip() or spec_code, shape, material)
	volume_override = flt(row.get("original_volume_override")) or None

	profile_segments = []
	angle = flt(row.get("angle")) or None
	if angle:
		# A flat CSV row can only describe a single-bevel profile (one angle, one height) —
		# a compound/stepped shape (11V9/12V9) needs its second segment added via Desk after
		# import, since a variable-length breakpoint list doesn't fit one CSV column. See PRD v7.
		profile_segments = [{"angle": angle, "height": flt(row["original_diamond_height"])}]

	wheel_type = frappe.get_doc(
		{
			"doctype": "Wheel Type",
			"spec_code": spec_code,
			"shape": shape,
			"material": material,
			"item": item,
			"legacy_spec_name": row.get("legacy_spec_name") or "",
			"original_diameter": flt(row["original_diameter"]),
			"original_inner_diameter": flt(row["original_inner_diameter"]),
			"original_diamond_height": flt(row["original_diamond_height"]),
			"total_body_height": flt(row.get("total_body_height")),
			"profile_segments": profile_segments,
			"auto_calc_volume": 0 if volume_override else 1,
			"original_volume": volume_override,
			"unit_cost": flt(row["unit_cost"]),
			"reorder_point": cint(row.get("reorder_point")),
			"reorder_qty": cint(row.get("reorder_qty")),
			"grit": get_or_create_simple_master("grit", row.get("grit")),
			"concentration": get_or_create_simple_master("concentration", row.get("concentration")),
			"bond": get_or_create_simple_master("bond", row.get("bond")),
		}
	).insert(ignore_permissions=True)

	cache[spec_code] = wheel_type.name
	summary["wheel_types_created"] += 1
	return wheel_type.name


def get_or_create_item(item_code: str, shape: str, material: str) -> str:
	"""Get-or-create the ERPNext Item backing a Wheel Type. The legacy sheet has no ERPNext
	item codes at all, so when a row leaves "item" blank, the caller defaults it to the
	spec_code — one Item per spec, matching Wheel Type's own one-Item-per-spec rule."""
	if frappe.db.exists("Item", item_code):
		return item_code

	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": f"{material} {shape} Resharpening Wheel — {item_code}",
			"item_group": "All Item Groups",
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"has_serial_no": 1,
		}
	).insert(ignore_permissions=True)
	return item_code


def get_or_create_simple_master(field: str, value: str | None) -> str | None:
	"""Get-or-create a Wheel Grit / Wheel Concentration / Wheel Bond record by code.
	Unlike Wheel Shape/Material, these don't drive the volume formula, so it's safe
	to extend the list on the fly rather than requiring it to pre-exist."""
	value = (value or "").strip()
	if not value:
		return None

	doctype, name_field = SIMPLE_MASTER_DOCTYPES[field]
	if not frappe.db.exists(doctype, value):
		frappe.get_doc({"doctype": doctype, name_field: value}).insert(ignore_permissions=True)
	return value


def create_wheel_with_baseline(row: dict, wheel_type_name: str):
	"""Create a Wheel at new-wheel dimensions, then submit a baseline Measurement Event
	carrying the row's current readings — reusing the live wear/retirement logic."""
	wheel_type = frappe.get_cached_doc("Wheel Type", wheel_type_name)

	wheel = frappe.get_doc(
		{
			"doctype": "Wheel",
			"factory_wheel_code": (row.get("factory_wheel_code") or "").strip() or None,
			"wheel_type": wheel_type_name,
			"status": "In Stock",
			"warehouse": row.get("warehouse") or "",
			"received_on": getdate(row["received_on"]) if row.get("received_on") else None,
			"current_diameter": wheel_type.original_diameter,
			"current_inner_diameter": wheel_type.original_inner_diameter,
			"current_diamond_height": wheel_type.original_diamond_height,
			"current_volume": wheel_type.original_volume,
		}
	).insert(ignore_permissions=True)

	baseline = frappe.get_doc(
		{
			"doctype": "Measurement Event",
			"wheel": wheel.name,
			"measurement_date": frappe.utils.now_datetime(),
			"measured_by": frappe.session.user,
			"diameter": flt(row["current_diameter"]),
			"inner_diameter": flt(row["current_inner_diameter"]),
			"diamond_height": flt(row["current_diamond_height"]),
		}
	).insert(ignore_permissions=True)
	baseline.submit()

	requested_status = (row.get("status") or "In Stock").strip()
	if requested_status != wheel.status:
		wheel.reload()
		wheel.status = requested_status
		if requested_status == "Retired":
			wheel.retirement_date = wheel.retirement_date or frappe.utils.today()
			wheel.retirement_reason = row.get("retirement_reason") or _("Backfilled as Retired")
		wheel.save(ignore_permissions=True)

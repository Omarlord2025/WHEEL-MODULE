# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import math

import frappe
from wheel_tracker.language_switch import _
from frappe.model.document import Document
from frappe.utils import flt

from wheel_tracker.wheel_tracker.doctype.wheel_shape.wheel_shape import evaluate_volume_formula
from wheel_tracker.wheel_tracker.doctype.wheel_tracker_settings.wheel_tracker_settings import (
	get_usable_volume_fraction,
)


class WheelType(Document):
	def validate(self):
		self.validate_dimensions()
		ensure_item_is_serialized(self.item)

		if self.requires_correction_factor:
			self.original_diamond_height = sum(flt(s.height) for s in self.profile_segments)

		if self.auto_calc_volume:
			self.original_volume = calculate_wheel_volume(
				self.original_diameter,
				self.original_inner_diameter,
				self.original_diamond_height,
				self.shape,
				self.profile_segments,
			)

		self.usable_original_volume = flt(self.original_volume) * get_usable_volume_fraction(
			self.usable_volume_floor_percent
		)
		self.cost_per_mm3 = (
			flt(self.unit_cost) / self.usable_original_volume if self.usable_original_volume else 0
		)

	def validate_dimensions(self):
		if flt(self.original_inner_diameter) >= flt(self.original_diameter):
			frappe.throw(_("Original Inner Diameter must be less than Original Diameter."))
		if self.requires_correction_factor:
			if not self.profile_segments:
				frappe.throw(_("At least one Profile Segment is required for profiled/angled Wheel Shapes."))
			for row in self.profile_segments:
				if flt(row.angle) <= 0 or flt(row.height) <= 0:
					frappe.throw(_("Row {0}: Profile Segment Angle and Height must both be greater than zero.").format(row.idx))
		elif flt(self.original_diamond_height) <= 0:
			frappe.throw(_("Original Diamond Layer Height must be greater than zero."))


def ensure_item_is_serialized(item_code: str) -> None:
	"""Make sure a Wheel Type's linked Item is serialized, so every physical Wheel gets
	a matching ERPNext Serial No and real stock movements against it actually retire/
	move the Wheel (see PRD v10). Reuses Item's own validate()/cant_change() guard —
	if the Item already has submitted stock transactions that block the change, that
	throws ERPNext's own clear error rather than this re-deriving the safety check."""
	if not item_code or frappe.db.get_value("Item", item_code, "has_serial_no"):
		return
	item = frappe.get_doc("Item", item_code)
	item.has_serial_no = 1
	item.save(ignore_permissions=True)


def calculate_wheel_volume(diameter, inner_diameter, height, shape, profile_segments=None) -> float:
	"""
	Volume (mm³) of a diamond/CBN layer. The actual geometry formula lives on
	`Wheel Shape.volume_formula` (PRD v24) — editable per shape without touching code —
	this function only handles the structural part that isn't really "the formula":
	dispatching flat vs profiled evaluation mode, and for profiled shapes, chaining
	each Profile Segment's own diameters from the previous one and summing.

	Flat/straight shapes (1A1, P-series slitting wheels...): the shape's formula is
	evaluated once, given `diameter`/`inner_diameter`/`height` directly. Default
	formula is the exact annulus (pi/4) x (D^2 - d^2) x H — verified against 73/78
	real measurement rows in the legacy sheet, matching to well under 1% (mostly
	exact); the other 5 are data-entry errors in that sheet itself (e.g. a recorded
	current diameter smaller than the bore), not a formula mismatch — see PRD v6.

	Profiled/angled shapes (1V1, 12V9/11V9...): the abrasive band is one or more
	conical frustum rings stacked axially, walked from the *big*-end outer/inner
	diameters (`diameter`/`inner_diameter` — what's actually specified or measured)
	inward through each `profile_segments` row in order. Each segment's *small*-end
	diameters are derived here from its own angle and height, assuming a uniform
	radial band thickness within that segment (both boundaries taper in parallel):
		D_small = D_big - 2 x segment.height x tan(segment.angle)
	and the shape's formula is evaluated once per segment with that segment's own
	d_out_big/d_out_small/d_in_big/d_in_small/height, summed across segments. Default
	formula is that outer frustum's volume minus the inner frustum's:
		V_segment = (pi x h / 12) x [(Dob^2 + Dob.Dos + Dos^2) - (Dib^2 + Dib.Dis + Dis^2)]
	A single segment (e.g. 1V1) is an exact match to the reference's worked example
	(Dob=100, Dib=78.4, angle=45, h=5 -> V=14284.19mm³). Two segments (e.g.
	11V9/12V9 — a main cone plus a separate chamfer near the bore, confirmed by CNC
	Leaders as the real physical shape, PRD v7) chain the second segment's diameters
	from where the first segment's ended; this case has no independent worked
	example to verify against yet, unlike the single-segment case above.

	Called with a Wheel Type's original dimensions for its original_volume, and
	with a Measurement Event's *current* outer diameter reading (inner
	diameter/segment heights/angles held at the Wheel Type's constant original
	values) for a worn wheel's current volume — real data shows the outer diameter
	is the only dimension that actually changes as a wheel wears; bore and layer
	height don't.
	"""
	shape_doc = frappe.get_cached_doc("Wheel Shape", shape)
	# Not shape_doc.requires_correction_factor: that's a fetch_from field (see Wheel
	# Shape), which only (re)populates when the Shape itself is next saved — reading it
	# straight from Wheel Geometry here is the one place this genuinely has to be
	# correct for every pre-existing Shape too, not just ones resaved since this field
	# was added.
	requires_correction_factor = frappe.get_cached_value(
		"Wheel Geometry", shape_doc.wheel_geometry, "requires_correction_factor"
	)

	if not requires_correction_factor:
		return evaluate_volume_formula(
			shape_doc.volume_formula,
			{"diameter": flt(diameter), "inner_diameter": flt(inner_diameter), "height": flt(height)},
		)

	d_out, d_in = flt(diameter), flt(inner_diameter)
	total_volume = 0.0
	for segment in profile_segments:
		delta = 2 * flt(segment.height) * math.tan(math.radians(flt(segment.angle)))
		d_out_next = d_out - delta
		d_in_next = d_in - delta
		total_volume += evaluate_volume_formula(
			shape_doc.volume_formula,
			{
				"d_out_big": d_out,
				"d_out_small": d_out_next,
				"d_in_big": d_in,
				"d_in_small": d_in_next,
				"height": flt(segment.height),
			},
		)
		d_out, d_in = d_out_next, d_in_next
	return total_volume

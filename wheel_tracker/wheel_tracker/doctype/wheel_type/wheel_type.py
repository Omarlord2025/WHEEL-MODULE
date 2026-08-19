# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from wheel_tracker.wheel_tracker.doctype.wheel_tracker_settings.wheel_tracker_settings import (
	get_usable_volume_fraction,
)


class WheelType(Document):
	def validate(self):
		self.validate_dimensions()

		if self.requires_correction_factor:
			self.original_diamond_height = sum(flt(s.height) for s in self.profile_segments)

		if self.auto_calc_volume:
			self.original_volume = calculate_wheel_volume(
				self.original_diameter,
				self.original_inner_diameter,
				self.original_diamond_height,
				self.requires_correction_factor,
				self.profile_segments,
			)

		self.usable_original_volume = flt(self.original_volume) * get_usable_volume_fraction()
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


def calculate_wheel_volume(
	diameter, inner_diameter, height, requires_angle_formula, profile_segments=None
) -> float:
	"""
	Volume (mm³) of a diamond/CBN layer — exact geometry, per CNC Leaders' formula
	reference ("Volume equations for grinding wheels" — see Wheel Tracker PRD v6/v7).

	Flat/straight shapes (1A1, P-series slitting wheels...): exact annulus
	-> (pi/4) x (D^2 - d^2) x H
	Verified against 73/78 real measurement rows in the legacy sheet, matching to
	well under 1% (mostly exact); the other 5 are data-entry errors in that sheet
	itself (e.g. a recorded current diameter smaller than the bore), not a formula
	mismatch — see PRD v6.

	Profiled/angled shapes (1V1, 12V9/11V9...): the abrasive band is one or more
	conical frustum rings stacked axially, walked from the *big*-end outer/inner
	diameters (`diameter`/`inner_diameter` — what's actually specified or measured)
	inward through each `profile_segments` row in order. Each segment's *small*-end
	diameters are derived from its own angle and height, assuming a uniform radial
	band thickness within that segment (both boundaries taper in parallel):
		D_small = D_big - 2 x segment.height x tan(segment.angle)
	and that segment's ring volume is the outer frustum's volume minus the inner
	frustum's:
		V_segment = (pi x h / 12) x [(Dob^2 + Dob.Dos + Dos^2) - (Dib^2 + Dib.Dis + Dis^2)]
	summed across segments. A single segment (e.g. 1V1) is an exact match to the
	reference's worked example (Dob=100, Dib=78.4, angle=45, h=5 -> V=14284.19mm³).
	Two segments (e.g. 11V9/12V9 — a main cone plus a separate chamfer near the
	bore, confirmed by CNC Leaders as the real physical shape, PRD v7) chain the
	second segment's diameters from where the first segment's ended; this case has
	no independent worked example to verify against yet, unlike the single-segment
	case above.

	Called with a Wheel Type's original dimensions for its original_volume, and
	with a Measurement Event's *current* outer diameter reading (inner
	diameter/segment heights/angles held at the Wheel Type's constant original
	values) for a worn wheel's current volume — real data shows the outer diameter
	is the only dimension that actually changes as a wheel wears; bore and layer
	height don't.
	"""
	if not requires_angle_formula:
		return (math.pi / 4) * (flt(diameter) ** 2 - flt(inner_diameter) ** 2) * flt(height)

	d_out, d_in = flt(diameter), flt(inner_diameter)
	total_volume = 0.0
	for segment in profile_segments:
		delta = 2 * flt(segment.height) * math.tan(math.radians(flt(segment.angle)))
		d_out_next = d_out - delta
		d_in_next = d_in - delta
		total_volume += _ring_frustum_volume(d_out, d_out_next, d_in, d_in_next, flt(segment.height))
		d_out, d_in = d_out_next, d_in_next
	return total_volume


def _ring_frustum_volume(d_out_big, d_out_small, d_in_big, d_in_small, height) -> float:
	"""Volume (mm³) of one conical-frustum ring: an outer solid cone frustum minus a
	coaxial inner one, both spanning the same `height`. See calculate_wheel_volume()."""
	outer = d_out_big**2 + d_out_big * d_out_small + d_out_small**2
	inner = d_in_big**2 + d_in_big * d_in_small + d_in_small**2
	return (math.pi * height / 12) * (outer - inner)

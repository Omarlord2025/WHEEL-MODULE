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

		if self.auto_calc_volume:
			self.original_volume = calculate_wheel_volume(
				self.original_diameter,
				self.original_inner_diameter,
				self.original_diamond_height,
				self.requires_correction_factor,
				self.angle,
			)

		self.usable_original_volume = flt(self.original_volume) * get_usable_volume_fraction()
		self.cost_per_mm3 = (
			flt(self.unit_cost) / self.usable_original_volume if self.usable_original_volume else 0
		)

	def validate_dimensions(self):
		if flt(self.original_inner_diameter) >= flt(self.original_diameter):
			frappe.throw(_("Original Inner Diameter must be less than Original Diameter."))
		if flt(self.original_diamond_height) <= 0:
			frappe.throw(_("Original Diamond Layer Height must be greater than zero."))
		if self.requires_correction_factor and flt(self.angle) <= 0:
			frappe.throw(_("Angle is required for profiled/angled Wheel Shapes."))


def calculate_wheel_volume(
	diameter, inner_diameter, height, requires_angle_formula, angle=0
) -> float:
	"""
	Volume (mm³) of a diamond/CBN layer — exact geometry, per CNC Leaders' formula
	reference ("Volume equations for grinding wheels" — see Wheel Tracker PRD v6).

	Flat/straight shapes (1A1, P-series slitting wheels...): exact annulus
	-> (pi/4) x (D^2 - d^2) x H
	Verified against 73/78 real measurement rows in the legacy sheet, matching to
	well under 1% (mostly exact); the other 5 are data-entry errors in that sheet
	itself (e.g. a recorded current diameter smaller than the bore), not a formula
	mismatch — see PRD v6.

	Profiled/angled shapes (12V9/11V9/1V1...): the abrasive band is a conical
	frustum ring, not a straight annulus. `diameter`/`inner_diameter` are the
	band's *big*-end outer/inner diameters (what's actually specified or measured);
	the *small*-end diameters are derived from the band's angle and height, assuming
	a uniform radial band thickness (both boundaries taper in parallel):
		D_small = D_big - 2 x H x tan(angle)
	then the ring volume is the outer frustum's volume minus the inner frustum's:
		V = (pi x H / 12) x [(Dob^2 + Dob.Dos + Dos^2) - (Dib^2 + Dib.Dis + Dis^2)]
	Exact match to the PDF's worked example (Dob=100, Dib=78.4, angle=45, H=5
	-> V=14284.19mm³).

	Called with a Wheel Type's original dimensions for its original_volume, and
	with a Measurement Event's *current* outer diameter reading (inner
	diameter/height/angle held at the Wheel Type's constant original values) for a
	worn wheel's current volume — real data shows the outer diameter is the only
	dimension that actually changes as a wheel wears; bore and layer height don't.
	"""
	if not requires_angle_formula:
		return (math.pi / 4) * (flt(diameter) ** 2 - flt(inner_diameter) ** 2) * flt(height)

	delta = 2 * flt(height) * math.tan(math.radians(flt(angle)))
	d_out_small = flt(diameter) - delta
	d_in_small = flt(inner_diameter) - delta
	outer = flt(diameter) ** 2 + flt(diameter) * d_out_small + d_out_small**2
	inner = flt(inner_diameter) ** 2 + flt(inner_diameter) * d_in_small + d_in_small**2
	return (math.pi * flt(height) / 12) * (outer - inner)

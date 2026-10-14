# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import math

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from wheel_tracker.language_switch import _

# Dummy values for self-checking a Volume Formula at save time — positive, with
# inner < outer (same constraint Wheel Type.validate_dimensions() enforces on real
# data) so a syntactically-valid-but-nonsensical formula still gets a fair test.
# SEGMENT_FORMULA_SAMPLE_VARS is the 1V1 worked example from the formula reference
# (Dob=100, Dib=78.4, angle=45°, h=5 -> small-end diameters 90/68.4 via the same
# delta = 2 x height x tan(angle) used in calculate_wheel_volume()) — the default
# segment formula below evaluates it to 14284.19mm³, the known-correct answer this
# formula was verified against originally (see PRD v6/v7).
FLAT_FORMULA_SAMPLE_VARS = {"diameter": 100.0, "inner_diameter": 78.4, "height": 5.0}
SEGMENT_FORMULA_SAMPLE_VARS = {
	"d_out_big": 100.0,
	"d_out_small": 90.0,
	"d_in_big": 78.4,
	"d_in_small": 68.4,
	"height": 5.0,
}

DEFAULT_FLAT_FORMULA = "(pi / 4) * (diameter**2 - inner_diameter**2) * height"
DEFAULT_SEGMENT_FORMULA = (
	"(pi * height / 12) * ("
	"(d_out_big**2 + d_out_big * d_out_small + d_out_small**2) - "
	"(d_in_big**2 + d_in_big * d_in_small + d_in_small**2)"
	")"
)


class WheelShape(Document):
	def validate(self):
		if not self.volume_formula:
			self.volume_formula = (
				DEFAULT_SEGMENT_FORMULA if self.requires_correction_factor else DEFAULT_FLAT_FORMULA
			)
		self.validate_volume_formula()

	def validate_volume_formula(self):
		"""Self-check the formula with sample numbers before anything else ever depends
		on it — a typo surfaces here, not three documents later on a real Wheel Type or
		Measurement Event save."""
		sample_vars = (
			SEGMENT_FORMULA_SAMPLE_VARS if self.requires_correction_factor else FLAT_FORMULA_SAMPLE_VARS
		)
		try:
			result = evaluate_volume_formula(self.volume_formula, sample_vars)
		except Exception as e:
			frappe.throw(_("Volume Formula is invalid: {0}").format(str(e)))
		if result <= 0:
			frappe.throw(_("Volume Formula must evaluate to a positive number."))


def evaluate_volume_formula(formula: str, variables: dict) -> float:
	"""Safely evaluate a Wheel Shape's own Volume Formula with the given variables,
	using Frappe's existing sandboxed expression evaluator (frappe.safe_eval) — the
	same mechanism behind Notification conditions and Server Script, never a raw
	eval(). `pi` is always available; the variable set otherwise depends on the
	calling convention — see Wheel Shape.volume_formula's own description, and
	wheel_type.calculate_wheel_volume() for where each set is built. Shared by
	Wheel Type (original volume) and Measurement Event (current volume reading),
	both via calculate_wheel_volume()."""
	try:
		return flt(frappe.safe_eval(formula, {"pi": math.pi}, dict(variables)))
	except Exception as e:
		frappe.throw(_("Error evaluating Volume Formula: {0}").format(str(e)))

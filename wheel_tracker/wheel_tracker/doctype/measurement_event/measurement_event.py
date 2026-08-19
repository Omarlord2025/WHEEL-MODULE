# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

from types import SimpleNamespace

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from wheel_tracker.wheel_tracker.doctype.wheel_tracker_settings.wheel_tracker_settings import (
	get_usable_volume_fraction,
)
from wheel_tracker.wheel_tracker.doctype.wheel_type.wheel_type import calculate_wheel_volume

WHEEL_FIELDS = ("wheel_type", "current_diameter", "current_inner_diameter", "current_diamond_height")


class MeasurementEvent(Document):
	def validate(self):
		wheel_type_name = frappe.db.get_value("Wheel", self.wheel, "wheel_type")
		if not wheel_type_name:
			frappe.throw(_("Wheel {0} does not exist.").format(self.wheel))
		wheel_type = frappe.get_cached_doc("Wheel Type", wheel_type_name)

		if not wheel_type.requires_measurement:
			frappe.throw(
				_(
					"{0} Wheels are tracked as usable/not-usable, not by caliper measurement "
					"— use Wheel Usability Check instead."
				).format(wheel_type.shape)
			)

		inner_diameter, height, segments = self._volume_inputs(wheel_type)
		self.confirmed_volume = calculate_wheel_volume(
			self.diameter, inner_diameter, height, wheel_type.requires_correction_factor, segments
		)

		usable_fraction = get_usable_volume_fraction()
		self.usable_volume = flt(self.confirmed_volume) * usable_fraction
		self.consumed_volume = flt(wheel_type.usable_original_volume) - flt(self.usable_volume)
		self.consumption_percent = (
			flt(self.consumed_volume) / flt(wheel_type.usable_original_volume) * 100
			if wheel_type.usable_original_volume
			else 0
		)

		self.previous_consumed_volume = get_last_consumed_volume(self.wheel, exclude=self.name)
		self.incremental_consumed_volume = max(
			flt(self.consumed_volume) - flt(self.previous_consumed_volume), 0
		)

		# "نسبة الخسارة" (loss ratio) in the formula reference — radial diameter loss, a
		# simple caliper-only cross-check independent of the volume formula. See PRD v7.
		self.radial_wear = (flt(wheel_type.original_diameter) - flt(self.diameter)) / 2

		self.cost_per_mm3 = flt(wheel_type.cost_per_mm3)
		self.job_cost = flt(self.incremental_consumed_volume) * self.cost_per_mm3

	def _volume_inputs(self, wheel_type):
		"""(inner_diameter, height, segments) to feed calculate_wheel_volume() alongside
		this event's own `diameter` reading — differs by geometry family (see PRD v8,
		validated against the real WHEELS WITH ANGLES data):

		Flat wheels wear only radially — the bore and layer height don't move, so use the
		Wheel Type's constant original values, not this event's own (redundant) readings.

		Single-bevel profiled wheels (one Profile Segment, e.g. 1V1/12V9/11V9) wear *along
		the slope* — diameter, inner diameter, and height all shrink together at the same
		fixed angle. Using this event's own current inner_diameter/diamond_height (not the
		Wheel Type's original constants) reproduced the real sheet's recorded current
		volume exactly for the large majority of rows; the Wheel Type's angle is the one
		thing that stays constant.

		Compound/stepped profiles (2+ segments) have no real data yet on how current
		readings map onto a multi-segment chain, so this falls back to the Wheel Type's
		original segments/height — a known, documented limitation, not a validated model.
		"""
		if not wheel_type.requires_correction_factor:
			return wheel_type.original_inner_diameter, wheel_type.original_diamond_height, None

		if len(wheel_type.profile_segments) == 1:
			angle = wheel_type.profile_segments[0].angle
			return self.inner_diameter, self.diamond_height, [SimpleNamespace(angle=angle, height=self.diamond_height)]

		return wheel_type.original_inner_diameter, wheel_type.original_diamond_height, wheel_type.profile_segments

	def on_submit(self):
		self.apply_to_wheel()
		self.update_job_card_rollup()

	def on_cancel(self):
		self.revert_from_wheel()
		self.update_job_card_rollup()

	def apply_to_wheel(self):
		wheel = frappe.get_doc("Wheel", self.wheel)
		was_retired = wheel.status == "Retired"

		wheel.current_diameter = self.diameter
		wheel.current_inner_diameter = self.inner_diameter
		wheel.current_diamond_height = self.diamond_height
		wheel.current_volume = self.confirmed_volume
		wheel.save(ignore_permissions=True)

		self.db_set("triggered_retirement", int(not was_retired and wheel.status == "Retired"))

	def revert_from_wheel(self):
		wheel = frappe.get_doc("Wheel", self.wheel)
		previous = get_previous_submitted_event(self.wheel, exclude=self.name)

		if previous:
			wheel.current_diameter = previous.diameter
			wheel.current_inner_diameter = previous.inner_diameter
			wheel.current_diamond_height = previous.diamond_height
			wheel.current_volume = previous.confirmed_volume
		else:
			wheel_type = frappe.get_cached_doc("Wheel Type", wheel.wheel_type)
			wheel.current_diameter = wheel_type.original_diameter
			wheel.current_inner_diameter = wheel_type.original_inner_diameter
			wheel.current_diamond_height = wheel_type.original_diamond_height
			wheel.current_volume = wheel_type.original_volume

		if self.triggered_retirement and wheel.status == "Retired":
			wheel.status = "In Use" if wheel.current_job_card else "In Stock"
			wheel.retirement_date = None
			wheel.retirement_reason = None

		wheel.save(ignore_permissions=True)

	def update_job_card_rollup(self):
		if not self.job_card:
			return
		from wheel_tracker.job_card_integration import update_job_card_wheel_cost

		update_job_card_wheel_cost(self.job_card)


def get_last_consumed_volume(wheel: str, exclude: str | None = None) -> float:
	"""Consumed Volume of the most recent submitted Measurement Event for a Wheel, or 0 if none."""
	filters = {"wheel": wheel, "docstatus": 1}
	if exclude:
		filters["name"] = ["!=", exclude]
	rows = frappe.get_all(
		"Measurement Event",
		filters=filters,
		fields=["consumed_volume"],
		order_by="measurement_date desc, creation desc",
		limit=1,
	)
	return flt(rows[0].consumed_volume) if rows else 0


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def measurable_wheel_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for Measurement Event's `wheel` field — only Wheels whose Type
	Requires Measurement (see Wheel Shape / PRD v9); everything else uses Wheel Usability
	Check instead. UX only — validate() is what actually enforces this."""
	return frappe.db.sql(
		"""
		select w.name, w.wheel_type
		from `tabWheel` w
		inner join `tabWheel Type` wt on wt.name = w.wheel_type
		where wt.requires_measurement = 1
			and w.name like %(txt)s
		order by w.name
		limit %(page_len)s offset %(start)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


def get_previous_submitted_event(wheel: str, exclude: str | None = None):
	"""Most recent submitted Measurement Event for a Wheel (full readings), or None."""
	filters = {"wheel": wheel, "docstatus": 1}
	if exclude:
		filters["name"] = ["!=", exclude]
	rows = frappe.get_all(
		"Measurement Event",
		filters=filters,
		fields=["diameter", "inner_diameter", "diamond_height", "confirmed_volume"],
		order_by="measurement_date desc, creation desc",
		limit=1,
	)
	return rows[0] if rows else None

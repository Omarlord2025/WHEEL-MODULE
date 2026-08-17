# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

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

		# Only the outer diameter changes as a wheel wears (see PRD v6) — inner diameter,
		# layer height, and angle stay at the Wheel Type's constant original values, same
		# formula as original_volume.
		self.confirmed_volume = calculate_wheel_volume(
			self.diameter,
			wheel_type.original_inner_diameter,
			wheel_type.original_diamond_height,
			wheel_type.requires_correction_factor,
			wheel_type.angle,
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

		self.cost_per_mm3 = flt(wheel_type.cost_per_mm3)
		self.job_cost = flt(self.incremental_consumed_volume) * self.cost_per_mm3

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

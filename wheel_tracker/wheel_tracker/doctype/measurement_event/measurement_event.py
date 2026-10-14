# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

from types import SimpleNamespace

import frappe
from wheel_tracker.language_switch import _
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
					"— use Wheel Retirement instead."
				).format(wheel_type.shape)
			)

		inner_diameter, height, segments = self._volume_inputs(wheel_type)
		self.confirmed_volume = calculate_wheel_volume(
			self.diameter, inner_diameter, height, wheel_type.shape, segments
		)

		usable_fraction = get_usable_volume_fraction(wheel_type.usable_volume_floor_percent)
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

		self.derive_job_cards()

	def derive_job_cards(self):
		"""Auto-derive which Job Card(s) this measurement's incremental wear applies to,
		from the Wheel's real assignment history since its previous submitted event — a
		Wheel can be assigned/released across several Job Cards between two measurements
		(see PRD v12), so job_cost is split equally across all of them. Recomputed on
		every save (idempotent); frozen once submitted, same as confirmed_volume et al."""
		if self.docstatus == 1:
			return

		since = self.get_job_card_history_cutoff()
		job_cards = self.get_job_cards_since(since)

		self.set("job_cards", [])
		if not job_cards:
			return

		share = flt(self.job_cost) / len(job_cards)
		for job_card in job_cards:
			self.append("job_cards", {"job_card": job_card, "allocated_cost": share})

	def get_job_card_history_cutoff(self):
		"""Datetime since which Job Card Wheel history counts toward this event — the
		Wheel's previous submitted Measurement Event's measurement_date, or its
		received_on/creation if this is the Wheel's first measurement."""
		previous = get_previous_submitted_event(self.wheel, exclude=self.name)
		if previous and previous.get("measurement_date"):
			return previous["measurement_date"]

		received_on, creation = frappe.db.get_value("Wheel", self.wheel, ["received_on", "creation"])
		return received_on or creation

	def get_job_cards_since(self, since) -> list:
		"""Distinct Job Cards this Wheel was assigned to (per Job Card Wheel rows) at or
		after `since`, oldest first. Falls back to the Wheel's current_job_card if history
		is empty but the Wheel is presently In Use (defensive — assignment always creates
		a Job Card Wheel row first, so this should not normally be needed)."""
		from wheel_tracker.job_card_integration import WHEEL_ROWS_FILTERS

		rows = frappe.get_all(
			"Job Card Wheel",
			filters={"wheel": self.wheel, "assigned_on": [">=", since], **WHEEL_ROWS_FILTERS},
			fields=["parent"],
			order_by="assigned_on asc",
		)
		job_cards = list(dict.fromkeys(row.parent for row in rows))

		if not job_cards:
			current_job_card = frappe.db.get_value("Wheel", self.wheel, "current_job_card")
			if current_job_card:
				job_cards = [current_job_card]

		return job_cards

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
		self.create_auto_retirement()
		self.update_job_card_rollup()

	def on_cancel(self):
		self.cancel_auto_retirement()
		self.revert_from_wheel()
		self.update_job_card_rollup()

	def create_auto_retirement(self):
		"""If apply_to_wheel() just auto-retired the Wheel (see Wheel.check_auto_retirement),
		create a Wheel Retirement *draft* for it — flagging immediately that the Wheel needs
		retiring, but deliberately leaving the real Material Issue for a human to review and
		submit (see PRD v15 — a customer decision: the Wheel's own status flips to Retired
		right away, but nothing leaves the stock ledger until someone confirms it). Does NOT
		submit the draft itself — that's Wheel Retirement's own on_submit
		(retire_wheel() + create_retirement_stock_entry()), reused unchanged whenever a human
		(or, before PRD v15, this same code) actually submits it. Must run strictly after
		apply_to_wheel()'s own wheel.save() has returned — creating a new top-level document
		here is safe, unlike doing this from inside Wheel.validate() itself, which would
		recurse into the save() still in progress. No-op if this event didn't trigger
		retirement."""
		if not self.triggered_retirement:
			return

		linked_job_cards = [row.job_card for row in self.get("job_cards") or []]

		retirement = frappe.new_doc("Wheel Retirement")
		retirement.wheel = self.wheel
		retirement.job_card = linked_job_cards[0] if len(linked_job_cards) == 1 else None
		retirement.check_date = frappe.utils.now_datetime()
		retirement.checked_by = self.measured_by
		retirement.retirement_reason = frappe.db.get_value("Wheel", self.wheel, "retirement_reason")
		retirement.insert(ignore_permissions=True)

		self.db_set("auto_retirement", retirement.name)

	def cancel_auto_retirement(self):
		"""Mirror of create_auto_retirement() for on_cancel(): if this event auto-created a
		Wheel Retirement, undo it too, keeping ERPNext's real stock ledger (if the draft was
		since reviewed and submitted) or just Wheel Tracker's own records (if it's still
		pending review) in step with the Wheel being un-retired. Runs before
		revert_from_wheel() so the retirement paperwork/stock movement are undone first, then
		the Wheel's own measured dimensions/status are restored. Still-pending drafts are
		deleted outright (cancel() only applies to submitted docs); already-reviewed-and-
		submitted ones are cancelled for real, reversing their Material Issue via Wheel
		Retirement's own on_cancel. No-op if no auto_retirement was recorded, or if it's
		already been cancelled/deleted independently."""
		if not self.auto_retirement or not frappe.db.exists("Wheel Retirement", self.auto_retirement):
			return
		retirement = frappe.get_doc("Wheel Retirement", self.auto_retirement)
		if retirement.docstatus == 1:
			retirement.cancel()
		elif retirement.docstatus == 0:
			# Clear our own Link to it first — frappe.delete_doc() refuses to delete a
			# document that's still referenced elsewhere, and this field is exactly that.
			self.db_set("auto_retirement", None)
			frappe.delete_doc("Wheel Retirement", retirement.name, ignore_permissions=True)

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
		"""Re-sum every Job Card this event's wear was split across (see derive_job_cards) —
		called on both submit and cancel; update_job_card_wheel_cost() always re-sums from
		scratch, so calling it once per linked Job Card here is correct and idempotent."""
		from wheel_tracker.job_card_integration import update_job_card_wheel_cost

		for job_card in {row.job_card for row in self.get("job_cards") or []}:
			update_job_card_wheel_cost(job_card)


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
		fields=["diameter", "inner_diameter", "diamond_height", "confirmed_volume", "measurement_date"],
		order_by="measurement_date desc, creation desc",
		limit=1,
	)
	return rows[0] if rows else None

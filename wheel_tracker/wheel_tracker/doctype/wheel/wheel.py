# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, today

from wheel_tracker.wheel_tracker.doctype.wheel_tracker_settings.wheel_tracker_settings import (
	get_usable_volume_fraction,
)

STATUS_IN_STOCK = "In Stock"
STATUS_IN_USE = "In Use"
STATUS_RETIRED = "Retired"


class Wheel(Document):
	def autoname(self):
		if not self.factory_wheel_code:
			self.factory_wheel_code = generate_factory_wheel_code(self.wheel_type)
		self.name = self.factory_wheel_code

	def validate(self):
		self.recalculate_wear()
		self.recalculate_cost()
		self.check_auto_retirement()

	def recalculate_wear(self):
		wheel_type = frappe.get_cached_doc("Wheel Type", self.wheel_type)
		usable_fraction = get_usable_volume_fraction()

		self.usable_current_volume = flt(self.current_volume) * usable_fraction
		self.consumed_volume = flt(wheel_type.usable_original_volume) - flt(self.usable_current_volume)

		if wheel_type.usable_original_volume:
			self.consumption_percent = (
				flt(self.consumed_volume) / flt(wheel_type.usable_original_volume) * 100
			)
		else:
			self.consumption_percent = 0

	def recalculate_cost(self):
		total = frappe.db.get_value(
			"Measurement Event",
			{"wheel": self.name, "docstatus": 1},
			"sum(job_cost)",
		)
		self.total_cost_allocated = flt(total)

	def check_auto_retirement(self):
		if self.status == STATUS_RETIRED:
			return
		if flt(self.consumption_percent) >= 100:
			self.status = STATUS_RETIRED
			self.retirement_date = today()
			self.retirement_reason = _("Auto-retired: consumption reached {0}%").format(
				round(flt(self.consumption_percent), 1)
			)
			self.current_job_card = None


def generate_factory_wheel_code(wheel_type_name: str) -> str:
	"""Auto-generate a Factory Wheel Code matching the legacy SH-<material>-<shape>-<dia>-T<height>-#### pattern.

	The material letter comes from Wheel Material.factory_code_letter (D for diamond-grit,
	B for CBN/borazon-grit — the real codes use B, not the more obvious-looking C).
	The SH- prefix is this app's own convention: the legacy sheet splits roughly evenly
	between SH- and SL- with no discernible pattern, so there's no clear alternative to prefer.
	"""
	wheel_type = frappe.get_cached_doc("Wheel Type", wheel_type_name)
	material_code = frappe.db.get_value("Wheel Material", wheel_type.material, "factory_code_letter") or "X"
	prefix = "SH-{0}-{1}-{2}-T{3}-".format(
		material_code,
		wheel_type.shape,
		int(flt(wheel_type.original_diameter)),
		int(flt(wheel_type.original_diamond_height)),
	)
	return make_autoname(prefix + ".####")


@frappe.whitelist()
def assign_to_job_card(wheel: str, job_card: str):
	"""Mark a Wheel In Use and link it to a Job Card. Called from the Job Card UI."""
	doc = frappe.get_doc("Wheel", wheel)
	if doc.status != STATUS_IN_STOCK:
		frappe.throw(_("Wheel {0} is not In Stock (currently {1}).").format(wheel, doc.status))

	doc.status = STATUS_IN_USE
	doc.current_job_card = job_card
	doc.save()
	return doc.status


@frappe.whitelist()
def release_from_job_card(wheel: str):
	"""Return a Wheel to In Stock, e.g. a job was cancelled before any wear was logged."""
	doc = frappe.get_doc("Wheel", wheel)
	if doc.status != STATUS_IN_USE:
		frappe.throw(_("Wheel {0} is not In Use.").format(wheel))

	doc.status = STATUS_IN_STOCK
	doc.current_job_card = None
	doc.save()
	return doc.status


@frappe.whitelist()
def retire_wheel(wheel: str, reason: str):
	"""Manually retire a Wheel outside the measurement-driven wear flow — called by
	Wheel Usability Check (see PRD v9), and usable directly for any Wheel that needs
	retiring for a reason other than reaching 100% consumption (e.g. physically
	damaged). A no-op if already Retired, so it's safe to call unconditionally."""
	doc = frappe.get_doc("Wheel", wheel)
	if doc.status == STATUS_RETIRED:
		return doc.status

	doc.status = STATUS_RETIRED
	doc.retirement_date = today()
	doc.retirement_reason = reason
	doc.current_job_card = None
	doc.save(ignore_permissions=True)
	return doc.status


@frappe.whitelist()
def reinstate_wheel(wheel: str):
	"""Bring a Retired Wheel back to In Stock — called by Wheel Usability Check when a
	later check finds it usable after all. A no-op if not currently Retired. Wheels
	that are still at >=100% consumption (see check_auto_retirement) immediately
	re-retire themselves on the save below — this can't be used to override a
	measurement-driven retirement that's still factually true."""
	doc = frappe.get_doc("Wheel", wheel)
	if doc.status != STATUS_RETIRED:
		return doc.status

	doc.status = STATUS_IN_STOCK
	doc.retirement_date = None
	doc.retirement_reason = None
	doc.save(ignore_permissions=True)
	return doc.status

# Copyright (c) 2026, CNC Leaders and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from wheel_tracker.language_switch import _


class WheelScrapSale(Document):
	def validate(self):
		self.validate_scrap_sales_account_configured()
		self.validate_wheels()
		self.total_amount = sum(flt(row.amount) for row in self.wheels)

	def validate_scrap_sales_account_configured(self):
		if not frappe.db.get_single_value("Wheel Tracker Settings", "scrap_sales_account"):
			frappe.throw(
				_(
					"No Scrap Sales Account is configured yet — set one on Wheel Tracker Settings before recording a scrap sale."
				)
			)

	def validate_wheels(self):
		if not self.wheels:
			frappe.throw(_("Add at least one Wheel to sell scrap from."))

		seen = set()
		for row in self.wheels:
			if row.wheel in seen:
				frappe.throw(_("Row {0}: Wheel {1} is listed more than once in this sale.").format(row.idx, row.wheel))
			seen.add(row.wheel)

			status = frappe.db.get_value("Wheel", row.wheel, "status")
			if status != "Retired":
				frappe.throw(
					_("Row {0}: Wheel {1} is not Retired (currently {2}) — only Retired Wheels can have their scrap sold.").format(
						row.idx, row.wheel, status
					)
				)

			if flt(row.amount) <= 0:
				frappe.throw(_("Row {0}: Amount must be greater than zero.").format(row.idx))

			existing = frappe.db.sql(
				"""
				select wss.name from `tabWheel Scrap Sale Wheel` wssw
				inner join `tabWheel Scrap Sale` wss on wss.name = wssw.parent
				where wssw.wheel = %(wheel)s and wss.docstatus = 1 and wss.name != %(name)s
				""",
				{"wheel": row.wheel, "name": self.name or ""},
				as_dict=True,
			)
			if existing:
				frappe.throw(
					_("Row {0}: Wheel {1}'s scrap was already sold on {2}.").format(
						row.idx, row.wheel, existing[0].name
					)
				)

	def on_submit(self):
		je = self.create_scrap_journal_entry()
		self.db_set("journal_entry", je.name)

	def on_cancel(self):
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()

	def create_scrap_journal_entry(self):
		"""One real Journal Entry per Wheel Scrap Sale — debits Payment Account, credits
		Wheel Tracker Settings' own Scrap Sales Account, for the total across every
		Wheel row. Reuses the Company's own default Cost Center if it has one, same as
		ERPNext's own documents do; left blank otherwise and ERPNext's own Journal Entry
		validation decides whether that's acceptable for this Company's accounting
		settings — not re-derived here."""
		scrap_sales_account = frappe.db.get_single_value("Wheel Tracker Settings", "scrap_sales_account")
		cost_center = frappe.db.get_value("Company", self.company, "cost_center")

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = self.company
		je.posting_date = self.posting_date
		je.user_remark = _("Scrap sale {0} — {1}").format(self.name, self.buyer)
		je.append(
			"accounts",
			{
				"account": self.payment_account,
				"debit_in_account_currency": self.total_amount,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": scrap_sales_account,
				"credit_in_account_currency": self.total_amount,
				"cost_center": cost_center,
			},
		)
		je.insert(ignore_permissions=True)
		je.submit()
		return je


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def retired_wheel_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for the Wheels table — only offers Retired Wheels that
	don't already have their scrap sold on a submitted Wheel Scrap Sale."""
	return frappe.db.sql(
		"""
		select w.name from `tabWheel` w
		where w.status = 'Retired'
		and w.name like %(txt)s
		and w.name not in (
			select wssw.wheel from `tabWheel Scrap Sale Wheel` wssw
			inner join `tabWheel Scrap Sale` wss on wss.name = wssw.parent
			where wss.docstatus = 1
		)
		order by w.name
		limit %(page_len)s offset %(start)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def get_retired_wheels_with_unsold_scrap():
	"""Every Retired Wheel that isn't already on a submitted Wheel Scrap Sale —
	used by the "Get Retired Wheels" button on the form to bulk-populate the
	Wheels table instead of looking each one up by hand."""
	return frappe.db.sql(
		"""
		select w.name as wheel
		from `tabWheel` w
		where w.status = 'Retired'
		and w.name not in (
			select wssw.wheel from `tabWheel Scrap Sale Wheel` wssw
			inner join `tabWheel Scrap Sale` wss on wss.name = wssw.parent
			where wss.docstatus = 1
		)
		order by w.name
		""",
		as_dict=True,
	)

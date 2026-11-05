# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import frappe
from event_management.permissions import validate_linked_scope
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime


class EMTicketType(Document):
	def validate(self):
		validate_linked_scope(self)
		event_start = frappe.db.get_value("EM Event", self.event, "start_date", for_update=True)
		if not self.is_new():
			frappe.db.get_value("EM Ticket Type", self.name, "name", for_update=True)
		if flt(self.price) < 0:
			frappe.throw("Ticket price cannot be negative.")
		if cint(self.total_quantity) <= 0:
			frappe.throw("Ticket quantity must be greater than zero.")
		if self.available_from and self.available_until and (
			get_datetime(self.available_from) >= get_datetime(self.available_until)
		):
			frappe.throw("Ticket availability start must be before its end.")
		if self.available_from and event_start and get_datetime(self.available_from) >= get_datetime(event_start):
			frappe.throw("Ticket sales must start before the event.")
		if self.available_until and event_start and get_datetime(self.available_until) > get_datetime(event_start):
			frappe.throw("Ticket sales must end by the event start.")
		if not self.is_new():
			rows = frappe.db.get_values(
				"EM Registration", {"ticket_type": self.name, "status": ["!=", "Cancelled"]},
				"quantity", for_update=True,
			)
			if cint(self.total_quantity) < sum(cint(row[0]) for row in rows):
				frappe.throw("Ticket quantity cannot be less than existing reservations.")

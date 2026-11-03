# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, get_datetime
from frappe.website.website_generator import WebsiteGenerator


class EMEvent(WebsiteGenerator):
	def validate(self):
		if not self.is_new():
			frappe.db.get_value("EM Event", self.name, "name", for_update=True)
		if cint(self.capacity) <= 0:
			frappe.throw("Event capacity must be greater than zero.")
		if self.start_date and self.end_date and (
			get_datetime(self.start_date) >= get_datetime(self.end_date)
		):
			frappe.throw("Event start date must be before end date.")
		if self.published:
			if self.status != "Published":
				frappe.throw("A published event must have Published status.")
			if not all((self.event_name, self.venue, self.start_date, self.end_date)):
				frappe.throw("Published events require a name, venue, and start and end dates.")
		if not self.is_new():
			rows = frappe.db.get_values(
				"EM Registration", {"event": self.name, "status": ["!=", "Cancelled"]},
				"quantity", for_update=True,
			)
			if cint(self.capacity) < sum(cint(row[0]) for row in rows):
				frappe.throw("Event capacity cannot be less than active registrations.")

	def make_route(self):
		return f"events/{self.scrubbed_title()}"

	def get_context(self, context):
		if not self.published:
			raise frappe.DoesNotExistError

		context.ticket_types = frappe.get_all(
			"EM Ticket Type",
			filters={"event": self.name},
			fields=["ticket_name", "price"],
			order_by="price asc",
		)

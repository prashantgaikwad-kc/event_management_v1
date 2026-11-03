# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import frappe
from frappe.website.website_generator import WebsiteGenerator


class EMEvent(WebsiteGenerator):
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

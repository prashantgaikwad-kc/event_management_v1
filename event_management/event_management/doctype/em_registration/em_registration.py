# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import base64

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime
from frappe.utils.print_format_generator import get_qr_code


class EMRegistration(Document):
	def before_save(self):
		if self.is_new():
			self.ticket_code = frappe.generate_hash(length=16)
			self.checked_in = 0
			self.check_in_time = None
		else:
			current = frappe.db.sql(
				"SELECT ticket_code, checked_in, check_in_time FROM `tabEM Registration` WHERE name = %s FOR UPDATE",
				self.name,
				as_dict=True,
			)[0]
			self.ticket_code = current.ticket_code
			self.checked_in = current.checked_in
			self.check_in_time = current.check_in_time

	def validate(self):
		if cint(self.quantity) <= 0:
			frappe.throw("Quantity must be greater than zero.")

		event = frappe.db.sql(
			"SELECT capacity FROM `tabEM Event` WHERE name = %s FOR UPDATE",
			self.event,
			as_dict=True,
		)[0]
		ticket = frappe.db.sql(
			"SELECT event, price, total_quantity FROM `tabEM Ticket Type` WHERE name = %s FOR UPDATE",
			self.ticket_type,
			as_dict=True,
		)[0]
		if ticket.event != self.event:
			frappe.throw("Ticket Type must belong to the selected Event.")
		if self.is_new() and not frappe.db.get_value("EM Ticket Type", self.ticket_type, "is_active"):
			frappe.throw("Ticket Type is not active.")

		if self.status != "Cancelled":
			registrations = frappe.db.sql(
				"""
				SELECT ticket_type, quantity FROM `tabEM Registration`
				WHERE event = %s AND status != 'Cancelled' AND name != %s
				FOR UPDATE
				""",
				(self.event, self.name),
				as_dict=True,
			)
			reserved = sum(cint(row.quantity) for row in registrations if row.ticket_type == self.ticket_type)
			if cint(self.quantity) > cint(ticket.total_quantity) - reserved:
				frappe.throw("Quantity exceeds the remaining available tickets.")

			reserved = sum(cint(row.quantity) for row in registrations)
			if cint(self.quantity) > cint(event.capacity) - reserved:
				frappe.throw("Quantity exceeds the remaining Event capacity.")

		self.total_amount = flt(ticket.price) * cint(self.quantity)
		add_on_quantities = {}
		add_ons = {}
		for name in sorted({row.add_on for row in self.add_ons if row.add_on}):
			add_ons[name] = frappe.db.sql(
				"SELECT event, price, total__quantity FROM `tabEM Add On` WHERE name = %s FOR UPDATE",
				name,
				as_dict=True,
			)[0]

		for row in self.add_ons:
			if cint(row.quantity) <= 0:
				frappe.throw("Add On quantity must be greater than zero.")
			if not row.add_on:
				continue

			add_on = add_ons[row.add_on]
			if add_on.event != self.event:
				frappe.throw("Add On must belong to the selected Event.")

			row.price = flt(add_on.price)
			row.amount = row.price * cint(row.quantity)
			self.total_amount += row.amount
			add_on_quantities[row.add_on] = add_on_quantities.get(row.add_on, 0) + cint(row.quantity)

		if self.status != "Cancelled":
			for name, quantity in add_on_quantities.items():
				reserved = frappe.db.sql(
					"""
					SELECT child.quantity
					FROM `tabEM Registration Add On` AS child
					JOIN `tabEM Registration` AS registration ON registration.name = child.parent
					WHERE child.add_on = %s AND registration.status != 'Cancelled'
					AND registration.name != %s
					FOR UPDATE
					""",
					(name, self.name),
				)
				if quantity > cint(add_ons[name].total__quantity) - sum(cint(row[0]) for row in reserved):
					frappe.throw("Add On quantity exceeds the remaining available stock.")


@frappe.whitelist()
def check_in(registration):
	doc = frappe.get_doc("EM Registration", registration)
	doc.check_permission("write")
	status, checked_in = frappe.db.sql(
		"SELECT status, checked_in FROM `tabEM Registration` WHERE name = %s FOR UPDATE",
		registration,
	)[0]
	if status != "Confirmed":
		frappe.throw("Only confirmed registrations can be checked in.")
	if checked_in:
		frappe.throw("Registration is already checked in.")

	frappe.db.set_value("EM Registration", registration, {
		"checked_in": 1,
		"check_in_time": now_datetime(),
	})


@frappe.whitelist(allow_guest=True)
def ticket_qr_code(ticket_code):
	if not frappe.db.exists("EM Registration", {"ticket_code": ticket_code}):
		frappe.throw("Invalid Ticket Code")

	frappe.response.filename = "ticket-qr.svg"
	frappe.response.filecontent = base64.b64decode(get_qr_code(ticket_code).split(",", 1)[1])
	frappe.response.content_type = "image/svg+xml"
	frappe.response.display_content_as = "inline"
	frappe.response.type = "download"

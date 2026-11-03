import base64

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, now_datetime
from frappe.utils.print_format_generator import get_qr_code


class EMRegistration(Document):
	def validate(self):
		self.lock_existing_registration()
		self.validate_status()
		self.validate_quantity()
		self.validate_event_and_ticket()
		self.validate_ticket_availability()
		self.validate_add_ons()
		self.validate_capacity()
		self.calculate_total()

	def lock_existing_registration(self):
		if self.is_new():
			self.ticket_code = frappe.generate_hash(length=16)
			self.checked_in = 0
			self.check_in_time = None
			return
		current = frappe.db.get_value(
			"EM Registration",
			self.name,
			["ticket_code", "checked_in", "check_in_time", "status"],
			as_dict=True,
			for_update=True,
		)
		if not current:
			frappe.throw("Registration does not exist.")
		self.ticket_code = current.ticket_code
		self.checked_in = current.checked_in
		self.check_in_time = current.check_in_time
		self._previous_status = current.status

	def validate_status(self):
		if self.is_new() and self.status == "Pending":
			return
		if not self.is_new() and self.status == self._previous_status:
			return
		if "System Manager" not in frappe.get_roles():
			frappe.throw("Only Event managers can change registration status.", frappe.PermissionError)
		if not self.is_new() and self._previous_status == "Cancelled":
			frappe.throw("Cancelled registrations cannot be reopened.")
		if self.status == "Cancelled" and self.checked_in:
			frappe.throw("Checked-in registrations cannot be cancelled.")

	def validate_quantity(self):
		if cint(self.quantity) <= 0:
			frappe.throw("Quantity must be greater than zero.")

	def validate_event_and_ticket(self):
		self._event = frappe.db.get_value(
			"EM Event",
			self.event,
			["capacity", "status", "published", "start_date"],
			as_dict=True,
			for_update=True,
		)
		self._ticket = frappe.db.get_value(
			"EM Ticket Type",
			self.ticket_type,
			["event", "price", "total_quantity", "is_active", "available_from", "available_until"],
			as_dict=True,
			for_update=True,
		)
		if not self._event or not self._ticket:
			frappe.throw("Event or Ticket Type does not exist.")
		if self._ticket.event != self.event:
			frappe.throw("Ticket Type must belong to the selected Event.")

	def validate_ticket_availability(self):
		if self.status == "Cancelled":
			return
		if not self._ticket.is_active:
			frappe.throw("Ticket Type is not active.")
		if self.is_new():
			now = now_datetime()
			if not self._event.published or self._event.status != "Published":
				frappe.throw("Event is not published.")
			if self._event.start_date and now >= get_datetime(self._event.start_date):
				frappe.throw("Event registration is closed.")
			if self._ticket.available_from and now < get_datetime(self._ticket.available_from):
				frappe.throw("Ticket sales have not started.")
			if self._ticket.available_until and now > get_datetime(self._ticket.available_until):
				frappe.throw("Ticket sales have ended.")

	def validate_add_ons(self):
		self._add_ons = {}
		self._add_on_quantities = {}
		for name in sorted({row.add_on for row in self.add_ons if row.add_on}):
			add_on = frappe.db.get_value(
				"EM Add On", name, ["event", "price", "total__quantity", "is_active"],
				as_dict=True, for_update=True,
			)
			if not add_on:
				frappe.throw("Add On does not exist.")
			self._add_ons[name] = add_on
		for row in self.add_ons:
			if cint(row.quantity) <= 0:
				frappe.throw("Add On quantity must be greater than zero.")
			if not row.add_on:
				continue
			add_on = self._add_ons[row.add_on]
			if add_on.event != self.event:
				frappe.throw("Add On must belong to the selected Event.")
			if self.status != "Cancelled" and not add_on.is_active:
				frappe.throw("Add On is not active.")
			row.price = flt(add_on.price)
			row.amount = row.price * cint(row.quantity)
			self._add_on_quantities[row.add_on] = self._add_on_quantities.get(row.add_on, 0) + cint(row.quantity)

	def validate_capacity(self):
		if self.status == "Cancelled":
			return
		registrations = frappe.db.get_values(
			"EM Registration",
			filters={"event": self.event, "status": ["!=", "Cancelled"], "name": ["!=", self.name]},
			fieldname=["ticket_type", "quantity"], as_dict=True, for_update=True,
		)
		ticket_reserved = sum(
			cint(row.quantity) for row in registrations if row.ticket_type == self.ticket_type
		)
		if cint(self.quantity) > cint(self._ticket.total_quantity) - ticket_reserved:
			frappe.throw("Quantity exceeds the remaining available tickets.")
		if cint(self.quantity) > cint(self._event.capacity) - sum(cint(row.quantity) for row in registrations):
			frappe.throw("Quantity exceeds the remaining Event capacity.")
		child = frappe.qb.DocType("EM Registration Add On")
		registration = frappe.qb.DocType("EM Registration")
		for name, quantity in self._add_on_quantities.items():
			rows = (
				frappe.qb.from_(child)
				.join(registration).on(registration.name == child.parent)
				.select(child.quantity)
				.where(child.add_on == name)
				.where(registration.status != "Cancelled")
				.where(registration.name != self.name)
				.for_update()
			).run()
			reserved = sum(cint(row[0]) for row in rows)
			if quantity > cint(self._add_ons[name].total__quantity) - reserved:
				frappe.throw("Add On quantity exceeds the remaining available stock.")

	def calculate_total(self):
		self.total_amount = flt(self._ticket.price) * cint(self.quantity)
		self.total_amount += sum(flt(row.amount) for row in self.add_ons if row.add_on)


@frappe.whitelist()
def check_in(registration):
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only Event managers can check in attendees.", frappe.PermissionError)
	doc = frappe.get_doc("EM Registration", registration)
	doc.check_permission("write")
	current = frappe.db.get_value(
		"EM Registration", registration, ["status", "checked_in"], for_update=True
	)
	if not current:
		frappe.throw("Registration does not exist.")
	status, checked_in = current
	if status != "Confirmed":
		frappe.throw("Only confirmed registrations can be checked in.")
	if checked_in:
		frappe.throw("Registration is already checked in.")
	frappe.db.set_value("EM Registration", registration, {
		"checked_in": 1,
		"check_in_time": now_datetime(),
	})


@frappe.whitelist()
def ticket_qr_code(ticket_code):
	registration = frappe.db.get_value("EM Registration", {"ticket_code": ticket_code}, "name")
	if not registration:
		frappe.throw("Invalid Ticket Code")
	doc = frappe.get_doc("EM Registration", registration)
	is_manager = "System Manager" in frappe.get_roles()
	if not is_manager and doc.owner != frappe.session.user:
		frappe.throw("Not permitted to view this ticket.", frappe.PermissionError)
	if is_manager:
		doc.check_permission("read")
	frappe.response.filename = "ticket-qr.svg"
	frappe.response.filecontent = base64.b64decode(get_qr_code(ticket_code).split(",", 1)[1])
	frappe.response.content_type = "image/svg+xml"
	frappe.response.display_content_as = "inline"
	frappe.response.type = "download"

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, now_datetime


class EMRegistration(Document):
	def validate(self):
		self.validate_quantity()
		self.validate_event_and_ticket()
		self.validate_add_ons()
		self.lock_existing_registration()
		self.validate_status()
		self.validate_ticket_availability()
		self.validate_capacity()
		self.calculate_total()
		self.validate_issued_tickets()

	def on_update(self):
		if self.status == "Confirmed":
			self.issue_tickets()
		elif self.status == "Cancelled":
			for ticket in frappe.db.get_all("EM Ticket", filters={"registration": self.name, "status": "Issued"}, pluck="name"):
				frappe.db.set_value("EM Ticket", ticket, "status", "Cancelled")

	def validate_issued_tickets(self):
		if self.is_new():
			return
		previous_total = frappe.db.get_value("EM Registration", self.name, "total_amount")
		if flt(previous_total) > 0 and flt(self.total_amount) <= 0:
			frappe.throw("A paid registration cannot be changed to a free registration.")
		tickets = frappe.db.get_all(
			"EM Ticket", filters={"registration": self.name},
			fields=["name", "event", "ticket_type", "status"],
		)
		if not tickets:
			return
		if self.status != "Cancelled" and flt(previous_total) <= 0 and flt(self.total_amount) > 0:
			frappe.throw("Issued free tickets cannot become payable.")
		if any(ticket.status == "Checked In" for ticket in tickets) and self.status == "Cancelled":
			frappe.throw("Checked-in tickets cannot be cancelled.")
		if self.status != "Cancelled" and (
			len(tickets) != cint(self.quantity)
			or any(ticket.event != self.event or ticket.ticket_type != self.ticket_type for ticket in tickets)
		):
			frappe.throw("Issued ticket quantity, event, and ticket type cannot be changed.")

	def issue_tickets(self):
		if self.status != "Confirmed":
			return
		if flt(self.total_amount) > 0:
			return
		from event_management.event_management.doctype.em_ticket.em_ticket import make_token

		existing = frappe.db.get_all("EM Ticket", filters={"registration": self.name}, pluck="name")
		if existing:
			if len(existing) != cint(self.quantity):
				frappe.throw("Ticket issuance is incomplete; manual review is required.")
			return
		was_issuing = frappe.flags.em_ticket_issuance
		frappe.flags.em_ticket_issuance = True
		try:
			for _ in range(cint(self.quantity)):
				frappe.get_doc({
					"doctype": "EM Ticket", "registration": self.name, "event": self.event,
					"ticket_type": self.ticket_type, "attendee_name": self.attendee_name,
					"token": make_token(), "status": "Issued",
				}).insert(ignore_permissions=True)
		finally:
			frappe.flags.em_ticket_issuance = was_issuing

		def queue_ticket_email():
			try:
				frappe.enqueue(
					"event_management.event_management.doctype.em_ticket.em_ticket.send_ticket_email",
					registration_name=self.name,
				)
			except Exception:
				frappe.logger("event_management").exception("Could not queue ticket email for %s", self.name)

		frappe.db.after_commit.add(queue_ticket_email)

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
		attendee_cancellation = (
			self.status == "Cancelled"
			and self._previous_status in ("Pending", "Confirmed")
			and self.owner == frappe.session.user
			and frappe.flags.get("em_attendee_cancellation") == self.name
		)
		if "System Manager" not in frappe.get_roles() and not attendee_cancellation:
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
def get_my_registrations():
	if frappe.session.user == "Guest":
		frappe.throw("Login is required.", frappe.PermissionError)
	registrations = frappe.db.get_all(
		"EM Registration", filters={"owner": frappe.session.user},
		fields=["name", "event", "ticket_type", "quantity", "total_amount", "status"],
		order_by="creation desc",
	)
	if not registrations:
		return []
	names = [row.name for row in registrations]
	checked_in = set(frappe.db.get_all(
		"EM Ticket", filters={"registration": ["in", names], "status": "Checked In"},
		pluck="registration",
	))
	add_ons = frappe.db.get_all(
		"EM Registration Add On", filters={"parent": ["in", names], "parenttype": "EM Registration"},
		fields=["parent", "add_on", "quantity", "amount"], order_by="idx asc",
	)
	events = {row.name: row.event_name for row in frappe.db.get_all(
		"EM Event", filters={"name": ["in", list({row.event for row in registrations})]},
		fields=["name", "event_name"],
	)}
	ticket_types = {row.name: row.ticket_name for row in frappe.db.get_all(
		"EM Ticket Type", filters={"name": ["in", list({row.ticket_type for row in registrations})]},
		fields=["name", "ticket_name"],
	)}
	add_on_names = {row.add_on for row in add_ons}
	add_on_labels = {row.name: row.add_on_name for row in frappe.db.get_all(
		"EM Add On", filters={"name": ["in", list(add_on_names)]},
		fields=["name", "add_on_name"],
	)} if add_on_names else {}
	registrations_by_name = {row.name: row for row in registrations}
	for row in registrations:
		row.event_name = events.get(row.event, row.event)
		row.ticket_name = ticket_types.get(row.ticket_type, row.ticket_type)
		row.can_cancel = row.status in ("Pending", "Confirmed") and row.name not in checked_in
		row.add_ons = []
	for add_on in add_ons:
		add_on.add_on_name = add_on_labels.get(add_on.add_on, add_on.add_on)
		registrations_by_name[add_on.parent].add_ons.append(add_on)
	return registrations


@frappe.whitelist(methods=["POST"])
def cancel_my_registration(registration):
	if frappe.session.user == "Guest":
		frappe.throw("Login is required.", frappe.PermissionError)
	current = frappe.db.get_value(
		"EM Registration", registration, ["owner", "status"], as_dict=True, for_update=True,
	)
	if not current or current.owner != frappe.session.user:
		frappe.throw("Not permitted to cancel this registration.", frappe.PermissionError)
	if current.status not in ("Pending", "Confirmed"):
		frappe.throw("This registration cannot be cancelled.")
	doc = frappe.get_doc("EM Registration", registration)
	doc.status = "Cancelled"
	frappe.flags.em_attendee_cancellation = registration
	try:
		doc.save(ignore_permissions=True)
	finally:
		frappe.flags.em_attendee_cancellation = None
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def check_in(registration):
	frappe.throw("Scan an issued EM Ticket to check in an attendee.")


@frappe.whitelist()
def ticket_qr_code(ticket_code):
	frappe.throw("Registration ticket codes are no longer valid; use issued EM Tickets.")

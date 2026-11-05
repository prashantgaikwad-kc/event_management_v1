# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import csv
from io import StringIO

import frappe
from event_management.permissions import validate_event_scope
from frappe.query_builder.functions import Coalesce, Count, Date
from frappe.utils import cint, get_datetime
from frappe.website.website_generator import WebsiteGenerator


class EMEvent(WebsiteGenerator):
	def validate(self):
		validate_event_scope(self)
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


def _dashboard_events(event=None):
	user = frappe.session.user
	roles = frappe.get_roles(user)
	if user != "Administrator" and "System Manager" not in roles and "EM Organizer" not in roles:
		frappe.throw("Organizer access is required.", frappe.PermissionError)
	filters = {}
	if user != "Administrator" and "System Manager" not in roles:
		filters["organizer"] = user
	if event:
		filters["name"] = event
	events = frappe.db.get_all("EM Event", filters=filters, pluck="name")
	if event and not events:
		frappe.throw("Not permitted to access this event.", frappe.PermissionError)
	return events


@frappe.whitelist()
def organizer_events():
	events = _dashboard_events()
	if not events:
		return []
	return frappe.db.get_all(
		"EM Event", filters={"name": ["in", events]},
		fields=["name", "event_name"], order_by="event_name asc", limit_page_length=0,
	)


@frappe.whitelist()
def organizer_summary(event=None):
	events = _dashboard_events(event)
	registrations = {"total": 0, "pending": 0, "confirmed": 0, "cancelled": 0}
	tickets = {"issued": 0, "checked_in": 0}
	if events:
		registration = frappe.qb.DocType("EM Registration")
		for status, count in (
			frappe.qb.from_(registration)
			.select(registration.status, Count(registration.name))
			.where(registration.event.isin(events))
			.groupby(registration.status)
		).run():
			registrations["total"] += count
			if status and status.lower() in registrations:
				registrations[status.lower()] = count
		ticket = frappe.qb.DocType("EM Ticket")
		for status, count in (
			frappe.qb.from_(ticket)
			.select(ticket.status, Count(ticket.name))
			.where(ticket.event.isin(events))
			.groupby(ticket.status)
		).run():
			if status == "Issued":
				tickets["issued"] = count
			elif status == "Checked In":
				tickets["checked_in"] = count
	issued_total = tickets["issued"] + tickets["checked_in"]
	return {
		"registrations": registrations,
		"tickets": {**tickets, "total_issued": issued_total},
		"attendance_percentage": round(tickets["checked_in"] * 100 / issued_total, 2) if issued_total else 0,
	}


@frappe.whitelist()
def organizer_registration_trend(event=None):
	events = _dashboard_events(event)
	if not events:
		return []
	registration = frappe.qb.DocType("EM Registration")
	registration_day = Date(Coalesce(registration.registration_date, registration.creation))
	rows = (
		frappe.qb.from_(registration)
		.select(registration_day, Count(registration.name))
		.where(registration.event.isin(events))
		.groupby(registration_day)
		.orderby(registration_day)
	).run()
	return [{"date": str(date), "count": count} for date, count in rows]


@frappe.whitelist()
def organizer_check_in_report(event=None):
	events = _dashboard_events(event)
	if not events:
		return []
	ticket = frappe.qb.DocType("EM Ticket")
	event_doc = frappe.qb.DocType("EM Event")
	ticket_type = frappe.qb.DocType("EM Ticket Type")
	return (
		frappe.qb.from_(ticket)
		.join(event_doc).on(event_doc.name == ticket.event)
		.join(ticket_type).on((ticket_type.name == ticket.ticket_type) & (ticket_type.event == ticket.event))
		.select(
			event_doc.event_name.as_("event"), ticket.attendee_name,
			ticket_type.ticket_name.as_("ticket_type"), ticket.status,
			ticket.checked_in_at.as_("check_in_time"),
		)
		.where(ticket.event.isin(events))
		.orderby(ticket.checked_in_at, order=frappe.qb.desc)
	).run(as_dict=True)


@frappe.whitelist()
def organizer_attendee_export(event=None):
	events = _dashboard_events(event)
	output = StringIO()
	writer = csv.writer(output)
	writer.writerow(["Event", "Attendee Name", "Email", "Ticket Type", "Registration Status"])
	if events:
		registration = frappe.qb.DocType("EM Registration")
		event_doc = frappe.qb.DocType("EM Event")
		ticket_type = frappe.qb.DocType("EM Ticket Type")
		rows = (
			frappe.qb.from_(registration)
			.join(event_doc).on(event_doc.name == registration.event)
			.join(ticket_type).on(
				(ticket_type.name == registration.ticket_type) & (ticket_type.event == registration.event)
			)
			.select(event_doc.event_name, registration.attendee_name, registration.email,
				ticket_type.ticket_name, registration.status)
			.where(registration.event.isin(events))
			.orderby(registration.registration_date)
		).run()
		for row in rows:
			writer.writerow([
				"'" + str(value) if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
				for value in row
			])
	frappe.response["type"] = "download"
	frappe.response["filename"] = "organizer_attendees.csv"
	frappe.response["filecontent"] = output.getvalue()

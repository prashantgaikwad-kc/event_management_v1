import frappe
from frappe.utils import cint, now_datetime


def get_context(context):
	context.title = "Upcoming Events"
	context.no_cache = 1
	context.events = get_upcoming_events()


@frappe.whitelist(allow_guest=True)
def get_upcoming_events():
	return frappe.get_all(
		"EM Event",
		filters={"published": 1, "status": "Published", "start_date": [">=", now_datetime()]},
		fields=["event_name", "venue", "start_date", "description", "route"],
		order_by="start_date asc",
	)


@frappe.whitelist(allow_guest=True)
def get_event_details(route):
	event = frappe.db.get_value(
		"EM Event",
		{"route": route, "published": 1, "status": "Published"},
		["name", "event_name", "description", "venue", "start_date", "end_date", "route", "capacity"],
		as_dict=True,
	)
	if not event:
		frappe.throw("Event not found.", frappe.DoesNotExistError)

	ticket_types = frappe.get_all(
		"EM Ticket Type",
		filters={"event": event.name, "is_active": 1},
		fields=["name", "ticket_name", "price", "total_quantity", "available_from", "available_until"],
		order_by="price asc",
	)
	registrations = frappe.get_all(
		"EM Registration",
		filters={"event": event.name, "status": ["!=", "Cancelled"]},
		fields=["ticket_type", "quantity"],
	)
	reserved = sum(cint(row.quantity) for row in registrations)
	event.remaining_capacity = max(0, cint(event.capacity) - reserved)
	for ticket in ticket_types:
		ticket_reserved = sum(cint(row.quantity) for row in registrations if row.ticket_type == ticket.name)
		ticket.remaining_quantity = min(
			event.remaining_capacity, max(0, cint(ticket.total_quantity) - ticket_reserved)
		)
	event.ticket_types = ticket_types
	return event

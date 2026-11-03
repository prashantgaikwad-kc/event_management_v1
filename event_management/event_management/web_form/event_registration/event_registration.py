import frappe
from frappe.utils import get_datetime, now_datetime


def get_list_context(context):
	context.get_list = get_registrations
	return context


def get_registrations(doctype, txt, filters, limit_start, limit_page_length, order_by):
	if frappe.session.user == "Guest":
		return []
	if doctype != "EM Registration":
		frappe.throw("Invalid registration list.", frappe.PermissionError)
	filters = dict(filters or {})
	filters["owner"] = frappe.session.user
	if txt:
		filters["name"] = ["like", f"%{txt}%"]
	return frappe.get_all(
		doctype,
		filters=filters,
		fields=["name", "attendee_name", "event", "status", "creation"],
		limit_start=limit_start,
		limit_page_length=limit_page_length,
		order_by=order_by,
	)


@frappe.whitelist()
def get_event_options(event):
	if not frappe.db.exists("EM Event", {
		"name": event, "published": 1, "status": "Published",
		"start_date": [">", now_datetime()],
	}):
		return {"tickets": [], "add_ons": []}

	now = now_datetime()
	tickets = frappe.get_all(
		"EM Ticket Type",
		filters={"event": event, "is_active": 1},
		fields=["name", "ticket_name", "price", "available_from", "available_until"],
	)
	return {
		"tickets": [
			{"name": ticket.name, "ticket_name": ticket.ticket_name, "price": ticket.price}
			for ticket in tickets
			if (not ticket.available_from or get_datetime(ticket.available_from) <= now)
			and (not ticket.available_until or now <= get_datetime(ticket.available_until))
		],
		"add_ons": frappe.get_all(
			"EM Add On",
			filters={"event": event, "is_active": 1},
			fields=["name", "add_on_name", "price"],
		),
	}

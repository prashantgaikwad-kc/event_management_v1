import frappe


def get_context(context):
	pass


def get_list_context(context):
	context.get_list = get_registrations
	return context


def get_registrations(doctype, txt, filters, limit_start, limit_page_length, order_by):
	if frappe.session.user == "Guest":
		return []

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
	if not frappe.db.exists("EM Event", {"name": event, "published": 1}):
		return {"tickets": [], "add_ons": []}

	return {
		"tickets": frappe.get_all(
			"EM Ticket Type",
			filters={"event": event, "is_active": 1},
			fields=["name", "ticket_name", "price"],
		),
		"add_ons": frappe.get_all(
			"EM Add On",
			filters={"event": event, "is_active": 1},
			fields=["name", "add_on_name", "price"],
		),
	}

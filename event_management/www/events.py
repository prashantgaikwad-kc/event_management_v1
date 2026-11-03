import frappe
from frappe.utils import now_datetime


def get_context(context):
	context.title = "Upcoming Events"
	context.no_cache = 1
	context.events = frappe.get_all(
		"EM Event",
		filters={"published": 1, "start_date": [">=", now_datetime()]},
		fields=["event_name", "venue", "start_date", "description", "route"],
		order_by="start_date asc",
	)

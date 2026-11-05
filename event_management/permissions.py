"""Document scope for EM Organizers.

Role permissions still grant the allowed actions; these hooks restrict their scope.
"""

import frappe


def _is_organizer(user):
	roles = frappe.get_roles(user)
	return "EM Organizer" in roles and "System Manager" not in roles


def event_query(user=None, doctype=None):
	user = user or frappe.session.user
	if not _is_organizer(user):
		return None
	event = frappe.qb.DocType("EM Event")
	return (event.organizer == frappe.qb.terms.LiteralValue(frappe.db.escape(user, percent=False))).get_sql(
		with_namespace=True, quote_char=_quote_char()
	)


def _quote_char():
	return '"' if frappe.db.db_type == "postgres" else "`"


def linked_query(doctype, user=None):
	user = user or frappe.session.user
	if not _is_organizer(user):
		return None
	event = frappe.qb.DocType("EM Event")
	linked = frappe.qb.DocType(doctype)
	assigned_events = frappe.qb.from_(event).select(event.name).where(
		event.organizer == frappe.qb.terms.LiteralValue(frappe.db.escape(user, percent=False))
	)
	return linked.event.isin(assigned_events).get_sql(with_namespace=True, quote_char=_quote_char())


def ticket_type_query(user=None, doctype=None):
	return linked_query("EM Ticket Type", user)


def add_on_query(user=None, doctype=None):
	return linked_query("EM Add On", user)


def has_event_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if not _is_organizer(user):
		return True
	return doc.organizer == user and (
		doc.is_new() or frappe.db.get_value("EM Event", doc.name, "organizer") == user
	)


def has_linked_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if not _is_organizer(user):
		return True
	if frappe.db.get_value("EM Event", doc.event, "organizer") != user:
		return False
	if not doc.is_new():
		old_event = frappe.db.get_value(doc.doctype, doc.name, "event")
		return frappe.db.get_value("EM Event", old_event, "organizer") == user
	return True


def validate_event_scope(doc):
	user = frappe.session.user
	if _is_organizer(user) and not has_event_permission(doc, "create" if doc.is_new() else "write", user):
		frappe.throw("You can only manage events assigned to you.", frappe.PermissionError)


def validate_linked_scope(doc):
	user = frappe.session.user
	if _is_organizer(user) and not has_linked_permission(doc, "create" if doc.is_new() else "write", user):
		frappe.throw("You can only manage items for your assigned events.", frappe.PermissionError)

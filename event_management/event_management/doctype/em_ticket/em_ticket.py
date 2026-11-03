# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import hashlib
import hmac
import secrets

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class EMTicket(Document):
	def before_insert(self):
		if not frappe.flags.em_ticket_issuance:
			frappe.throw("Tickets can only be created from confirmed registrations.", frappe.PermissionError)

	def validate(self):
		if self.is_new():
			return
		current = frappe.db.get_value(
			"EM Ticket", self.name,
			["registration", "event", "ticket_type", "attendee_name", "token", "status", "checked_in_at", "checked_in_by"],
			as_dict=True, for_update=True,
		)
		if not current or any(self.get(field) != current.get(field) for field in current):
			frappe.throw("Issued ticket credentials and check-in state cannot be edited.", frappe.PermissionError)

	def on_trash(self):
		frappe.throw("Issued tickets cannot be deleted.", frappe.PermissionError)


def make_token():
	return secrets.token_urlsafe(32)


def _signature(token):
	key = frappe.conf.get("encryption_key")
	if not key:
		frappe.throw("Site encryption key is required for ticket credentials.")
	return hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()


def _credential(token):
	return f"{token}.{_signature(token)}"


@frappe.whitelist()
def get_my_tickets(registration):
	if frappe.session.user == "Guest":
		frappe.throw("Login is required.", frappe.PermissionError)
	owner = frappe.db.get_value("EM Registration", registration, "owner")
	if not owner or owner != frappe.session.user:
		frappe.throw("Not permitted to view these tickets.", frappe.PermissionError)
	rows = frappe.db.get_all(
		"EM Ticket", filters={"registration": registration},
		fields=["name", "event", "ticket_type", "attendee_name", "status", "token", "checked_in_at"],
	)
	return [{
		"name": row.name, "event": row.event, "ticket_type": row.ticket_type,
		"attendee_name": row.attendee_name, "status": row.status,
		"checked_in_at": row.checked_in_at,
		"qr_credential": _credential(row.token) if row.status == "Issued" else None,
	} for row in rows]


@frappe.whitelist(methods=["POST"])
def check_in_ticket(qr_credential):
	if frappe.session.user == "Guest" or not {"System Manager", "EM Gate Staff"}.intersection(frappe.get_roles()):
		frappe.throw("Only authorized gate staff can check in tickets.", frappe.PermissionError)
	if not isinstance(qr_credential, str) or len(qr_credential) > 256:
		frappe.throw("Invalid ticket credential.")
	try:
		token, signature = qr_credential.split(".")
	except ValueError:
		frappe.throw("Invalid ticket credential.")
	if not token or not hmac.compare_digest(signature, _signature(token)):
		frappe.throw("Invalid ticket credential.")
	registration = frappe.db.get_value("EM Ticket", {"token": token}, "registration")
	if not registration:
		frappe.throw("Invalid ticket credential.")
	current = frappe.db.get_value("EM Registration", registration, "status", for_update=True)
	if current != "Confirmed":
		frappe.throw("Registration is not confirmed.")
	ticket = frappe.db.get_value(
		"EM Ticket", {"token": token}, ["name", "status", "registration"], as_dict=True, for_update=True,
	)
	if not ticket or ticket.registration != registration or ticket.status == "Cancelled":
		frappe.throw("Ticket is not valid for check-in.")
	if ticket.status == "Checked In":
		return {"ticket": ticket.name, "status": "Already Checked In"}
	if ticket.status != "Issued":
		frappe.throw("Ticket is not issued.")
	frappe.db.set_value("EM Ticket", ticket.name, {
		"status": "Checked In", "checked_in_at": now_datetime(), "checked_in_by": frappe.session.user,
	})
	return {"ticket": ticket.name, "status": "Checked In"}

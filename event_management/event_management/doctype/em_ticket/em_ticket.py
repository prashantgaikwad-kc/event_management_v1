# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import hashlib
import hmac
import io
import secrets
from html import escape

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from PIL import Image
from pyqrcode import create as create_qr


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


def send_ticket_email(registration_name):
	try:
		registration = frappe.db.get_value(
			"EM Registration", registration_name,
			["email", "event", "ticket_type", "status", "total_amount", "quantity"], as_dict=True,
		)
		if not registration or registration.status != "Confirmed" or registration.total_amount != 0:
			return
		tickets = frappe.db.get_all(
			"EM Ticket", filters={"registration": registration_name},
			fields=["name", "attendee_name", "token", "status"], order_by="name asc",
		)
		if len(tickets) != registration.quantity or any(ticket.status == "Cancelled" for ticket in tickets):
			return
		event_name = frappe.db.get_value("EM Event", registration.event, "event_name")
		ticket_name = frappe.db.get_value("EM Ticket Type", registration.ticket_type, "ticket_name")
		parts = [f"<h2>{escape(event_name or registration.event)}</h2>"]
		images = []
		for ticket in tickets:
			qr = create_qr(_credential(ticket.token))
			width = len(qr.code) + 8
			image = Image.new("1", (width, width), 1)
			pixels = image.load()
			for y, row in enumerate(qr.code):
				for x, value in enumerate(row):
					if value:
						pixels[x + 4, y + 4] = 0
			buffer = io.BytesIO()
			image.resize((width * 6, width * 6), Image.Resampling.NEAREST).save(buffer, format="PNG")
			filename = f"{ticket.name}.png"
			images.append({"filename": filename, "filecontent": buffer.getvalue()})
			parts.append(
				f"<p><strong>Ticket:</strong> {escape(ticket.name)}<br>"
				f"<strong>Attendee:</strong> {escape(ticket.attendee_name or '')}<br>"
				f"<strong>Ticket type:</strong> {escape(ticket_name or registration.ticket_type)}</p>"
				f'<img embed="{filename}" alt="QR code for ticket {escape(ticket.name)}">'
			)
		frappe.sendmail(
			recipients=[registration.email], subject=f"Tickets for {event_name or registration.event}",
			message="".join(parts), inline_images=images,
		)
	except Exception:
		frappe.logger("event_management").exception("Could not prepare ticket email for %s", registration_name)


@frappe.whitelist()
def get_my_tickets(registration=None):
	if frappe.session.user == "Guest":
		frappe.throw("Login is required.", frappe.PermissionError)
	if registration:
		owner = frappe.db.get_value("EM Registration", registration, "owner")
		if not owner or owner != frappe.session.user:
			frappe.throw("Not permitted to view these tickets.", frappe.PermissionError)
		registrations = [registration]
	else:
		registrations = frappe.db.get_all(
			"EM Registration", filters={"owner": frappe.session.user}, pluck="name"
		)
		if not registrations:
			return []
	rows = frappe.db.get_all(
		"EM Ticket", filters={"registration": ["in", registrations]},
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
	_require_gate_staff()
	if not isinstance(qr_credential, str) or len(qr_credential) > 256:
		frappe.throw("Invalid ticket credential.")
	try:
		token, signature = qr_credential.split(".")
	except ValueError:
		frappe.throw("Invalid ticket credential.")
	if not token or not hmac.compare_digest(signature, _signature(token)):
		frappe.throw("Invalid ticket credential.")
	ticket = frappe.db.get_value("EM Ticket", {"token": token}, ["name", "registration"], as_dict=True)
	if not ticket:
		frappe.throw("Invalid ticket credential.")
	return _check_in(ticket.name, ticket.registration)


def _require_gate_staff():
	if frappe.session.user == "Guest" or not {"System Manager", "EM Gate Staff"}.intersection(frappe.get_roles()):
		frappe.throw("Only authorized gate staff can check in tickets.", frappe.PermissionError)


@frappe.whitelist()
def search_tickets(query):
	_require_gate_staff()
	if not isinstance(query, str) or not query.strip():
		return []
	term = f"%{query.strip()[:100]}%"
	ticket = frappe.qb.DocType("EM Ticket")
	registration = frappe.qb.DocType("EM Registration")
	return (
		frappe.qb.from_(ticket)
		.join(registration).on(ticket.registration == registration.name)
		.select(ticket.name, ticket.attendee_name, ticket.event, ticket.ticket_type, ticket.status)
		.where((ticket.attendee_name.like(term)) | (registration.email.like(term)))
		.orderby(ticket.creation, order=frappe.qb.desc)
		.limit(20)
	).run(as_dict=True)


@frappe.whitelist(methods=["POST"])
def manual_check_in(ticket_id):
	_require_gate_staff()
	if not isinstance(ticket_id, str) or not ticket_id:
		frappe.throw("Invalid ticket.")
	registration = frappe.db.get_value("EM Ticket", ticket_id, "registration")
	if not registration:
		frappe.throw("Invalid ticket.")
	return _check_in(ticket_id, registration, reject_duplicate=True)


def _check_in(ticket_id, registration, reject_duplicate=False):
	current = frappe.db.get_value("EM Registration", registration, "status", for_update=True)
	if current != "Confirmed":
		frappe.throw("Registration is not confirmed.")
	ticket = frappe.db.get_value(
		"EM Ticket", ticket_id, ["name", "status", "registration"], as_dict=True, for_update=True,
	)
	if not ticket or ticket.registration != registration or ticket.status == "Cancelled":
		frappe.throw("Ticket is not valid for check-in.")
	if ticket.status == "Checked In":
		if reject_duplicate:
			frappe.throw("Ticket is already checked in.")
		return {"ticket": ticket.name, "status": "Already Checked In"}
	if ticket.status != "Issued":
		frappe.throw("Ticket is not issued.")
	frappe.db.set_value("EM Ticket", ticket.name, {
		"status": "Checked In", "checked_in_at": now_datetime(), "checked_in_by": frappe.session.user,
	})
	return {"ticket": ticket.name, "status": "Checked In"}

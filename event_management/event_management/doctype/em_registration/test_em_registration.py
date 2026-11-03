import frappe
from frappe.handler import is_valid_http_method
from frappe.tests import IntegrationTestCase

from event_management.event_management.doctype.em_registration.em_registration import (
	check_in,
	ticket_qr_code,
)
from event_management.event_management.doctype.em_ticket.em_ticket import check_in_ticket, get_my_tickets


class IntegrationTestEMRegistration(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.event = frappe.get_doc({
			"doctype": "EM Event",
			"event_name": f"Test Event {frappe.generate_hash(length=8)}",
			"venue": "Test Venue",
			"capacity": 2,
			"status": "Published",
			"published": 1,
			"start_date": "2030-01-01 10:00:00",
			"end_date": "2030-01-01 12:00:00",
		}).insert()
		self.ticket = frappe.get_doc({
			"doctype": "EM Ticket Type",
			"ticket_name": "General",
			"event": self.event.name,
			"price": 0,
			"total_quantity": 2,
			"is_active": 1,
		}).insert()
		self.add_on = frappe.get_doc({
			"doctype": "EM Add On",
			"add_on_name": "Lunch",
			"event": self.event.name,
			"price": 5,
			"total__quantity": 1,
			"is_active": 1,
		}).insert()

	def registration(self, quantity=1, add_on_quantity=0):
		doc = frappe.get_doc({
			"doctype": "EM Registration",
			"attendee_name": "Test Attendee",
			"email": "attendee@example.com",
			"mobile_number": "9999999999",
			"event": self.event.name,
			"ticket_type": self.ticket.name,
			"quantity": quantity,
			"status": "Pending",
		})
		if add_on_quantity:
			doc.append("add_ons", {"add_on": self.add_on.name, "quantity": add_on_quantity})
		return doc

	def test_event_capacity(self):
		self.registration(quantity=2).insert()
		with self.assertRaises(frappe.ValidationError):
			self.registration().insert()
		self.event.capacity = 1
		with self.assertRaises(frappe.ValidationError):
			self.event.save()

	def test_ticket_capacity(self):
		self.ticket.total_quantity = 1
		self.ticket.save()
		self.registration().insert()
		with self.assertRaises(frappe.ValidationError):
			self.registration().insert()
		self.ticket.total_quantity = 0
		with self.assertRaises(frappe.ValidationError):
			self.ticket.save()

	def test_add_on_stock(self):
		self.registration(add_on_quantity=1).insert()
		with self.assertRaises(frappe.ValidationError):
			self.registration(add_on_quantity=1).insert()
		self.add_on.total__quantity = 0
		with self.assertRaises(frappe.ValidationError):
			self.add_on.save()

	def test_duplicate_check_in(self):
		doc = self.registration().insert()
		doc.status = "Confirmed"
		doc.save()
		credential = get_my_tickets(doc.name)[0]["qr_credential"]
		self.assertEqual(check_in_ticket(credential)["status"], "Checked In")
		self.assertEqual(check_in_ticket(credential)["status"], "Already Checked In")
		self.assertEqual(frappe.db.get_value("EM Registration", doc.name, "checked_in"), 0)
		with self.assertRaises(frappe.ValidationError):
			check_in(doc.name)
		with self.assertRaises(frappe.ValidationError):
			doc.status = "Cancelled"
			doc.save()

	def test_quantity_and_duplicate_issuance(self):
		doc = self.registration(quantity=2).insert()
		doc.status = "Confirmed"
		doc.save()
		self.assertEqual(len(get_my_tickets(doc.name)), 2)
		doc.save()
		self.assertEqual(len(get_my_tickets(doc.name)), 2)

	def test_invalid_token_and_cancellation(self):
		doc = self.registration().insert()
		doc.status = "Confirmed"
		doc.save()
		credential = get_my_tickets(doc.name)[0]["qr_credential"]
		with self.assertRaises(frappe.ValidationError):
			check_in_ticket(credential + "x")
		with self.assertRaises(frappe.ValidationError):
			check_in_ticket("invalid")
		doc.status = "Cancelled"
		doc.save()
		self.assertEqual(get_my_tickets(doc.name)[0]["status"], "Cancelled")
		with self.assertRaises(frappe.ValidationError):
			check_in_ticket(credential)

	def test_paid_tickets_require_independent_verification(self):
		self.ticket.price = 10
		self.ticket.save()
		doc = self.registration().insert()
		doc.status = "Confirmed"
		doc.payment_status = "Paid"
		doc.payment_reference = "claimed-payment"
		doc.save()
		self.assertFalse(frappe.db.exists("EM Ticket", {"registration": doc.name}))

	def test_issued_free_tickets_cannot_become_payable(self):
		doc = self.registration().insert()
		doc.status = "Confirmed"
		doc.save()
		self.ticket.price = 10
		self.ticket.save()
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		self.assertEqual(frappe.db.get_value("EM Registration", doc.name, "total_amount"), 0)
		self.assertEqual(get_my_tickets(doc.name)[0]["status"], "Issued")

	def test_other_user_cannot_retrieve_tickets(self):
		doc = self.registration().insert()
		doc.status = "Confirmed"
		doc.save()
		other = frappe.get_doc({
			"doctype": "User", "email": f"other-{frappe.generate_hash(length=8)}@example.com",
			"first_name": "Other", "send_welcome_email": 0,
		}).insert(ignore_permissions=True)
		user = frappe.session.user
		try:
			frappe.set_user(other.name)
			with self.assertRaises(frappe.PermissionError):
				get_my_tickets(doc.name)
		finally:
			frappe.set_user(user)

	def test_gate_staff_can_check_in(self):
		doc = self.registration().insert()
		doc.status = "Confirmed"
		doc.save()
		credential = get_my_tickets(doc.name)[0]["qr_credential"]
		staff = frappe.get_doc({
			"doctype": "User", "email": f"gate-{frappe.generate_hash(length=8)}@example.com",
			"first_name": "Gate", "send_welcome_email": 0,
		}).insert(ignore_permissions=True)
		staff.add_roles("EM Gate Staff")
		user = frappe.session.user
		try:
			frappe.set_user(staff.name)
			self.assertEqual(check_in_ticket(credential)["status"], "Checked In")
			self.assertEqual(frappe.db.get_value("EM Ticket", {"registration": doc.name}, "checked_in_by"), staff.name)
		finally:
			frappe.set_user(user)

	def test_check_in_requires_post(self):
		request = getattr(frappe.local, "request", None)
		try:
			frappe.local.request = frappe._dict(method="GET")
			with self.assertRaises(frappe.PermissionError):
				is_valid_http_method(check_in_ticket)
			frappe.local.request.method = "POST"
			is_valid_http_method(check_in_ticket)
		finally:
			frappe.local.request = request

	def test_ticket_cannot_be_created_or_edited_directly(self):
		doc = self.registration().insert()
		doc.status = "Confirmed"
		doc.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({
				"doctype": "EM Ticket", "registration": doc.name, "event": doc.event,
				"ticket_type": doc.ticket_type, "token": frappe.generate_hash(length=32),
			}).insert(ignore_permissions=True)
		ticket = frappe.get_doc("EM Ticket", frappe.db.get_value("EM Ticket", {"registration": doc.name}, "name"))
		ticket.status = "Checked In"
		with self.assertRaises(frappe.PermissionError):
			ticket.save(ignore_permissions=True)

	def test_invalid_status_transitions(self):
		doc = self.registration().insert()
		doc.status = "Cancelled"
		doc.save()
		doc.status = "Confirmed"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_unauthorized_access(self):
		doc = self.registration().insert()
		user = frappe.session.user
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				get_my_tickets(doc.name)
			with self.assertRaises(frappe.PermissionError):
				check_in_ticket("invalid")
			with self.assertRaises(frappe.ValidationError):
				ticket_qr_code(doc.ticket_code)
			doc.status = "Confirmed"
			with self.assertRaises(frappe.PermissionError):
				doc.save(ignore_permissions=True)
		finally:
			frappe.set_user(user)

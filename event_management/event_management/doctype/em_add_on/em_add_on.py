# Copyright (c) 2026, Prashant and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class EMAddOn(Document):
	def validate(self):
		frappe.db.get_value("EM Event", self.event, "name", for_update=True)
		if not self.is_new():
			frappe.db.get_value("EM Add On", self.name, "name", for_update=True)
		if flt(self.price) < 0:
			frappe.throw("Add On price cannot be negative.")
		if cint(self.total__quantity) < 0:
			frappe.throw("Add On stock cannot be negative.")
		if not self.is_new():
			child = frappe.qb.DocType("EM Registration Add On")
			registration = frappe.qb.DocType("EM Registration")
			rows = (
				frappe.qb.from_(child)
				.join(registration).on(registration.name == child.parent)
				.select(child.quantity)
				.where(child.add_on == self.name)
				.where(registration.status != "Cancelled")
				.for_update()
			).run()
			if cint(self.total__quantity) < sum(cint(row[0]) for row in rows):
				frappe.throw("Add On stock cannot be less than existing usage.")

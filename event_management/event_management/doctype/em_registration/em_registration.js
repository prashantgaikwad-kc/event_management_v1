// Copyright (c) 2026, Prashant and contributors
// For license information, please see license.txt

frappe.ui.form.on("EM Registration", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.status === "Confirmed" && !frm.doc.checked_in) {
			frm.add_custom_button("Check In", () => {
				frappe.call({
					method: "event_management.event_management.doctype.em_registration.em_registration.check_in",
					args: { registration: frm.doc.name },
					callback() {
						frm.reload_doc();
					},
				});
			});
		}
	},

	setup(frm) {
		frm.set_query("ticket_type", () => ({
			filters: { event: frm.doc.event },
		}));
		frm.set_query("add_on", "add_ons", () => ({
			filters: { event: frm.doc.event },
		}));
	},

	event(frm) {
		frm.set_value("ticket_type", null);
		frm.clear_table("add_ons");
		frm.refresh_field("add_ons");
		frm.set_value("total_amount", 0);
	},

	ticket_type(frm) {
		calculate_total(frm);
	},

	quantity(frm) {
		calculate_total(frm);
	},
});

function calculate_total(frm) {
	if (!frm.doc.ticket_type) {
		frm.set_value("total_amount", (frm.doc.add_ons || []).reduce((total, row) => total + flt(row.amount), 0));
		return;
	}

	const ticket_type = frm.doc.ticket_type;
	frappe.db.get_value("EM Ticket Type", ticket_type, "price").then((result) => {
		if (frm.doc.ticket_type === ticket_type) {
			let total = flt(result.message.price) * (frm.doc.quantity || 0);
			for (const row of frm.doc.add_ons || []) {
				total += flt(row.amount);
			}
			frm.set_value("total_amount", total);
		}
	});
}

frappe.ui.form.on("EM Registration Add On", {
	add_on(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.add_on) {
			frappe.model.set_value(cdt, cdn, "price", 0);
			frappe.model.set_value(cdt, cdn, "amount", 0);
			calculate_total(frm);
			return;
		}

		const add_on = row.add_on;
		frappe.db.get_value("EM Add On", add_on, "price").then((result) => {
			if (row.add_on === add_on && frm.doc.add_ons.includes(row)) {
				frappe.model.set_value(cdt, cdn, "price", result.message.price || 0);
				frappe.model.set_value(cdt, cdn, "amount", flt(result.message.price) * (row.quantity || 0));
				calculate_total(frm);
			}
		});
	},

	quantity(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.price) * (row.quantity || 0));
		calculate_total(frm);
	},

	add_ons_remove(frm) {
		calculate_total(frm);
	},
});

let tickets = {};
let add_ons = {};

function calculate_total() {
	let total = flt(tickets[frappe.web_form.get_value("ticket_type")]) *
		flt(frappe.web_form.get_value("quantity"));
	for (const row of frappe.web_form.get_value("add_ons") || []) {
		total += flt(add_ons[row.add_on]) * flt(row.quantity);
	}
	frappe.web_form.set_value("total_amount", total);
}

frappe.web_form.on("event", async function (_field, event) {
	await frappe.web_form.set_value("ticket_type", "");
	await frappe.web_form.set_value("add_ons", []);
	frappe.web_form.fields_dict.ticket_type.set_data([]);
	tickets = {};
	add_ons = {};
	calculate_total();
	if (!event) return;

	const response = await frappe.call({
		method: "event_management.event_management.web_form.event_registration.event_registration.get_event_options",
		args: { event },
	});
	if (frappe.web_form.get_value("event") !== event) return;

	const options = response.message;
	for (const ticket of options.tickets) tickets[ticket.name] = ticket.price;
	for (const add_on of options.add_ons) add_ons[add_on.name] = add_on.price;
	frappe.web_form.fields_dict.ticket_type.set_data(
		options.tickets.map((ticket) => ({ value: ticket.name, label: ticket.ticket_name }))
	);
	frappe.web_form.fields_dict.add_ons.grid.update_docfield_property(
		"add_on",
		"options",
		JSON.stringify(options.add_ons.map((add_on) => ({ value: add_on.name, label: add_on.add_on_name })))
	);
	frappe.web_form.fields_dict.add_ons.grid.refresh();
	calculate_total();
});

frappe.web_form.on("ticket_type", calculate_total);
frappe.web_form.on("quantity", calculate_total);
frappe.web_form.fields_dict.add_ons.grid.wrapper.on("change", "input", () => {
	setTimeout(calculate_total, 0);
});
frappe.web_form.fields_dict.add_ons.grid.wrapper.on("click", () => {
	setTimeout(calculate_total, 0);
});

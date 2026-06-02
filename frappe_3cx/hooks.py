app_name = "frappe_3cx"
app_title = "Frappe 3CX"
app_publisher = "Your Company"
app_description = "One-way 3CX call logging into Frappe/ERPNext, linked to Contacts."
app_email = "you@example.com"
app_license = "MIT"

# Create the integration role on install.
after_install = "frappe_3cx.install.after_install"

# Show logged calls on the Contact form and on linked party records.
override_doctype_dashboards = {
    "Contact": "frappe_3cx.overrides.contact_dashboard.get_dashboard_data",
    "Customer": "frappe_3cx.overrides.party_dashboard.get_dashboard_data",
    "Supplier": "frappe_3cx.overrides.party_dashboard.get_dashboard_data",
    "Lead": "frappe_3cx.overrides.party_dashboard.get_dashboard_data",
}

"""Surface Telephony Call Logs on the Connections tab of party records
(Customer, Supplier, Lead, ...).

Telephony Call Log reaches the party through its top-level Dynamic Link pair
(`party` + `party_type`), so the dashboard is told about it via the
`dynamic_links` mapping: {linked_doctype: [link_fieldname, doctype_fieldname]}.

The same function is reused for every party doctype -- it only needs to
declare the link, not know which party it is.
"""


def get_dashboard_data(data):
    data.setdefault("transactions", [])
    data.setdefault("dynamic_links", {})

    data["dynamic_links"]["Telephony Call Log"] = ["party", "party_type"]

    data["transactions"].append({
        "label": "Telephony",
        "items": ["Telephony Call Log"],
    })
    return data

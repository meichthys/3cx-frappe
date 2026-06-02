"""Add a "Telephony" group to the Contact form's Connections tab so that all
calls linked to a contact are visible directly from that contact.
"""


def get_dashboard_data(data):
    data.setdefault("transactions", [])
    data.setdefault("non_standard_fieldnames", {})

    # Telephony Call Log links to Contact via its `contact` field.
    data["non_standard_fieldnames"]["Telephony Call Log"] = "contact"

    data["transactions"].append({
        "label": "Telephony",
        "items": ["Telephony Call Log"],
    })
    return data

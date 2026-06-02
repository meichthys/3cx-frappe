import frappe

ROLE = "3CX Integration"


def after_install():
    """Create a dedicated, API-only role for the 3CX service account.

    Assign this role (and nothing else) to the user whose API key/secret 3CX
    uses. It grants create/read/write on Telephony Call Log only.
    """
    if not frappe.db.exists("Role", ROLE):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": ROLE,
            "desk_access": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()

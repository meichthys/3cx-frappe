"""Controller for Telephony Call Log.

No custom logic is needed for one-way logging; population happens in
frappe_3cx.api.log_call. Kept as a thin Document subclass so the doctype
behaves like any other and stays easy to extend.
"""

from frappe.model.document import Document


class TelephonyCallLog(Document):
    pass

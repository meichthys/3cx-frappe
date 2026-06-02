"""Public API consumed by the 3CX CRM integration template.

Two endpoints:
  * lookup_contact  -> identifies an inbound caller (3CX "Contact Lookup")
  * log_call        -> records a finished call    (3CX "Call Journaling")

Both are authenticated (no allow_guest). 3CX authenticates with a Frappe
API key/secret sent as `Authorization: token <key>:<secret>`.
"""

import frappe
from frappe.utils import get_datetime, get_url

from frappe_3cx.utils import (
    find_contact,
    maybe_create_contact,
    parse_duration,
)

CALL_LOG = "Telephony Call Log"


@frappe.whitelist()
def lookup_contact(number=None, **kwargs):
    """Return contact details for a caller number, in 3CX-friendly JSON.

    3CX calls this on an inbound call and maps the response fields onto its
    own contact card (name shown on the phone, link back to the CRM, etc.).
    """
    number = number or kwargs.get("Number") or kwargs.get("phone")
    result = {"found": False, "count": 0, "contacts": []}

    if not number:
        return result

    name = find_contact(number)
    if not name:
        return result

    contact = frappe.db.get_value(
        "Contact",
        name,
        ["name", "first_name", "last_name", "company_name",
         "email_id", "phone", "mobile_no"],
        as_dict=True,
    )

    display_name = " ".join(
        p for p in [contact.first_name, contact.last_name] if p
    ) or contact.name

    result["found"] = True
    result["count"] = 1
    result["contacts"].append({
        "id": contact.name,
        "name": display_name,
        "first_name": contact.first_name or "",
        "last_name": contact.last_name or "",
        "company": contact.company_name or "",
        "email": contact.email_id or "",
        "phone": contact.phone or "",
        "mobile": contact.mobile_no or "",
        "crm_url": get_url("/app/contact/{0}".format(contact.name)),
    })
    return result


@frappe.whitelist()
def log_call(
    call_id=None,
    number=None,
    agent=None,
    direction="Incoming",
    call_type=None,
    status=None,
    duration=0,
    start_time=None,
    end_time=None,
    did=None,
    recording_url=None,
    contact_name=None,
    **kwargs
):
    """Create or update a 3CX Call Log and link it to a Contact.

    Idempotent: the document is named after `call_id`, so a repeated post for
    the same call updates the existing record instead of duplicating it.
    Designed never to lose a call -- if no contact matches, the call is still
    logged with an empty contact field.
    """
    # Be liberal about field names so it works whatever the 3CX template sends.
    call_id = call_id or kwargs.get("CallID") or kwargs.get("callid")
    number = number or kwargs.get("Number")
    agent = agent or kwargs.get("Agent")
    call_type = call_type or kwargs.get("CallType")
    contact_name = contact_name or kwargs.get("Name")
    recording_url = recording_url or kwargs.get("RecordingURL") or kwargs.get("Recording")
    direction = _normalize_direction(
        direction or kwargs.get("CallDirection") or "Incoming"
    )

    # Never drop a call: synthesise an id if 3CX did not send one.
    if not call_id:
        call_id = "3cx-{0}".format(frappe.generate_hash(length=12))

    try:
        if frappe.db.exists(CALL_LOG, call_id):
            doc = frappe.get_doc(CALL_LOG, call_id)
        else:
            doc = frappe.new_doc(CALL_LOG)
            doc.call_id = call_id

        doc.caller_number = number
        doc.agent = agent
        doc.direction = direction
        doc.call_type = call_type
        doc.status = status or kwargs.get("Status")
        doc.did = did or kwargs.get("DidNumber") or kwargs.get("DID")
        doc.duration = parse_duration(duration or kwargs.get("Duration"))
        doc.recording_url = recording_url
        doc.contact_name = contact_name
        doc.start_time = _safe_datetime(
            start_time or kwargs.get("CallStartTimeUTC") or kwargs.get("DateTime")
        )
        doc.end_time = _safe_datetime(end_time or kwargs.get("CallEndTimeUTC"))

        contact = find_contact(number)
        if not contact and _auto_create_enabled():
            contact = maybe_create_contact(number, contact_name)
        if contact:
            doc.contact = contact
            _link_primary_party(doc, contact)

        doc.save()
        frappe.db.commit()
        return {"ok": True, "call_log": doc.name, "contact": doc.contact}

    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="3CX: log_call failed", message=frappe.get_traceback())
        return {"ok": False, "error": "logging_failed"}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _link_primary_party(doc, contact):
    """Copy the contact's primary linked party (Customer / Lead / Supplier /
    ...) onto the call log, so the call also surfaces on that party's record.

    A contact's `links` rows are ordered; the earliest is treated as primary.
    """
    link = frappe.db.get_value(
        "Dynamic Link",
        {"parenttype": "Contact", "parent": contact, "parentfield": "links"},
        ["link_doctype", "link_name"],
        as_dict=True,
        order_by="creation asc",
    )
    if link and link.link_doctype and link.link_name:
        doc.party_type = link.link_doctype
        doc.party = link.link_name


def _normalize_direction(value):
    text = (value or "").strip().lower()
    if text in ("outbound", "outgoing", "out"):
        return "Outgoing"
    return "Incoming"


def _safe_datetime(value):
    if not value:
        return None
    try:
        return get_datetime(value)
    except Exception:
        return None


def _auto_create_enabled():
    try:
        return bool(frappe.db.get_single_value("Telephony Settings", "auto_create_contact"))
    except Exception:
        return False

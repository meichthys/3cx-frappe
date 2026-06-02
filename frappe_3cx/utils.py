"""Shared helpers for the 3CX integration.

Kept deliberately small and dependency-free so the behaviour is easy to
reason about and unit-test.
"""

import re

import frappe

# Matches everything that is NOT a digit. Used to normalise phone numbers.
_NON_DIGIT = re.compile(r"\D")

# Default number of trailing digits to compare when matching a caller's
# number to a stored contact. 8 digits is enough to be specific while
# tolerating country-code / formatting differences. Overridable in settings.
DEFAULT_MATCH_DIGITS = 8

# SQL fragment that strips the most common separators from a column so that
# "+1 (555) 123-4567" and "5551234567" compare equal. {col} is substituted in.
_SQL_STRIP = (
    "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
    "{col},' ',''),'-',''),'(',''),')',''),'+',''),'.',''),'/','')"
)


def normalize_number(number):
    """Return only the digits of a phone number, or '' for empty input."""
    if not number:
        return ""
    return _NON_DIGIT.sub("", str(number))


def _match_digits_count():
    try:
        value = frappe.db.get_single_value("Telephony Settings", "number_match_digits")
    except Exception:
        value = None
    return int(value) if value else DEFAULT_MATCH_DIGITS


def find_contact(number):
    """Find the most recently modified Contact whose phone ends with `number`.

    Returns the Contact name (its document id) or None. Reads go through
    frappe.db directly so the calling user does not need read permission on
    Contact -- only on the call log doctype.
    """
    digits = normalize_number(number)
    if not digits:
        return None

    tail = digits[-_match_digits_count():]
    if not tail:
        return None

    pattern = "%" + tail  # suffix match: a stored number must END with `tail`

    # 1) Primary source: the Contact Phone child table (modern Frappe schema).
    rows = frappe.db.sql(
        """
        SELECT parent AS contact
        FROM `tabContact Phone`
        WHERE {stripped} LIKE %(pattern)s
        ORDER BY modified DESC
        LIMIT 1
        """.format(stripped=_SQL_STRIP.format(col="phone")),
        {"pattern": pattern},
        as_dict=True,
    )
    if rows:
        return rows[0].contact

    # 2) Fallback: the cached primary fields on Contact itself.
    rows = frappe.db.sql(
        """
        SELECT name AS contact
        FROM `tabContact`
        WHERE {phone} LIKE %(pattern)s OR {mobile} LIKE %(pattern)s
        ORDER BY modified DESC
        LIMIT 1
        """.format(
            phone=_SQL_STRIP.format(col="phone"),
            mobile=_SQL_STRIP.format(col="mobile_no"),
        ),
        {"pattern": pattern},
        as_dict=True,
    )
    return rows[0].contact if rows else None


def maybe_create_contact(number, contact_name=None):
    """Create a minimal Contact for an unknown caller. Returns its name or None.

    Only called when auto-create is enabled in 3CX Settings.
    """
    try:
        contact = frappe.new_doc("Contact")
        full_name = (contact_name or "").strip()
        if full_name:
            first, _, last = full_name.partition(" ")
            contact.first_name = first
            if last:
                contact.last_name = last
        else:
            contact.first_name = number  # fall back to the number as the name

        contact.append("phone_nos", {"phone": number, "is_primary_phone": 1})
        contact.insert(ignore_permissions=True)
        return contact.name
    except Exception:
        frappe.log_error(title="3CX: auto-create contact failed")
        return None


def parse_duration(value):
    """Return an int number of seconds from either seconds or 'HH:MM:SS'."""
    if value in (None, ""):
        return 0
    text = str(value).strip()
    if ":" in text:
        try:
            parts = [int(p) for p in text.split(":")]
            seconds = 0
            for part in parts:
                seconds = seconds * 60 + part
            return seconds
        except ValueError:
            return 0
    try:
        return int(float(text))
    except ValueError:
        return 0

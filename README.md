# Frappe 3CX

> [!WARNING]
> This application was created with ClaudeCode and is not fully tested. Use at your own risk.

A small, one-way integration that logs **incoming 3CX calls** into Frappe/ERPNext
and links each call to the matching **Contact**.

It uses the supported **3CX CRM Integration** mechanism (the CRM Integration
Wizard), where 3CX calls two REST endpoints that this app exposes:

| 3CX step          | When it fires        | What this app does                                  |
|-------------------|----------------------|-----------------------------------------------------|
| Contact Lookup    | on an inbound call   | finds the Contact by phone number, returns its name + a link back to the CRM |
| Call Journaling   | when the call ends   | creates/updates a **Telephony Call Log**, links it to that Contact, and to the Contact's primary party (Customer/Lead/Supplier) |

There is no polling, no WebSocket, and no persistent connection to babysit. 3CX
owns the timing and retries; this side is just two stateless endpoints plus a
doctype. (The Call Control API is the other option, but it is built for *driving*
calls and needs a live connection — overkill and more fragile for one-way
logging.)

> Note on naming: the doctypes are called **Telephony Call Log** and
> **Telephony Settings** rather than "3CX …" because Frappe turns a doctype name
> into a Python class name, and a class can't start with a digit. The 3CX
> branding lives in the app and module names.

---

## 1. Install

```bash
cd ~/frappe-bench
bench get-app /path/to/frappe_3cx        # or a git URL
bench --site yoursite install-app frappe_3cx
bench --site yoursite migrate
bench --site yoursite clear-cache
```

Tested against Frappe/ERPNext **v15** (should work on v14 unchanged).

## 2. Create the 3CX service account

3CX authenticates to Frappe with an API key/secret of a dedicated user.

1. Create a new **User** (e.g. `3cx@yourcompany.com`), type *System User*.
2. Give it the single role **3CX Integration** (created automatically on install).
   That role grants create/read/write on Telephony Call Log only — least
   privilege. (Contact reads in the lookup endpoint bypass user permissions
   intentionally, so no Contact role is needed.)
3. On that user, open **API Access → Generate Keys** to get an `api_key` and
   `api_secret`.

The auth header 3CX must send is:

```
Authorization: token <api_key>:<api_secret>
```

## 3. Endpoints

Base URL is your site. Frappe wraps return values in `{"message": ...}`.

**Contact lookup** (GET):
```
GET /api/method/frappe_3cx.api.lookup_contact?number=<caller_number>
```
Response:
```json
{"message": {
  "found": true,
  "count": 1,
  "contacts": [{
    "id": "John Doe-Acme",
    "name": "John Doe",
    "first_name": "John", "last_name": "Doe",
    "company": "Acme", "email": "john@acme.com",
    "phone": "+15551234567", "mobile": "",
    "crm_url": "https://yoursite/app/contact/John Doe-Acme"
  }]
}}
```

**Call journaling** (POST, JSON body):
```
POST /api/method/frappe_3cx.api.log_call
```
Accepted fields (all optional except that a `call_id` is strongly recommended
for de-duplication): `call_id`, `number`, `agent`, `direction`, `call_type`,
`status`, `duration`, `start_time`, `end_time`, `did`, `recording_url`,
`contact_name`. `duration` accepts seconds or `HH:MM:SS`. Re-posting the same
`call_id` updates the existing record instead of creating a duplicate.

## 4. Configure 3CX (CRM Integration Wizard)

In the 3CX CRM Integration Wizard (per the 3CX guide):

- **Authentication** — add a request header `Authorization` with value
  `token <api_key>:<api_secret>`.
- **Contact Lookup** — GET to `/api/method/frappe_3cx.api.lookup_contact`,
  with query parameter `number` = the 3CX *Number* variable. Map the JSON
  response: results path `contacts`; then `first_name`, `last_name`,
  `company`, `email` to the matching 3CX contact fields, `id` as the contact
  id, and `crm_url` as the "open contact" link.
- **Call Journaling** — POST to `/api/method/frappe_3cx.api.log_call` with a
  JSON body. In the V20 wizard you pick variables from the journaling
  variable list; map them to these field names:

  | This app field  | V20 variable     |
  |-----------------|------------------|
  | `call_id`       | CallID           |
  | `number`        | Number           |
  | `agent`         | Agent            |
  | `direction`     | CallDirection    |
  | `call_type`     | CallType         |
  | `duration`      | Duration         |
  | `start_time`    | DateTime         |
  | `contact_name`  | Name             |
  | `recording_url` | Recording        |

  `end_time` is optional — V20 doesn't always expose a separate end-time
  variable, and start + duration is enough. If your template does expose one,
  map it to `end_time`. The endpoint also accepts the raw V20 names
  (`CallID`, `CallDirection`, `DateTime`, `Recording`, `DidNumber`, etc.)
  directly, so it still works if a mapping is left at its default.

Leave outbound call journaling disabled — this integration is inbound-only by
design, though it will correctly tag a call `Outgoing` if one is ever sent.

## 5. Test without 3CX

```bash
KEY=...; SECRET=...; SITE=https://yoursite

# Lookup (URL-encode the +)
curl -s "$SITE/api/method/frappe_3cx.api.lookup_contact?number=%2B15551234567" \
  -H "Authorization: token $KEY:$SECRET"

# Log a test call
curl -s -X POST "$SITE/api/method/frappe_3cx.api.log_call" \
  -H "Authorization: token $KEY:$SECRET" \
  -H "Content-Type: application/json" \
  -d '{"call_id":"TEST-001","number":"+15551234567","agent":"101",
       "direction":"Incoming","call_type":"Inbound","duration":"00:01:23",
       "start_time":"2026-06-02 10:00:00","end_time":"2026-06-02 10:01:23"}'
```

Open the matched Contact and check the **Connections** tab for a **Telephony**
group listing the call.

## 6. Settings

**Telephony Settings** (single doctype):

- *Auto-create a Contact for unknown callers* — off by default. When off,
  calls from unknown numbers are still logged, just left unlinked.
- *Digits to match* — trailing digits compared when matching a number to a
  Contact (default 8; tolerates country-code/formatting differences).

## Linking to parties

When a call matches a Contact, the app also copies that Contact's primary
linked party (its first **Customer / Lead / Supplier** link) onto the call via
a standard Dynamic Link (`party_type` + `party`). The call then appears under a
**Telephony** group on that party's Connections tab as well as the Contact's.

One thing to confirm on your bench: the party-side Connections entry is wired
through the dashboard override in `overrides/party_dashboard.py`. The link data
is always written regardless, so even if the Connections group doesn't render
on some Frappe build, the calls remain fully queryable and reportable by
`party`/`party_type` — it's purely a display-tab concern, fixable in that one
file. (Only the *primary* party is linked, since a Contact is almost always
attached to a single party; multi-party linking is a small extension if you
need it.)

## How it stays robust

- Calls are named by `call_id`, so retries update rather than duplicate.
- A call is never dropped: an unknown number is still logged (unlinked, no
  Contact created — per the default), and a missing `call_id` gets a generated
  one.
- The journaling endpoint catches and rolls back on any error, logs to the
  Error Log, and returns `{"ok": false}` rather than 500-ing.
- Number matching strips separators and compares trailing digits, so
  `+1 (555) 123-4567` matches `5551234567`.

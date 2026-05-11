# PHQ Intelligence Bot — API Endpoints

**Base URL:** `https://aibot.matrixupp.com`

All endpoints require a valid Matrix JWT in the `Authorization` header:
```
Authorization: Bearer <matrix_jwt>
```

The bot validates the token against your existing JWT secret, issuer (`socialMedia`),
and audience (`socialMediaUsers`) — no separate login needed.

---

## Endpoints for Matrix Team Integration

### 1. Ask a Question (Main Query)

```
POST /api/v2/chat/query
```

**Request body:**
```json
{
  "query": "Varanasi mein pichle 30 din mein kya incidents hue?",
  "session_id": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | Yes | Question in Hindi or English (2–1000 chars) |
| `session_id` | string | No | Pass previous `session_id` for follow-up questions; omit to start new session |

**Response:**
```json
{
  "session_id": "sess_abc123",
  "answer": "पिछले 30 दिनों में वाराणसी में 3 प्रमुख घटनाएं हुईं...",
  "confidence": 0.82,
  "evidence_count": 7,
  "sources": ["Twitter", "Facebook", "Official Report"],
  "district_detected": "Varanasi",
  "latency_ms": 1240
}
```

**How to use `session_id`:**
- First message: send `session_id: null` → get back a new `session_id`
- Follow-up messages: pass the same `session_id` → bot remembers context

---

### 2. List Officer's Sessions

```
GET /api/v2/chat/sessions
```

Returns all past conversations for the logged-in officer (identified by JWT).

**Response:**
```json
[
  {
    "session_id": "sess_abc123",
    "title": "Varanasi mein pichle 30 din...",
    "created_at": "2026-05-10T09:30:00",
    "updated_at": "2026-05-10T09:35:00"
  }
]
```

---

### 3. Get Full Chat History

```
GET /api/v2/chat/sessions/{session_id}/messages
```

Returns the complete message thread for a session (for "resume conversation" feature).

**Response:**
```json
[
  {"role": "user", "content": "Varanasi mein incidents?", "created_at": "..."},
  {"role": "assistant", "content": "पिछले 30 दिनों में...", "created_at": "..."}
]
```

---

### 4. Health Check

```
GET /health
```

No auth required. Returns server status.

```json
{"status": "ok", "version": "1.0.0"}
```

---

## Widget Integration (Copy-paste into Matrix base template)

```html
<!-- Add before </body> in your base HTML template -->
<script
  src="https://aibot.matrixupp.com/static/widget/chat-widget.js"
  data-api="https://aibot.matrixupp.com"
  data-token-fn="getMatrixToken">
</script>

<script>
  // Tell the widget where to find the JWT.
  // Replace with whatever key Matrix stores the JWT under.
  window.getMatrixToken = () =>
    localStorage.getItem('matrix_jwt') ||
    sessionStorage.getItem('token') ||
    sessionStorage.getItem('jwt') || '';
</script>
```

This adds a floating 🤖 chat button on every Matrix page — no separate page needed.

---

## Dedicated Full-Screen Chat Page

```
https://aibot.matrixupp.com/
```

- Full GPT-style interface with session sidebar
- Session history per officer (based on JWT identity)
- Hindi + English supported
- Direct link can be embedded as an iframe or navigation menu item

---

## CORS

The bot allows requests from `*.matrixupp.com` origins. If Matrix runs on a
different domain, share the domain and we will add it to the allowlist.

---

## Rate Limits

| Limit | Value |
|---|---|
| Requests per officer per minute | 30 |
| Max query length | 1000 characters |
| Session history kept | 30 days |

---

## Error Codes

| HTTP | Meaning |
|---|---|
| 401 | JWT missing, expired, or invalid |
| 403 | Session belongs to a different officer |
| 422 | Query too short or too long |
| 500 | Internal error (check `/health`) |

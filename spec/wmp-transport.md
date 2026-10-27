# WMP Transport Bindings

## Wallet Messaging Protocol — Transport Bindings

**Status:** Draft  
**Version:** 0.1.0  
**Date:** 2026-04-29

## 1. Overview

WMP is transport-agnostic. This document defines three standard transport bindings:

1. **WebSocket** — Persistent bidirectional channels for real-time communication.
2. **HTTPS** — Request/response and streaming for firewall-friendly deployments.
3. **Native Messaging** — Browser extension and OS-level inter-process communication.

All transports carry the same JSON-RPC 2.0 messages. A WMP implementation MUST support at least one binding and SHOULD support WebSocket for real-time use cases.

## 2. Common Requirements

### 2.1 TLS

All network transports MUST use TLS 1.3 or later. Native messaging between local processes MAY omit TLS when operating within a single trust boundary (e.g., browser ↔ extension host).

### 2.2 Framing

Each transport defines how individual JSON-RPC 2.0 messages are framed and delimited. Messages MUST be valid UTF-8 encoded JSON.

### 2.3 Message Size Limits

Implementations MUST support messages up to 64 KiB. Implementations MAY support larger messages and SHOULD advertise their limit during capability negotiation.

### 2.4 Content Type

When a transport uses HTTP headers, the content type MUST be `application/json`.

### 2.5 Connection Lifecycle

Each transport binding defines its own connection lifecycle. The WMP session lifecycle (Section 4 of [wmp-core.md](wmp-core.md)) is independent of transport connections — a session MAY survive transport reconnections.

## 3. WebSocket Binding

### 3.1 Connection Establishment

```
Client                                        Server
  │                                              │
  │─── GET /wmp (Upgrade: websocket) ───────────>│
  │<── 101 Switching Protocols ──────────────────│
  │                                              │
  │─── wmp.session.create (JSON-RPC) ───────────>│
  │<── result (session_id) ──────────────────────│
  │                                              │
```

**Endpoint:** The WebSocket endpoint is discovered via `/.well-known/wmp-configuration` (Section 7.5 of [wmp-core.md](wmp-core.md)). Default path: `/wmp`.

**Subprotocol:** Clients SHOULD request the `wmp.v1` WebSocket subprotocol:

```
Sec-WebSocket-Protocol: wmp.v1
```

### 3.2 Framing

Each WebSocket text frame contains exactly one JSON-RPC 2.0 message (or one JSON array for batch requests). JSON-RPC framing is always the outermost layer — when MLS encryption is active, the encrypted ciphertext is carried *inside* the JSON-RPC envelope (in the message `body` field) with the `wmp` metadata indicating `encrypted: true` and the corresponding `epoch`. The transport layer never sees raw MLS binary data.

| Frame Type | Content |
|-----------|---------|
| Text | JSON-RPC 2.0 message (plaintext or containing MLS-encrypted body) |
| Binary | Reserved for future use |

### 3.3 Ping/Pong

WebSocket ping/pong frames MUST be used for keepalive. Implementations SHOULD send a ping every 30 seconds and close the connection after 90 seconds without a pong.

### 3.4 Authentication

Authentication is performed as the first JSON-RPC 2.0 exchange after the WebSocket connection is established, via `wmp.session.create` with authentication credentials in the params.

Alternatively, authentication MAY be performed at the HTTP level before the upgrade:
- Bearer token in the `Authorization` header of the upgrade request.
- Query parameter `token` in the upgrade URL (NOT RECOMMENDED for production).

### 3.5 Reconnection

Clients SHOULD implement automatic reconnection with exponential backoff:

- Initial delay: 1 second
- Maximum delay: 30 seconds
- Maximum attempts: configurable (default: 10)

On reconnection, the client sends `wmp.session.resume` with the previous `session_id`. The server MAY accept or reject the resumption.

```json
{
  "jsonrpc": "2.0",
  "id": "reconnect-1",
  "method": "wmp.session.resume",
  "params": {
    "wmp": {"version": "0.1"},
    "session_id": "ses-a1b2c3d4",
    "last_received_id": "msg-previous"
  }
}
```

### 3.6 Multiplexing

A single WebSocket connection MAY carry messages for multiple WMP sessions. Messages are routed by the `session_id` field in the `wmp` metadata object.

## 4. HTTPS Binding

### 4.1 Endpoint

Default path: `/wmp`

### 4.2 Request/Response Mode

For simple request-response interactions, standard HTTP POST is used:

```
POST /wmp HTTP/1.1
Host: example.com
Content-Type: application/json
Authorization: Bearer <token>

{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "wmp.session.create",
  "params": {...}
}
```

```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {...}
}
```

### 4.3 Server-Sent Events (SSE) Mode

For server-initiated messages (notifications, flow progress), SSE is used:

```
GET /wmp/events?session_id=ses-a1b2c3d4 HTTP/1.1
Host: example.com
Authorization: Bearer <token>
Accept: text/event-stream
```

```
HTTP/1.1 200 OK
Content-Type: text/event-stream

id: 41
event: wmp
data: {"jsonrpc":"2.0","method":"wmp.flow.progress","params":{...}}

id: 42
event: wmp
data: {"jsonrpc":"2.0","method":"wmp.message.deliver","params":{...}}
```

Client-to-server messages are sent via POST while listening on the SSE stream. The remainder of this section applies to every binding that uses SSE, including the streamable mode of Section 4.4.

Two terms are used below: the **event buffer** is the bounded per-session record of events a server has sent, from which it can replay; the **cursor** is the event ID a client last received.

#### 4.3.1 Session IDs and Access Control

- The session ID is assigned by the server. It is returned in `wmp.session_id` of the `wmp.session.create` result (Section 4.1 of [wmp-core.md](wmp-core.md)). A `wmp.session.create` request MUST NOT carry a session ID, in the `wmp` metadata object or in the `Wmp-Session-Id` header; a server MUST refuse one that does with `-32602` (Invalid params) and MUST NOT create a session under a client-chosen ID. Session IDs MUST carry at least 128 bits of entropy from a cryptographically secure source.
- Every POST and every GET of this binding MUST be authenticated (Section 4.4 of [wmp-core.md](wmp-core.md)), and the server MUST bind the session to the authenticated principal that created it. A request with no valid credentials MUST be answered with HTTP `401`.
- A request that names a session that does not exist and a request that names a session owned by a different principal MUST be indistinguishable to the caller: same HTTP status (`404` for a GET of the event stream), same body, and for a POST the same JSON-RPC error `-31000` (Session not found). A server MUST NOT reveal that a session ID exists to a principal that does not own it.

#### 4.3.2 Event IDs

- Every event the server sends for a session MUST carry an SSE `id` field.
- An event ID is an opaque string of printable ASCII characters (no spaces, no control characters). Event IDs are unique within a session and strictly ordered by emission: the server can tell which of two IDs was emitted first. They are not guaranteed to be contiguous, and a client MUST NOT parse, increment or compare them; it only stores the last one it received and sends it back.
- A replayed event carries the ID it had when it was first sent.
- The SSE `event` field is `wmp` and `data` holds exactly one JSON-RPC message (Section 2.2).
- A client records the ID of each event after processing it. It dedupes by event ID: an event whose ID it has already processed, delivered again by a replay, MUST NOT be processed a second time.

#### 4.3.3 Replay with `Last-Event-ID`

A client that reconnects to the event stream resumes from its cursor by sending it:

- as the `Last-Event-ID` HTTP request header; a server MUST accept this form; and
- as the `last_event_id` query parameter of the GET, for clients that cannot set request headers on the first request of an event stream (for example a browser `EventSource` that is created anew rather than reconnected by the user agent). A server SHOULD accept this form. When a request carries both, the header takes precedence.

When the cursor is present and the server holds every event emitted after it, the server MUST send those events, in order, each exactly once, before any event emitted after the stream was opened, and MUST NOT send the event the cursor names. When the cursor is the newest event, nothing is replayed. When the request carries no cursor, the server sends no replay: the stream starts at the next event emitted. A client that needs the past events of a session it has no cursor for uses `wmp.session.resume` (Section 4.5 of [wmp-core.md](wmp-core.md)).

Replayed events are retained copies. A server that retains outbound notifications MUST NOT retain members that profile documents define as secret in the retained copy; the live notification is delivered only to the connection that is streaming when it is emitted. The replay of a `wmp.flow.complete` of the OpenID4VCI flow is specified in Section 3.1.4.2 of [wmp-openid4x.md](wmp-openid4x.md): the secret members are omitted and listed in `redacted_members`. A client that needs them stays connected from before it starts the flow until the completion arrives.

#### 4.3.4 Event Buffer and Gaps

A server MUST bound the event buffer of every session, by event count and SHOULD also by total size, so that a slow or absent client cannot make it grow without limit. A server SHOULD retain at least the 200 most recent events of a session. The oldest events are evicted first. Eviction is not announced.

A **gap** exists when the server cannot replay every event emitted after the cursor. Eviction of the cursor event itself is not a gap: the cursor names an event the client already has, so what matters is whether its successor is still held. To tell, a server keeps, besides the buffered events, the ID of the newest event it has evicted (the eviction watermark). A cursor is replayable when it is the watermark or any retained event; it presents a gap when it is older than the watermark, or when the server does not recognise it as an ID it issued for this session (never issued, or the session's buffer and watermark were discarded, for example by a restart). A server cannot always tell the unrecognised cases apart from an evicted one and MUST treat them the same way.

When the cursor presents a gap, the server MUST answer the GET with HTTP `410` (Gone) and MUST NOT open the event stream, so that no part of the replay is delivered. The body is OPTIONAL; if present it is `application/json` and is a JSON-RPC error object. A `410` is not a transport failure to be retried with the same cursor.

A client that receives a `410`:

1. MUST stop reconnecting with that cursor and discard it;
2. opens a new event stream with no cursor, so that it has a connection to receive on;
3. then calls `wmp.session.resume` (Section 4.5 of [wmp-core.md](wmp-core.md)) with its `resumption_token`. The notifications the server re-sends as part of that resume (below) are delivered on the stream of step 2. Events emitted between the 410 and the resume are not lost either: they are on that stream.

If the resume fails (`-31000` or `-31001`, Section 4.5.4 of [wmp-core.md](wmp-core.md)), the client creates a new session.

The events lost in the gap are not recovered through the event stream, and the protocol has no in-band resynchronisation message. What a client needs to continue is recovered by the resume:

- the latest `wmp.flow.progress` of every active flow (Section 4.5.3 of [wmp-core.md](wmp-core.md)); and
- the terminal notification (`wmp.flow.complete`, `wmp.flow.error` or the cancellation) of every flow of the session that has ended. A server MUST therefore keep the terminal notification of each flow for the lifetime of the session, outside the event buffer, in its redacted form (Section 3.1.4.2 of [wmp-openid4x.md](wmp-openid4x.md)), and MUST re-send those on resume, after the progress notifications. A client that already processed the terminal notification of a flow ignores the repeat. Without this a client whose terminal notification was evicted would wait for a flow that has ended.

A secret member of a completion that was only ever delivered live is never recovered; the client treats the issuance as Section 3.1.4.2 of [wmp-openid4x.md](wmp-openid4x.md) describes. A client that, after the resume, still holds a flow that it never saw end and that the server did not report as active or terminal MUST treat that flow as lost and fail it locally.

#### 4.3.5 Heartbeat

An idle event stream is indistinguishable, to a client, from a connection that a proxy has dropped silently. The server SHOULD therefore write an SSE comment line (a line that begins with `:`, for example `: keepalive`) followed by a blank line to every open event stream at least every 30 seconds in which no event was sent. A comment carries no `id`, is not a WMP message and MUST NOT change the client's cursor.

A client SHOULD treat 90 seconds without any bytes from the server on an event stream as a dead connection, close it and reconnect with its cursor (the same bounds as the WebSocket ping of Section 3.3). A server MAY send an SSE `retry` field to set the reconnection delay of the user agent.

A server MUST NOT let one slow reader stall delivery to other connections or block the code that emits events: it SHOULD close a stream whose write does not complete within a bounded time. The client then reconnects with its cursor, which is exactly the recovery of Section 4.3.3 and, if the buffer has moved on, of Section 4.3.4.

### 4.4 Streamable HTTP Mode

Following MCP's streamable HTTP pattern, a single endpoint can handle both directions:

- **POST /wmp** — Client sends JSON-RPC requests. Server responds with JSON-RPC responses. The response MAY be streamed as SSE if the request includes `Accept: text/event-stream`.
- **GET /wmp** — Opens an SSE stream for server-initiated notifications. Sections 4.3.1 to 4.3.5 apply to this stream as they do to the stream of Section 4.3; the session is named by the `Wmp-Session-Id` header or the `session_id` query parameter.

### 4.5 Session Correlation

HTTP requests MUST include the session ID:
- In the `wmp` metadata object within the JSON-RPC message, OR
- In the `Wmp-Session-Id` HTTP header, OR
- In the `session_id` query parameter of a GET (Section 4.3).

Every request except `wmp.session.create` carries one of these; the ID is the one the server assigned (Section 4.3.1). When a request carries the ID in more than one place the values MUST be equal, otherwise the server MUST refuse it with `-32602` (Invalid params).

In this binding the `last_received_id` of `wmp.session.resume` ([wmp-core.md](wmp-core.md) Section 4.5.1) is the last **event ID** the client received on the event stream (Section 4.3.2), not a message `id`. A client that has no event ID omits it. A server that cannot find the event ID MUST still resume the session (resume is the recovery for a gap, Section 4.3.4) and report what it knows in `missed_messages`.

### 4.6 Polling Fallback

For environments where SSE is not available, clients MAY poll:

```json
{
  "jsonrpc": "2.0",
  "id": "poll-001",
  "method": "wmp.message.poll",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "since": "msg-last-received",
    "limit": 50
  }
}
```

## 5. Native Messaging Binding

### 5.1 Overview

The native messaging binding supports communication between:
- Browser extensions and native host applications
- Local processes on the same machine (e.g., wallet CLI ↔ wallet agent)

### 5.2 Browser Extension Native Messaging

Uses the browser's native messaging API (Chrome/Firefox `runtime.connectNative()`).

**Framing:** Length-prefixed JSON. Each message is preceded by a 4-byte (32-bit) native-endian integer indicating the message length in bytes, followed by the UTF-8 encoded JSON-RPC 2.0 message.

```
[4 bytes: length][N bytes: JSON-RPC 2.0 message]
```

### 5.3 Stdio Transport

For CLI tools and local agents, WMP supports stdio transport (compatible with MCP stdio):

**Framing:** Newline-delimited JSON (NDJSON). Each line contains exactly one JSON-RPC 2.0 message.

```
{"jsonrpc":"2.0","id":"1","method":"wmp.session.create","params":{...}}\n
{"jsonrpc":"2.0","id":"1","result":{...}}\n
```

### 5.4 Unix Domain Sockets

For local inter-process communication with higher throughput:

**Socket path:** `$XDG_RUNTIME_DIR/wmp/<application>.sock` (Linux), `~/Library/Application Support/wmp/<application>.sock` (macOS).

**Framing:** Same as WebSocket text framing — each message is a complete JSON-RPC 2.0 message terminated by a newline.

### 5.5 Security Considerations for Native Messaging

- Native messaging MUST verify the identity of the connecting process (e.g., browser extension ID, process UID).
- Unix domain sockets MUST use filesystem permissions to restrict access.
- Stdio transport inherits the security context of the parent process.

## 6. Connection Topologies

WMP supports three connection topologies. The topology determines who initiates the transport connection and how messages are routed.

### 6.1 Direct Topology

Both parties are network-reachable. The initiator opens a transport connection directly to the responder's endpoint (discovered via `/.well-known/wmp-configuration`).

```
   Initiator                 Responder
      │                         │
      └────────────────────────>│
   (connects outbound      (listens on advertised
    to responder's          WMP endpoint)
    endpoint)
```

**When to use:** Server-to-server, wallet-to-backend (e.g., OID4VCI flows where the wallet connects to the issuer), or any scenario where the responder has a publicly-reachable endpoint.

**Connection direction:** Initiator → Responder.

### 6.2 Relay Topology

One or both parties cannot accept inbound connections (mobile apps, browser extensions, NATed devices). Both parties connect **outbound** to a shared relay.

```
   Initiator             Relay             Responder
      │                   │                   │
      └──────────────────>│<──────────────────┘
   (outbound WS)        (relays)         (outbound WS)
```

**When to use:** Wallet-to-wallet communication, mobile-to-mobile, any scenario where at least one party cannot be directly reached.

**Connection direction:** Both parties → Relay (outbound). Neither party needs to accept inbound connections.

**How it works:**

1. Both parties discover their relay endpoint (via `relay` field in `/.well-known/wmp-configuration` or profile-specific resolver).
2. Both parties maintain a persistent outbound connection (WebSocket or SSE) to their relay.
3. The initiator sends `wmp.session.create` addressed to the responder's identifier.
4. The relay resolves the responder's relay endpoint (which may be the same relay or a different one) and routes the session creation.
5. If the responder's relay is different, inter-relay routing occurs (relay-to-relay connection).

**Relay pairing:** A participant's relay is determined by their `/.well-known/wmp-configuration`:

```json
{
  "endpoints": {
    "websocket": "wss://relay.example.com/wmp"
  },
  "relay": "wss://relay.example.com/wmp"
}
```

When the `relay` field equals an endpoint in `endpoints`, the participant is indicating they receive messages through that relay (they connect outbound and listen for inbound session requests).

**Multi-relay routing:**

```
Alice's Wallet ──> Alice's Relay ──> Bob's Relay <── Bob's Wallet
                   (relay-to-relay federation)
```

Inter-relay routing uses standard WMP transport (one relay connects to the other's endpoint). The relay chain (§5.7 of wmp-core.md) records the path.

### 6.3 Hybrid Topology

The initiator connects directly to the responder's endpoint, but the responder delivers messages to third parties via relay:

```
   Wallet            Backend            Relay         Other Wallet
     │                  │                 │                │
     └─────────────────>│                 │                │
                        └────────────────>│<───────────────┘
   (direct to      (processes and    (relays to
    backend)        forwards)         third party)
```

**When to use:** Wallet-to-backend-to-wallet flows (e.g., an issuer backend orchestrating credential issuance, then routing a message to another wallet).

### 6.4 Topology Discovery

A participant's well-known configuration implicitly declares the topology:

| Configuration | Implied topology |
|---------------|------------------|
| `endpoints` has a publicly-reachable URL, no `relay` field | Direct — this entity accepts inbound connections |
| `endpoints` and `relay` both present, pointing to same host | Relay — this entity connects outbound to its relay |
| `endpoints` has a publicly-reachable URL AND `relay` present | Hybrid — accepts direct connections AND uses relay for outbound to others |

Implementations MUST support at least one of: (a) accepting inbound connections (server mode), or (b) connecting outbound to a relay (client mode). Consumer wallets typically implement only client mode.

### 6.5 Relay Registration

A participant registers with their relay by connecting and sending `wmp.relay.register`:

```json
{
  "jsonrpc": "2.0",
  "id": "reg-001",
  "method": "wmp.relay.register",
  "params": {
    "wmp": {"version": "0.1", "sender": "did:key:z6MkfAlice..."},
    "auth": {
      "type": "signed_challenge",
      "challenge": "<relay-provided challenge>",
      "signature": "eyJ..."
    }
  }
}
```

After successful registration, the relay routes incoming messages for that identifier to this connection. If the connection drops, the relay queues messages until the participant reconnects and resumes (§4.5 of wmp-core.md).

## 7. Transport Negotiation

### 7.1 Capability Advertisement

The well-known configuration (Section 7.5 of [wmp-core.md](wmp-core.md)) advertises supported transports:

```json
{
  "endpoints": {
    "websocket": "wss://example.com/wmp",
    "https": "https://example.com/wmp",
    "sse": "https://example.com/wmp/events"
  },
  "transports": ["websocket", "https", "native"],
  "preferred_transport": "websocket"
}
```

### 7.2 Upgrade

A session started on one transport MAY be migrated to another by initiating a new transport connection and using `wmp.session.resume`.

## 8. Comparison of Transport Bindings

| Feature | WebSocket | HTTPS | Native Messaging |
|---------|-----------|-------|-----------------|
| Bidirectional | Yes | Via SSE + POST | Yes |
| Real-time | Yes | SSE: Yes, Poll: No | Yes |
| Firewall-friendly | Usually | Yes | N/A (local) |
| Connection overhead | Low (persistent) | Higher (per-request) | Low |
| Browser support | Yes | Yes | Extension only |
| MLS support | Full | Full | Full |
| Offline delivery | No | Via polling | No |
| Multiplexing | Yes | Via headers | Per-connection |

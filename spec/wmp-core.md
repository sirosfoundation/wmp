# WMP Core Specification

## Wallet Messaging Protocol — Core

**Status:** Draft  
**Version:** 0.1.0  
**Date:** 2026-04-29

## 1. Introduction

The Wallet Messaging Protocol (WMP) is a multi-party messaging protocol built on JSON-RPC 2.0 with end-to-end encryption provided by the Messaging Layer Security (MLS) protocol (RFC 9420). WMP is designed to be transport-agnostic, running over WebSockets, HTTPS, and native messaging infrastructure.

### 1.1 Design Goals

1. **Simplicity** — Use JSON-RPC 2.0 as the sole RPC envelope, avoiding the complexity of SOAP/XML (AS4) or layered envelopes (DIDComm 2.1).
2. **MCP Compatibility** — Share the JSON-RPC 2.0 envelope format and capability negotiation pattern with the Model Context Protocol, enabling interoperability where applicable.
3. **Multi-party Security** — Leverage MLS for scalable group key management, forward secrecy, and post-compromise security.
4. **Transport Flexibility** — Define clean transport bindings rather than coupling to a single transport.
5. **Wallet-native** — First-class support for credential exchange, presentation, and wallet-to-wallet messaging flows.

### 1.2 Relationship to Other Protocols

| Protocol | Relationship |
|----------|-------------|
| JSON-RPC 2.0 | Wire format — all WMP messages are valid JSON-RPC 2.0 messages |
| MLS (RFC 9420) | End-to-end encryption and group key management |
| MCP | Compatible envelope; WMP extends with messaging semantics |
| DIDComm 2.1 | Similar goals; WMP uses JSON-RPC instead of DIDComm envelopes |
| AS4 | Similar goals; WMP avoids SOAP/XML complexity |
| OID4VCI/OID4VP | Supported via the OpenID4x profile ([wmp-openid4x.md](wmp-openid4x.md)) |
| WebAuthn | Authentication binding for verifiable presentations ([wmp-webauthn-binding.md](wmp-webauthn-binding.md)) |

### 1.3 Terminology

- **Participant** — An entity in a WMP session (wallet, agent, service).
- **Session** — A logical messaging context, optionally backed by an MLS group.
- **Channel** — A transport-level connection between two endpoints.
- **Envelope** — A JSON-RPC 2.0 message with WMP-specific extensions.

## 2. Protocol Architecture

```
┌─────────────────────────────────────────────────┐
│                  Application                     │
│  (wallet flows, credential exchange, messaging)  │
├─────────────────────────────────────────────────┤
│              WMP Session Layer                   │
│  (session management, routing, capabilities)     │
├─────────────────────────────────────────────────┤
│              WMP Message Layer                   │
│  (JSON-RPC 2.0 envelope, method dispatch)        │
├─────────────────────────────────────────────────┤
│              MLS Encryption Layer                │
│  (group keys, E2E encryption, key schedule)      │
├─────────────────────────────────────────────────┤
│              Transport Binding                   │
│  (WebSocket | HTTPS | Native Messaging)          │
└─────────────────────────────────────────────────┘
```

### 2.1 Layering

WMP defines four layers:

1. **Transport Binding** — Handles framing and delivery of octets between endpoints. See [wmp-transport.md](wmp-transport.md).
2. **MLS Encryption Layer** — Optional. When enabled, provides E2E encryption for multi-party sessions. See [wmp-mls.md](wmp-mls.md).
3. **WMP Message Layer** — JSON-RPC 2.0 message processing, method routing, error handling.
4. **WMP Session Layer** — Session lifecycle, participant management, capability negotiation.

For point-to-point sessions without E2E encryption requirements, the MLS layer MAY be omitted and transport-level security (TLS) used instead.

### 2.2 Version Negotiation

WMP uses semantic versioning for the protocol version string (`MAJOR.MINOR`). Versions with the same MAJOR number are backward-compatible (new MINOR versions add features but do not break existing behavior).

#### 2.2.1 Version Advertisement

The well-known configuration (§7.5.1) MUST include a `supported_versions` field:

```json
{
  "supported_versions": ["0.1", "0.2"],
  "endpoints": {...}
}
```

This allows clients to determine the server's capabilities before initiating a session.

#### 2.2.2 Version Selection

Version is negotiated during session creation:

1. The initiator sends `wmp.session.create` with `wmp.version` set to the **highest version it supports**.
2. The responder selects the highest version it supports that is ≤ the initiator's version.
3. The responder returns the selected version in the result's `wmp.version` field.
4. All subsequent messages in the session use the negotiated version.

**Example:** Initiator supports 0.2, responder supports 0.1 and 0.2:

```json
// Request
{"wmp": {"version": "0.2", "sender": "..."}, ...}

// Response — responder selects 0.2
{"wmp": {"version": "0.2", "session_id": "ses-..."}, ...}
```

**Example:** Initiator supports 0.2, responder only supports 0.1:

```json
// Request
{"wmp": {"version": "0.2", "sender": "..."}, ...}

// Response — responder selects 0.1 (highest it supports)
{"wmp": {"version": "0.1", "session_id": "ses-..."}, ...}
```

**Version strings and comparison.** A version is `MAJOR.MINOR`: two non-negative decimal integers separated by one dot, with no sign, no leading zeros (other than `0` itself) and no further components. `0.10` is a later version than `0.9`; versions are compared as the pair of integers (MAJOR first), never as strings. A `wmp.version` that is absent, empty or not of this form MUST be rejected with `-32602` (Invalid params).

**Selection rule.** The responder selects the highest version it supports that has the **same MAJOR** as the initiator's version and a MINOR **not greater** than the initiator's. A responder never selects a version higher than the initiator offered, and never selects a version of a different MAJOR. If there is none the responder MUST reject the session with `-31013`; this includes a responder whose lowest version of the initiator's MAJOR is higher than the initiator's (it supports `0.2` and later only, the initiator offers `0.1`).

| Initiator offers | Responder supports | Result |
|------------------|--------------------|--------|
| `0.2` | `0.1`, `0.2` | `0.2` |
| `0.2` | `0.1` | `0.1` |
| `0.10` | `0.9` | `0.9` |
| `0.2` | `0.1`, `0.3` | `0.1` |
| `0.1` | `0.2` | `-31013` |
| `1.0` | `0.1`, `0.2` | `-31013` |

The `-31013` error `data` SHOULD be `{"supported_versions": [...]}`, an array of every version string the responder supports.

**Initiator.** The initiator MUST accept a result whose `wmp.version` is a version it supports, has the MAJOR it offered and is not greater than the version it offered. It MUST treat any other result as a failed negotiation (as if the responder had answered `-31013`), MUST NOT send further messages in the session and SHOULD close it.

If the responder does not support any version compatible with the initiator (different MAJOR version, or none low enough as above), it MUST reject the session with a new error:

| Code | Message | Description |
|------|---------|-------------|
| -31013 | Version not supported | No compatible protocol version. `data` SHOULD include `supported_versions` array. |

#### 2.2.3 Version Invariants

- All messages within a session MUST use the negotiated version string.
- A participant MUST NOT send features defined in a higher version than negotiated.
- Implementations MUST ignore unknown fields in the `wmp` metadata object (forward compatibility).
- The same rule applies to every other object in the protocol; see Section 9.5 (Extension Members).
- The `wmp.version` field is REQUIRED in all messages to enable stateless routing by intermediaries.

## 3. Message Format

### 3.1 Base Envelope

All WMP messages are valid JSON-RPC 2.0 messages. WMP uses the `params` object to carry protocol metadata alongside method-specific parameters.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "msg-550e8400-e29b-41d4-a716-446655440000",
  "method": "wmp.session.create",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "timestamp": "2026-04-29T10:15:30Z"
    },
    ...method-specific parameters
  }
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "msg-550e8400-e29b-41d4-a716-446655440000",
  "result": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "timestamp": "2026-04-29T10:15:31Z"
    },
    ...method-specific result
  }
}
```

**Notification (no response expected):**

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "timestamp": "2026-04-29T10:15:32Z"
    },
    ...notification parameters
  }
}
```

### 3.2 WMP Metadata Object

The `wmp` object within `params` or `result` carries protocol metadata:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | REQUIRED | Protocol version (e.g., `"0.1"`) |
| `session_id` | string | OPTIONAL | Session identifier. Omitted for session creation requests. |
| `sender` | string | OPTIONAL | Sender identifier (DID, URI, or opaque ID). |
| `sender_delegate` | object | OPTIONAL | Delegate acting on behalf of the sender (see Section 3.3). |
| `timestamp` | string | OPTIONAL | ISO 8601 timestamp. |
| `timestamp_token` | string | OPTIONAL | Base64url-encoded RFC 3161 timestamp token from a trusted TSA. |
| `encrypted` | boolean | OPTIONAL | `true` if the payload is MLS-encrypted. Default: `false`. |
| `epoch` | integer | OPTIONAL | MLS epoch number when `encrypted` is `true`. |
| `signature` | string | OPTIONAL | Detached JWS for non-repudiation (see Section 5.4). |
| `expires_at` | string | OPTIONAL | ISO 8601 timestamp. If set, the message MUST NOT be delivered after this time. Servers MUST discard queued messages past this time (see §5.3.1). |
| `deliver_after` | string | OPTIONAL | ISO 8601 timestamp. The message MUST NOT be delivered before this time (scheduled delivery). |
| `identity_assertions` | array | OPTIONAL | Legal identity bindings (see Section 5.6). |
| `relay_chain` | array | OPTIONAL | Relay provenance chain (see Section 5.7). |
| `trace_id` | string | OPTIONAL | Distributed tracing identifier. |

### 3.3 Delegation

WMP supports delegation — the ability for one entity to act on behalf of another. When a message is sent by a delegate, the `sender_delegate` field in the `wmp` metadata identifies the delegate while `sender` identifies the principal on whose behalf the delegate acts.

**`sender_delegate` object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | REQUIRED | Delegate identifier (WMP identifier scheme) |
| `identity_assertions` | array | OPTIONAL | Verifiable assertions proving the delegate's legal identity (same format as §5.6) |
| `authorization` | object | OPTIONAL | Proof of authorization to act on behalf of the principal |

**`authorization` object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | REQUIRED | Authorization type: `verifiable_presentation`, `mandate`, `power_of_attorney` |
| `credential` | string | OPTIONAL | Authorization credential (VP token or reference) |
| `scope` | string[] | OPTIONAL | Authorized actions (e.g., `["submit", "retrieve"]`) |
| `valid_until` | string | OPTIONAL | ISO 8601 expiry of the delegation |

**Example — delegate sending on behalf of an organization:**

```json
{
  "wmp": {
    "version": "0.1",
    "session_id": "ses-a1b2c3d4",
    "sender": "ebcore:iso6523:0007:5567164818",
    "sender_delegate": {
      "id": "x509:san:dns:agent.example.com",
      "authorization": {
        "type": "verifiable_presentation",
        "credential": "eyJ...",
        "scope": ["submit", "retrieve"]
      }
    }
  }
}
```

When evidence is generated for a message sent by a delegate, the evidence MUST include both the principal's identity (`original_sender`) and the delegate's identity (`original_sender_delegate`) as defined in [wmp-evidence.md](wmp-evidence.md) Section 4.2.

> **Note on recipient delegation:** A recipient's delegate is tracked by the relay at delivery time. When the R-ERDS delivers to a delegate, the evidence MUST record the delegate's identity in `original_recipient_delegate`. The relay determines recipient delegation from the recipient's session authentication and any registered delegate authorizations.

### 3.4 Message-Level Delivery Metadata

The following fields MAY be included in `params` alongside `wmp`, `to`, `content_type`, and `body` for `wmp.message.deliver` calls. These carry per-message delivery metadata corresponding to ERDS relay metadata (ETSI EN 319 522-2 §6).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reply_to` | string | OPTIONAL | Identifier to which replies should be directed (overrides `sender`). |
| `in_reply_to` | string | OPTIONAL | JSON-RPC `id` of a previous message this message replies to (threading). |
| `message_type` | string | OPTIONAL | Semantic message type URI or short code (e.g., `"invoice"`, `"order"`, `"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"`). |
| `consignment_mode` | string | OPTIONAL | Requested mode of consignment for the recipient. See Section 3.5. |
| `recipient_assurance_level` | string | OPTIONAL | Minimum identity assurance level required for the recipient before delivery. See Section 3.5.1. |
| `applicable_policies` | string[] | OPTIONAL | Policy URIs or OIDs that subsequent relays and the R-ERDS MUST support. A relay that cannot enforce a listed policy MUST reject the message with `-31005`. |

### 3.5 Consignment Modes

The `consignment_mode` field specifies how the recipient's relay (R-ERDS) should deliver the user content to the recipient. This governs which evidence events are produced.

| Mode | Description | Evidence flow |
|------|-------------|---------------|
| `basic` | Content is delivered directly without prior acceptance. | `delivery_confirmed` or `delivery_failed` |
| `consented` | Recipient is notified and must explicitly accept or reject before content is accessible. | `notification_sent` → `acceptance_confirmed` / `acceptance_rejected` / `acceptance_expired` |
| `consented_signed` | As `consented`, but the recipient must additionally produce a signed acknowledgment. | `notification_sent` → `acceptance_confirmed` (with signed receipt) / `acceptance_rejected` / `acceptance_expired` |

When `consignment_mode` is absent, the R-ERDS applies its default policy (typically `basic`).

A relay MUST NOT forward a message to an R-ERDS whose capabilities (§7.5.1 CSI metadata) do not include support for the requested `consignment_mode`. In this case, the relay MUST reject the message with error `-31005` (Capability not supported) and `data` indicating `{"unsupported": "consignment_mode"}`.

#### 3.5.1 Recipient Assurance Level

The `recipient_assurance_level` field allows the sender to require that the recipient's identity be verified to a minimum level before delivery. Values are drawn from the eIDAS assurance level vocabulary or a binding-specific enumeration:

| Value | Description |
|-------|-------------|
| `low` | Reduced degree of confidence in the claimed identity |
| `substantial` | Substantial degree of confidence |
| `high` | High degree of confidence (e.g., eIDAS high, in-person identity proofing) |

The R-ERDS MUST NOT deliver the message if it cannot authenticate the recipient at or above the requested level. In this case, a `delivery_failed` evidence with reason `insufficient_assurance` is generated.

Relays SHOULD check the next ERDS's capability metadata (via CSI, §7.5.1) for supported assurance levels before forwarding. If the downstream ERDS cannot support the requested level, the relay MUST reject with `-31005`.

### 3.6 Method Naming Convention

WMP methods use a dot-separated namespace:

```
wmp.<domain>.<action>
```

Domains:
- `wmp.session.*` — Session lifecycle
- `wmp.message.*` — Message delivery
- `wmp.capability.*` — Capability negotiation
- `wmp.flow.*` — Structured flows (credential exchange, etc.)
- `wmp.resolve.*` — Metadata resolution (see Section 5.8)
- `wmp.mls.*` — MLS group management
- `wmp.evidence.*` — Delivery evidence (see [wmp-evidence.md](wmp-evidence.md))

Application-specific methods use their own namespace prefix (e.g., `wallet.*`, `oid4vci.*`).

### 3.7 Batch Messages

JSON-RPC 2.0 batch requests are supported. Multiple WMP method calls MAY be sent as a JSON array:

```json
[
  {"jsonrpc": "2.0", "id": "1", "method": "wmp.message.deliver", "params": {...}},
  {"jsonrpc": "2.0", "id": "2", "method": "wmp.message.deliver", "params": {...}}
]
```

### 3.8 Error Codes

WMP extends the standard JSON-RPC 2.0 error code space:

| Code | Message | Description |
|------|---------|-------------|
| -32700 | Parse error | Invalid JSON |
| -32600 | Invalid Request | Not a valid JSON-RPC 2.0 request |
| -32601 | Method not found | Method does not exist |
| -32602 | Invalid params | Invalid method parameters |
| -32603 | Internal error | Internal server error |
| -31000 | Session not found | Referenced session does not exist |
| -31001 | Session expired | Session has expired |
| -31002 | Not authorized | Sender not authorized for this operation |
| -31003 | Encryption required | Operation requires MLS encryption |
| -31004 | MLS error | MLS protocol error (details in `data`) |
| -31005 | Capability not supported | Requested capability not available |
| -31006 | Flow error | Structured flow error (details in `data`; `retryable` flag indicates whether the action can be resent — see §6.2.1) |
| -31007 | Rate limited | Too many requests |
| -31008 | Participant not found | Referenced participant not in session |
| -31009 | Evidence required | Operation requires evidence generation (evidence profile) |
| -31010 | Signature invalid | Non-repudiation signature verification failed |
| -31011 | Timestamp invalid | Trusted timestamp verification failed or self-asserted timestamp outside clock skew tolerance (see §8.5). `data` SHOULD include `acceptable_window_seconds`. |
| -31012 | Identity assertion invalid | Identity assertion verification failed (diagnostic `data` in response — see §5.6.2) |
| -31013 | Version not supported | No compatible protocol version (§2.2) |
| -31014 | Queue full | Offline message queue for recipient is full; sender SHOULD retry later |
| -31015 | Delegation invalid | Delegate authorization invalid, expired, or not permitted by ERDS policy |
| -31016 | Consignment mode unsupported | Requested consignment mode not supported by the recipient's ERDS |
| -31017 | Assurance level unsupported | Requested recipient assurance level cannot be met |
| -31018 | Policy unsupported | One or more applicable policies cannot be enforced |
| -31019 | Plaintext hash mismatch | Decrypted plaintext does not match the sender's `plaintext_hash` commitment (§5.2.1) |

#### 3.8.1 `-31005` Capability not supported

`-31005` is the one error for "the other side asked for something this session does not offer". Its `data`, when present, is an object whose `unsupported` member is a string naming what is unsupported: a capability name (`transaction_data`), a protocol feature (`consignment_mode`), or a flow type (the `flow_type` value as sent). Receivers key on `unsupported` and MUST ignore other `data` members they do not understand; a sender MAY add members that help the receiver recover (Section 9.5).

`-31005` applies, as the error response to the request, in each of these cases:

1. A request needs a capability that was not negotiated for the session (Section 10.3).
2. A `wmp.flow.start` names a `flow_type` that the receiver does not implement or whose capability (Section 6.5, item 2) was not negotiated. An unknown flow type is an unsupported capability: the receiver MUST NOT answer `-32602` (Invalid params) or `-31006` (Flow error), and the `data` is `{"unsupported": "<flow_type>"}`. A known flow type with invalid `params` is still `-32602`.
3. A relay cannot meet a requirement of the message it was asked to forward (Sections 3.4, 3.5, 7.5.1.1).

A flow that has already started and then cannot continue for lack of a capability ends with `wmp.flow.error` carrying `code` `-31005` and the same `data` (for example the OID4VP `transaction_data` case of [wmp-openid4x.md](wmp-openid4x.md) Section 2.3). Such a profile MAY define additional `data` members for that failure; they are extension members (Section 9.5) next to `unsupported`, not a replacement for it. In particular, an OID4VP flow that ends with `-31005` for `transaction_data` and whose verifier response mode produced a redirect carries `data` `{"unsupported": "transaction_data", "redirect_uri": "<url>"}`, so that a wallet that only looks at `unsupported` and a wallet that follows the redirect are both served.

```json
{
  "jsonrpc": "2.0",
  "id": "flow-err-002",
  "error": {
    "code": -31005,
    "message": "Capability not supported",
    "data": {"unsupported": "no-such-flow"}
  }
}
```

#### 3.8.2 `-31019` Plaintext hash mismatch

`-31019` is raised by a recipient that decrypted a message carrying `plaintext_hash` and found that the hash of the decrypted plaintext content object does not equal `plaintext_hash.value` (Section 5.2.1). When the `wmp.message.deliver` carried an `id`, it is the error response to that request; a deliver sent as a notification has no response, and the recipient only withholds the acknowledgment. In both cases the message MUST NOT be acknowledged. It is used for that mismatch only: `plaintext_hash` on a message that is not encrypted, or naming a hash algorithm the recipient does not support, is `-32602`. `data` is OPTIONAL; if present it MUST NOT contain the recomputed hash or any part of the plaintext, since the error may be seen by parties that cannot decrypt the message.

## 4. Session Lifecycle

### 4.1 Session Creation

A session is initiated by one participant and joined by others.

```
Initiator                         Responder
    │                                 │
    │──── wmp.session.create ────────>│
    │                                 │
    │<─── result (session_id, caps) ──│
    │                                 │
    │──── wmp.session.join (opt.) ───>│  (additional participants)
    │                                 │
```

**`wmp.session.create` params:**

```json
{
  "wmp": {"version": "0.1", "sender": "x509:san:dns:wallet.example.com"},
  "participants": ["x509:san:dns:issuer.example.eu"],
  "capabilities_offered": {
    "messaging": {"max_size": 65536},
    "flows": {"max_concurrent": 5},
    "mcp": {"tools": true, "resources": false}
  },
  "security": {
    "mode": "mls",
    "cipher_suites": [1, 2]
  },
  "ttl": 3600
}
```

**Result:**

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
  "capabilities": {
    "messaging": {"max_size": 65536},
    "flows": {"max_concurrent": 5}
  },
  "security": {
    "mode": "mls",
    "cipher_suite": 1,
    "mls_group_info": "<base64url-encoded MLS GroupInfo>"
  },
  "challenge": "ch-9f8e7d6c"
}
```

### 4.2 Capability Negotiation

Modeled after MCP's `initialize` handshake. The initiator offers capabilities; the responder selects the intersection it supports. Only capabilities present in both the offer and the response are active for the session.

#### 4.2.1 Negotiation Rules

1. The initiator sends `capabilities_offered` — a map of capability names to capability-specific parameters.
2. The responder returns `capabilities` — the subset it accepts, potentially with narrowed parameters.
3. A capability omitted from the response is not available in the session.
4. Either party MAY query the negotiated capabilities at any time via `wmp.capability.list`.
5. Capabilities MAY be renegotiated mid-session via `wmp.capability.update` (see Section 4.2.4).

#### 4.2.2 Standard Capabilities

| Capability | Description | Parameters |
|-----------|-------------|------------|
| `messaging` | Free-form message delivery | `max_size`: max message body bytes |
| `flows` | Structured flow orchestration | `max_concurrent`: max parallel flows |
| `sign` | Client-side signing operations | `proof_types`: supported proof types |
| `mcp` | MCP-compatible tool/resource access | `tools`: bool, `resources`: bool, `prompts`: bool |
| `relay` | Message relay to third parties | `destinations`: allowed destination patterns |
| `offline` | Offline message queuing and delivery status | `max_queued`: max queued messages, `ttl`: default queue retention (seconds), `status_notifications`: boolean (server sends `wmp.message.status` notifications to sender) |
| `resolve` | Metadata resolution (see Section 5.8) | `supported_types`: resolution types available |

Additional capabilities are defined by profiles. For example, the OpenID4x profile ([wmp-openid4x.md](wmp-openid4x.md)) defines `oid4vci` and `oid4vp` capabilities.

#### 4.2.3 Security Mode Negotiation

The `security` object in session creation determines the encryption model:

| Mode | Description | When to use |
|------|-------------|-------------|
| `tls` | Transport-level security only | Backend processes plaintext (e.g., flow orchestration, tool invocation) |
| `mls` | E2E encryption via MLS group | Backend relays messages, multi-party, wallet-to-wallet |
| `mls-optional` | MLS available but not required per-message | Mixed sessions where some messages need E2E and others don't |

**`tls` mode** — No MLS overhead. The transport (TLS/WSS) provides confidentiality. Suitable when the responder is the message processor.

```json
{
  "security": {
    "mode": "tls",
    "min_tls_version": "1.3"
  }
}
```

**`mls` mode** — All application messages are MLS-encrypted. The responder may act as a relay without accessing plaintext.

```json
{
  "security": {
    "mode": "mls",
    "cipher_suites": [1, 2]
  }
}
```

**`mls-optional` mode** — MLS is established but per-message encryption is at the sender's discretion. The `wmp.encrypted` metadata field indicates whether a given message is MLS-encrypted. This supports hybrid sessions where the backend processes some messages (e.g., flow orchestration) but relays others end-to-end (e.g., wallet-to-wallet messages through the same connection).

```json
{
  "security": {
    "mode": "mls-optional",
    "cipher_suites": [1],
    "encrypted_capabilities": ["messaging", "relay"]
  }
}
```

The `encrypted_capabilities` array lists which capabilities MUST use MLS encryption. Messages for unlisted capabilities use TLS only.

#### 4.2.4 Capability Update

Capabilities can be renegotiated mid-session (e.g., upgrading to MLS after initial TLS-only setup, or adding a new flow type):

```json
{
  "jsonrpc": "2.0",
  "id": "cap-update-1",
  "method": "wmp.capability.update",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:alice.example.com"},
    "add": {
      "relay": {"destinations": ["did:web:carol.example.com"]}
    },
    "remove": ["oid4vp"],
    "security": {
      "mode": "mls-optional",
      "cipher_suites": [1],
      "encrypted_capabilities": ["relay"]
    }
  }
}
```

The responder confirms by returning the updated negotiated capabilities:

```json
{
  "jsonrpc": "2.0",
  "id": "cap-update-1",
  "result": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "capabilities": {
      "messaging": {"max_size": 65536},
      "oid4vci": {"supported_grants": ["pre-authorized_code"]},
      "flows": {"max_concurrent": 5},
      "relay": {"destinations": ["did:web:carol.example.com"]}
    },
    "security": {
      "mode": "mls-optional",
      "cipher_suite": 1,
      "encrypted_capabilities": ["relay"],
      "mls_group_info": "<base64url-encoded MLS GroupInfo>"
    }
  }
}
```

#### 4.2.5 `wmp.capability.list`

Query the current negotiated state at any time:

**`wmp.capability.list` result:**

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
  "capabilities": {
    "messaging": {"max_size": 65536},
    "oid4vci": {"supported_grants": ["pre-authorized_code"]},
    "flows": {"max_concurrent": 5}
  },
  "security": {
    "mode": "mls-optional",
    "cipher_suite": 1,
    "encrypted_capabilities": ["relay"]
  }
}
```

### 4.3 Session Termination

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.session.close",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:alice.example.com"},
    "reason": "complete"
  }
}
```

Reason codes: `complete`, `timeout`, `error`, `user_cancelled`.

### 4.4 Authentication

Authentication binds a transport connection to a participant identity. WMP defines a concrete authentication sub-protocol that runs during or immediately after session creation.

#### 4.4.1 Authentication Model

Authentication is **per-participant** and **per-session**. Each participant authenticates using the mechanism appropriate to their identifier scheme (Section 7.4). The protocol supports three patterns:

1. **Inline authentication** — Credentials are included in `wmp.session.create`. Used when the initiator can prove identity without a challenge (e.g., bearer tokens, mTLS).
2. **Challenge-response authentication** — The responder issues a `challenge` in the session create result. The initiator completes authentication via `wmp.session.authenticate`. Used for signature-based authentication.
3. **Mutual authentication** — Both parties authenticate. The initiator authenticates inline or via challenge-response; the responder authenticates by including credentials in the session create result.

#### 4.4.2 The `auth` Field

The `wmp.session.create` params MAY include an `auth` object:

```json
{
  "wmp": {"version": "0.1", "sender": "x509:san:dns:alice.example.com"},
  "participants": ["x509:san:dns:issuer.example.eu"],
  "auth": {
    "type": "bearer",
    "token": "eyJhbGciOiJFUzI1NiIs..."
  },
  "capabilities_offered": {...},
  "security": {"mode": "tls"}
}
```

**Authentication types:**

| Type | Fields | Description |
|------|--------|-------------|
| `bearer` | `token` | Bearer token (JWT, opaque token, etc.). The token audience SHOULD be the responder's identifier or endpoint URL. |
| `dpop` | `token`, `proof` | DPoP-bound token (RFC 9449). `proof` is the DPoP proof JWT. |
| `mtls` | *(none — implicit)* | Authentication via the TLS client certificate on the transport connection. No additional fields needed; the responder verifies the certificate chain. |
| `signed_challenge` | `signature`, `challenge` | Detached JWS (§5.4 format) over the challenge value. Used in the second round-trip after receiving a challenge. |
| `x5c` | `x5c`, `signature`, `challenge` | X.509 certificate chain + signed challenge. The leaf certificate MUST contain a SAN matching the sender's identifier. |

#### 4.4.3 Challenge-Response Flow

When the responder cannot authenticate the initiator from the initial `wmp.session.create` alone (e.g., the sender uses a DID and no bearer token was provided), the responder returns a `challenge` in the session create result:

```
Initiator                              Responder
    │                                       │
    │── wmp.session.create ────────────────>│
    │   {sender: "did:web:alice...",        │
    │    auth: null}                         │
    │                                       │
    │<── result (session_id, challenge) ────│
    │   {challenge: "ch-9f8e7d6c",          │
    │    auth_required: true}               │
    │                                       │
    │── wmp.session.authenticate ──────────>│
    │   {auth: {type: "signed_challenge",   │
    │    challenge: "ch-9f8e7d6c",          │
    │    signature: "eyJ..."}}              │
    │                                       │
    │<── result {authenticated: true} ──────│
    │                                       │
```

**`wmp.session.authenticate` params:**

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:alice.example.com"},
  "auth": {
    "type": "signed_challenge",
    "challenge": "ch-9f8e7d6c",
    "signature": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDp3ZWI6YWxpY2UuZXhhbXBsZS5jb20ja2V5LTEiLCJiNjQiOmZhbHNlLCJjcml0IjpbImI2NCJdfQ..SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
  }
}
```

**Challenge signature construction:**

The `signed_challenge` signature is a detached JWS (same format as §5.4) where the payload `M` is the UTF-8 encoding of the following JSON object, JCS-canonicalized:

```json
{
  "challenge": "ch-9f8e7d6c",
  "session_id": "ses-a1b2c3d4",
  "sender": "x509:san:dns:alice.example.com",
  "timestamp": "2026-04-29T10:15:31Z"
}
```

The `session_id` binding prevents replay of the signed challenge to a different session. The `timestamp` MUST be within the receiver's clock skew tolerance (§8.5).

**Result:**

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
  "authenticated": true,
  "participant_id": "x509:san:dns:alice.example.com"
}
```

If authentication fails, the responder returns error `-31002` (Not authorized) with diagnostic details in `data`.

#### 4.4.4 `auth_required` Flag

The session create result MAY include `auth_required: true` to indicate that the session is in a **pending** state and no other methods will be accepted until `wmp.session.authenticate` succeeds. Implementations MUST reject all non-authentication requests on a pending session with error `-31002`.

When `auth_required` is absent or `false`, the session is immediately active (authentication was either completed inline or is not required by the responder's policy).

#### 4.4.5 Responder Authentication

The session create result MAY include the responder's own `auth` object for mutual authentication:

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
  "capabilities": {...},
  "challenge": "ch-9f8e7d6c",
  "auth": {
    "type": "x5c",
    "x5c": ["MIIB...(leaf)...", "MIIC...(issuer)..."],
    "signature": "eyJ...",
    "challenge": "<initiator-provided nonce if sent in create params>"
  }
}
```

For mutual authentication, the initiator MAY include a `nonce` field in `wmp.session.create` params that the responder signs in its `auth` response.

#### 4.4.6 Authentication and Identifier Schemes

Each identifier scheme maps to one or more authentication types:

| Scheme | Recommended auth type | Notes |
|--------|----------------------|-------|
| `x509:san:*` | `mtls` or `x5c` | Present certificate chain at TLS level or in `auth` field. RECOMMENDED for server-side entities (issuers, verifiers, wallet providers). |
| `x509:sha256:*` | `x5c` | Present certificate matching the fingerprint |
| `did:web`, `did:webvh` | `signed_challenge` | Sign with key from DID Document (DID profile resolver, §7.5.4) |
| `did:key`, `did:jwk` | `signed_challenge` | Key is inline in the DID — no resolution needed. Appropriate for wallet units and non-public endpoints. |
| `uri` (HTTPS) | `bearer` or `mtls` | Bearer token from the URI authority, or TLS cert for the domain |
| `ebcore:*` | `mtls` or `bearer` | SMP-registered certificate or SMP-issued token |
| `opaque` | `bearer` | Session-scoped bearer token only |

#### 4.4.7 Security Requirements

- Challenges MUST be cryptographically random, at least 128 bits of entropy.
- Challenges MUST be single-use. A responder MUST NOT accept the same challenge value twice.
- Challenge validity MUST be time-bounded (RECOMMENDED: 60 seconds).
- The `session_id` MUST be bound into the challenge-response signature to prevent cross-session replay.
- Bearer tokens MUST be validated for audience, expiry, and issuer.
- For `mtls`, the TLS client certificate MUST be verified against a trust anchor appropriate to the sender's identifier scheme.

### 4.5 Session Resumption

When a transport connection is lost (network failure, mobile app backgrounding), a client MAY resume an existing session on a new connection without repeating capability negotiation.

#### 4.5.1 `wmp.session.resume`

```json
{
  "jsonrpc": "2.0",
  "id": "resume-001",
  "method": "wmp.session.resume",
  "params": {
    "wmp": {"version": "0.1", "sender": "x509:san:dns:alice.example.com"},
    "session_id": "ses-a1b2c3d4",
    "resumption_token": "rt-base64url-encoded-token",
    "last_received_id": "msg-550e8400"
  }
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | REQUIRED | Session to resume |
| `resumption_token` | string | REQUIRED | Opaque token issued by the server at session creation or last resume |
| `last_received_id` | string | OPTIONAL | Last message `id` successfully received — server will replay messages after this |

**Result:**

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
  "resumed": true,
  "resumption_token": "rt-new-token-for-next-resume",
  "missed_messages": 3,
  "capabilities": {...},
  "security": {...}
}
```

#### 4.5.2 Resumption Token

The session create result SHOULD include a `resumption_token`:

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
  "capabilities": {...},
  "resumption_token": "rt-base64url-encoded-token"
}
```

The token is an opaque, server-generated value that:
- Binds to the session and the authenticated participant identity
- Is rotated on each successful resume (one-time use)
- Has a configurable lifetime (RECOMMENDED: equal to session TTL)
- MUST NOT be guessable (at least 128 bits of entropy)

#### 4.5.3 State Preservation

On successful resumption:
- Negotiated capabilities remain active
- Active flows resume from their last state (no automatic restart). The responder MUST re-send the latest `wmp.flow.progress` for each active flow as part of message replay (§6.2.1).
- The MLS epoch is preserved — the client continues with its current group state
- The server delivers any queued messages since `last_received_id`

#### 4.5.4 Resumption Failure

If the token is invalid, expired, or the session no longer exists, the server returns error `-31000` (Session not found) or `-31001` (Session expired). The client MUST create a new session.

## 5. Message Delivery

### 5.1 Direct Messages

Point-to-point messages within a session:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com"
    },
    "to": ["x509:san:dns:bob.example.com"],
    "content_type": "application/json",
    "body": { ... }
  }
}
```

A responder that only orchestrates flows for its client, with no other participant in the session to deliver to (for example a wallet backend in a `tls` session with the wallet as the only participant), has no recipient for a `wmp.message.deliver`. When such a responder receives a `wmp.message.deliver` **request** (one that carries an `id`) it MUST answer `-31008` (Participant not found) and MUST NOT hand the message to its flow engine; it does not acknowledge it. It handles an inbound `wmp.message.ack` or `wmp.message.status` notification by logging it and counting it in a metric, not by routing it to the flow engine, and sends no response.

### 5.2 Group Messages

When MLS is active, the message content is encrypted inside the JSON-RPC envelope. The JSON-RPC framing is always the outermost layer — it is never encrypted.

**Encryption construction:**

1. The sender constructs the **plaintext payload** — a JSON object containing the fields that would normally appear in `params` *excluding* the `wmp` metadata. For a `wmp.message.deliver` call, this is `{to, content_type, body}`.
2. The plaintext is UTF-8 encoded and encrypted using the MLS group's current epoch key, producing an MLS `MLSMessage` (RFC 9420 §6).
3. The resulting binary ciphertext is base64url-encoded and placed in the `ciphertext` field of the outer JSON-RPC envelope.
4. The outer envelope's `wmp` metadata carries `encrypted: true` and `epoch` so recipients know which key to use for decryption.

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "encrypted": true,
      "epoch": 3
    },
    "ciphertext": "<base64url-encoded MLS MLSMessage>"
  }
}
```

**On decryption**, the recipient:

1. Identifies the session and epoch from `wmp.session_id` and `wmp.epoch`.
2. Base64url-decodes the `ciphertext` field.
3. Decrypts the MLS `MLSMessage` using the group key for the given epoch.
4. Parses the resulting UTF-8 bytes as a JSON object containing the plaintext fields (`to`, `content_type`, `body`, etc.).

The `wmp` metadata (version, session_id, sender, encrypted, epoch) remains in plaintext for routing — relays need these fields to forward messages without access to the encrypted content. See [wmp-mls.md](wmp-mls.md) Section 4 for full details.

#### 5.2.1 Plaintext Commitment

Every signature and hash computed outside the MLS group — the sender's non-repudiation signature (§5.4), relay provenance (§5.7), and evidence content hashes ([wmp-evidence.md](wmp-evidence.md) §4.3) — binds to the ciphertext as transmitted. MLS ciphertext is specific to one transmission and one epoch. A party that later holds only the decrypted plaintext therefore cannot show a third party that the plaintext is what those artefacts attest to, short of producing the ciphertext *and* the group key that opens it.

The `plaintext_hash` field closes this gap. It is a sender-asserted, salted commitment to the plaintext content object, carried in the outer envelope as a sibling of `ciphertext`. Because it sits outside `wmp`, it is part of the §5.4 content object and is covered by the sender's signature, by every relay-chain hash, and by every evidence `original_content_hash` — without exposing the plaintext to relays.

**Envelope field:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `plaintext_hash` | object | OPTIONAL | Commitment to the plaintext content object. Fields: `algorithm` (`sha-256` REQUIRED to support; `sha-384`, `sha-512` OPTIONAL) and `value` (base64url, no padding). MUST only be present when `wmp.encrypted` is `true`. |

**Construction (sender):**

1. Build the plaintext content object as in §5.2 step 1 and add a `salt` field: a base64url-encoded (no padding) random value of at least 16 bytes, freshly generated for each message.
2. Compute `plaintext_hash.value` = BASE64URL(HASH(UTF8(JCS(plaintext content object)))), where HASH is the algorithm named in `plaintext_hash.algorithm` and JCS is applied under the same rules as §5.4.
3. Encrypt the plaintext content object — `salt` included — per §5.2 steps 2–3.
4. Place `plaintext_hash` in `params` as a sibling of `ciphertext` (or in `result` for an encrypted response).
5. If signing per §5.4, sign as usual. The content object is now `{"ciphertext": ..., "plaintext_hash": {...}}`, so the signature covers the commitment.

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "encrypted": true,
      "epoch": 3,
      "signature": "<detached JWS over {ciphertext, plaintext_hash}>"
    },
    "ciphertext": "<base64url-encoded MLS MLSMessage>",
    "plaintext_hash": {
      "algorithm": "sha-256",
      "value": "<base64url-encoded hash of JCS(plaintext content object)>"
    }
  }
}
```

The `salt` is required because the plaintext content object may have low entropy — a short body, a fixed content type, a small set of plausible recipients. Without it a relay could confirm a guessed plaintext by hashing the guess. With it, `plaintext_hash` reveals nothing about the plaintext to anyone who cannot decrypt the ciphertext. Recipients hash the decrypted object exactly as received, `salt` included; they MUST NOT strip or reorder anything before canonicalization.

**Verification (recipient):**

After decrypting per §5.2, a recipient that finds `plaintext_hash` in the envelope MUST:

1. Compute HASH(UTF8(JCS(decrypted plaintext content object))) using `plaintext_hash.algorithm`.
2. Compare the result to `plaintext_hash.value`.
3. On mismatch, reject the message with `-31019` (Plaintext hash mismatch) and MUST NOT acknowledge it (§5.3). A mismatch means the sender committed to something other than what the recipient can decrypt; acknowledging would let the evidence chain attest to content the sender can later disown.

A recipient MUST reject with `-32602` (Invalid params) a message that carries `plaintext_hash` while `wmp.encrypted` is absent or `false`, or whose `plaintext_hash.algorithm` it does not support.

Relays MUST forward `plaintext_hash` unchanged. It is part of the content object; any modification invalidates the sender's signature and every relay-chain entry (§5.7).

**Third-party verification.** A verifier presented with (a) a plaintext content object, (b) the outer content object `{ciphertext, plaintext_hash}` together with its `wmp.signature`, and (c) an evidence record can establish that the evidence attests to that plaintext without any MLS key material:

1. HASH(UTF8(JCS(a))) equals `plaintext_hash.value`.
2. The §5.4 signature over (b) verifies under the sender's key.
3. HASH(UTF8(JCS(b))) equals the evidence record's `original_content_hash.value`.
4. The evidence signature and timestamp token verify per [wmp-evidence.md](wmp-evidence.md) §8.1.

Parties that intend to rely on this chain MUST retain the outer content object and `wmp.signature` alongside the plaintext for as long as they retain the evidence.

**Negotiation.** `plaintext_hash` needs no capability of its own. It is an ordinary content-object field: a recipient that does not implement this section ignores it, and the §5.4 extraction rule covers it regardless. Profiles MAY require it; the evidence profile defines a `require_plaintext_hash` capability parameter for that purpose ([wmp-evidence.md](wmp-evidence.md) §2).

### 5.3 Message Acknowledgment

Recipients MAY acknowledge message receipt:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.ack",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:bob.example.com"},
    "message_ids": ["msg-550e8400-e29b-41d4-a716-446655440000"],
    "status": "received"
  }
}
```

Status values: `received`, `read`, `processed`, `failed`.

#### 5.3.1 Offline Delivery and Message Status

When the `offline` capability is negotiated and a recipient is disconnected, the server queues messages for later delivery. The `wmp.message.status` notification provides sender visibility into the delivery lifecycle.

**Per-message expiry:** The `expires_at` field in the `wmp` metadata object (§3.2) sets a per-message deadline. If `expires_at` is set and the message is still queued at that time, the server MUST discard it. If `expires_at` is absent, the message uses the `offline.ttl` from capability negotiation. If neither is set, server-default retention applies.

**`wmp.message.status` notification** (server → sender):

When `status_notifications` is `true` in the negotiated `offline` capability, the server sends delivery lifecycle notifications to the sender:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.status",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "message_id": "msg-550e8400",
    "status": "queued",
    "recipient": "did:web:citizen.example.com",
    "queued_until": "2026-05-03T14:10:00Z"
  }
}
```

**Status values:**

| Status | Description |
|--------|-------------|
| `queued` | Message accepted and queued; recipient is offline. `queued_until` indicates the time at which the message will expire from the queue. |
| `delivered` | Message delivered to recipient (on reconnect or when recipient comes online). |
| `expired` | Message expired from queue before delivery. The sender MAY retry or take compensating action. |
| `dropped` | Message dropped because the recipient's queue is full (`max_queued` exceeded). |

**Semantics:**

- The server sends `queued` immediately when it accepts a message for an offline recipient. The JSON-RPC result for the original `wmp.message.deliver` call confirms acceptance; the `queued` notification provides the additional detail that the recipient is offline.
- The server sends exactly one terminal status per message: `delivered`, `expired`, or `dropped`.
- If `status_notifications` is `false` or the `offline` capability is not negotiated, the server does best-effort delivery with no sender feedback.

**Queue overflow:** When the recipient's queue reaches `max_queued`, the server rejects new messages with error `-31014` (Queue full). The sender receives this as the JSON-RPC error response to the `wmp.message.deliver` call.

**Flow interaction:** When a flow is in progress and a participant goes offline, flow timeouts (§6.2.1) operate independently of the offline queue. The `expires_at` on flow-related messages SHOULD be set to match the flow timeout to avoid delivering stale flow steps.

**Evidence integration:** For ERDS delivery evidence ([wmp-evidence.md](wmp-evidence.md)), the `delivered` status provides the basis for delivery evidence records. The `expired` or `dropped` statuses provide the basis for non-delivery evidence.

### 5.4 Non-Repudiation Signatures

MLS provides sender authentication within a group, but MLS authentication keys are ephemeral and group-scoped — they cannot produce standalone artifacts verifiable by third parties (auditors, courts). For non-repudiation, WMP defines an optional `signature` field in the `wmp` metadata object.

The `signature` field carries a **detached JWS** (RFC 7515 Appendix F) over the message content, created with a long-lived key bound to the sender's identity (not the MLS leaf key). Using standard JOSE ensures interoperability with existing libraries and alignment with the broader OID4VC ecosystem.

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "timestamp": "2026-04-29T10:15:30Z",
      "signature": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDp3ZWI6YWxpY2UuZXhhbXBsZS5jb20ja2V5LTEifQ..SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    },
    "to": ["x509:san:dns:bob.example.com"],
    "content_type": "application/json",
    "body": { ... }
  }
}
```

The `signature` field is a **compact JWS with detached payload** (RFC 7515 Appendix F): `<header>..<signature>` (the payload segment between the dots is empty). The JWS protected header carries `alg`, `kid`, and optionally `x5c`:

```json
{
  "alg": "EdDSA",
  "kid": "did:web:alice.example.com#key-1",
  "b64": false,
  "crit": ["b64"]
}
```

**JWS header parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `alg` | REQUIRED | JWA algorithm identifier (`EdDSA`, `ES256`, `ES384`, `PS256`, etc.) |
| `kid` | REQUIRED | Key identifier — URI referencing the verification key (DID URL, X.509 SKI, JWK thumbprint) |
| `x5c` | OPTIONAL | X.509 certificate chain (base64-encoded DER, leaf first) |
| `b64` | REQUIRED | MUST be `false` (RFC 7797 — unencoded payload) |
| `crit` | REQUIRED | MUST include `"b64"` |

**Payload construction:**

The signed payload `M` is constructed as follows:

1. **Extract the content object.** For requests: take the `params` JSON object and remove the `wmp` key — the remaining key/value pairs form the content object. For responses: take the `result` or `error` JSON object as-is.
2. **Canonicalize.** Apply JCS (RFC 8785) to the content object. This produces a deterministic UTF-8 byte string `M`.

**Encrypted messages.** When `wmp.encrypted` is `true` (§5.2), the same extraction rule applies to the outer envelope: `params` minus `wmp` is `{"ciphertext": "<base64url MLSMessage>"}` — plus `plaintext_hash` when the sender includes the plaintext commitment of §5.2.1 — and that object is the content object. The signature therefore binds to the ciphertext as transmitted, not to the decrypted plaintext fields. This is deliberate — it lets relays and evidence generators (see [wmp-evidence.md](wmp-evidence.md) §4.3) verify the signature and compute content hashes without access to the plaintext. Signers MUST NOT sign the plaintext content object when `encrypted` is `true`.

**JCS compliance requirements:**

Implementations MUST use a canonicalization library that is fully compliant with RFC 8785 and passes the RFC 8785 test suite (Appendix B of that RFC). In addition:

- **Duplicate keys:** WMP content objects MUST NOT contain duplicate JSON keys at any nesting level. Implementations MUST reject messages with duplicate keys before canonicalization or signature verification. Signing a message with duplicate keys is a protocol error.
- **Number range:** JSON numbers in WMP content objects that will be signed MUST be within the IEEE 754 double-precision safe integer range ($|n| \leq 2^{53} - 1$ for integers). For values outside this range, use JSON strings instead. Implementations SHOULD reject numbers outside this range in signed content.
- **Unicode:** JCS preserves byte sequences without Unicode normalization. Implementations MUST NOT apply NFC, NFD, or other Unicode normalization to string values before or during canonicalization. Fields used in signature-critical paths SHOULD use ASCII-safe values where possible.
- **Test vectors:** WMP implementations that produce or verify non-repudiation signatures SHOULD verify their JCS implementation against the WMP canonicalization test vectors (published as a companion document).

Concretely, for a request with:
```json
{ "params": { "wmp": {...}, "to": [...], "content_type": "...", "body": {...} } }
```
the content object is `{"to": [...], "content_type": "...", "body": {...}}` and `M` = JCS(content object) encoded as UTF-8 bytes.

**JWS Signing Input:**

Per RFC 7515 §5.1 with the RFC 7797 `b64: false` modification, the signing input is the byte concatenation:

```
ASCII(BASE64URL(UTF8(JWS Protected Header))) || 0x2E || M
```

where `0x2E` is the ASCII period character and `M` is the raw canonical payload bytes (NOT base64url-encoded, because `b64` is `false`). The digital signature is computed over this exact byte string.

**Output encoding (compact serialization with detached payload):**

The `wmp.signature` field value is the JWS Compact Serialization with the payload segment omitted (RFC 7515 Appendix F):

```
BASE64URL(UTF8(JWS Protected Header)) || '.' || '' || '.' || BASE64URL(JWS Signature)
```

That is, the value has the form `<header>..<signature>` — two base64url strings separated by two consecutive period characters (the empty middle segment indicates the payload is detached and must be reconstructed from the message content).

**Signing procedure:**

1. Construct the JWS Protected Header JSON object containing `alg`, `kid`, `b64: false`, `crit: ["b64"]`, and optionally `x5c`.
2. Compute `HEADER` = BASE64URL(UTF8(JWS Protected Header)).
3. Extract the content object from the message (remove `wmp` from `params`, or use `result`/`error` directly).
4. Compute `M` = UTF8(JCS(content object)).
5. Compute the signing input: `ASCII(HEADER) || 0x2E || M`.
6. Sign the signing input with the private key using the algorithm specified by `alg`, producing the signature bytes `S`.
7. Set `wmp.signature` = `HEADER || '..' || BASE64URL(S)`.

**Verification procedure:**

1. Parse `wmp.signature` by splitting on `'.'` — this yields three segments: `HEADER`, `""` (empty), and `SIG`.
2. Decode `HEADER` from base64url to obtain the JWS Protected Header JSON. Verify that `b64` is `false` and `crit` includes `"b64"`.
3. Extract the content object from the received message (same extraction rule as signing).
4. Compute `M` = UTF8(JCS(content object)).
5. Compute the signing input: `ASCII(HEADER) || 0x2E || M`.
6. Decode `SIG` from base64url to obtain the signature bytes `S`.
7. Verify `S` over the signing input using the public key identified by `kid` (resolved via DID document, X.509 certificate, etc.) or the leaf certificate in `x5c`.

**When to sign:** Non-repudiation signatures are OPTIONAL by default. Profiles MAY require them for specific flow types or capabilities. The `evidence` profile (see [wmp-evidence.md](wmp-evidence.md)) requires signatures on all evidence messages.

**JAdES compatibility:** WMP non-repudiation signatures are structurally compatible with JAdES-B-B (ETSI EN 319 182-1) when the JWS protected header includes the `sigT` (signing time) claim. Implementations operating under EU eIDAS requirements that need qualified or advanced electronic signatures MAY produce full JAdES-B-T signatures by switching to JWS JSON Serialization and including an RFC 3161 timestamp token in the `etsiU` unsigned header array. A WMP profile for JAdES-B-T and above is out of scope for this core specification but MAY be defined in a separate document.

### 5.5 Trusted Timestamping

The `timestamp` field in `wmp` metadata is self-asserted by the sender. For legally-binding time attestation, the `timestamp_token` field carries an externally-issued timestamp.

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "timestamp": "2026-04-29T10:15:30Z",
      "timestamp_token": "<base64url-encoded RFC 3161 TimeStampToken>"
    },
    "to": ["x509:san:dns:bob.example.com"],
    "content_type": "application/json",
    "body": { ... }
  }
}
```

The timestamp token MUST be an RFC 3161 `TimeStampToken` obtained from a trusted Time Stamping Authority (TSA). The token MUST cover the hash of the message content (same canonicalized content as for non-repudiation signatures).

For EU regulatory contexts, the TSA SHOULD be a qualified trust service provider under eIDAS.

Implementations MAY also use RFC 9162 (Certificate Transparency) signed timestamps, encoded in the same field with a distinguishing prefix:

| Format | Prefix | Description |
|--------|--------|-------------|
| RFC 3161 | (none) | Standard TSA timestamp token |
| RFC 9162 SCT | `sct:` | Signed Certificate Timestamp |

### 5.6 Identity Assertions

WMP identifiers (DIDs, X.509 fingerprints, etc.) are cryptographic identifiers that do not inherently bind to a legal identity. For scenarios requiring legal person identification (e.g., eIDAS ERDS, regulatory compliance), the `identity_assertions` field carries verifiable bindings between the cryptographic identifier and a legal identity.

> **Note:** Identity assertions are *sender-initiated* proofs attached to messages or sessions — analogous to a TLS client certificate. WMP Core does not define a mechanism for the relying party to request specific credentials or claims before the sender presents them. For *verifier-initiated* credential requests (where a verifier asks a holder to prove specific attributes), use the `oid4vp` flow type in [wmp-openid4x.md](wmp-openid4x.md). When a sender presents an assertion that does not satisfy the RP's policy, the RP rejects it with error `-31012` including diagnostic data (§5.6.2), enabling the sender to retry with an appropriate assertion. Profiles MAY extend the session create response with additional fields (e.g., `identity_assertion_requirements`) to pre-signal RP expectations.

Identity assertions use a **presentation model**: the sender produces a Verifiable Presentation (VP) bound to the WMP session, rather than transmitting a raw credential. This ensures:

- **Holder binding** — The VP proves the sender controls the credential (proof of possession).
- **Replay protection** — The `nonce` (from the session challenge) and `audience` (session ID or MLS group ID) prevent replay across sessions.
- **Selective disclosure** — The sender discloses only the claims required for the interaction.

#### Session Challenge

The session create response includes a `challenge` field — a server-generated nonce that MUST be used as the `nonce` parameter in any `verifiable_presentation` identity assertion within that session. This binds the presentation to the session and prevents replay.

Each identity assertion has a `type` indicating the assertion mechanism, and an optional `trust_hints` array. Trust hints are **suggestions from the sender** indicating trust frameworks under which the underlying credential *may* be verifiable. The relying party (RP) is never obligated to follow a hint — the RP's local trust policy always determines which frameworks are acceptable and how credentials are validated.

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "identity_assertions": [
        {
          "type": "verifiable_presentation",
          "format": "vc+sd-jwt",
          "vp_token": "eyJ...",
          "audience": "ses-a1b2c3d4",
          "nonce": "ch-9f8e7d6c",
          "disclosed_claims": ["given_name", "family_name", "org_id"],
          "trust_hints": [
            {
              "framework": "eidas_lote",
              "lote_url": "https://eidas.ec.europa.eu/efda/tl/browser/",
              "issuer_service_id": "urn:uuid:..."
            },
            {
              "framework": "openid_federation",
              "trust_anchor": "https://federation.example.eu",
              "entity_statement": "eyJ..."
            }
          ]
        }
      ]
    },
    "to": ["x509:san:dns:bob.example.com"],
    "content_type": "application/json",
    "body": { ... }
  }
}
```

**Identity assertion types:**

| Type | Description |
|------|-------------|
| `verifiable_presentation` | A Verifiable Presentation (OID4VP `vp_token`) proving possession of a credential and disclosing selected claims. Fields: `format` (credential format, e.g., `vc+sd-jwt`, `mso_mdoc`), `vp_token` (the encoded VP token), `audience` (session ID or MLS group ID — binds the presentation to the session), `nonce` (session challenge — prevents replay), `disclosed_claims` (array of claim names disclosed in the VP, for RP convenience). |
| `x509_chain` | An X.509 certificate chain binding the sender's key to an identity via a CA. Fields: `x5c` (base64-encoded DER chain, leaf first). |

#### MLS Group Considerations

In MLS-encrypted sessions with multiple participants, identity assertions are **session-scoped**: the `audience` is the session ID and the `nonce` is the session challenge. All group members can verify the presentation. If a participant requires a per-recipient assertion (e.g., with recipient-specific audience), this SHOULD be handled via a separate direct WMP session between the two parties.

#### 5.6.1 Trust Hints

The `trust_hints` array is OPTIONAL. Each entry is a **hint** suggesting a trust framework and providing enough information for the RP to efficiently locate and execute the corresponding validation path. The RP decides independently whether to act on any given hint.

A hint is actionable when it provides the RP with a concrete starting point for validation. Each framework type defines the fields that make a hint actionable:

| Framework | Description | Actionable fields |
|-----------|-------------|-------------------|
| `eidas_lote` | eIDAS Trusted List. | `lote_url` — URL of the LoTE/LoTL to search. `issuer_service_id` — the service identifier of the issuer within the list (optional; speeds lookup). |
| `openid_federation` | OpenID Federation trust chain. | `trust_anchor` — entity ID of the trust anchor. `entity_statement` — pre-fetched subordinate statement JWT (optional; avoids discovery round-trip). |
| `x509_pki` | X.509 PKI validation. | `root_ca` — issuer DN or SKI of the expected root CA (optional; narrows trust store search). |
| `external` | National or sector-specific framework. | `uri` — framework identifier URI. `validation_endpoint` — URL of a status/validation service (optional). |

**RP processing model:**

1. The RP receives an identity assertion with zero or more `trust_hints`.
2. The RP compares each hint's `framework` against its local trust policy. Hints referencing frameworks the RP does not support are silently ignored.
3. For each accepted framework, the RP uses the hint's fields as a starting point for validation (e.g., fetching the referenced LoTE and checking whether the credential issuer appears as a trusted service).
4. The RP MAY validate the credential under a framework *not* listed in the hints, if the RP's own policy and configuration support it.
5. If no hint matches the RP's policy and the RP cannot independently determine a trust path, the assertion SHOULD be treated as untrusted.

When `trust_hints` is absent, the RP determines the applicable trust model entirely from local policy and the credential content itself.

Identity assertions are OPTIONAL in WMP Core. Profiles MAY mandate specific assertion types and require that certain trust hints be present. For example, an ERDS profile could require `verifiable_credential` with at least one `eidas_lote` hint referencing a LoTE published under the EU Trusted List framework.

Identity assertions MAY be sent once during session creation and are then valid for the session lifetime, or MAY be attached to individual messages when per-message identity binding is required.

#### 5.6.2 Identity Assertion Rejection

When a relying party rejects an identity assertion, it MUST return error code `-31012` with a `data` object containing diagnostic information. This enables the sender to understand the rejection reason and retry with an appropriate assertion without requiring an out-of-band negotiation mechanism.

**Error `data` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `reason` | string | REQUIRED. Machine-readable rejection reason (see table below). |
| `accepted_formats` | array of string | OPTIONAL. Credential formats the RP accepts (e.g., `vc+sd-jwt`, `mso_mdoc`). |
| `required_claims` | array of string | OPTIONAL. Claim names the RP requires to be disclosed. |
| `accepted_trust_frameworks` | array of string | OPTIONAL. Trust framework identifiers the RP recognizes. |
| `message` | string | OPTIONAL. Human-readable diagnostic message. |

**Rejection reasons:**

| Reason | Description |
|--------|-------------|
| `unsupported_format` | The assertion format is not accepted by the RP. |
| `insufficient_claims` | The disclosed claims do not satisfy the RP's requirements. |
| `untrusted_issuer` | The credential issuer is not trusted under any framework accepted by the RP. |
| `invalid_proof` | The VP proof (signature, nonce binding, or audience) is invalid. |
| `expired` | The credential or presentation has expired. |
| `revoked` | The credential has been revoked. |

**Example rejection response:**

```json
{
  "jsonrpc": "2.0",
  "id": "msg-1",
  "error": {
    "code": -31012,
    "message": "Identity assertion invalid",
    "data": {
      "reason": "unsupported_format",
      "accepted_formats": ["vc+sd-jwt"],
      "required_claims": ["given_name", "family_name"],
      "accepted_trust_frameworks": ["eidas_lote"]
    }
  }
}
```

The sender MAY use the diagnostic data to construct a new identity assertion and resend the message or call `wmp.session.authenticate` (§4.4) with the corrected assertion. Implementations MUST NOT disclose sensitive policy details in the diagnostic data beyond what is necessary for the sender to construct an acceptable assertion.

> **Extensibility:** The rejection diagnostic model is intentionally minimal. Profiles that require richer verifier-initiated credential negotiation (e.g., full `presentation_definition` support) SHOULD use the OID4VP flow type rather than extending the `-31012` error data.

### 5.7 Relay Provenance

When a message traverses multiple WMP relays, each relay appends an entry to the `relay_chain` array before forwarding. On receipt, the recipient can inspect this chain to determine which relays handled the message, verify each hop's signature, and detect any tampering or unexpected routing:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {
      "version": "0.1",
      "session_id": "ses-a1b2c3d4",
      "sender": "x509:san:dns:alice.example.com",
      "relay_chain": [
        {
          "relay": "wss://relay-a.example.com/wmp",
          "relay_id": "x509:san:dns:relay-a.example.com",
          "timestamp": "2026-04-29T10:15:30Z",
          "signature": "eyJhbGciOiJFUzI1NiIsImtpZCI6Ing1MDk6c2FuOmRuczpyZWxheS1hLmV4YW1wbGUuY29tI2tleS0xIiwiYjY0IjpmYWxzZSwiY3JpdCI6WyJiNjQiXX0..MEUCIQDx-signature-a"
        },
        {
          "relay": "wss://relay-b.example.com/wmp",
          "relay_id": "x509:san:dns:relay-b.example.com",
          "timestamp": "2026-04-29T10:15:31Z",
          "signature": "eyJhbGciOiJFUzI1NiIsImtpZCI6Ing1MDk6c2FuOmRuczpyZWxheS1iLmV4YW1wbGUuY29tI2tleS0xIiwiYjY0IjpmYWxzZSwiY3JpdCI6WyJiNjQiXX0..MEUCIQDx-signature-b"
        }
      ]
    },
    "to": ["x509:san:dns:bob.example.com"],
    "content_type": "application/json",
    "body": { ... }
  }
}
```

**Relay chain entry fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `relay` | string | REQUIRED | Relay endpoint URI |
| `relay_id` | string | REQUIRED | Relay identifier (WMP identifier scheme) |
| `timestamp` | string | REQUIRED | ISO 8601 timestamp when relay processed the message |
| `timestamp_token` | string | OPTIONAL | RFC 3161 timestamp token for the relay hop |
| `signature` | string | OPTIONAL | Detached JWS (RFC 7515 Appendix F) — see relay signature construction below |
| `service_class` | string | OPTIONAL | Service class: `best_effort`, `standard`, `registered`, `certified` |

Each relay in the chain SHOULD append its entry before forwarding. The `signature` field in each entry allows recipients to verify relay provenance independently. When the `evidence` capability is active (see [wmp-evidence.md](wmp-evidence.md)), relays MUST sign their entries.

**Relay signature construction:**

The relay entry signature uses the same detached JWS format as §5.4, but the payload is constructed differently to bind the relay hop to the message content:

1. **Compute the content hash.** Take the content object (same extraction as §5.4 — `params` minus `wmp`), JCS-canonicalize it, and compute its SHA-256 hash: `H` = SHA-256(UTF8(JCS(content object))).
2. **Construct the relay signing object.** Build the following JSON object:
   ```json
   {
     "content_hash": "<base64url(H)>",
     "relay": "<relay endpoint URI>",
     "relay_id": "<relay identifier>",
     "timestamp": "<ISO 8601 timestamp>"
   }
   ```
   Include `previous_chain` (array of prior relay entry signatures, in order) if this is not the first hop, to chain the provenance.
3. **Canonicalize.** Apply JCS (RFC 8785) to the relay signing object to produce payload bytes `M`.
4. **Sign.** Compute the detached JWS over `M` exactly as specified in §5.4 (signing input = `ASCII(HEADER) || 0x2E || M`, output = `HEADER..BASE64URL(S)`).

This construction binds each relay's attestation to both the message content (via the hash) and the relay's own identity and timestamp, while keeping the relay entry compact (the full message content is not repeated).

### 5.8 Metadata Resolution

WMP defines a generic metadata resolution mechanism via `wmp.resolve`. This is a simple request/response method — not a flow — for looking up metadata about identifiers, credential types, trust relationships, and endpoints.

The `resolve` capability MUST be negotiated during session creation to use resolve methods.

#### 5.8.1 `wmp.resolve`

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "res-001",
  "method": "wmp.resolve",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "type": "vctm",
    "uri": "https://credentials.example.com/identity"
  }
}
```

**Response:**

The result carries the resolved document as an opaque `body` alongside a `content_type`, making the format extensible to any metadata representation. For `vctm` resolution the body MUST be the full Verifiable Credential Type Metadata document as defined in [SD-JWT VC Type Metadata](https://www.ietf.org/archive/id/draft-ietf-oauth-sd-jwt-vc-06.html#section-6):

```json
{
  "jsonrpc": "2.0",
  "id": "res-001",
  "result": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "type": "vctm",
    "uri": "https://credentials.example.com/identity",
    "content_type": "application/vctm+json",
    "body": {
      "vct": "https://credentials.example.com/identity",
      "name": "National ID Card",
      "description": "Government-issued identity credential",
      "display": [
        {"lang": "en", "name": "National ID", "description": "Government-issued identity credential"}
      ],
      "claims": [
        {"path": ["given_name"], "display": [{"lang": "en", "name": "First name"}]},
        {"path": ["family_name"], "display": [{"lang": "en", "name": "Last name"}]},
        {"path": ["birthdate"], "display": [{"lang": "en", "name": "Date of birth"}]}
      ],
      "schema": {
        "type": "object",
        "properties": {
          "given_name": {"type": "string"},
          "family_name": {"type": "string"},
          "birthdate": {"type": "string", "format": "date"}
        }
      }
    },
    "trust_info": {
      "trusted": true,
      "source": "registry"
    }
  }
}
```

**Request fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | REQUIRED | Resolution type (see below) |
| `uri` | string | REQUIRED | Identifier or URI to resolve |
| `options` | object | OPTIONAL | Type-specific resolution options |

**Response fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | REQUIRED | Echoed resolution type |
| `uri` | string | REQUIRED | Echoed identifier/URI |
| `content_type` | string | REQUIRED | Media type of `body` (e.g. `application/vctm+json`) |
| `body` | object/string | REQUIRED | The resolved metadata document. `null` if not found. |
| `trust_info` | object | OPTIONAL | Trust evaluation for the resolved entity |

**Standard resolution types:**

| Type | Resolves | Returns |
|------|----------|---------|
| `vctm` | Verifiable Credential Type URI | Credential type metadata (display, claims, schema) |
| `issuer_metadata` | Issuer URL | OID4VCI issuer metadata (supported credentials, grants) |
| `trust` | Entity identifier | Trust evaluation (chain, status, trust list membership) |
| `endpoint` | Participant identifier | WMP endpoint(s) and capabilities |
| `openid_federation` | Entity ID URL | OpenID Federation entity configuration and trust chain |

Profiles MAY define additional resolution types. For example, the eDelivery profile ([wmp-edelivery.md](wmp-edelivery.md)) adds `smp` for SMP/BDXL participant lookups.

#### 5.8.2 Resolve Capability Parameters

```json
{
  "resolve": {
    "supported_types": ["vctm", "issuer_metadata", "trust", "endpoint"]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `supported_types` | string[] | Resolution types this endpoint can serve |

#### 5.8.3 Error Handling

Resolution failures use standard WMP error responses:

```json
{
  "jsonrpc": "2.0",
  "id": "res-001",
  "error": {
    "code": -31005,
    "message": "Resolution type not supported",
    "data": {"type": "smp"}
  }
}
```

A resolution that succeeds but finds no metadata returns a result with `body: null`.

## 6. Structured Flows

WMP supports structured multi-step flows as a general-purpose mechanism for coordinating multi-step interactions over a session. Flows are state machines with a common lifecycle. Domain-specific flow types (e.g., credential issuance, presentation) are defined in profile documents.

The `flows` capability MUST be negotiated during session creation to use flow methods.

### 6.1 Flow Lifecycle

```
Initiator                         Responder
    │                                 │
    │──── wmp.flow.start ────────────>│
    │<─── wmp.flow.progress ──────────│  (0..n steps)
    │──── wmp.flow.action ───────────>│  (participant decisions)
    │<─── wmp.flow.progress ──────────│
    │<─── wmp.flow.complete ──────────│  (terminal)
    │                                 │
    │  ── OR (abnormal termination) ──│
    │                                 │
    │<─── wmp.flow.error ─────────────│  (terminal)
    │──── wmp.flow.cancel ───────────>│  (terminal)
    │                                 │
```

**Flow states:**

| State | Description |
|-------|-------------|
| `in_progress` | Flow is active; `wmp.flow.progress` updates may be sent. |
| `completed` | Terminal. Flow finished successfully via `wmp.flow.complete`. |
| `error` | Terminal. Flow failed via `wmp.flow.error`. |
| `cancelled` | Terminal. Flow was cancelled via `wmp.flow.cancel`. |
| `timed_out` | Terminal. Flow exceeded its `timeout`. Responder sends `wmp.flow.error` with reason `timeout`. |

### 6.2 Flow Methods

#### `wmp.flow.start`

Initiates a new flow. The `flow_type` identifies the type of flow and determines what parameters are expected. Flow types are either built-in (defined below) or profile-defined.

**Params:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_type` | string | REQUIRED | Flow type identifier |
| `flow_id` | string | REQUIRED | Unique flow identifier (scoped to session) |
| `timeout` | integer | OPTIONAL | Flow timeout in seconds. After expiry, the responder MUST send `wmp.flow.error` with reason `timeout`. If omitted, the profile's default timeout applies (or no timeout). |
| `params` | object | OPTIONAL | Flow-type-specific parameters |

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:alice.example.com"},
  "flow_type": "approval",
  "flow_id": "flow-7890",
  "params": {
    "subject": "Document review request",
    "body": "Please review and approve the attached.",
    "attachments": [{"content_type": "application/pdf", "uri": "https://example.com/doc/123"}]
  }
}
```

#### `wmp.flow.progress`

Sent by the responder to update the initiator on flow state. MAY be sent zero or more times.

**Params:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | REQUIRED | Flow identifier |
| `step` | string | REQUIRED | Current step identifier |
| `payload` | object | OPTIONAL | Step-specific data |

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.flow.progress",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_id": "flow-7890",
    "step": "awaiting_review",
    "payload": {
      "reviewer": "x509:san:dns:bob.example.com",
      "deadline": "2026-05-01T00:00:00Z"
    }
  }
}
```

#### `wmp.flow.action`

Sent by a participant to provide input or make a decision within a flow.

**Params:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | REQUIRED | Flow identifier |
| `action` | string | REQUIRED | Action identifier |
| `params` | object | OPTIONAL | Action-specific parameters |

```json
{
  "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:alice.example.com"},
  "flow_id": "flow-7890",
  "action": "approve",
  "params": {
    "comment": "Looks good."
  }
}
```

#### `wmp.flow.complete`

Sent when a flow reaches a terminal state successfully.

**Params:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | REQUIRED | Flow identifier |
| `result` | object | OPTIONAL | Flow-type-specific result data |

#### `wmp.flow.error`

Sent when a flow fails. This is a terminal notification — the flow cannot be continued after this.

**Params:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | REQUIRED | Flow identifier |
| `code` | integer | REQUIRED | Error code |
| `message` | string | REQUIRED | Error description |
| `data` | object | OPTIONAL | Additional error context |

**Well-known error reasons** (in `data.reason`):

| Reason | Description |
|--------|-------------|
| `timeout` | The flow exceeded the `timeout` specified in `wmp.flow.start`. |
| `invalid_state` | The flow is in a state that cannot proceed (e.g., dependency failed). |
| `rejected` | The responder declined the flow (e.g., approval denied). |

#### `wmp.flow.cancel`

Sent by the initiator (or any authorized participant) to terminate a flow before completion. The responder MUST acknowledge the cancellation and treat the flow as terminal.

**Params:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | REQUIRED | Flow identifier |
| `reason` | string | OPTIONAL | Machine-readable cancellation reason (e.g., `user_cancelled`, `superseded`, `no_longer_needed`) |

**Result:**

```json
{
  "flow_id": "flow-7890",
  "status": "cancelled"
}
```

If the flow has already reached a terminal state (`completed`, `error`, or `cancelled`), the responder returns error `-31006` with `data.reason` set to `already_terminal`.

### 6.2.1 Flow Error Recovery

**Action rejection and retry:** When a `wmp.flow.action` is rejected (e.g., invalid action for the current step), the responder returns error `-31006`. The `data` object SHOULD include:

| Field | Type | Description |
|-------|------|-------------|
| `reason` | string | Machine-readable reason (e.g., `invalid_action`, `invalid_params`, `wrong_step`). |
| `retryable` | boolean | `true` if the initiator MAY resend a corrected action; `false` if the flow has moved to an error state. |
| `current_step` | string | The step the flow is currently in (helps the initiator understand the expected action). |

```json
{
  "jsonrpc": "2.0",
  "id": "action-1",
  "error": {
    "code": -31006,
    "message": "Flow error",
    "data": {
      "flow_id": "flow-7890",
      "reason": "invalid_action",
      "retryable": true,
      "current_step": "awaiting_review"
    }
  }
}
```

**Reconnect behavior:** When a session is resumed (§4.5), the responder MUST re-send the latest `wmp.flow.progress` notification for each active (non-terminal) flow as part of the message replay. This ensures the initiator recovers flow state without a dedicated status query method.

### 6.3 Built-in Flow Types

The following flow types are defined by WMP Core:

| Flow Type | Description |
|-----------|-------------|
| `sign` | Request a cryptographic signature from a participant |
| `approval` | Request approval or consent from a participant |
| `message` | Free-form structured message exchange |

Additional flow types are defined by profile documents:
- OpenID4x profile ([wmp-openid4x.md](wmp-openid4x.md)): `oid4vci`, `oid4vp`

### 6.4 Sign Flow

The `sign` flow type requests a cryptographic signature from a participant. It is used when one party needs another to produce a proof, sign a document, or authorize an operation.

**Start params:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | REQUIRED | `generate_proof`, `sign_document`, `authorize` |
| `nonce` | string | OPTIONAL | Nonce for replay protection |
| `audience` | string | OPTIONAL | Intended audience for the signature |
| `payload` | object/string | OPTIONAL | Data to be signed |

```json
{
  "jsonrpc": "2.0",
  "id": "sign-001",
  "method": "wmp.flow.start",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_type": "sign",
    "flow_id": "flow-sign-001",
    "params": {
      "action": "generate_proof",
      "nonce": "n-0S6_WzA2Mj",
      "audience": "https://example.com",
      "proof_type": "jwt"
    }
  }
}
```

### 6.5 Profile-Defined Flow Types

Profiles extend WMP with domain-specific flow types. A profile document MUST define for each flow type:

1. The flow type identifier string.
2. The capability name that MUST be negotiated to use the flow type.
3. The `params` schema for `wmp.flow.start`.
4. The set of `step` identifiers used in `wmp.flow.progress`.
5. The set of `action` identifiers used in `wmp.flow.action`.
6. The `result` schema for `wmp.flow.complete`.

A `wmp.flow.start` for a flow type that no negotiated capability provides, including one that no implemented profile defines, is answered with `-31005` as Section 3.8.1 describes.

## 7. Participant Addressing

### 7.1 Identifier Model

WMP does not mandate a single identifier scheme. Participants are identified by URIs or structured identifiers, and the protocol treats identifiers as **opaque strings** for routing purposes. The identifier scheme is determined by the identifier's prefix — no separate `scheme` field is needed.

Identifiers are always plain strings:

```json
"did:web:alice.example.com"
"x509:sha256:b3c4d5e6f7..."
"x509:san:dns:relay-a.example.com"
"https://university.example.eu"
"ebcore:iso6523:0088:7315458756324"
```

**Scheme inference rules:**

| Prefix | Scheme |
|--------|--------|
| `did:` | `did` |
| `x509:` | `x509` / `x509-san` / `x509-dn` (determined by sub-prefix) |
| `mdoc:` | `mdoc` |
| `urn:` | `urn` |
| `ebcore:` | `ebcore` |
| `https://` | `uri` |
| *(other)* | `opaque` |

All `https://` identifiers use the `uri` scheme for discovery purposes. Trust evaluation (e.g., whether an `https://` entity participates in an OpenID Federation) is orthogonal and handled via `identity_assertions` and `trust_hints` (Section 5.6).

An optional `display` field MAY be included in structured contexts (e.g., participant lists in UI-facing metadata) but is never required by the protocol:

```json
{
  "id": "did:web:alice.example.com",
  "display": "Alice (example.com)"
}
```

### 7.2 Supported Identifier Schemes

| Scheme | Syntax | Description | Ecosystem |
|--------|--------|-------------|------------|
| `did` | `did:<method>:<id>` | Decentralized Identifiers (any method) | W3C DID |
| `x509` | `x509:sha256:<fingerprint>` | X.509 certificate fingerprint | eIDAS, EUDI, ISO 18013 |
| `x509-san` | `x509:san:uri:<value>` or `x509:san:dns:<value>` | X.509 Subject Alternative Name | eIDAS, TLS |
| `x509-dn` | `x509:dn:<distinguished-name>` | X.509 Subject Distinguished Name | eIDAS, PKI |
| `uri` | `https://<endpoint>` | HTTPS URI (entity IDs, issuer `iss`, client_id) | OID4VCI, OID4VP, OIDF |
| `mdoc` | `mdoc:issuer:<issuer-data-element>` | ISO 18013-5 mdoc issuer identifier | mDL, EUDI |
| `urn` | `urn:<namespace>:<id>` | URN-based identifiers | National ID systems |
| `ebcore` | `ebcore:<catalog>:<scheme>:<id>` | ebCore Party Identifier (ISO 6523, etc.) | eDelivery, PEPPOL |
| `opaque` | `<session-scoped-id>` | Opaque session-scoped identifier | Anonymous/pseudonymous |

> **Note:** OpenID Federation entities are identified by their entity ID (`https://...`). The federation trust chain is a trust mechanism, not an addressing scheme — it is handled via `identity_assertions` with `trust_hints` of framework `openid_federation`.

### 7.3 Identifier in Session Messages

The `sender` field in the `wmp` metadata object carries the participant's identifier. The identifier scheme used MUST be consistent within a session — a participant MUST NOT change their identifier scheme mid-session without renegotiation.

```json
{
  "wmp": {
    "version": "0.1",
    "session_id": "ses-a1b2c3d4",
    "sender": "x509:san:dns:alice.example.com"
  }
}
```

```json
{
  "wmp": {
    "version": "0.1",
    "session_id": "ses-x509-001",
    "sender": "x509:sha256:b3c4d5e6f7..."
  }
}
```

```json
{
  "wmp": {
    "version": "0.1",
    "session_id": "ses-oidf-001",
    "sender": "https://university.example.eu"
  }
}
```

### 7.4 Identifier Binding and Authentication

How a participant proves control of their identifier depends on the scheme:

| Scheme | Authentication Method |
|--------|----------------------|
| `x509` / `x509-san` / `x509-dn` | Present X.509 certificate chain; verify against trust anchor (eIDAS trust list, national CA). RECOMMENDED for server-side entities. |
| `did` | DID Document verification key; prove control via signature (requires DID profile resolver, Section 7.5.4). `did:key` and `did:jwk` have inline keys — no resolution needed. |
| `uri` | TLS certificate for the domain; or bearer token issued by the URI authority. Optionally, OpenID Federation entity statement chain via `identity_assertions`. |
| `mdoc` | ISO 18013-5 issuer authentication (IACA certificate) |
| `ebcore` | Mutual TLS with the certificate from SMP; or bearer token issued by the SMP authority |
| `opaque` | Session-level authentication only (bearer token); no external identity binding |

Multiple authentication methods MAY be supported simultaneously. The responder determines whether it can authenticate the initiator's identifier scheme based on its own policy. If the responder does not support the initiator's scheme, it MUST reject the session with error `-31002` (Not authorized).

The well-known configuration (§7.5.1) advertises `accepted_schemes` so that clients can check scheme compatibility *before* attempting a connection. This is informational — the authoritative check happens during authentication (§4.4).

```json
{
  "wmp": {"version": "0.1", "sender": "x509:san:dns:wallet.example.com"},
  "participants": ["x509:san:dns:issuer.example.eu"],
  "capabilities_offered": {...}
}
```

### 7.5 Endpoint Discovery

WMP defines a layered discovery architecture with a single primary mechanism — well-known configuration for domain-based identifiers — plus profile-extensible resolvers for identifier schemes that require scheme-specific resolution (DID Documents, eDelivery SMP, etc.).

> **Privacy principle:** Endpoints are associated with **service providers** (wallet providers, issuers, verifiers), not with individual users or wallet units. Discovery MUST NOT require or assume the availability of public per-user metadata (such as per-user DID Documents or per-user well-known configurations). The binding between a user and their wallet provider is private information. Relaying bridges the provider's endpoint to the correct wallet unit internally.

#### 7.5.1 Primary Mechanism: Well-Known Configuration

The primary discovery mechanism is the **well-known WMP configuration** document, served at `/.well-known/wmp-configuration` on the identifier's domain. This is the REQUIRED mechanism for all domain-based identifiers.

**Domain extraction rules:**

| Identifier type | Domain extraction |
|-----------------|-------------------|
| `x509:san:dns:example.com` | Use the SAN DNS value: `example.com` |
| `x509:san:uri:https://example.com/...` | Extract the host: `example.com` |
| `https://example.com` | Use the host directly: `example.com` |
| `https://example.com/path` | Use the host: `example.com` |
| `did:web:example.com` | Extract domain from DID: `example.com` |
| `did:web:example.com:path:...` | Extract domain: `example.com` (path components are ignored for discovery — the endpoint is the provider's, not a per-user path) |
| `did:<other-method>:...` | Domain not extractable — use DID profile resolver (§7.5.4) or session parameters |
| `ebcore:...` | See profile-specific resolver (Section 7.5.3) |
| `x509:sha256:...` | Domain not extractable — use session parameters or profile resolver |
| `mdoc:...` | Domain not extractable — use session parameters or profile resolver |
| `opaque` | No discovery — endpoint provided during session creation |

For any identifier where a domain can be extracted, discovery is:

```
GET https://<domain>/.well-known/wmp-configuration
```

**Well-known WMP configuration document:**

```json
{
  "supported_versions": ["0.1"],
  "endpoints": {
    "websocket": "wss://example.com/wmp",
    "https": "https://example.com/wmp"
  },
  "capabilities": {
    "messaging": {},
    "flows": {"max_concurrent": 10},
    "evidence": {
      "event_types": ["submission_accepted", "delivery_confirmed", "retrieval_confirmed"]
    }
  },
  "accepted_schemes": ["did", "x509", "uri"],
  "security_modes": ["tls", "mls", "mls-optional"],
  "mls_key_packages": "https://example.com/.well-known/mls-key-packages",
  "erds": {
    "consignment_modes": ["basic", "consented"],
    "assurance_levels": ["low", "substantial", "high"],
    "supported_policies": [
      "urn:etsi:erds:policy:qualified",
      "urn:example:erds:policy:corporate"
    ],
    "delegation": true,
    "evidence_repository": "https://example.com/evidence",
    "evidence_retention": "P10Y"
  },
  "recipient_metadata": {
    "accepted_content_types": ["application/json", "application/pdf"],
    "max_message_size": 10485760,
    "consignment_preferences": "consented",
    "encryption_required": false
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `supported_versions` | string[] | REQUIRED | Protocol versions this endpoint supports (§2.2) |
| `endpoints` | object | REQUIRED | Map of transport type to endpoint URL |
| `capabilities` | object | OPTIONAL | Pre-advertised capabilities (informational) |
| `accepted_schemes` | string[] | OPTIONAL | Identifier schemes this endpoint can authenticate (pre-connect hint for clients) |
| `security_modes` | string[] | OPTIONAL | Supported security modes |
| `mls_key_packages` | string | OPTIONAL | URL to MLS KeyPackages endpoint |
| `relay` | string | OPTIONAL | Default relay endpoint for this entity |
| `erds` | object | OPTIONAL | ERDS capability metadata (Common Service Interface, see §7.5.1.1) |
| `recipient_metadata` | object | OPTIONAL | Recipient capability preferences (Common Service Interface, see §7.5.1.2) |

#### 7.5.1.1 ERDS Capability Metadata (`erds`)

The `erds` object publishes the endpoint's ERDS service capabilities, corresponding to the Common Service Interface (CSI) defined in ETSI EN 319 522-2 §9 and EN 319 522-3 §6. This enables senders and relays to determine service compatibility *before* session establishment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `consignment_modes` | string[] | OPTIONAL | Supported consignment modes: `basic`, `consented`, `consented_signed` |
| `assurance_levels` | string[] | OPTIONAL | Identity assurance levels supported for recipient authentication: `low`, `substantial`, `high` |
| `supported_policies` | string[] | OPTIONAL | Policy URIs or OIDs this ERDS enforces (corresponding to MD05) |
| `delegation` | boolean | OPTIONAL | Whether sender/recipient delegation is supported. Default: `false` |
| `evidence_repository` | string | OPTIONAL | URL of the evidence repository API (see [wmp-evidence.md](wmp-evidence.md) §6) |
| `evidence_retention` | string | OPTIONAL | ISO 8601 duration for evidence retention (e.g., `P10Y`) |
| `scheduled_delivery` | boolean | OPTIONAL | Whether `deliver_after` (scheduled delivery) is supported. Default: `false` |

**Relay routing behavior:** Before forwarding a message to a downstream ERDS, a relay SHOULD fetch or cache the downstream's `erds` metadata from its well-known configuration and verify that:

1. The requested `consignment_mode` (§3.5) is in `consignment_modes`.
2. The requested `recipient_assurance_level` (§3.5.1) is in `assurance_levels`.
3. All `applicable_policies` from the message (§3.4) are in `supported_policies`.

If any check fails, the relay MUST reject the message with error `-31005` and `data` indicating the unsupported capability.

#### 7.5.1.2 Recipient Capability Metadata (`recipient_metadata`)

The `recipient_metadata` object publishes the endpoint's preferences as a *recipient* of messages. This enables senders to tailor messages and avoid delivery failures.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `accepted_content_types` | string[] | OPTIONAL | MIME types the recipient can process |
| `max_message_size` | integer | OPTIONAL | Maximum message body size in bytes |
| `consignment_preferences` | string | OPTIONAL | Preferred consignment mode (`basic`, `consented`, `consented_signed`). Senders SHOULD respect this unless their policy requires a different mode. |
| `encryption_required` | boolean | OPTIONAL | Whether MLS encryption is mandatory for incoming messages. Default: `false` |

> **Design rationale:** The `erds` and `recipient_metadata` objects correspond to the ETSI EN 319 522 Common Service Interface (CSI) — specifically, ERDS capabilities (EN 319 522-3 §6.3.2) and recipient capabilities (EN 319 522-3 §6.3.1). Publishing these in the well-known configuration allows pre-session compatibility checks without requiring a separate CSI protocol.

> **Design rationale:** Discovery is intentionally decoupled from trust mechanisms. A participant's WMP endpoint is found via well-known configuration regardless of whether they participate in OpenID Federation, eIDAS trust lists, or any other trust framework. Trust is established *after* connection via `identity_assertions` and `trust_hints`.

#### 7.5.2 Fallback: Session Parameters

When the primary well-known mechanism cannot be used (no extractable domain, or the identifier is session-scoped), the endpoint MUST be provided explicitly during session creation via the `endpoint` field in the participant list or out-of-band configuration.

#### 7.5.3 Profile-Extensible Resolvers

For identifier schemes that require scheme-specific resolution logic (e.g., DID Document resolution, eDelivery BDXL/SMP lookup), profiles MAY register **identifier resolvers**. A resolver maps an identifier to a WMP endpoint URL.

The discovery resolution order is:

1. **Primary (domain-based):** Extract domain → fetch `/.well-known/wmp-configuration` (§7.5.1)
2. **Resolver chain:** Profile-registered resolvers for identifier schemes without extractable domains
3. **Fallback:** Session parameters / out-of-band configuration (§7.5.2)

For DID identifiers with extractable domains (e.g., `did:web`), step 1 applies directly — the DID profile resolver (step 2) is not needed. For non-domain DIDs (e.g., `did:key`, `did:jwk`, `did:tdw`), the DID profile resolver is used.

A profile registers a resolver by declaring which identifier scheme prefixes it handles. The resolver returns the WMP endpoint URL (and optionally pre-fetched capabilities), or signals that it cannot resolve the identifier.

**Resolver interface (informative — see go-wmp `IdentifierResolver` for the Go binding):**

```
resolve(identifier: string) → { endpoint: string, capabilities?: object } | null
```

**Standard profile resolvers:**

| Profile | Scheme(s) | Resolution method |
|---------|-----------|-------------------|
| `did` (see Section 7.5.4) | `did:*` | DID Document `service` entry of type `WMPMessaging` |
| `edelivery` | `ebcore:*` | BDXL DNS U-NAPTR → SMP → WMP endpoint |

Profiles that define resolvers MUST document their resolution algorithm, failure modes, and caching behavior.

#### 7.5.4 DID Profile Resolver

For DID identifiers without an extractable domain (e.g., `did:key`, `did:jwk`, `did:tdw`), the DID Document provides a **profile-specific resolver** for endpoint discovery. This mechanism is registered as a standard profile resolver (§7.5.3).

For DID identifiers with an extractable domain (e.g., `did:web`, `did:webvh`), well-known configuration (§7.5.1) is the primary discovery mechanism. DID Document resolution MAY be used as a supplementary source but is not required.

**Resolution algorithm:**

1. Resolve the DID Document using the DID method's resolution mechanism.
2. Search the `service` array for an entry with `type` equal to `WMPMessaging`.
3. Extract the `serviceEndpoint` URL from the matching entry.
4. If no `WMPMessaging` service is found and a domain is derivable from the DID (e.g., `did:web:example.com` → `example.com`), fall back to well-known configuration (§7.5.1).
5. If no domain is derivable (e.g., `did:key`, `did:jwk`), discovery fails — the endpoint MUST be provided via session parameters (§7.5.2) or relay registration (§7.5.5).

> **Note:** For `did:web` identifiers, well-known configuration is preferred because both mechanisms derive from the same domain. The DID Document MAY be used for key discovery (below) even when endpoint discovery uses well-known configuration.

> **Privacy note:** DID Documents that encode per-user endpoint information (e.g., `did:web:wallet.example.com:users:alice` with a per-user `WMPMessaging` service entry) publicly expose the user-to-provider binding. This is a privacy violation in most wallet deployments. See §7.5.5 for the recommended architecture where endpoints are associated with wallet providers, not individual users.

**DID Document service entry:**

```json
{
  "id": "did:key:z6Mkf...#wmp",
  "type": "WMPMessaging",
  "serviceEndpoint": "wss://relay.example.com/wmp"
}
```

The service entry provides only the endpoint URL. Trust evaluation is performed independently via `identity_assertions` after session establishment.

**Key discovery via DID Document:**

When a non-repudiation signature (Section 5.4) uses a `kid` in the form of a DID URL (e.g., `did:web:alice.example.com#key-1`), the verification key is resolved by:

1. Resolving the DID Document.
2. Locating the `verificationMethod` with the matching `id`.
3. Extracting the public key material.

This is the ONLY mechanism for key discovery when `kid` is a DID URL. When `kid` uses another scheme (X.509 SKI, JWK thumbprint, HTTPS URL), the corresponding scheme-specific key resolution applies.

**MLS KeyPackage discovery via DID Document:**

Alternatively to the well-known `mls-key-packages` endpoint, a DID Document MAY include a service entry:

```json
{
  "id": "did:web:provider.example.com#mls-keys",
  "type": "MLSKeyPackages",
  "serviceEndpoint": "https://provider.example.com/.well-known/mls-key-packages"
}
```

This is functionally equivalent to the `mls_key_packages` field in the well-known configuration and is provided for DID ecosystems where the DID Document is the canonical metadata publication point. The well-known configuration is preferred when both are available.

**Relay discovery via DID Document:**

```json
{
  "id": "did:key:z6Mkf...#relay",
  "type": "WMPRelay",
  "serviceEndpoint": "wss://relay.example.com/wmp"
}
```

This is functionally equivalent to the `relay` field in the well-known configuration. This mechanism is primarily useful for `did:key` and `did:jwk` identifiers where no domain is available for well-known configuration.

#### 7.5.5 Deployment Models

Different WMP participants have different infrastructure capabilities. This section describes common deployment models and their recommended discovery approach.

> **Terminology:** A *wallet provider* is the organization that operates the wallet backend infrastructure. A *wallet unit* is a specific wallet instance belonging to a specific user. In multi-tenant deployments, the wallet provider operates the WMP endpoint; individual wallet units are reached via relaying through the provider's endpoint.

**1. Self-hosted server (issuer, verifier, enterprise)**

The participant controls a domain and runs a web server.

- **Identifier:** `x509:san:dns:example.com` (RECOMMENDED), `https://example.com`, or `did:web:example.com`
- **Discovery:** Well-known configuration at `/.well-known/wmp-configuration` (§7.5.1)
- **Authentication:** `mtls` or `x5c` with certificate containing the SAN (RECOMMENDED for server-side entities)
- **Example:** A government credential issuer at `x509:san:dns:gov-issuer.example.eu`

**2. Cloud/hybrid wallet (multi-tenant wallet provider)**

A wallet provider operates a cloud backend serving multiple users. The provider is the tenant, not the user. The binding between a user and their wallet provider is private.

- **Provider identifier:** `x509:san:dns:wallet.example.com` (RECOMMENDED) or `did:web:wallet.example.com`
- **Discovery:** Well-known configuration at `https://wallet.example.com/.well-known/wmp-configuration` — a single configuration for the entire provider, not per-user configurations
- **User routing:** The provider's relay receives incoming sessions addressed to user identifiers and routes internally to the correct wallet unit. The user's identifier appears in the `participants` field of `wmp.session.create`, but the endpoint discovered is always the provider's.
- **User identifiers:** Users MAY use `did:key` or other non-domain identifiers. Their identifier does not need to be publicly resolvable — the wallet provider knows which user identifiers it serves and routes accordingly.
- **Privacy guarantee:** No per-user DID Documents, no per-user well-known configurations, no per-user sub-path resolution. The only publicly discoverable information is the wallet provider's endpoint.

```
Sender → discovers wallet.example.com via x509:san:dns (well-known config)
       → connects to wss://wallet.example.com/wmp (provider's relay endpoint)
       → sends wmp.session.create with target user identifier in participants
       → provider's relay routes internally to the correct wallet unit
       → user↔provider binding is never exposed publicly
```

Well-known configuration for a wallet provider:

```json
{
  "supported_versions": ["0.1"],
  "endpoints": {
    "websocket": "wss://wallet.example.com/wmp"
  },
  "relay": "wss://wallet.example.com/wmp",
  "accepted_schemes": ["did", "x509", "uri"],
  "security_modes": ["mls", "tls"],
  "mls_key_packages": "https://wallet.example.com/.well-known/mls-key-packages"
}
```

> **Anti-pattern:** Publishing per-user DID Documents (e.g., `did:web:wallet.example.com:users:alice`) with `WMPMessaging` service entries publicly exposes which users are served by which wallet provider. This leaks private information and SHOULD NOT be used in production deployments. Similarly, per-user sub-path well-known configurations (`https://wallet.example.com/users/alice/.well-known/wmp-configuration`) have the same privacy problem.

**3. Mobile/native wallet (no web server)**

The wallet runs on a mobile device or desktop app with no publicly reachable HTTP server. The wallet is operated by a wallet provider that runs relay infrastructure.

- **Wallet unit identifier:** `did:key:z6Mkf...` or `did:jwk:...` (non-public, not independently discoverable)
- **Provider identifier:** `x509:san:dns:provider.example.com` (discoverable via well-known configuration)
- **Discovery:** The wallet provider's well-known configuration advertises the relay endpoint. The wallet unit registers with the provider's relay using `wmp.relay.register`. Incoming sessions addressed to the wallet unit's `did:key` identifier are routed by the relay to the wallet's persistent connection.
- **Discovery — session parameters:** Alternatively, the wallet's endpoint MAY be provided out-of-band (e.g., in an OID4VCI credential offer URL or a QR code).

```json
{
  "id": "did:key:z6Mkf...#wmp",
  "type": "WMPMessaging",
  "serviceEndpoint": "wss://provider.example.com/wmp"
}
```

> **Note:** The `did:key` identifier is appropriate here because the wallet unit has no public domain. The DID Document service entry (above) is only needed when the DID profile resolver is used for discovery. In the common case, the sender already knows the wallet provider's endpoint (via well-known configuration on the provider's domain) and the wallet unit's `did:key` is provided via session parameters or out-of-band exchange.

**4. IoT/embedded device**

- **Identifier:** X.509 device certificate (`x509:sha256:...`) or device-specific `did:key`
- **Discovery:** Relay-mediated (same as mobile wallet) or session parameters from a device management system

**5. Privacy-preserving (no public endpoint)**

Participants who do not want a discoverable WMP endpoint.

- **Identifier:** `did:key`, session-scoped `opaque`, or any identifier without a published discovery document
- **Discovery:** Endpoint is provided exclusively via session parameters during session creation. No publicly resolvable discovery metadata is published.
- **Trade-off:** Only works when the initiator already knows the participant's endpoint (e.g., from a prior interaction, invitation link, or out-of-band exchange).

### 7.6 Cross-Scheme Sessions

A WMP session MAY include participants using different identifier schemes. The protocol makes no assumption that both sides use the same identifier type — each participant is discovered and authenticated independently using its own scheme.

**Example:** A wallet provider identified by `x509:san:dns` communicating with an issuer also identified by `x509:san:dns`:

```json
{
  "wmp": {"version": "0.1", "sender": "x509:san:dns:wallet.example.com"},
  "participants": ["x509:san:dns:gov-issuer.example.eu"],
  "capabilities_offered": {
    "flows": {"max_concurrent": 5}
  },
  "security": {"mode": "tls"}
}
```

**Cross-scheme example:** A wallet unit identified by `did:key` (routed via its provider's relay) communicating with an issuer identified by `x509:san:dns`:

```json
{
  "wmp": {"version": "0.1", "sender": "did:key:z6Mkf..."},
  "participants": ["x509:san:dns:gov-issuer.example.eu"],
  "capabilities_offered": {
    "flows": {"max_concurrent": 5}
  },
  "security": {"mode": "tls"}
}
```

**Pre-connect compatibility check:** Before connecting, the initiator MAY fetch the responder's well-known configuration and verify that `accepted_schemes` includes the initiator's scheme. If not, the initiator knows the responder cannot authenticate its identifier scheme and can avoid the connection attempt.

**How discovery works in cross-scheme scenarios:**

1. **Wallet provider** (`x509:san:dns:wallet.example.com`): Extract domain `wallet.example.com` → fetch `https://wallet.example.com/.well-known/wmp-configuration`
2. **Issuer** (`x509:san:dns:gov-issuer.example.eu`): Extract domain `gov-issuer.example.eu` → fetch `https://gov-issuer.example.eu/.well-known/wmp-configuration`
3. **Wallet unit** (`did:key:z6Mkf...`): No domain extractable — endpoint is provided via session parameters or the sender knows the provider's relay endpoint from a prior exchange

Both domain-based participants use the same primary discovery mechanism (Section 7.5.1). The identifier scheme determines *authentication* — not discovery.

**How authentication works in this scenario:**

| Participant | Scheme | Authentication method |
|-------------|--------|----------------------|
| Wallet provider | `x509:san:dns` | mTLS with certificate containing the SAN, or `x5c` signed challenge |
| Wallet unit | `did:key` | Detached JWS signed with key inline in the DID |
| Issuer | `x509:san:dns` | mTLS with certificate containing the SAN, or bearer token |

Each participant authenticates using the mechanism appropriate to its own identifier scheme (Section 7.4). The responder validates the initiator's scheme during authentication (§4.4) — if the responder cannot handle the initiator's scheme, it rejects the session with error `-31002`.

**Key principle:** Discovery and authentication are per-participant, not per-session. A session is scheme-agnostic — it only requires that each participant can be discovered and authenticated by its counterparty. Scheme compatibility is checked at authentication time, not declared in session creation parameters.

## 8. Security Considerations

### 8.1 Transport Security

All WMP transports MUST use TLS 1.3 or later. Certificate validation MUST follow standard PKI practices.

### 8.2 Authentication

Session participants MUST authenticate during or immediately after session creation (Section 4.4). The authentication protocol supports inline credentials, challenge-response, and mutual authentication patterns.

**Core requirements:**

- Every active session MUST have at least one authenticated participant (the initiator).
- The responder SHOULD authenticate the initiator before accepting any application-level messages.
- For relay topologies, both the sender and the relay MUST authenticate to each other (Section 8.7).
- Authentication credentials MUST be bound to the session (via `session_id` in challenge-response signatures) to prevent cross-session replay.
- Bearer tokens MUST have bounded lifetime and appropriate audience restrictions.

Profiles MAY define additional authentication mechanisms. For example, the DID discovery profile (Section 7.5.4) enables authentication via DID Document verification keys using the `signed_challenge` auth type.

### 8.3 Authorization

Authorization is session-scoped. The session creator defines allowed participants and capabilities. Participants MUST NOT be able to escalate their own capabilities.

### 8.4 End-to-End Encryption

When the negotiated security mode is `mls` or `mls-optional`, message confidentiality and authenticity are guaranteed independently of transport security. See [wmp-mls.md](wmp-mls.md) for details.

MLS authenticates plaintext only to group members. Signatures and hashes produced outside the group bind to ciphertext. Where a third party must later be able to tie evidence to a specific plaintext, senders include the salted `plaintext_hash` commitment of §5.2.1.

In `mls-optional` mode, the `encrypted_capabilities` list determines which capabilities require MLS encryption. A message for a capability listed in `encrypted_capabilities` that arrives without MLS encryption MUST be rejected with error `-31003` (Encryption required). Messages for unlisted capabilities are protected by transport-level TLS only.

This hybrid model enables a single session to carry both:
- **Orchestration traffic** (e.g., flow steps, tool invocations) processed by the backend in plaintext over TLS
- **Relay traffic** (e.g., wallet-to-wallet messages) encrypted E2E through the same backend

### 8.5 Replay Protection

- Message `id` fields MUST be unique within a session.
- MLS epoch numbers provide additional replay protection for encrypted messages.

#### 8.5.1 Timestamp Validation

The self-asserted `timestamp` field (§3.2) MUST be validated against the receiver's local clock. The receiver MUST reject messages where the timestamp differs from the local clock by more than the configured **clock skew tolerance**.

**Default clock skew tolerance:** 30 seconds. Implementations SHOULD use this default unless deployment conditions require a different value. Profiles MAY specify a stricter tolerance.

> **Rationale:** WMP operates over persistent connections (WebSocket) or direct HTTPS — network latency is typically milliseconds. A 30-second window accommodates mobile devices with imprecise clocks while limiting the replay window. The previous 5-minute default was inherited from Kerberos-era assumptions about wide-area clock drift that do not apply to modern NTP-synchronized systems.

When a timestamp fails validation, the receiver MUST return error `-31011` with a `data` object:

```json
{
  "code": -31011,
  "message": "Timestamp invalid",
  "data": {
    "reason": "clock_skew",
    "acceptable_window_seconds": 30,
    "server_time": "2026-05-03T14:00:00Z"
  }
}
```

The `server_time` field allows the sender to diagnose and correct clock drift. Implementations SHOULD log timestamp rejections for operational monitoring.

#### 8.5.2 Timestamp Token Precedence

When both `timestamp` (self-asserted) and `timestamp_token` (RFC 3161 from a TSA) are present on a message:

1. The `timestamp_token` is **authoritative** for the message's time. The receiver validates the token against its trusted TSA list.
2. The self-asserted `timestamp` is **informational** when a token is present — it is a convenience for display and logging but is not used for replay validation.
3. The self-asserted `timestamp` MUST NOT differ from the time in the `timestamp_token` by more than the clock skew tolerance. If it does, the receiver SHOULD treat the self-asserted timestamp as unreliable but MUST NOT reject the message solely for this reason (the token is authoritative).
4. When only `timestamp` is present (no token), the self-asserted value is used for replay validation against the clock skew tolerance.

#### 8.5.3 Interaction with Message Expiry

The `expires_at` field (§3.2, §5.3.1) and `timestamp` are independent:

- A message with `timestamp` within the clock skew tolerance but `expires_at` in the past MUST be discarded (expired).
- A message with `expires_at` in the future but `timestamp` outside the clock skew tolerance MUST be rejected with `-31011`.
- For queued offline messages (§5.3.1), the `timestamp` validation is performed at queue insertion time, not at delivery time. A queued message whose `timestamp` was valid when queued is delivered without re-validating the timestamp on reconnect.

### 8.6 Rate Limiting

Implementations SHOULD enforce rate limits per participant per session. The `-31007` error code is used to signal rate limiting.

### 8.7 Session-Transport Binding

A session MUST be bound to an authenticated transport context to prevent session hijacking (an attacker who learns a `session_id` injecting messages on a different connection).

#### 8.7.1 Binding Mechanism

When a session is created, the server binds it to the authenticated identity of the transport:

| Transport | Binding mechanism |
|-----------|-------------------|
| WebSocket | The session is bound to the WebSocket connection. Only messages from the same connection (or a successfully resumed connection via §4.5) are accepted. |
| HTTPS | The session is bound to the bearer token or mTLS certificate. Each HTTP request MUST present the same credential. |
| Native messaging | The session is bound to the process identity (extension ID, socket peer credentials). |

**Invariant:** A message on session `S` is accepted only if it arrives on a transport connection authenticated as the sender identity recorded for that session.

#### 8.7.2 Connection Loss and Rebinding

When a transport connection drops:
1. The session enters a **suspended** state on the server.
2. Messages for that session are queued (subject to the `offline` capability limits — see §5.3.1). Per-message `expires_at` is respected; messages without `expires_at` use the `offline.ttl` from capability negotiation.
3. To rebind, the participant MUST use `wmp.session.resume` (§4.5) with a valid `resumption_token`.
4. The server re-authenticates the participant during resumption (the `resumption_token` serves as proof of prior authentication).
5. After successful resumption, the session is bound to the new transport connection and queued messages are delivered. The server sends `wmp.message.status` notifications with status `delivered` to senders for any queued messages that were successfully delivered on reconnect.

A `session_id` alone is NEVER sufficient to send messages — it is not a secret and MUST NOT be treated as one. The binding is to the authenticated identity, not the session ID string.

#### 8.7.3 Relay Mode Binding

In relay topology (§6.2 of wmp-transport.md), each hop has its own session-transport binding:

```
Alice ←── auth binding ──→ Relay ←── auth binding ──→ Bob
(session A-R)                      (session R-B)
```

The relay authenticates both Alice and Bob independently. The relay verifies that:
- Messages claiming `sender: alice` arrive on Alice's authenticated connection
- Messages claiming `sender: bob` arrive on Bob's authenticated connection

A relay MUST NOT forward a message where the `wmp.sender` does not match the authenticated identity of the connection it arrived on. This prevents sender spoofing through relays.

#### 8.7.4 Multiplexing Isolation

When multiple sessions share a single transport connection (§3.6 of wmp-transport.md):
- Each session retains its own independent state and security context.
- A participant authenticated for session A is NOT automatically authorized for session B on the same connection, unless session B was also created/joined on that connection.
- Session IDs from different connections MUST NOT be conflated.

### 8.8 Relay Privacy

#### 8.8.1 Threat Model

In relay topology, the relay is an active intermediary with access to:
- **Always visible:** `wmp` metadata (sender, recipient identifiers, session_id, timestamps), message sizes, timing
- **In TLS mode:** Full message content (since the relay terminates TLS)
- **In MLS mode:** Only routing metadata; message content is end-to-end encrypted

The relay is trusted for availability (message delivery) but minimally trusted for confidentiality and integrity. The following threats apply:

| Threat | MLS mode | TLS mode |
|--------|----------|----------|
| Content interception | Protected | **Exposed** |
| Metadata collection (who talks to whom, when, frequency) | **Exposed** | **Exposed** |
| Sender/recipient correlation | **Exposed** | **Exposed** |
| Message injection | Protected (MLS authenticates senders) | **Possible** without additional signatures |
| Selective message dropping | **Possible** (detectable via evidence profile) | **Possible** |
| Traffic analysis (timing, size) | **Exposed** | **Exposed** |

#### 8.8.2 Relay Obligations

A relay implementation MUST:
- Authenticate all connected participants before routing messages
- Verify `wmp.sender` matches the authenticated identity on the connection (§8.7.3)
- Not modify message content in transit (integrity)
- Forward all messages for active sessions without selective dropping (unless rate-limited)

A relay implementation MUST NOT:
- Log or retain message content beyond what is necessary for queuing (unless operating as an evidence relay under the evidence profile)
- Correlate identifiers across sessions unless required by law

A relay implementation SHOULD:
- Minimize metadata retention (RECOMMENDED: retain only routing state for active sessions)
- Support configurable retention policies
- Provide a machine-readable privacy policy at `/.well-known/wmp-configuration`:

```json
{
  "privacy": {
    "metadata_retention": "session_only",
    "content_retention": "none",
    "logging_policy": "https://relay.example.com/privacy"
  }
}
```

#### 8.8.3 Mitigations

**For content confidentiality:** Use `mls` or `mls-optional` security mode. MLS ensures the relay cannot read message content.

**For metadata privacy:** The following mitigations reduce metadata exposure:

1. **Padding** — Implementations SHOULD pad messages to fixed size buckets (e.g., 1KB, 4KB, 16KB, 64KB) to resist size-based traffic analysis.
2. **Batching** — Relay implementations MAY batch-forward messages at regular intervals rather than immediately, reducing timing correlation.
3. **Identifier opacity** — Future versions of WMP may define a mechanism for participants to use ephemeral relay-visible identifiers that are unlinkable across sessions.

**For integrity:** Use non-repudiation signatures (§5.4) on messages traversing relays. In relay mode without MLS, signatures are the primary defense against relay-injected messages.

**For availability:** The evidence profile ([wmp-evidence.md](wmp-evidence.md)) provides signed delivery receipts that detect selective message dropping by relays.

#### 8.8.4 Relay Selection Trust

Participants SHOULD choose relays operated by entities they trust. The well-known configuration's `relay` field is self-declared — a participant chooses their own relay. Trust in the *counterparty's* relay is implicit: by communicating with a participant, you accept that their chosen relay will handle routing metadata.

For high-security contexts, both parties MAY negotiate to use a mutually trusted relay via the `relay` capability parameter, or use direct topology to avoid relays entirely.

### 8.9 JSON Canonicalization Security

WMP uses JCS (RFC 8785) for canonicalizing content objects before signing (§5.4, §5.7) and in authentication challenge-response (§4.4). While JCS is well-specified, the following risks arise from implementation variance:

**Number precision divergence.** JSON has no integer/float type distinction. Different parsers may represent the same JSON number differently — for example, JavaScript's `JSON.parse` truncates integers beyond $2^{53} - 1$ while Go's `json.Number` preserves arbitrary precision. This produces different canonical forms and causes signature verification failures. WMP mitigates this by requiring signed content to stay within the IEEE 754 safe integer range (§5.4).

**Duplicate key ambiguity.** RFC 8259 recommends unique JSON keys but does not forbid duplicates. When duplicates are present, different parsers retain different values, producing different canonical output from identical input. WMP mitigates this by requiring duplicate key rejection (§5.4).

**Unicode normalization variance.** JCS does not normalize Unicode — it preserves the exact byte sequence. Two strings that are canonically equivalent under NFC/NFD (e.g., `"é"` as U+00E9 vs. U+0065 U+0301) produce different JCS output and therefore different signature inputs. This is by design: JCS is a byte-level canonicalization. Implementations MUST NOT apply Unicode normalization during canonicalization. Content that requires cross-platform string equivalence SHOULD use pre-composed (NFC) form or ASCII-safe encoding.

**Mitigation summary:**

| Risk | Mitigation | Reference |
|------|------------|-----------|
| Number precision | Safe integer range constraint | §5.4 |
| Duplicate keys | Reject before canonicalization | §5.4 |
| Unicode normalization | No normalization; prefer ASCII-safe fields | §5.4 |
| Non-compliant libraries | Require RFC 8785 test suite compliance | §5.4 |
| Cross-implementation drift | WMP canonicalization test vectors | Companion document |

### 8.10 Notification Authentication

WMP uses JSON-RPC 2.0 notifications (messages with no `id` field, expecting no response) for several methods: `wmp.message.deliver`, `wmp.flow.progress`, `wmp.flow.complete`, `wmp.flow.error`, `wmp.flow.cancel`, `wmp.message.status`, and `wmp.message.ack`. The authentication guarantees for notifications differ by topology.

#### 8.10.1 Direct Topology

In direct topology, every notification arrives on a transport connection that is bound to an authenticated identity (§8.7.1). The recipient can trust that the `wmp.sender` is authentic because the transport binding was established during session creation. This provides the same authentication assurance as request-response messages.

#### 8.10.2 Relay Topology

In relay topology, the relay authenticates each participant independently and verifies that `wmp.sender` matches the authenticated identity of the originating connection (§8.7.3). However, the recipient has no independent cryptographic proof that the relay faithfully forwarded the notification — the relay is a trusted intermediary. This means:

1. **Participant-originated notifications** (e.g., `wmp.flow.progress`, `wmp.flow.complete`, `wmp.flow.cancel`): The relay is trusted to verify the sender's identity before forwarding. A compromised relay could forge or modify these notifications. This is consistent with the relay trust model described in §8.8.4.

2. **Server-originated notifications** (e.g., `wmp.message.status`): These are generated by the recipient's infrastructure, not by the remote participant. In relay mode, the relay itself may generate delivery status notifications. The sender trusts these to the extent it trusts the relay.

**Mitigations:**

- **Non-repudiation signatures (§5.4):** The `wmp.signature` field is valid on any WMP message, including notifications. For sessions operating through untrusted relays without MLS, implementations SHOULD apply non-repudiation signatures to flow lifecycle notifications (`wmp.flow.progress`, `wmp.flow.complete`, `wmp.flow.error`, `wmp.flow.cancel`). Recipients SHOULD verify these signatures when present.
- **MLS end-to-end encryption:** When MLS is active, all messages — including notifications — are authenticated end-to-end. A relay cannot forge notifications within the MLS group. This is the strongest mitigation.
- **Flow cancel authorization:** Only the flow initiator or participants named in the `wmp.flow.start` request are authorized to send `wmp.flow.cancel` for that flow. Unauthorized cancel attempts MUST be rejected with `-31002` (Not authorized).

#### 8.10.3 Topology-Aware Implementation Guidance

| Topology | Notification assurance | Recommended mitigation |
|----------|----------------------|----------------------|
| Direct | Authenticated by transport binding | None needed |
| Relay (MLS) | End-to-end authenticated | None needed |
| Relay (TLS only) | Trusted to relay's integrity | Non-repudiation signatures on flow notifications |

Implementations that operate in relay mode without MLS SHOULD treat flow lifecycle notifications as advisory until confirmed by application-level state (e.g., verifying that a credential delivered via `wmp.flow.complete` is actually valid).

### 8.11 Discovery Metadata Integrity

The well-known configuration document (§7.5.1) is served as plain JSON over HTTPS. Its integrity depends on the TLS connection to the domain and the trustworthiness of the domain's DNS resolution. This is the same trust model used by OpenID Connect Discovery, OAuth Authorization Server Metadata, and similar protocols.

**Threats:**

- **DNS or BGP hijacking** combined with certificate misissuance could allow an attacker to serve a malicious configuration pointing to attacker-controlled endpoints or relays.
- **CDN or reverse proxy compromise** could alter the configuration in transit between the origin server and the client.
- **Cache poisoning** could serve stale or modified configurations after endpoint rotation.

**Existing mitigations:**

| Mechanism | Protection |
|-----------|------------|
| TLS (HTTPS) | Integrity and confidentiality in transit |
| DNSSEC | Prevents DNS spoofing (when deployed) |
| CAA records | Constrains certificate issuance to authorized CAs |
| Certificate Transparency | Detects unauthorized certificate issuance |

**Recommendations:**

- Deployments SHOULD use DNSSEC and CAA records to strengthen domain-based discovery. Combined with Certificate Transparency monitoring, this provides strong integrity guarantees for well-known configuration documents without requiring additional metadata infrastructure.
- Trust frameworks such as OpenID Federation define signed entity statements that can carry WMP endpoint metadata with hierarchical trust chains. Profiles MAY specify OpenID Federation as a metadata integrity mechanism.
- Implementations SHOULD apply standard HTTP cache validation (ETags, `Cache-Control`) and SHOULD NOT cache well-known configurations beyond their declared freshness lifetime.
- The DID profile resolver (§7.5.4) provides an alternative discovery path for DID identifiers. However, the integrity guarantees of DID Documents depend on the specific DID method — `did:web` has the same HTTPS/DNS trust model as well-known configuration and does not provide additional integrity.

### 8.12 Participant Revocation Mid-Session

WMP core does not define a mechanism for removing a single participant from an active session without closing it. This section documents the gap and the available mitigations.

**Two-party sessions:** The common WMP pattern is a bilateral session (wallet ↔ issuer, wallet ↔ verifier). In this case, removing one participant is equivalent to closing the session. Implementations SHOULD use `wmp.session.close` with reason `error` or `user_cancelled` when a counterparty's credentials are revoked or trust is lost.

**Multi-party sessions with MLS:** When MLS is active, `wmp.mls.group.remove` ([wmp-mls.md](wmp-mls.md) §3.4) cryptographically excludes a participant from the group. After removal, the participant can no longer decrypt new messages. This is the primary mechanism for mid-session revocation in multi-party deployments. Implementations that detect credential revocation (e.g., via CRL, OCSP, or status list checks) SHOULD issue `wmp.mls.group.remove` promptly.

**Multi-party sessions without MLS:** No WMP-defined removal mechanism exists. Implementations requiring this capability SHOULD either:
1. Adopt MLS (`mls` or `mls-optional` security mode) to gain `wmp.mls.group.remove`, or
2. Close the session and recreate it without the revoked participant.

**Credential revocation detection:** WMP does not mandate continuous credential status monitoring during sessions. Implementations operating in regulated environments (e.g., eIDAS, PSD2) SHOULD define credential freshness requirements in their profile specification, including how often to check revocation status and the required response when revocation is detected.

> **Future work:** A future version of WMP may define `wmp.session.remove` and `wmp.session.leave` methods with proper authorization semantics, notification to remaining participants, and interaction with active flows. Profiles requiring these semantics before standardization MAY define them under a profile-specific namespace.

## 9. Extensibility

### 9.1 Namespace Conventions

WMP uses dot-separated namespaces for both methods and capabilities. The following prefixes are reserved:

| Prefix | Owner | Specification |
|--------|-------|---------------|
| `wmp.*` | WMP Core | This document |
| `oid4vci.*` | WMP OpenID4x Profile | [wmp-openid4x.md](wmp-openid4x.md) |
| `oid4vp.*` | WMP OpenID4x Profile | [wmp-openid4x.md](wmp-openid4x.md) |
| `evidence.*` | WMP Evidence Profile | [wmp-evidence.md](wmp-evidence.md) |
| `edelivery.*` | WMP eDelivery Profile | [wmp-edelivery.md](wmp-edelivery.md) |
| `mcp.*` | WMP Agent capability | This document |

Applications and private extensions SHOULD use reverse-domain notation to avoid collisions:

```
org.acme.invoice.submit
com.example.wallet.backup
io.siros.registry.lookup
```

Short prefixes without reverse-domain notation (e.g., `wallet.*`) are acceptable for community-adopted namespaces but carry collision risk. Implementations MUST NOT use the `wmp.*` prefix for custom methods or capabilities.

### 9.2 Custom Methods

Applications MAY define custom methods under their own namespace. Custom methods participate in normal capability negotiation — the capability under which a custom method operates MUST be negotiated before use.

### 9.3 Custom Capabilities

Custom capabilities follow the same pattern as standard capabilities and are declared during session creation. The capability name SHOULD match the method namespace it governs.

### 9.4 Protocol Extensions

Protocol extensions are registered via capability negotiation and MUST be documented with their own specification.

### 9.5 Extension Members

Optional members MAY be added to the `params` and `result` objects of existing methods, flow types, flow steps and actions, and to other protocol objects, without changing the WMP protocol version (Section 2.2) and without a new capability. Such a member is an **extension member**. The following rules make this safe between peers that implement different revisions of a profile.

1. **Receivers ignore unknown members.** A receiver MUST ignore any member of a protocol object that it does not understand: it MUST NOT reject the message, and MUST NOT treat the member as an error, because of it. A receiver that forwards an object it did not originate SHOULD forward unknown members unchanged.
2. **Senders do not depend on understanding.** A sender MUST NOT require its peer to understand an extension member, and MUST be able to complete the exchange correctly if the member is dropped, unless the feature is negotiated: if the peer's understanding is needed for correctness or safety (for example, because dropping the member would silently change what the user is asked to approve), the member MUST be gated by a capability negotiated under Section 4.2, and the sender MUST NOT send it to a peer that did not offer that capability. The `transaction_data` capability of the OpenID4x profile is an example.
3. **Optional means omitted, not null.** An extension member that has no value MUST be omitted. A receiver MUST treat an absent member as "not supplied", and SHOULD treat an explicit `null` for an extension member the same way unless its definition says otherwise.
4. **Opaque values stay opaque.** An extension member that carries an object defined elsewhere (for example an OpenID4VP `client_metadata` object) is carried verbatim: an intermediary MUST NOT add, remove or reorder its members.
5. **Naming.** A member name without a prefix is defined by this specification or by a WMP profile, and is listed in that document's extension table (for example Section 7 of [wmp-openid4x.md](wmp-openid4x.md)); adding a row to that table is a MINOR revision of the document that does not change the protocol version. Names defined outside WMP follow Section 9.1: a private or application-specific member MUST use a reverse-domain prefix (`org.acme.risk_score`) and MUST NOT use a prefix reserved in Section 9.1. A member name MUST NOT be reused with a different meaning.
6. **Version and capability interplay.** Neither the protocol version nor a capability version is raised for a purely additive, ignorable member. A capability `versions` entry (for example `transaction_data`) is raised only when a peer must change behavior to remain correct, as in rule 2.
7. **Schemas are open.** The published JSON Schemas (`schema/`) do not set `additionalProperties: false` on protocol objects, so a message carrying an extension member validates. Schemas remain strict for required members and constrained values (`required`, `enum`, `const`, `type`, `pattern`, `minimum`). The one `additionalProperties` keyword that remains, on the capabilities map, requires each custom capability value to be an object.

## 10. Conformance

### 10.1 Conformance Levels

- **WMP Basic** — JSON-RPC 2.0 envelope, session lifecycle, message delivery. Security mode `tls` only.
- **WMP Secure** — WMP Basic plus security modes `mls` and `mls-optional`. Capability-driven encryption.
- **WMP Flows** — WMP Basic plus structured flows (`sign`, `approval`, `message`) and the `flows` capability.
- **WMP Agent** — WMP Basic plus `mcp` capability for MCP-compatible tool/resource access.
- **WMP Registered** — WMP Secure plus evidence profile (`evidence` capability), non-repudiation signatures, and trusted timestamping.

Profile-specific conformance levels (e.g., OpenID4x Wallet, ERDS) are defined in their respective profile documents.

### 10.2 Required Support

All WMP implementations MUST support:
- JSON-RPC 2.0 message parsing and generation
- At least one transport binding
- Session lifecycle methods (`wmp.session.create`, `wmp.session.close`)
- Capability negotiation (`capabilities_offered` / `capabilities` exchange)
- Security mode negotiation (at minimum `tls` mode)
- Error code handling

### 10.3 Capability Negotiation Requirements

All implementations MUST reject requests for capabilities that were not negotiated during session creation or via `wmp.capability.update` with error `-31005` (Capability not supported). A `wmp.flow.start` whose `flow_type` the implementation does not know is such a request (Section 3.8.1, item 2).

All implementations MUST reject messages that violate the negotiated security mode (e.g., unencrypted messages for capabilities listed in `encrypted_capabilities`) with error `-31003` (Encryption required).

## 11. IANA Considerations

This document does not currently define any IANA registries. When WMP progresses toward standardization, the following registries are anticipated:

### 11.1 WMP Method Namespace Registry

A registry of method namespace prefixes, each with:
- **Prefix:** The dot-separated namespace (e.g., `wmp.*`)
- **Owning specification:** Reference to the defining document
- **Contact:** Responsible party
- **Registration policy:** Specification Required (for short prefixes) or First Come First Served (for reverse-domain prefixes)

### 11.2 WMP Capability Registry

A registry of standard capability names, each with:
- **Name:** The capability identifier (e.g., `messaging`, `flows`, `evidence`)
- **Owning specification:** Reference to the defining document
- **Parameters:** Schema of the capability's negotiation parameters
- **Registration policy:** Specification Required

### 11.3 WMP Error Code Registry

A registry of WMP-specific error codes (the -31xxx range), each with:
- **Code:** The numeric error code
- **Name:** Human-readable name
- **Owning specification:** Reference to the defining document
- **Registration policy:** Standards Action

### 11.4 WMP Authentication Scheme Registry

A registry of authentication scheme types (§4.4), each with:
- **Type:** The scheme identifier (e.g., `bearer`, `dpop`, `mtls`, `did_auth`)
- **Owning specification:** Reference to the defining document
- **Registration policy:** Specification Required

> **Note:** Until formal IANA registration is pursued, the namespace conventions in §9.1 and the reserved prefixes table serve as the de facto registry. Profile authors SHOULD coordinate namespace claims via the WMP specification repository.

## References

- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [RFC 9420 — The Messaging Layer Security (MLS) Protocol](https://www.rfc-editor.org/rfc/rfc9420)
- [RFC 8785 — JSON Canonicalization Scheme (JCS)](https://www.rfc-editor.org/rfc/rfc8785)
- [RFC 3161 — Internet X.509 PKI Time-Stamp Protocol](https://www.rfc-editor.org/rfc/rfc3161)
- [RFC 7515 — JSON Web Signature (JWS)](https://www.rfc-editor.org/rfc/rfc7515)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [ETSI EN 319 522-1 — Electronic Registered Delivery Services](https://www.etsi.org/deliver/etsi_en/319500_319599/31952201/)

## Profiles

- [WMP OpenID4x Profile](wmp-openid4x.md) — OID4VCI and OID4VP flows
- [WMP Evidence Profile](wmp-evidence.md) — Registered delivery evidence and receipts
- [WMP eDelivery Profile](wmp-edelivery.md) — eDelivery/SMP/BDXL integration and organizational discovery

# WMP MLS Integration

## Wallet Messaging Protocol — MLS Encryption Layer

**Status:** Draft  
**Version:** 0.1.0  
**Date:** 2026-04-29

## 1. Overview

WMP uses the Messaging Layer Security (MLS) protocol (RFC 9420) for end-to-end encryption in multi-party sessions. MLS provides:

- **Forward secrecy** — Compromise of current keys does not reveal past messages.
- **Post-compromise security** — The protocol recovers security after key compromise.
- **Scalable group management** — Efficient key agreement for groups of any size.
- **Sender authentication** — Each message is authenticated to its sender.

MLS is OPTIONAL for WMP sessions. Point-to-point sessions MAY rely on transport-level TLS instead. MLS is RECOMMENDED for multi-party sessions and any session where end-to-end encryption is required.

## 2. MLS Configuration

### 2.1 Cipher Suite

WMP implementations MUST support:

- **MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519** (0x0001)

WMP implementations SHOULD support:

- **MLS_128_DHKEMP256_AES128GCM_SHA256_P256** (0x0002)

### 2.2 Credential Type

MLS requires each group member to present a credential that binds their identity to their leaf node key. WMP supports multiple MLS credential types to match the identifier scheme in use:

| WMP Identifier Scheme | MLS Credential Type | Identity Binding |
|-----------------------|--------------------|-----------------|
| `did` | `basic` or `x509` | DID string as identity; or X.509 cert with DID in SAN URI |
| `x509` / `x509-san` / `x509-dn` | `x509` | X.509 certificate chain; identity from subject/SAN |
| `uri` | `basic` | HTTPS URI as identity; trust optionally verified via OpenID Federation entity statements or TLS |
| `mdoc` | `x509` | IACA-issued certificate chain |
| `opaque` | `basic` | Opaque session-scoped string as identity |

**`x509` credential type** — The X.509 certificate chain is included in the MLS credential. Validation follows the trust anchor rules for the identifier scheme (eIDAS trust list for EUDI, IACA for mdoc, PKI CA for general X.509).

**`basic` credential type** — The identity field contains the participant's WMP identifier string. Authentication is performed outside MLS (e.g., via OpenID Federation entity statement verification, DID Document key verification, or bearer token validation during session creation). The MLS credential binds the authenticated identity to the leaf node key.

When participants in the same MLS group use different identifier schemes, each participant uses the MLS credential type appropriate for their scheme. The group creator MUST advertise accepted credential types during group creation:

```json
{
  "jsonrpc": "2.0",
  "id": "mls-create-1",
  "method": "wmp.mls.group.create",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "group_id": "<base64url-encoded group ID>",
    "cipher_suite": 1,
    "accepted_credential_types": ["x509", "basic"],
    "accepted_identity_schemes": ["did", "x509", "uri"],
    "group_info": "<base64url-encoded GroupInfo>",
    "welcomes": {
      "did:key:z6MkfBob...": "<base64url-encoded Welcome>",
      "x509:san:dns:org.example.eu": "<base64url-encoded Welcome>"
    }
  }
}
```

### 2.3 Key Packages

Participants publish MLS KeyPackages at a well-known endpoint:

**Well-known endpoint:**
```
GET /.well-known/mls-key-packages
```

**Response:**
```json
{
  "key_packages": [
    {
      "id": "kp-001",
      "cipher_suite": 1,
      "key_package": "<base64url-encoded MLS KeyPackage>",
      "expires": "2026-05-29T00:00:00Z"
    }
  ]
}
```

The well-known configuration document (see wmp-core.md Section 7.5.1) advertises this endpoint via the `mls_key_packages` field. Profiles MAY define alternative KeyPackage publication mechanisms (e.g., the DID discovery profile defines a `MLSKeyPackages` DID Document service entry; see wmp-core.md Section 7.5.4).

## 3. Group Lifecycle

### 3.1 Group Creation

When a session with `"encryption": "mls"` is created, the initiator:

1. Creates a new MLS group.
2. Fetches KeyPackages for all initial participants.
3. Generates Welcome messages for each participant.
4. Distributes the Welcome messages and GroupInfo.

```json
{
  "jsonrpc": "2.0",
  "id": "mls-create-1",
  "method": "wmp.mls.group.create",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "group_id": "<base64url-encoded group ID>",
    "cipher_suite": 1,
    "group_info": "<base64url-encoded GroupInfo>",
    "welcomes": {
      "did:key:z6MkfBob...": "<base64url-encoded Welcome>",
      "did:key:z6MkfCarol...": "<base64url-encoded Welcome>"
    }
  }
}
```

### 3.2 Joining a Group

A participant joins by processing the Welcome message:

```json
{
  "jsonrpc": "2.0",
  "id": "mls-join-1",
  "method": "wmp.mls.group.join",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "did:key:z6MkfBob..."},
    "welcome_processed": true
  }
}
```

### 3.3 Adding Participants

```json
{
  "jsonrpc": "2.0",
  "id": "mls-add-1",
  "method": "wmp.mls.group.add",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:wallet.example.com"},
    "participant": "did:key:z6MkfDave...",
    "commit": "<base64url-encoded MLS Commit>",
    "welcome": "<base64url-encoded Welcome>"
  }
}
```

### 3.4 Removing Participants

```json
{
  "jsonrpc": "2.0",
  "id": "mls-remove-1",
  "method": "wmp.mls.group.remove",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:wallet.example.com"},
    "participant": "did:key:z6MkfCarol...",
    "commit": "<base64url-encoded MLS Commit>"
  }
}
```

### 3.5 Key Updates

Participants SHOULD perform regular key updates for post-compromise security:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.mls.group.update",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "x509:san:dns:wallet.example.com", "epoch": 4},
    "commit": "<base64url-encoded MLS Commit>"
  }
}
```

## 4. Message Encryption

### 4.1 Plaintext to Ciphertext

When MLS is active, the message content fields (everything in `params` except the `wmp` metadata object) form the plaintext input to MLS. The JSON-RPC envelope is never encrypted — it always remains the outermost transport frame.

```
┌──────────────────────────────────────────────┐
│ Plaintext: content fields as JSON object      │
│ {"to":[...],"content_type":"...","body":{}}   │
└──────────────┬───────────────────────────────┘
               │ UTF-8 encode → MLS encrypt (epoch key)
               ▼
┌──────────────────────────────────┐
│ MLS MLSMessage (ciphertext)      │
│ <binary>                         │
└──────────────┬───────────────────┘
               │ base64url encode
               ▼
┌──────────────────────────────────────────────┐
│ JSON-RPC envelope (always plaintext framing)  │
│ {"jsonrpc":"2.0",                             │
│  "method":"wmp.message.deliver",              │
│  "params":{"wmp":{..., "encrypted":true,      │
│                   "epoch":3},                 │
│            "ciphertext":"<base64url>"}}        │
└──────────────────────────────────────────────┘
```

The `method` field in the outer envelope indicates what kind of message this is (e.g. `wmp.message.deliver`). The actual content (recipients, body, flow data, etc.) is inside the ciphertext and opaque to relays.

### 4.2 Base64url Encoding

The MLS `MLSMessage` binary output is encoded as base64url (RFC 4648 §5, no padding) for inclusion in the JSON-RPC text envelope. This ensures all transports (WebSocket text frames, HTTPS, native messaging) can carry encrypted messages uniformly without requiring binary frame support.

### 4.3 Encryption Scope

The following fields are encrypted (inside the MLS ciphertext):
- `to` (recipients)
- `content_type`
- `body`
- Any other content fields in `params` (flow data, action params, etc.)
- `salt` (when the sender uses the plaintext commitment of [wmp-core.md](wmp-core.md) §5.2.1)
- For responses: `result` or `error`

The following fields remain in plaintext (in the outer JSON-RPC envelope, for routing):
- `jsonrpc`
- `method`
- `id` (for request/response correlation)
- `wmp.version`
- `wmp.session_id`
- `wmp.encrypted`
- `wmp.epoch`
- `wmp.sender`
- `plaintext_hash` (optional salted commitment to the plaintext, [wmp-core.md](wmp-core.md) §5.2.1) — it must stay outside the ciphertext so that relays and evidence generators can cover it with their signatures and hashes

## 5. Delivery Service

### 5.1 Role

In MLS terminology, the Delivery Service (DS) is responsible for:
- Distributing MLS handshake messages (Welcome, Commit, etc.)
- Routing encrypted application messages to group members
- Storing and forwarding messages for offline participants

### 5.2 WMP Relay

A WMP relay is a server that acts as the Delivery Service. It:

1. Maintains WebSocket connections to online participants.
2. Queues messages for offline participants.
3. Forwards MLS handshake messages.
4. Does NOT have access to plaintext (E2E encryption).

The relay processes only the plaintext `wmp` metadata for routing. The encrypted payload is opaque to the relay.

### 5.3 Relay Discovery

Relays are discovered via:
- Well-known configuration: `relay` field in `/.well-known/wmp-configuration`
- Profile-specific resolvers (e.g., the DID discovery profile defines a `WMPRelay` DID Document service type; see wmp-core.md Section 7.5.4)

### 5.4 Message Queuing

The relay queues messages for offline participants. When a participant reconnects:

```json
{
  "jsonrpc": "2.0",
  "id": "fetch-1",
  "method": "wmp.message.fetch",
  "params": {
    "wmp": {"version": "0.1", "sender": "did:web:bob.example.com"},
    "since_epoch": 2,
    "sessions": ["ses-a1b2c3d4"]
  }
}
```

**Result:**

```json
{
  "jsonrpc": "2.0",
  "id": "fetch-1",
  "result": {
    "messages": [
      {"wmp": {..., "encrypted": true, "epoch": 3}, "ciphertext": "..."},
      {"wmp": {..., "encrypted": true, "epoch": 3}, "ciphertext": "..."}
    ],
    "has_more": false
  }
}
```

## 6. Authentication Service

### 6.1 Role

The MLS Authentication Service (AS) validates participant credentials. In WMP, this maps to:

- Verifying identifier control (scheme-specific authentication; see wmp-core.md Section 7.4)
- Validating X.509 certificates in MLS credentials
- Checking trust lists for organizational participants

### 6.2 Integration with Trust Framework

WMP leverages the existing trust infrastructure:

- **Trust lists** — Organizational participants verified against trust lists
- **Identifier resolution** — Scheme-specific resolution (e.g., DID resolution for `did:*` identifiers via the DID discovery profile)
- **Key attestation** — Hardware-bound keys verified via attestation

## 7. Security Considerations

### 7.1 Relay Trust Model

The relay is an untrusted intermediary. It handles routing and queuing but cannot read encrypted content. Participants MUST verify MLS group membership independently.

### 7.2 Key Package Freshness

Key packages have a limited validity period. Participants MUST regularly publish fresh key packages. The recommended validity period is 30 days.

### 7.3 Forward Secrecy Window

MLS provides forward secrecy at the epoch boundary. Frequent key updates reduce the window of vulnerability. Implementations SHOULD trigger a key update after every N messages (recommended: 100) or T time (recommended: 1 hour), whichever comes first.

### 7.4 Metadata Privacy

The `wmp` metadata (session ID, sender, timestamp) is visible to the relay. Implementations concerned with metadata privacy SHOULD use anonymous session IDs and minimize metadata exposure.

The optional `plaintext_hash` field ([wmp-core.md](wmp-core.md) §5.2.1) is also visible to the relay. It is salted with at least 128 bits of fresh randomness carried inside the ciphertext, so it does not let a relay confirm a guessed plaintext. Senders MUST NOT omit or reuse the salt.

## 8. Post-Quantum Cryptography

### 8.1 Migration Path

MLS is well-positioned for post-quantum cryptography (PQC) migration. The cipher suite negotiation mechanism allows new PQC cipher suites to be adopted without protocol changes — only configuration updates are needed.

This is a structural advantage over AS4/ebXML, where PQC migration requires new XML-DSIG algorithm identifiers, changes to the XML canonicalization pipeline, and client library updates across the ecosystem.

### 8.2 PQC Cipher Suites

When IETF assigns MLS cipher suite identifiers for PQC algorithms, WMP implementations SHOULD support them. The anticipated cipher suites are:

| Cipher Suite | KEM | AEAD | Hash | Signature | Status |
|-------------|-----|------|------|-----------|--------|
| TBD | ML-KEM-768 | AES-256-GCM | SHA-384 | ML-DSA-65 | Awaiting IETF assignment |
| TBD | X25519+ML-KEM-768 (hybrid) | AES-256-GCM | SHA-384 | Ed25519+ML-DSA-65 (hybrid) | Awaiting IETF assignment |

### 8.3 Hybrid Transition Strategy

WMP deployments SHOULD follow a three-phase migration:

1. **Phase 1 — Algorithm-agile foundation (current):** Deploy with classical cipher suites (X25519, Ed25519). Ensure cipher suite selection is configuration-driven, not hard-coded. Publish MLS KeyPackages for multiple cipher suites.

2. **Phase 2 — Hybrid operation:** When PQC cipher suites are standardized, add hybrid cipher suites (classical + PQC in parallel) to KeyPackages and session creation offers. MLS cipher suite negotiation ensures backward compatibility — peers that don't support hybrid fall back to classical. Non-repudiation signatures (Section 5.4 of [wmp-core.md](wmp-core.md)) transition to ML-DSA or hybrid signing.

3. **Phase 3 — PQC primary:** PQC cipher suites become the default. Classical-only cipher suites are deprecated. Evidence signatures (see [wmp-evidence.md](wmp-evidence.md)) are issued exclusively with PQC algorithms.

### 8.4 Key Size Considerations

PQC algorithms produce significantly larger keys and signatures:

| Algorithm | Public Key | Signature/Ciphertext |
|-----------|-----------|---------------------|
| Ed25519 (current) | 32 bytes | 64 bytes |
| ML-DSA-65 (PQC) | 1,952 bytes | 3,309 bytes |
| X25519 (current) | 32 bytes | — |
| ML-KEM-768 (PQC) | 1,184 bytes | 1,088 bytes |

This impacts MLS KeyPackage sizes, Welcome messages, and Commit messages. Implementations MUST increase message size limits accordingly. The default 64 KiB limit (Section 2.3 of [wmp-transport.md](wmp-transport.md)) is sufficient for PQC-sized messages, but implementations SHOULD monitor actual message sizes during hybrid operation.

### 8.5 Timestamp and Evidence Implications

RFC 3161 timestamp tokens and evidence signatures (see [wmp-evidence.md](wmp-evidence.md)) must also transition to PQC algorithms. Since these are long-lived artifacts (potentially retained for years for legal evidence), the transition to PQC for evidence signing is MORE urgent than for ephemeral MLS encryption. Implementations SHOULD adopt hybrid evidence signatures in Phase 2.

## 9. The `did:mls` Method — the Group as an Audience Identifier

### 9.1 The Method

The method name is `mls`. The identifier is:

```
did:mls:<group_id>
```

where `<group_id>` is the group identifier this specification already defines (Section 3.1's `group_id`, the base64url-encoded MLS GroupId). The method-specific identifier is exactly the group's own identifier — no transformation, no namespace, no additional structure.

`did:mls` is a **naming method**: it names the MLS group an artifact is addressed to, inside a `client_id` scheme the OpenID4VP ecosystem already parses. It requires **no DID document, no resolution, and carries no key material**. The verifier's authenticity in a request whose `client_id` is a `did:mls` identifier is established exactly as for any other request — the request object's signature against its certificate chain and the verifier trust evaluation ([wmp-openid4x.md](wmp-openid4x.md) Section 7.4) — and never through the DID.

### 9.2 The Audience Binding

In an acceptance presentation whose request carries `client_id = did:mls:<group_id>`, the wallet's key binding JWT carries `aud = did:mls:<group_id>` (OpenID4VP 1.0 binds the key binding JWT's `aud` to the request's `client_id`): the presentation is **for the group**. The recipient's acceptance gate reads the `aud` and correlates the presentation to the consignment group unambiguously — the group identifier cannot be mistaken for a verifier identity, a DNS name, or a certificate hash, because the method name says what it is.

### 9.3 Why No Resolution

The protocol already verifies everything that needs verifying:

- the request's signature — the certificate chain in the request object's `x5c` header, verified before any client_id scheme processing;
- the verifier's trust — the policy evaluation over the verified chain;
- the group's membership and keys — the MLS layer's own machinery (KeyPackages, credentials, epochs — Sections 2 and 3).

A DID-document key resolution would duplicate none of this. The identifier is a name; the keys are elsewhere; the layer that needs them already has them. A wallet MUST NOT attempt to resolve a `did:mls` identifier, and a resolver MUST NOT be required to answer it.

### 9.4 The Session–Group Mapping

A consignment session (`ses-…`, WMP Core's session identifier) runs in exactly one MLS group. The relay that hosts the session knows the mapping. A wallet that needs to know which group a session's presentations belong to learns it from the flow, not from the identifier: the `aud` names the group directly, and the session correlation rides the `nonce` (the session's challenge) beside it.

# WMP Use Cases and Flow Mapping

## Wallet Messaging Protocol — Use Cases

**Status:** Draft  
**Version:** 0.1.0  
**Date:** 2026-04-29

## 1. Overview

This document describes how WMP supports various messaging use cases across wallet-to-wallet, human-to-agent, human-to-organization, and multi-party scenarios. Implementation-specific migration guides for existing wallet systems are maintained in their respective repositories.

## 2. Human-to-Human Messaging

### 3.1 Overview

Two wallet holders communicate directly through their wallet applications. Messages are E2E encrypted via MLS.

### 2.2 Session Establishment

Alice wants to message Bob. Both have wallets managed by wallet providers. Alice's wallet is hosted by `wallet-a.example.com` and Bob's by `wallet-b.example.com`. Each user's wallet unit uses a `did:key` identifier; discovery routes through the provider's relay.

```
Alice's Wallet          Relay           Bob's Wallet
      │                   │                   │
      │── wmp.session.create ──>│             │
      │   {participants:        │             │
      │    ["did:key:z6Mkf..."]}│             │
      │                   │                   │
      │   (relay fetches Bob's KeyPackage)    │
      │                   │                   │
      │── wmp.mls.group.create ─>│            │
      │   {welcomes: {bob: ...}}│             │
      │                   │                   │
      │                   │── notification ──>│
      │                   │   {new session}   │
      │                   │                   │
      │                   │<── wmp.mls.group.join
      │                   │                   │
      │── wmp.message.deliver ──>│            │
      │   {encrypted, body:      │            │
      │    "Hello Bob!"}         │───────────>│
      │                   │                   │
      │                   │<── wmp.message.deliver
      │<──────────────────│   {encrypted,     │
      │                   │    body: "Hi!"}   │
      │                   │                   │
```

### 2.3 Message Types for Human Messaging

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-h2h-001", "sender": "did:key:z6MkfAlice..."},
    "content_type": "text/plain",
    "body": "Hello Bob!"
  }
}
```

Supported content types:
- `text/plain` — Plain text
- `application/json` — Structured data
- `text/markdown` — Rich text

### 2.4 Offline Delivery

When Bob is offline, the relay queues messages. When Bob's wallet reconnects, it fetches queued messages via `wmp.message.fetch`.

## 3. Human-to-Agent Messaging

### 3.1 Overview

A wallet holder interacts with an AI agent or automated service. This is the primary use case for MCP compatibility.

### 3.2 MCP Tool Invocation over WMP

An agent can expose MCP-compatible tools through a WMP session:

```json
{
  "jsonrpc": "2.0",
  "id": "tools-1",
  "method": "tools/list",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-agent-001"}
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": "tools-1",
  "result": {
    "wmp": {"version": "0.1", "session_id": "ses-agent-001"},
    "tools": [
      {
        "name": "verify_credential",
        "description": "Verify a verifiable credential",
        "inputSchema": {
          "type": "object",
          "properties": {
            "credential": {"type": "string"}
          },
          "required": ["credential"]
        }
      }
    ]
  }
}
```

### 3.3 Agent-Initiated Credential Request

An agent can request credentials from a human user:

```
Agent                   Relay            User's Wallet
  │                       │                    │
  │── wmp.flow.start ────>│───────────────────>│
  │   {flow_type: "oid4vp",                    │
  │    request: {                               │
  │      presentation_definition: {...}}}       │
  │                       │                    │
  │                       │<── wmp.flow.action │
  │                       │   {action: "select_credentials",
  │<──────────────────────│    params: {       │
  │                       │     consent: true, │
  │                       │     selections: [{ │
  │                       │      query_id,     │
  │                       │      selection_handle}]}
  │                       │                    │
  │                       │<── wmp.flow.complete
  │<──────────────────────│   {vp_token: "..."}│
  │                       │                    │
```

## 4. Human-to-Organization Messaging

### 4.1 Overview

A wallet holder communicates with an organization (government agency, bank, university). The organization runs a WMP endpoint as part of its infrastructure.

### 4.2 Credential Issuance Flow

```
User's Wallet           Org's WMP Endpoint
      │                        │
      │── wmp.session.create ─>│
      │   {capabilities:       │
      │    ["oid4vci"]}         │
      │<── result ─────────────│
      │                        │
      │── wmp.flow.start ────>│
      │   {flow_type: "oid4vci",│
      │    params: {offer_uri}} │
      │                        │
      │   ... (standard OID4VCI flow over WMP) ...
      │                        │
      │<── wmp.flow.complete ──│
      │   {credentials: [...]} │
      │                        │
```

### 4.3 Document Submission

Organizations can define custom flows for document submission:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.flow.start",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-org-001", "sender": "did:key:z6MkfUser..."},
    "flow_type": "document_submission",
    "flow_id": "flow-doc-001",
    "params": {
      "document_type": "application/pdf",
      "document": "<base64url-encoded document>",
      "metadata": {
        "title": "Tax return 2025",
        "reference": "REF-2025-001"
      }
    }
  }
}
```

### 4.4 Status Notifications

Organizations can push status updates to the user's wallet:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.message.deliver",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-org-001", "sender": "x509:san:dns:agency.gov"},
    "content_type": "application/json",
    "body": {
      "type": "status_update",
      "reference": "REF-2025-001",
      "status": "approved",
      "message": "Your application has been approved.",
      "actions": [
        {
          "type": "credential_offer",
          "offer_uri": "https://agency.gov/offers/abc123"
        }
      ]
    }
  }
}
```

## 5. Multi-Party Scenarios

### 5.1 Credential Verification with Third Party

A verifier requests a presentation, and the holder involves a trusted third party (e.g., a guardian or legal representative):

```
Verifier          Relay          Holder          Guardian
   │                │              │                │
   │── flow.start ──>│─────────────>│                │
   │   (oid4vp)      │              │                │
   │                │              │── session.create ─>│
   │                │              │   (invite guardian)│
   │                │              │                │
   │                │              │<── message ────│
   │                │              │   "I approve"  │
   │                │              │                │
   │                │<── flow.action │              │
   │<───────────────│   (consent)   │               │
   │                │              │                │
   │<── flow.complete│             │                │
   │   {vp_token}    │              │                │
```

### 5.2 Organizational Workflow

Multiple parties in an organization coordinate on a credential issuance:

- Applicant submits request via WMP
- Request is routed to reviewer (human or agent)
- Reviewer approves/requests changes
- Credential is issued back to applicant

All steps use the same WMP session with MLS encryption.

## 6. Comparison with Alternatives

### 6.1 WMP vs. AS4 (ebMS 3.0)

| Aspect | AS4 (ebMS 3.0) | WMP |
|--------|----------------|-----|
| **Primary goal** | B2B/G2G document exchange (eDelivery) | Wallet-to-wallet, human-to-agent, H2O flows |
| **Wire format** | SOAP 1.2 / XML with MIME multipart | JSON-RPC 2.0 |
| **Message model** | One-way push with optional receipts (pull mode available) | Request/Response + Notification |
| **Encryption** | WS-Security (XML Encryption), S/MIME, TLS | MLS (RFC 9420) |
| **Signing** | XML Signature (WS-Security) | JWS / COSE, per-message in metadata |
| **Non-repudiation** | ebMS Signal receipts (NRR), signed SOAP headers | ERDS evidence receipts with RFC 3161 timestamps |
| **Transport** | HTTP(S) only | WebSocket, HTTPS, Native Messaging |
| **Real-time** | No (pull-based or scheduled push) | Yes (WebSocket / SSE) |
| **Multi-party** | Via intermediaries (MSH chaining) | Native MLS groups |
| **Identity** | Party IDs (ebCore Party ID Type), X.509 | 11 identifier schemes (DID, X.509, ebCore, OpenID Federation, …) |
| **Discovery** | SMP + BDXL (DNS) | `wmp.resolve` + optional eDelivery profile for SMP/BDXL |
| **Credential exchange** | Not built-in (payload-agnostic) | Native OID4VCI/OID4VP flows via profiles |
| **MCP compatibility** | None | Native (shared JSON-RPC 2.0 envelope) |
| **Reliability** | ebMS reliability (retries, duplicate detection, ordering) | Application-layer; relay capability for store-and-forward |
| **Tooling** | Heavy XML/SOAP stack (Holodeck, Domibus, Oxalis) | Standard JSON libraries |
| **Spec complexity** | Very high (OASIS ebMS 3.0 + AS4 profile + SBDH + SMP + BDXL) | Compact (core + transport + MLS + profiles) |
| **PQC readiness** | Not specified | Hybrid ML-KEM + X25519 (MLS spec §8) |
| **eDelivery coexistence** | Native | WMP eDelivery profile (SMP participant metadata, AS4 fallback) |

**When to choose AS4:** Existing eDelivery / PEPPOL infrastructure, mandated B2B/G2G document exchange, regulatory requirements for OASIS-standard messaging, integration with legacy SOAP/XML ecosystems.

**When to choose WMP:** Interactive credential flows, wallet-native communication, agent integration (MCP), real-time messaging, lightweight deployment without XML/SOAP overhead, PQC-ready encryption.

### 6.2 WMP vs. DIDComm 2.1

| Aspect | DIDComm 2.1 | WMP |
|--------|-------------|-----|
| Wire format | DIDComm envelope (JOSE/COSE) | JSON-RPC 2.0 |
| Encryption | Per-message JOSE | MLS group keys |
| Key management | Per-recipient encrypt | MLS key schedule |
| Transport | HTTP, WebSocket, BLE | WebSocket, HTTP, Native |
| Multi-party | Multiple recipients | MLS groups (scalable) |
| RPC pattern | Message-based | Request/Response + Notification |
| MCP compatibility | None | Native (shared envelope) |
| Specification size | Large (multiple specs) | Compact |

### 6.3 WMP vs. Matrix

| Aspect | Matrix | WMP |
|--------|--------|-----|
| **Primary goal** | Decentralised IM / VoIP / IoT | Wallet-to-wallet, human-to-agent, H2O flows |
| **Wire format** | REST + JSON events (custom envelope) | JSON-RPC 2.0 |
| **Message model** | Events in a room DAG (append-only, eventually consistent) | Request/Response + Notification (stateless RPC) |
| **Encryption** | Olm (1:1 Double Ratchet) + Megolm (group ratchet) | MLS (RFC 9420) |
| **Key management** | Per-device Olm sessions, Megolm session keys shared O(n) per ratchet epoch | MLS tree-based key schedule, O(log n) update cost |
| **Forward secrecy** | Yes (Olm ratchet) | Yes (MLS epoch keys) |
| **Post-compromise security** | Olm: yes; Megolm: limited (new sessions) | Yes (MLS guarantees PCS per epoch) |
| **Multi-party** | Rooms with DAG-based state resolution | MLS groups with tree-KEM |
| **Federation** | Full-mesh homeserver federation (Server-Server API) | No built-in federation; relay capability for store-and-forward |
| **Identity** | `@user:domain` + optional 3PID (email, phone) | 11 identifier schemes (DID, X.509, OpenID Federation, ebCore, …) |
| **Transport** | HTTPS only (C-S API, S-S API) | WebSocket, HTTPS, Native Messaging |
| **Server requirement** | Homeserver required (stores full event history) | Serverless possible; relay optional |
| **State persistence** | Full room history replicated across homeservers | Stateless messages; persistence is application-layer |
| **Credential exchange** | Not built-in (would require custom events) | Native OID4VCI/OID4VP flows via profiles |
| **MCP compatibility** | None | Native (shared JSON-RPC 2.0 envelope) |
| **Non-repudiation** | Homeserver signatures on events (server-level) | Per-message signatures with evidence receipts (ERDS) |
| **Spec complexity** | Large (C-S, S-S, AS, Identity, Push APIs + room versions) | Compact (core + transport + MLS + profiles) |
| **PQC readiness** | Not specified | Hybrid ML-KEM + X25519 (MLS spec §8) |

**When to choose Matrix:** General-purpose decentralised messaging, bridging to existing chat platforms (IRC, Slack, Discord), persistent chat history with server-side search, large public communities.

**When to choose WMP:** Credential exchange workflows, wallet-native communication, agent-to-agent (MCP) integration, lightweight peer-to-peer without mandatory server infrastructure, regulated delivery with evidence/receipts.

### 6.4 Key Advantages of WMP

1. **Single envelope format** — JSON-RPC 2.0 everywhere. No translation layers.
2. **MLS efficiency** — Group key management scales O(n) not O(n²) for multi-party.
3. **MCP interoperability** — Agents can participate using standard MCP tooling.
4. **Transport flexibility** — Native messaging enables browser extension and CLI integration.
5. **Incremental adoption** — WMP Basic (no MLS) is trivial to implement. MLS adds security when needed.

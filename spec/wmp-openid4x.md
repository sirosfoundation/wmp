# WMP OpenID4x Profile

## Wallet Messaging Protocol — OpenID for Verifiable Credentials Profile

**Status:** Draft  
**Version:** 0.1.0  
**Date:** 2026-04-29

## 1. Introduction

This document defines the WMP profile for OpenID for Verifiable Credential Issuance (OID4VCI) and OpenID for Verifiable Presentations (OID4VP) flows. It specifies the capabilities, flow types, step identifiers, and action identifiers required to run these protocols over WMP.

Verifiable Credential Type Metadata (VCTM) resolution is handled by the generic `wmp.resolve` mechanism defined in WMP Core Section 5.8, using resolution type `vctm`.

This profile builds on [WMP Core](wmp-core.md) Section 6 (Structured Flows) and Section 6.5 (Profile-Defined Flow Types).

### 1.1 Conformance Level

**WMP Wallet** — An implementation conforming to this profile MUST support WMP Flows (Core Section 10.1) plus the capabilities and flow types defined in this document.

## 2. Capabilities

This profile defines the following capabilities for use in `wmp.session.create` negotiation:

| Capability | Description | Parameters |
|-----------|-------------|------------|
| `oid4vci` | OID4VCI credential issuance flows | `supported_grants`: grant types, `supported_formats`: credential formats |
| `oid4vp` | OID4VP verifiable presentation flows | `supported_response_modes`: response modes, `supported_formats`: credential formats |
| `transaction_data` | OID4VP `transaction_data` processing (EC TS12 payment SCA) | `versions`: capability versions, `hash_algs`: hash algorithms |

Implementations that need VCTM resolution SHOULD also negotiate the `resolve` capability (WMP Core Section 5.8) with `"vctm"` in `supported_types`.

### 2.1 `oid4vci` Capability

**Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| `supported_grants` | string[] | Grant types: `authorization_code`, `pre-authorized_code` |
| `supported_formats` | string[] | Credential formats: `vc+sd-jwt`, `jwt_vc_json`, `mso_mdoc`, `ldp_vc` |
| `supported_proof_types` | string[] | Proof types: `jwt`, `cwt`, `ldp` |
| `batch_issuance` | boolean | Whether batch credential issuance is supported |

**Example:**

```json
{
  "oid4vci": {
    "supported_grants": ["authorization_code", "pre-authorized_code"],
    "supported_formats": ["vc+sd-jwt", "mso_mdoc"],
    "supported_proof_types": ["jwt"],
    "batch_issuance": true
  }
}
```

### 2.2 `oid4vp` Capability

**Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| `supported_response_modes` | string[] | Response modes: `direct_post`, `direct_post.jwt`, `dc_api`, `dc_api.jwt` |
| `supported_formats` | string[] | Credential formats accepted for presentation |
| `supported_algorithms` | string[] | Signing algorithms for VP tokens |

**Example:**

```json
{
  "oid4vp": {
    "supported_response_modes": ["direct_post", "dc_api"],
    "supported_formats": ["vc+sd-jwt", "mso_mdoc"],
    "supported_algorithms": ["ES256", "EdDSA"]
  }
}
```

### 2.3 `transaction_data` Capability

A wallet offers `transaction_data` when it can process OID4VP `transaction_data` end to end: validate it against the type metadata of the attestation it is bound to, show it to the user, and bind it into the presentation. EC TS12 (strong customer authentication for payments) requires this for a presentation of an SCA attestation.

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `versions` | integer[] | REQUIRED | Versions of this capability the wallet implements. Version `1` is defined by this section and Section 3.2.5. A non-empty array. |
| `hash_algs` | string[] | OPTIONAL | `transaction_data_hashes_alg` names the wallet can compute, for example `sha-256`. |

**Example:**

```json
{
  "transaction_data": {
    "versions": [1],
    "hash_algs": ["sha-256"]
  }
}
```

**Rules:**

- A wallet MUST offer the capability only if it implements everything Section 3.2.5 requires of it. An implementation that ignores `transaction_data` would sign the presentation without the transaction hashes and without the user seeing the transaction.
- An orchestrator MUST NOT send `transaction_data` to a wallet whose **offered** capabilities (`capabilities_offered` in `wmp.session.create`) do not list a version it supports. The test is on what the wallet offered, not on the negotiated result: negotiation may fall back to all of the orchestrator's capabilities when a wallet offers none, and that is not evidence that the wallet supports anything.
- When a request carries `transaction_data` and the wallet did not offer the capability, the orchestrator MUST end the OID4VP flow with `wmp.flow.error` code `-31005` (Capability not supported) and `data` `{"unsupported": "transaction_data"}`, and MUST report the failure to the verifier as `invalid_transaction_data` (OID4VP). It MUST NOT omit the transaction data and continue.
- A wallet that does not offer the capability behaves exactly as before for every request that carries no `transaction_data`.

## 3. Flow Types

### 3.1 `oid4vci` Flow — Credential Issuance

#### 3.1.1 Start Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `credential_offer` | string | OPTIONAL | Credential offer URI (`openid-credential-offer://...`) |
| `credential_offer_uri` | string | OPTIONAL | HTTPS URI pointing to the credential offer |
| `issuer` | string | OPTIONAL | Issuer identifier |
| `tx_code` | string | OPTIONAL | Pre-authorized code transaction code (user PIN) |

At least one of `credential_offer` or `credential_offer_uri` MUST be provided.

**Example:**

```json
{
  "jsonrpc": "2.0",
  "id": "vci-001",
  "method": "wmp.flow.start",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "did:web:alice.example.com"},
    "flow_type": "oid4vci",
    "flow_id": "flow-vci-001",
    "params": {
      "credential_offer_uri": "https://issuer.example.com/offers/abc123"
    }
  }
}
```

#### 3.1.2 Progress Steps

| Step | Description | Payload |
|------|-------------|---------|
| `parsing_offer` | Parsing the credential offer | `offer`: parsed offer object |
| `resolving_metadata` | Fetching issuer metadata | — |
| `metadata_fetched` | Issuer metadata retrieved | `issuer_metadata`: issuer metadata object |
| `evaluating_trust` | Evaluating trust chain for issuer | — |
| `trust_evaluated` | Trust evaluation complete | `trust_info`: trust evaluation result |
| `awaiting_offer_acceptance` | Waiting for user to accept/select credential configurations from the offer | `credentials`: available credential configurations, `issuer_metadata`: display info |
| `awaiting_tx_code` | Waiting for transaction code (PIN) | `tx_code_description`: description text |
| `authorization_pending` | OAuth authorization in progress | `authorization_url`: URL for user-agent redirect |
| `generating_proof` | Generating key proof | `proof_request`: proof parameters |
| `requesting_credential` | Sending credential request to issuer | — |
| `credential_received` | Credential received, processing | `credential_preview`: preview of issued credential |

**Example:**

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.flow.progress",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_id": "flow-vci-001",
    "step": "awaiting_offer_acceptance",
    "payload": {
      "credentials": [
        {
          "index": 0,
          "format": "vc+sd-jwt",
          "type": "VerifiableCredential",
          "vct": "https://credentials.example.com/identity",
          "display": {
            "name": "National ID Card",
            "locale": "en",
            "logo_uri": "https://issuer.example.com/logo.png"
          }
        }
      ],
      "issuer_metadata": {
        "issuer": "https://issuer.example.com",
        "display": {"name": "Government ID Service"}
      },
      "trust_info": {
        "trusted": true,
        "trust_chain": ["eIDAS Trust List"]
      }
    }
  }
}
```

#### 3.1.3 Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `accept_offer` | Accept credential configuration(s) from the offer | `selected_indices`: int[], `consent`: bool |
| `provide_tx_code` | Provide transaction code | `tx_code`: string |
| `authorize` | Complete OAuth authorization | `auth_code`: string, `code_verifier`: string |
| `cancel` | Cancel the flow | `reason`: string (optional) |

**Example:**

```json
{
  "jsonrpc": "2.0",
  "id": "vci-action-001",
  "method": "wmp.flow.action",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "did:web:alice.example.com"},
    "flow_id": "flow-vci-001",
    "action": "accept_offer",
    "params": {
      "selected_indices": [0],
      "consent": true
    }
  }
}
```

#### 3.1.4 Completion Result

| Field | Type | Description |
|-------|------|-------------|
| `credentials` | object[] | Issued credentials |
| `credentials[].format` | string | Credential format |
| `credentials[].credential` | string | The credential (JWT, SD-JWT, mdoc CBOR) |
| `credentials[].vct` | string | Verifiable Credential Type identifier |
| `credentials[].c_nonce` | string | Server nonce for subsequent proofs |
| `credential_metadata` | object | OPTIONAL. The OpenID4VCI 1.1 response-level `credential_metadata` object (openid/OpenID4VCI#721) of the Credential Response or Deferred Credential Response, relayed verbatim. It applies to every entry of `credentials[]`. See 3.1.4.1 |
| `credential_metadata_encrypted_response` | boolean | OPTIONAL. `true` only when `credential_metadata` came in a JWE-encrypted issuer response. When `credential_metadata` is present and this member is absent the value arrived as plain JSON, which is always the case for deferred issuance |
| `refresh_token` | string | OPTIONAL. OAuth refresh token the issuer returned with this batch; the client stores it for renewal. A secret (see 3.1.4.2) |
| `dpop_jwk` | string | OPTIONAL. Present only with `refresh_token`: the private JWK of the DPoP key the refresh token is bound to. A secret |
| `dpop_key_id` | string | OPTIONAL. Present only with `refresh_token` when the DPoP key is client-held: the identifier of that key |
| `redacted_members` | string[] | OPTIONAL. Set by the server only on a *replayed* completion: the names, in alphabetical order, of the secret members withheld from the retained copy (see 3.1.4.2). Never set on the live notification |

##### 3.1.4.1 `credential_metadata`

- The value MUST be a JSON object. The sender relays members verbatim and in order (only insignificant whitespace may change) and preserves members it does not understand. A receiver MUST ignore members it does not understand.
- The object is shared with display data, which is mostly what it carries (`display[]`, `claims[]`, logo and background images).
- Extension members use collision-resistant names. The member `org.siros.secret_seed` is defined by the privatedata specification, Section 5A (it is not an OpenID4VCI member). Its value is an object that maps a namespace (1 to 64 UTF-8 bytes, not `namespaces`) to a seed of exactly 32 lowercase hexadecimal characters; it has 1 to 8 members.
- A completion that carries `org.siros.secret_seed` is valid only if the issuer response was JWE-encrypted (`credential_metadata_encrypted_response` is `true`) and carried a `notification_id`. A wallet MUST refuse the issuance when the member is present and `credential_metadata_encrypted_response` is not `true`, and MUST NOT store anything from it. The remaining wallet obligations (commitment verification, strip-before-merge, storage only inside the encrypted container) are those of privatedata Section 5A.
- `credential_metadata` MAY carry secrets. Implementations MUST NOT log it, MUST NOT include it in error messages or diagnostics, and MUST NOT retain it in any buffer, replay store or persisted state other than the wallet's secret store.

##### 3.1.4.2 Replay of a completion

The secret members of a completion are `credential_metadata`, `credential_metadata_encrypted_response`, `refresh_token`, `dpop_jwk` and `dpop_key_id`. A server that keeps outbound notifications for replay (for example for SSE `Last-Event-ID` resume or `wmp.session.resume`) MUST NOT retain any of them in the retained copy. The live notification carries them and is delivered only to the connection that is streaming when the completion is emitted. A replayed `wmp.flow.complete` for the same flow omits every secret member that the live one carried, keeps `credentials[]` and all other members unchanged, and carries `"redacted_members"`: an array listing exactly the members that were omitted (for example `["credential_metadata", "credential_metadata_encrypted_response", "dpop_jwk", "dpop_key_id", "refresh_token"]`). It is absent when nothing was omitted and never present on the live notification.

The marker means "withheld", not "the issuer sent none". A client that receives a replayed completion with `redacted_members` MUST treat every listed member as not recoverable: it MUST NOT conclude that the member did not exist, MUST NOT fabricate or substitute a value (in particular no refresh token, DPoP key or secret seed), and MUST treat an issuance that required a listed member (a delivered secret) as failed, to be re-issued. A credential whose `refresh_token` and `dpop_jwk` were withheld cannot be renewed without re-issuance. A client that needs these members therefore has to be connected to the event stream before it starts the flow and stay connected until the completion arrives. Clients dedupe replays by event ID.

#### 3.1.5 Sign Sub-flow

During OID4VCI, the orchestrator may need the wallet to generate a key proof. This uses the WMP Core `sign` flow type as a nested flow:

```json
{
  "jsonrpc": "2.0",
  "id": "vci-sign-001",
  "method": "wmp.flow.start",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_type": "sign",
    "flow_id": "flow-vci-001-sign",
    "params": {
      "action": "generate_proof",
      "nonce": "n-0S6_WzA2Mj",
      "audience": "https://issuer.example.com",
      "proof_type": "jwt",
      "parent_flow_id": "flow-vci-001"
    }
  }
}
```

The `parent_flow_id` field links the sign flow to the parent OID4VCI flow. The sign flow completes with the proof JWT in the result:

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.flow.complete",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_id": "flow-vci-001-sign",
    "result": {
      "proof_jwt": "eyJ..."
    }
  }
}
```

### 3.2 `oid4vp` Flow — Verifiable Presentation

The `oid4vp` flow is a *verifier-initiated* credential query: the verifier specifies what credentials/claims are needed and the wallet holder explicitly consents to disclosure. For *sender-initiated* identity binding (session authentication without a verifier request), see `identity_assertions` in WMP Core Section 5.6.

#### 3.2.1 Start Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_uri` | string | OPTIONAL | OID4VP request URI (`openid4vp://...`) |
| `request_uri_ref` | string | OPTIONAL | HTTPS URI referencing the authorization request |
| `presentation_definition` | object | OPTIONAL | Inline presentation definition |
| `dcql_query` | object | OPTIONAL | DCQL query (Digital Credentials Query Language) |
| `client_id` | string | OPTIONAL | Verifier client ID |

**Example:**

```json
{
  "jsonrpc": "2.0",
  "id": "vp-001",
  "method": "wmp.flow.start",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "did:web:alice.example.com"},
    "flow_type": "oid4vp",
    "flow_id": "flow-vp-001",
    "params": {
      "request_uri_ref": "https://verifier.example.com/requests/xyz789"
    }
  }
}
```

#### 3.2.2 Progress Steps

| Step | Description | Payload |
|------|-------------|---------|
| `parsing_request` | Parsing the authorization request | — |
| `request_parsed` | Request parsed | `verifier_info`: verifier metadata, `presentation_definition`: requirements |
| `evaluating_trust` | Evaluating trust for verifier | — |
| `trust_evaluated` | Trust evaluation complete | `trust_info`: trust evaluation result |
| `matching_credentials` | Matching credentials against requirements | — |
| `awaiting_consent` | Waiting for user to select credentials and consent to disclosure | `matched_credentials`: matching credentials, `requested_claims`: claims requested |
| `generating_presentation` | Generating VP token | — |

#### 3.2.3 Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `select_credentials` | Select credentials and consent to disclosure | `selections`: credential selections with claim disclosure, `consent`: bool |
| `cancel` | Cancel the flow | `reason`: string (optional) |

**Credential selection with selective disclosure:**

```json
{
  "jsonrpc": "2.0",
  "id": "vp-action-001",
  "method": "wmp.flow.action",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4", "sender": "did:web:alice.example.com"},
    "flow_id": "flow-vp-001",
    "action": "select_credentials",
    "params": {
      "selections": [
        {
          "credential_id": "cred-001",
          "disclosed_claims": ["given_name", "family_name", "age_over_18"]
        }
      ],
      "consent": true
    }
  }
}
```

#### 3.2.4 Completion Result

| Field | Type | Description |
|-------|------|-------------|
| `vp_token` | string/string[] | VP token(s) |
| `presentation_submission` | object | Presentation submission descriptor |
| `response_code` | string | Response code from verifier (if applicable) |

#### 3.2.5 Presentation Sign Sub-flow

To obtain the VP token the orchestrator starts a nested `sign` flow with `action` `sign_presentation`, linked to the `oid4vp` flow by `parent_flow_id`, as for the OID4VCI sign sub-flow in Section 3.1.5. This section defines the members relevant to `transaction_data`; other members are defined by the implementation profile.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | REQUIRED | `sign_presentation` |
| `nonce` | string | REQUIRED | The verifier's `nonce` |
| `audience` | string | REQUIRED | The verifier's client identifier |
| `parent_flow_id` | string | REQUIRED | The `oid4vp` flow this sub-flow belongs to |
| `response_mode` | string | OPTIONAL | The `response_mode` of the verifier's request. Required for a request that carries `transaction_data` (EC TS12 puts it in the key binding JWT). |
| `credentials_to_include` | object[] | OPTIONAL | Credentials already selected: `credential_id`, `credential_query_id`, `disclosed_claims` |
| `transaction_data` | object[] | OPTIONAL | The request's transaction data, one entry per element of the verifier's array, in the verifier's order. Only present for a wallet that offered the `transaction_data` capability. |

Each `transaction_data` entry has these members:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `raw` | string | REQUIRED | The entry exactly as the verifier sent it: the base64url string from the request's `transaction_data` array |
| `type` | string | REQUIRED | `type` of the decoded entry |
| `credential_ids` | string[] | REQUIRED | `credential_ids` of the decoded entry: the DCQL credential query ids the entry is bound to |
| `payload` | object | OPTIONAL | `payload` of the decoded entry (EC TS12 Section 4.2) |
| `transaction_data_hashes_alg` | string[] | OPTIONAL | The verifier's list of acceptable hash algorithms for this entry. An **array**, as in OID4VP; a bare string SHOULD be accepted from older peers. |

**Example:**

```json
{
  "jsonrpc": "2.0",
  "id": "vp-sign-001",
  "method": "wmp.flow.start",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_type": "sign",
    "flow_id": "flow-vp-001-sign",
    "params": {
      "action": "sign_presentation",
      "nonce": "bUtJdjJESWdmTWNjb011YQ",
      "audience": "x509_san_dns:shop.example.com",
      "parent_flow_id": "flow-vp-001",
      "response_mode": "direct_post",
      "credentials_to_include": [
        {"credential_id": "cred-001", "credential_query_id": "pay"}
      ],
      "transaction_data": [
        {
          "raw": "eyJ0eXBlIjoidXJuOmV1ZGk6c2NhOnBheW1lbnQ6MSIsImNyZWRlbnRpYWxfaWRzIjpbInBheSJdLCJwYXlsb2FkIjp7InRyYW5zYWN0aW9uX2lkIjoidHgtMDAwMSJ9fQ",
          "type": "urn:eudi:sca:payment:1",
          "credential_ids": ["pay"],
          "payload": {"transaction_id": "tx-0001"}
        }
      ]
    }
  }
}
```

**Requirements on the wallet:**

1. **Hash `raw`.** `transaction_data_hashes` in the key binding JWT is the base64url encoding of the hash of the ASCII bytes of `raw`, exactly as received. The wallet MUST NOT decode `raw` before hashing and MUST NOT hash a re-serialization of the decoded members (key order, whitespace, character escapes and number formatting do not survive it). Entries are hashed in the order given. When the verifier gave `transaction_data_hashes_alg` the wallet uses one of the listed algorithms and puts that single name, as a string, in the key binding JWT's `transaction_data_hashes_alg`; otherwise it uses `sha-256`.
2. **Do not trust the decoded members.** The wallet MUST decode `raw` itself, and use that, not `type`, `credential_ids` or `payload` as sent, to validate and to display. The other members are an aid, and a wallet MUST refuse an entry whose members disagree with what `raw` decodes to. Otherwise a compromised orchestrator could show one transaction and bind another.
3. **Fail closed.** The wallet MUST fail the sub-flow, and show the user why, if it cannot validate an entry, cannot compute a requested hash, or does not support an entry's `type`. OID4VP requires an error for even one unrecognized transaction data type. It MUST NOT answer with a presentation that omits the hashes.
4. **Format.** EC TS12 version 1.0.1 covers SD-JWT VC only. For another credential format the wallet MUST fail the sub-flow rather than present without binding the transaction.

The sub-flow completes with the VP token as in Section 3.1.5. The wallet is responsible for the remaining requirements of EC TS12 (display of the transaction, the `amr` claim, `jti`, logging); they are not carried in this protocol.

## 4. Complete OID4VCI Flow Example

```
wallet                             orchestrator
      │                                    │
      │── wmp.session.create ─────────────>│
      │   {capabilities_offered:           │
      │     {oid4vci: {                    │
      │       supported_grants:            │
      │         ["pre-authorized_code"],   │
      │       supported_formats:           │
      │         ["vc+sd-jwt"]},            │
      │      flows: {max_concurrent: 5}}}  │
      │<── result {session_id, caps} ──────│
      │                                    │
      │── wmp.flow.start ────────────────>│
      │   {flow_type: "oid4vci",           │
      │    flow_id: "flow-vci-001",        │
      │    params: {credential_offer_uri:  │
      │      "https://issuer.example.com   │
      │       /offers/abc123"}}            │
      │                                    │
      │<── wmp.flow.progress ──────────────│
      │   {step: "metadata_fetched",       │
      │    payload: {issuer_metadata}}      │
      │                                    │
      │<── wmp.flow.progress ──────────────│
      │   {step: "trust_evaluated",        │
      │    payload: {trust_info}}           │
      │                                    │
      │<── wmp.flow.progress ──────────────│
      │   {step: "awaiting_offer_acceptance",│
      │    payload: {credentials: [...]}}   │
      │                                    │
      │── wmp.flow.action ───────────────>│
      │   {action: "accept_offer",         │
      │    params: {selected_indices: [0],  │
      │             consent: true}}         │
      │                                    │
      │<── wmp.flow.start (nested) ────────│
      │   {flow_type: "sign",              │
      │    flow_id: "flow-vci-001-sign",   │
      │    params: {action:                │
      │      "generate_proof",             │
      │      nonce: "...",                 │
      │      audience: "https://..."}}     │
      │                                    │
      │── wmp.flow.complete (nested) ─────>│
      │   {flow_id: "flow-vci-001-sign",   │
      │    result: {proof_jwt: "eyJ..."}}  │
      │                                    │
      │<── wmp.flow.complete ──────────────│
      │   {flow_id: "flow-vci-001",        │
      │    result: {credentials: [         │
      │      {format: "vc+sd-jwt",         │
      │       credential: "eyJ..."}]}}     │
      │                                    │
```

## 5. Complete OID4VP Flow Example

```
verifier-agent                   user-wallet
      │                              │
      │── wmp.session.create ───────>│
      │   {capabilities_offered:     │
      │     {oid4vp: {...},          │
      │      flows: {max_concurrent: 1}}}
      │<── result ───────────────────│
      │                              │
      │── wmp.flow.start ───────────>│
      │   {flow_type: "oid4vp",      │
      │    params: {                 │
      │      presentation_definition:│
      │        {input_descriptors:   │
      │          [{id: "id_card",    │
      │            constraints:      │
      │             {...}}]}}}       │
      │                              │
      │<── wmp.flow.progress ────────│
      │   {step: "awaiting_consent", │
      │    payload: {matched_creds}} │
      │                              │
      │   (user reviews and consents)│
      │                              │
      │<── wmp.flow.action ──────────│
      │   {action: "select_credentials",
      │    params: {selections: [...],│
      │             consent: true}}  │
      │                              │
      │<── wmp.flow.complete ────────│
      │   {result: {vp_token: "..."}}│
      │                              │
```

## 6. Security Considerations

### 6.1 Issuer/Verifier Trust

Before presenting credentials or accepting issued credentials, implementations MUST evaluate trust in the counterparty. The `trust_evaluated` progress step provides trust evaluation results. Implementations SHOULD NOT auto-accept credentials from untrusted issuers or auto-disclose credentials to untrusted verifiers.

### 6.2 Selective Disclosure

When the `oid4vp` flow reaches `awaiting_consent`, the wallet MUST present the user with the specific claims requested and allow the user to control which claims are disclosed. Implementations MUST NOT disclose claims beyond what the user explicitly consents to.

### 6.3 Nonce Binding

All proof JWTs generated in OID4VCI sign sub-flows MUST be bound to the nonce provided by the issuer. Implementations MUST reject proofs with missing or mismatched nonces.

### 6.4 Credential Offer Validation

Implementations MUST validate credential offers before processing:
- Verify the offer URI scheme and structure
- Resolve and validate issuer metadata
- Check credential types against known VCTMs

### 6.5 Transaction Data

`transaction_data` makes the user's consent legally significant (a payment authorization), so the display and the hash must describe the same bytes. Section 3.2.5 therefore has the wallet derive what it shows from `raw`, which is also what it hashes, and treat everything else the orchestrator sends as untrusted. Capability negotiation (Section 2.3) keeps the data away from wallets that would drop it silently; the orchestrator's refusal is the only barrier for those, so it MUST NOT be skipped for unauthenticated or "best effort" flows.

## References

- [WMP Core Specification](wmp-core.md)
- [OpenID for Verifiable Credential Issuance 1.0](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html)
- [OpenID for Verifiable Presentations 1.0](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html)
- [Verifiable Credential Type Metadata](https://www.ietf.org/archive/id/draft-ietf-oauth-sd-jwt-vc-05.html)
- [EC TS12: Specification of Strong Customer Authentication (SCA) Implementation with the Wallet, v1.0.1](https://github.com/eu-digital-identity-wallet/eudi-doc-standards-and-technical-specifications/blob/main/docs/technical-specifications/ts12-electronic-payments-SCA-implementation-with-wallet.md)

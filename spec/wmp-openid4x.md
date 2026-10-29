# WMP OpenID4x Profile

## Wallet Messaging Protocol — OpenID for Verifiable Credentials Profile

**Status:** Draft  
**Version:** 0.1.0  
**Date:** 2026-04-29

## 1. Introduction

This document defines the WMP profile for OpenID for Verifiable Credential Issuance (OID4VCI) and OpenID for Verifiable Presentations (OID4VP) flows. It specifies the capabilities, flow types, step identifiers, and action identifiers required to run these protocols over WMP.

Verifiable Credential Type Metadata (VCTM) resolution is handled by the generic `wmp.resolve` mechanism defined in WMP Core Section 5.8, using resolution type `vctm`. The result carries the type metadata in `metadata` and has the same content as the type metadata a wallet backend embeds with an issued credential; Core Section 5.8.1 ("`vctm` resolution") defines the lookup, the members and the failure behaviour.

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
- When a request carries `transaction_data` and the wallet did not offer the capability, the orchestrator MUST end the OID4VP flow with `wmp.flow.error` code `-31005` (Capability not supported) and `data` `{"unsupported": "transaction_data"}`, and MUST report the failure to the verifier as `invalid_transaction_data` (OID4VP). It MUST NOT omit the transaction data and continue. When the verifier's response mode produced a redirect (for example `query` or `fragment`), the orchestrator adds its URL as `redirect_uri` to the same `data` (`{"unsupported": "transaction_data", "redirect_uri": "..."}`), as it does for a refused presentation (Section 3.2.6). `unsupported` is always present; `redirect_uri` is an additive extension member (WMP Core Sections 3.8.1 and 9.5) and a wallet that does not know it ignores it.
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
| `credentials[].credential` | string | The credential (JWT, SD-JWT, mdoc CBOR). Absent when `credential_response_encrypted` is `true` |
| `credentials[].vct` | string | Verifiable Credential Type identifier |
| `credentials[].c_nonce` | string | Server nonce for subsequent proofs |
| `credential_response_encrypted` | boolean | OPTIONAL. `true` when the issuer's response was encrypted to a key only the client holds. The server relayed the JWE unread (see 3.1.5.1), so `credentials[]` entries carry no `credential` value and the completion carries no `credential_metadata`; the client pairs `credentials[i]` with the i-th credential it decrypted, and a count mismatch is an error |
| `credential_metadata` | object | OPTIONAL. Only for a plain (unencrypted) issuer response: the display-only members `display` and `claims` of its response-level `credential_metadata` (openid/OpenID4VCI#721), applying to every entry of `credentials[]`. See 3.1.4.1. Never present when `credential_response_encrypted` is `true` |
| `refresh_token` | string | OPTIONAL. OAuth refresh token the issuer returned with this batch; the client stores it for renewal. A secret (see 3.1.4.2) |
| `dpop_jwk` | string | OPTIONAL. Present only with `refresh_token`: the private JWK of the DPoP key the refresh token is bound to. A secret |
| `dpop_key_id` | string | OPTIONAL. Present only with `refresh_token` when the DPoP key is client-held: the identifier of that key |
| `redacted_members` | string[] | OPTIONAL. Set by the server only on a *replayed* completion: the names, in alphabetical order, of the secret members withheld from the retained copy (see 3.1.4.2). Never set on the live notification |

##### 3.1.4.1 `credential_metadata`

- Present only for a plain issuer response, and then only with the members `display` and `claims`, relayed as received. The sender drops every other member (extension members, including `auxiliary_data`) and never relays or logs them. A receiver MUST ignore members it does not understand.
- A plain issuer response that carries `auxiliary_data` is refused by the server (the issuance fails); `auxiliary_data` is delivered only in an encrypted response, which the client decrypts itself (3.1.5.1). Validation and storage of it are the wallet's obligations.

##### 3.1.4.2 Replay of a completion

The secret members of a completion are `refresh_token`, `dpop_jwk` and `dpop_key_id`. A server that keeps outbound notifications for replay (for example for SSE `Last-Event-ID` resume or `wmp.session.resume`) MUST NOT retain any of them in the retained copy. The live notification carries them and is delivered only to the connection that is streaming when the completion is emitted. A replayed `wmp.flow.complete` for the same flow omits every secret member that the live one carried, keeps `credentials[]` and all other members unchanged, and carries `"redacted_members"`: an array listing exactly the members that were omitted (for example `["dpop_jwk", "dpop_key_id", "refresh_token"]`). It is absent when nothing was omitted and never present on the live notification.

The marker means "withheld", not "the issuer sent none". A client that receives a replayed completion with `redacted_members` MUST treat every listed member as not recoverable: it MUST NOT conclude that the member did not exist, MUST NOT fabricate or substitute a value (in particular no refresh token or DPoP key), and MUST treat an issuance that required a listed member as failed, to be re-issued. A credential whose `refresh_token` and `dpop_jwk` were withheld cannot be renewed without re-issuance. A client that needs these members therefore has to be connected to the event stream before it starts the flow and stay connected until the completion arrives. Clients dedupe replays by event ID.

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

##### 3.1.5.1 Credential response encryption (engine-blind)

The server never holds a credential-response key and never decrypts the issuer's response; it relays ciphertext. Two further `sign` actions carry this. Their params are additive members of the sign sub-flow params (extension registry: Section 7.6; Core Section 9.5) and peers that do not know them ignore them.

`generate_proof` gains `credential_response_encryption`, present only when the issuer offers response encryption:

```json
"params": {
  "action": "generate_proof", "parent_flow_id": "flow-vci-001",
  "nonce": "n-0S6_WzA2Mj", "audience": "https://issuer.example.com", "proof_type": "jwt", "count": 1,
  "proof_types_supported": {"jwt": {"proof_signing_alg_values_supported": ["ES256"]}},
  "credential_response_encryption": {"alg": "ECDH-ES", "enc": "A256GCM", "required": true}
}
```

`alg` and `enc` are the pair negotiated from the issuer metadata (`ECDH-ES`, `ECDH-ES+A128KW`, `ECDH-ES+A192KW`, `ECDH-ES+A256KW` with `A128GCM`, `A256GCM`, `A128CBC-HS256`, `A256CBC-HS512`); the issuer's JWE MUST use exactly that pair. `required` is `true` when the issuer requires encryption. The client generates a fresh ephemeral P-256 key per `generate_proof` request, keeps the private key, and returns the public JWK in the sign result as `credential_response_encryption_jwk` (`{"kty":"EC","crv":"P-256","x":"...","y":"...","use":"enc","alg":"<negotiated>"}`, `kid` optional). Absent or empty means declined; with `required: true` the server fails the issuance. An unusable JWK fails the issuance. A `generate_proof` that carries `credential_response_encryption` and neither `proof_type` nor `proof_types_supported` is a request for the key alone: the client returns `credential_response_encryption_jwk` and no proofs. Any request that carries `proof_type` or `proof_types_supported`, with or without `credential_response_encryption`, asks for proofs as in Section 3.1.5, so a request that predates this section keeps its meaning.

When the issuer answers with a JWE (for the Credential Request or a Deferred Credential Request) the server starts a sign sub-flow with action `decrypt_credential_response`:

```json
"params": {"action": "decrypt_credential_response", "parent_flow_id": "flow-vci-001", "jwe": "<compact JWE>", "deferred": false}
```

The client decrypts, keeps the credentials and the response-level `credential_metadata` locally, and completes the sub-flow with control members only: `transaction_id` (and optionally `interval`) when issuance is deferred, otherwise `credential_count` (1 to 256), never both; or an `error`. The server then polls the deferred endpoint (repeating the same `credential_response_encryption` JWK in the Deferred Credential Request) or completes the flow with `credential_response_encrypted: true`. The client supplies the `notification_id` itself in the credential notification.

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
| `select_credentials` | Record the user's decision to disclose, per credential query of the verifier's request (Section 3.2.3.1) | `consent`: bool, `selections`: `{query_id, selection_handle}` objects |
| `cancel` | Cancel the flow | `reason`: string (optional) |

**Consent and selection:**

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
      "consent": true,
      "selections": [
        {
          "query_id": "pid",
          "selection_handle": "Zm9yLXRoZS13YWxsZXQtb25seQ"
        }
      ]
    }
  }
}
```

##### 3.2.3.1 `select_credentials` Parameters

The `params` of a `select_credentials` action have exactly these members:

| Member | Type | Required | Description |
|--------|------|----------|-------------|
| `consent` | boolean | REQUIRED | `true` if the user consents to the disclosure described by `selections`; `false` if the user declines |
| `selections` | object[] | REQUIRED when `consent` is `true` (at least one element), otherwise absent or empty | One element per credential query the user consents to answer |

Each element of `selections` has exactly these members, both REQUIRED:

| Member | Type | Description |
|--------|------|-------------|
| `query_id` | string | The `id` of a credential query in the DCQL query of the verifier's own request; for a request that carries a `presentation_definition` instead of a DCQL query (Section 3.2.1), the `id` of one of its `input_descriptors` (an arbitrary string there, so the form check is only: 1 to 256 characters, no ASCII or Unicode whitespace, no C0 or C1 control characters and no zero-width or byte-order-mark characters, as the pattern in the schema spells out). It MUST occur in the verifier's request, and at most once in `selections` |
| `selection_handle` | string | The opaque per-flow handle, the same value in every element. It is the handle of the `match` result (Section 3.3.2), unchanged, when the result carried one; otherwise (no `match` flow ran, or its result omitted the handle) the wallet chooses one for this flow at this point by the rules of Section 3.3.2. 22 or more base64url characters without padding (the pattern of `schema/methods/match-result.json`) |

The orchestrator learns that the user consented, and for which of the verifier's own query ids. It does not learn which credential the user chose for a query, how many credentials could answer it, or which claims are disclosed.

**The wallet bounds disclosure.** The wallet MUST disclose, for each selected `query_id`, no more than the query asks for: the claims named by that credential query, honouring its `claim_sets`, and the claims that the format requires to make the presentation verifiable. The user MAY narrow the disclosure in the wallet, never widen it. The orchestrator does not receive claim names in this action and therefore does not check them; the check of which claims a presentation may carry is the wallet's (Section 6.2).

**Closed set.** `params` of `select_credentials` and each element of `selections` are closed: nothing but the members above may be present. In particular they MUST NOT carry, in any member or at any depth: a credential identifier, `credential_id`, `disclosed_claims` or any other claim name, path or value, a disclosure, a credential or any part of one, `vct`, `doctype`, a credential `format`, an issuer or trust-anchor identity, a count of credentials, or free text. An orchestrator MUST NOT ask a wallet for such data in this action. The rule of WMP Core Section 9.5 that unknown members are ignored does not apply here, because ignoring a member would still have received it.

The orchestrator validates `params` against `schema/methods/select-credentials-params.json`, selected by the `action` of a flow it recorded as `oid4vp`, never by members of the params. It MUST refuse `params` that have a member other than those above, whose members have the wrong type, whose `selection_handle` is not of the form above, differs between elements, or (when the `match` result for this request carried a handle) differs from that handle, or whose `query_id` is not an `id` in the verifier's request or is repeated; and `selections` that is present and non-empty when `consent` is `false`, or empty or absent when it is `true`. It refuses by ending the `oid4vp` flow with a terminal `wmp.flow.error` on that flow, code `-32602` (Invalid params), whose `data` MUST NOT echo any member of the offending params, and reports `access_denied` to the verifier as in Section 3.2.6 (no `error_description`). The `wmp.flow.action` is a request and the wallet awaits its response, so the orchestrator MUST also answer it with a correlated JSON-RPC error response, code `-32602` and no `data`; the terminal `wmp.flow.error` is a separate notification and does not answer the request. The orchestrator MUST NOT log, store or forward the offending members, and MUST NOT act on a part of refused params.

When `consent` is `false` the orchestrator ends the flow as for a user who declined (Section 3.2.6); it does not start a `sign_presentation` sub-flow.

**One naming, everywhere.** The names above are final and are the same on every wire that carries this decision, including an orchestrator's own client protocol (for example a WebSocket flow-action channel that is not WMP): the action is `select_credentials` (not `consent`), its payload is the `params` of this Section (`consent`, `selections[].query_id`, `selections[].selection_handle`; not `selected_credentials`), and the sign request carries `credentials_to_include` as `[{"credential_query_id": ...}]` plus `selection_handle` (Section 3.2.5). An orchestrator MUST NOT accept the old action name or payload shape alongside, and a wallet MUST NOT send it.

**Breaking change.** Earlier drafts carried `selections` of `{credential_id, disclosed_claims}` with `consent`. That shape is a violation of this Section: a receiver that gets it refuses it as above.

#### 3.2.4 Completion Result

| Field | Type | Description |
|-------|------|-------------|
| `vp_token` | string/string[]/object | VP token(s) |
| `presentation_submission` | object | Presentation submission descriptor |
| `response_code` | string | Response code from verifier (if applicable) |

`vp_token`, when present, is a non-empty string, a non-empty array of non-empty strings or, for a DCQL request, a non-empty object whose values are non-empty arrays of non-empty strings (`{"<credential query id>": ["<presentation>", ...]}`). A result whose `vp_token` is any other value (for example null, a boolean, a number, an empty string, array or object, an array holding a non-string, an empty string or an array, or an object value that is not an array of non-empty strings) MUST be refused as a malformed result, and the value MUST NOT be logged or echoed.

#### 3.2.5 Presentation Sign Sub-flow

To obtain the VP token the orchestrator starts a nested `sign` flow with `action` `sign_presentation`, linked to the `oid4vp` flow by `parent_flow_id`, as for the OID4VCI sign sub-flow in Section 3.1.5. This section defines the members relevant to `transaction_data`, plus the extension members of Section 7; other members are defined by the implementation profile.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | REQUIRED | `sign_presentation` |
| `nonce` | string | REQUIRED | The verifier's `nonce` |
| `audience` | string | REQUIRED | The verifier's client identifier |
| `parent_flow_id` | string | REQUIRED | The `oid4vp` flow this sub-flow belongs to |
| `client_metadata` | object | OPTIONAL | The verifier's `client_metadata`, verbatim. See Section 7.1. |
| `verifier_jwk_thumbprint` | string | OPTIONAL | Thumbprint of the verifier's response-encryption key. See Section 7.2. |
| `verifier_session_id` | string | OPTIONAL | The verifier's session identifier. See Section 7.3. |
| `response_mode` | string | OPTIONAL | The `response_mode` of the verifier's request. Required for a request that carries `transaction_data` (EC TS12 puts it in the key binding JWT). |
| `credentials_to_include` | object[] | OPTIONAL | The credential queries the user consented to answer, each `{"credential_query_id": "<DCQL id>"}` and nothing else: no credential identifier and no claim names (Section 3.2.3.1). The wallet knows which credential and which claims. |
| `selection_handle` | string | REQUIRED when the sub-flow follows a `select_credentials` action with `consent` `true`, otherwise absent | The handle of that action (Section 3.2.3.1), handed back unchanged; the wallet maps it to its own selection. The orchestrator MUST NOT interpret it and MUST NOT alter or omit it; a wallet MUST fail the sub-flow with a `wmp.flow.error` (not `rejected`) if it is missing or unknown. See Section 3.3.2. |
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
        {"credential_query_id": "pay"}
      ],
      "selection_handle": "Zm9yLXRoZS13YWxsZXQtb25seQ",
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

#### 3.2.6 Refusing the Sign Sub-flow

A wallet that will not sign (the user declined, the wallet does not trust the verifier, or a value the signature must bind is missing) ends the `sign` sub-flow with `wmp.flow.error` and `data.reason` `rejected`, the well-known reason of WMP Core Section 6.2 for a responder that declines. Any other `wmp.flow.error` is a failure, not a refusal.

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.flow.error",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_id": "flow-vp-001-sign",
    "code": -31006,
    "message": "declined",
    "data": {"reason": "rejected"}
  }
}
```

The orchestrator MUST end the `oid4vp` flow at once and MUST NOT wait for the sub-flow's timeout. It reports the refusal to the verifier as `access_denied` (OID4VP) with the request's `state` and **no** `error_description`, using the response mode of the request. `message` and any other `data` members of the sub-flow's `wmp.flow.error` stay between the wallet and the orchestrator: the orchestrator MUST NOT forward them to the verifier, since they may say why the wallet refused.

Towards the wallet the `oid4vp` flow ends with a terminal `wmp.flow.error` on the parent flow, code `-31006`. This profile defines no `wmp.flow.complete` result for a refused presentation. When the response mode of the request produced a verifier redirect (for example `query` or `fragment`), its URL is carried in `data.redirect_uri`; `data` is omitted otherwise.

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.flow.error",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_id": "flow-vp-001",
    "code": -31006,
    "message": "User declined the request",
    "data": {"redirect_uri": "https://verifier.example.com/cb?error=access_denied&state=st-1"}
  }
}
```

### 3.3 `match` Flow — Local Credential Matching

The `match` flow type lets an orchestrator ask the wallet whether it can satisfy a DCQL query, without learning anything about what the wallet holds beyond the answer. It is a nested flow of an `oid4vp` flow, linked to it by `parent_flow_id` in its `params`, and is defined by this profile for use with the `oid4vp` capability: a wallet that did not negotiate `oid4vp` is sent no `match` flow, and a `match` start to such a wallet is `-31005` as for any flow type (WMP Core Section 3.8.1). It has no progress steps and no actions.

#### 3.3.1 Start Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `parent_flow_id` | string | REQUIRED | The `oid4vp` flow this flow belongs to (as for the `sign` sub-flows, Section 3.1.5) |
| `dcql_query` | object | REQUIRED | The verifier's DCQL query, as validated by the orchestrator |
| `client_metadata`, `verified_request` | object | OPTIONAL | The request context of Sections 7.1 and 7.5, with the same meaning as in the `sign_presentation` params |

The start carries only data that originates from the verifier request. It carries nothing about the wallet.

#### 3.3.2 Result

The wallet ends the flow with `wmp.flow.complete`. The result has exactly these members:

| Member | Type | Required | Description |
|--------|------|----------|-------------|
| `satisfiable` | boolean | REQUIRED | `true` if the wallet can satisfy the query, including its `credential_sets`; `false` otherwise |
| `satisfiable_query_ids` | string[] | OPTIONAL | The `id` values of the query's credential queries that the wallet can satisfy. Each element MUST be an `id` that occurs in the `dcql_query` of the start, at most once |
| `selection_handle` | string | OPTIONAL | An opaque handle that means something only to the wallet (below) |
| `code` | string | REQUIRED when `satisfiable` is `false`, otherwise absent | `no_match` (no credential matches), `insufficient` (some match, the query as a whole cannot be satisfied) or `error` (the wallet could not evaluate the query) |

```json
{
  "jsonrpc": "2.0",
  "method": "wmp.flow.complete",
  "params": {
    "wmp": {"version": "0.1", "session_id": "ses-a1b2c3d4"},
    "flow_id": "flow-vp-001-match",
    "result": {
      "satisfiable": true,
      "satisfiable_query_ids": ["pid"],
      "selection_handle": "Zm9yLXRoZS13YWxsZXQtb25seQ"
    }
  }
}
```

`selection_handle` is chosen by the wallet at random (at least 128 bits, base64url) for this flow only. It MUST NOT be derived from a credential, its identifier, its content or the user, and MUST NOT be reused in another flow. The orchestrator treats it as an opaque string it can hand back: the wallet puts it in each element of `selections` of the `select_credentials` action (Section 3.2.3.1), and the orchestrator includes it unchanged as `selection_handle` in the `sign` params of the `sign_presentation` that follows (Section 3.2.5), where the wallet maps it to its own selection. The orchestrator MUST NOT interpret it.

#### 3.3.3 No credential data reaches the orchestrator

The wallet MUST evaluate the query locally. A `match` result MUST NOT carry anything other than the four members above. In particular it MUST NOT carry, in any member or at any depth: a claim value, a claim name or path, a disclosure, a credential or any part of one, a credential identifier, `vct`, `doctype`, a credential `format`, an issuer or trust-anchor identity, a count of credentials, or free text (including an error message or the reason for a failure; `code` is the whole reason). `satisfiable_query_ids` names the verifier's own query ids and nothing more.

The orchestrator MUST refuse a result that has a member other than those of Section 3.3.2, whose members have the wrong type, whose `code` is not one of the listed values or is present when `satisfiable` is `true` or absent when it is `false`, or whose `satisfiable_query_ids` has an element that is not an `id` of the query or is repeated. A `wmp.flow.complete` is a notification and has no response, so it refuses by ending the parent `oid4vp` flow with a terminal `wmp.flow.error` on the parent flow, code `-32602` (Invalid params), whose `data` MUST NOT echo any member of the offending result; it reports `access_denied` to the verifier as in Section 3.2.6 (no `error_description`). It MUST NOT log, store or forward the offending members. The orchestrator validates the result against `schema/methods/match-result.json`, which it selects by the flow type it recorded for the `flow_id` when it started the flow, never by members of the result: a result that omits `satisfiable` is refused like any other. This is a closed set: the rule of WMP Core Section 9.5 that unknown members are ignored does not apply to a `match` result, because ignoring a member would still have received it.

An orchestrator MUST NOT ask the wallet for credential data in order to match, and MUST NOT fall back to doing so when a wallet cannot match locally; such a wallet answers `satisfiable` `false` with `code` `error`, or ends the flow with `wmp.flow.error` `-31006` and `data.reason` `rejected` when the user declines. A rejected `match` sub-flow is handled exactly as a rejected `sign` sub-flow in Section 3.2.6: the orchestrator ends the `oid4vp` flow at once, without waiting for a timeout, reports `access_denied` to the verifier with the request's `state` and no `error_description`, does not forward the sub-flow's `message` or other `data`, and sends the wallet the terminal `wmp.flow.error` of Section 3.2.6 on the parent flow. An orchestrator that uses this flow has no wallet-derived `matched_credentials` or `requested_claims` to put in the `awaiting_consent` payload of Section 3.2.2 and omits them; the wallet shows its own.

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
      │    params: {consent: true,   │
      │      selections: [{query_id, │
      │       selection_handle}]}}   │
      │                              │
      │<── wmp.flow.complete ────────│
      │   {result: {vp_token: "..."}}│
      │                              │
```

## 6. Security Considerations

### 6.1 Issuer/Verifier Trust

Before presenting credentials or accepting issued credentials, implementations MUST evaluate trust in the counterparty. The `trust_evaluated` progress step provides trust evaluation results. Implementations SHOULD NOT auto-accept credentials from untrusted issuers or auto-disclose credentials to untrusted verifiers.

### 6.2 Selective Disclosure

When the `oid4vp` flow reaches `awaiting_consent`, the wallet MUST present the user with the specific claims requested and allow the user to control which claims are disclosed. Implementations MUST NOT disclose claims beyond what the user explicitly consents to, and the wallet MUST NOT disclose beyond what the verifier's query asks for. That bound is enforced in the wallet; the orchestrator never sees claim names in the `select_credentials` action (Section 3.2.3.1) and so cannot vet them.

### 6.3 Nonce Binding

All proof JWTs generated in OID4VCI sign sub-flows MUST be bound to the nonce provided by the issuer. Implementations MUST reject proofs with missing or mismatched nonces.

### 6.4 Credential Offer Validation

Implementations MUST validate credential offers before processing:
- Verify the offer URI scheme and structure
- Resolve and validate issuer metadata
- Check credential types against known VCTMs

### 6.5 Credential Matching

Matching is where an orchestrator would most easily learn what a wallet holds, so Section 3.3.3 makes the result a closed set and forbids the orchestrator to ask for more. The answer reveals at most which of the verifier's own query ids the wallet can satisfy.

### 6.6 Transaction Data

`transaction_data` makes the user's consent legally significant (a payment authorization), so the display and the hash must describe the same bytes. Section 3.2.5 therefore has the wallet derive what it shows from `raw`, which is also what it hashes, and treat everything else the orchestrator sends as untrusted. Capability negotiation (Section 2.3) keeps the data away from wallets that would drop it silently; the orchestrator's refusal is the only barrier for those, so it MUST NOT be skipped for unauthenticated or "best effort" flows.

## 7. Extension Members

The members below are optional extension members in the sense of WMP Core Section 9.5: receivers MUST ignore them if they do not understand them, and senders MUST NOT require them to be understood. Adding a purely additive, ignorable member does not change the WMP protocol version or the version of any capability. A member whose processing is required for correctness or safety is not covered by the ignore rule: `transaction_data` and `response_mode` (for a request that carries transaction data) remain gated by the `transaction_data` capability (Section 2.3) and the fail-closed requirements of Section 3.2.5, as Core Section 9.5 rule 2 provides. This table is the registry of extension members of this profile; a new member is added here, with its location and semantics, in a MINOR revision of this document.

| Member | Carried in | Type | Section | Since |
|--------|-----------|------|---------|-------|
| `client_metadata` | `sign` params (`sign_presentation`); matching request params; `credential_selection` progress payload | object | 7.1 | 0.1.0 |
| `verifier_jwk_thumbprint` | `sign` params (`sign_presentation`) | string | 7.2 | 0.1.0 |
| `verifier_session_id` | `sign` params (`sign_presentation`) | string | 7.3 | 0.1.0 |
| `verified_request` | `sign` params (`sign_presentation`); matching request params; `credential_selection` progress payload | object | 7.5 | 0.1.0 |
| `selection_handle` | `sign` params (`sign_presentation`); `match` result; each element of `selections` in `select_credentials` params | string | 3.2.3.1, 3.3 | 0.1.0 |
| `credential_response_encryption` | `sign` params (`generate_proof`) | object | 7.6 | 0.1.0 |
| `jwe`, `deferred` | `sign` params (`decrypt_credential_response`) | string, boolean | 7.6 | 0.1.0 |
| `credential_response_encrypted` | `oid4vci` completion result | boolean | 3.1.4, 7.6 | 0.1.0 |
| `context` | `trust_evaluated` progress payload (when `verifier_trust_evaluated` is `true`) | object | 7.4 | 0.1.0 |
| `response_mode` | `sign` params (`sign_presentation`) | string | 3.2.5 | 0.1.0 |
| `transaction_data` | `sign` params (`sign_presentation`) | object[] | 3.2.5 (gated by the `transaction_data` capability) | 0.1.0 |
| `response_encryption` | `sign` params (`sign_presentation`, `response_mode` `direct_post.jwt` only) | object | 7.7 | 0.1.0 |
| `state` | `sign` params (`sign_presentation`, together with `response_encryption`) | string | 7.7 | 0.1.0 |
| `response_jwe` | `sign` result (`sign_presentation`, `response_mode` `direct_post.jwt` only) | string | 7.7 | 0.1.0 |

### 7.1 `client_metadata`

The verifier's OpenID4VP `client_metadata` JSON object, taken verbatim from the validated request object (inline, or fetched from `client_metadata_uri`). It carries what the orchestrator itself does not model, notably `vp_formats_supported`. For a `zkp_req` presentation (typically with `response_mode` `direct_post.jwt`) its `vp_formats_supported.zkp_req` holds the `system_id_values` and `proof_system_values` from which the wallet chooses its circuit and proof system.

- The sender MUST omit the member when the request had no client metadata, that is, neither an inline `client_metadata` nor one resolved from `client_metadata_uri`. A request with only `client_metadata_uri` carries the fetched object.
- The value is carried verbatim (Core Section 9.5 rule 4); the wallet MUST NOT assume any member beyond those it understands.
- It is carried on the `sign` params of a `sign_presentation` action, and, where an implementation passes the request context to the wallet in a credential matching request or in the payload of a `credential_selection` progress message, in those too, with the same name and meaning. This profile does not otherwise define those messages.

```json
"client_metadata": {
  "jwks": {"keys": []},
  "vp_formats_supported": {
    "zkp_req": {
      "system_id_values": ["longfellow-libzk-v1"],
      "proof_system_values": ["vega"]
    }
  }
}
```

### 7.2 `verifier_jwk_thumbprint`

The JWK Thumbprint (RFC 7638, SHA-256) of the verifier's response-encryption key, as an **unpadded base64url** string. For `response_mode` `direct_post.jwt` the member is never empty: the wallet uses it to build the OpenID4VP session transcript (the handover for mdoc). If the orchestrator cannot read that key it MUST fail the flow rather than send an empty value; go-wallet-backend fails the flow with a `SIGN_ERROR` flow error. This section defines the member for `direct_post.jwt` only; go-wallet-backend omits it for other response modes, and whether it is sent for another encrypted mode (for example `dc_api.jwt`, whose handover also needs the thumbprint) is not defined here.

### 7.3 `verifier_session_id`

The verifier-assigned identifier of this presentation session. A ZK pseudonym's verifier context binds to the session rather than to the verifier's static identity, so it needs this value rather than `audience` alone. Omitted for non-ZK presentations and for OID4VCI sign sub-flows.

### 7.4 `context` (verifier trust result)

When the engine evaluates verifier trust, the `verifier_trust_evaluated` flow progress (a `trust_evaluated` step whose payload has `verifier_trust_evaluated: true`) MAY carry `context`, containing only `verifier_ids` from the PDP response (omitted if none): a list of `{verifier_id_type, verifier_id, basis?}`, present only when the PDP policy enables it and the identifier was verified. Wallets read the verifier identifier for pseudonym derivation from it. For `x509_san_dns` the value is the bare lower-case DNS name, so the wallet forms the `x509_san_dns:<dns>` prefix itself; semantic ids already carry the `semantic_id:` prefix. Cache hits carry the same context as fresh evaluations.

- The sender MUST NOT forward any other member of the PDP context (such as `reason` or `trust_metadata`), and omits `context` entirely when there are no `verifier_ids`.
- `verifier_id_type` is an opaque string; `basis` says how the identifier was verified.

```json
"context": {
  "verifier_ids": [
    {"verifier_id_type": "semantic", "verifier_id": "semantic_id:VATSE-556000000101", "basis": "x5c-chain"},
    {"verifier_id_type": "x509_san_dns", "verifier_id": "verifier.example.com", "basis": "client-id-binding"}
  ]
}
```

### 7.5 `verified_request`

The OpenID4VP request as the orchestrator validated it. It is built once per flow and carried identically at every point where an implementation passes the request context to the wallet: the `sign` params of a `sign_presentation` action, a credential matching request, and the payload of a `credential_selection` progress message. A wallet therefore applies one policy over the whole flow and over every transport, including a redirect flow. The member carries no trust verdict. The wallet MUST still require the verifier trust result (the `verifier.trusted` outcome of Section 7.4's evaluation) and, for the x509 `client_id` schemes, MUST NOT treat `signed` as a substitute for it: the SAN or hash binding of the certificate to `client_id` is the trust evaluation's check, not the signature check. This profile does not otherwise define those messages. Its members are additive, and receivers MUST ignore members they do not understand.

| Member | Meaning |
|--------|---------|
| `client_id` | The request's own `client_id`, after the `client_id` match and scheme-prefix checks. It is not an administrator-configured audience (such as the one carried by `verifier.client_id`). |
| `client_id_scheme` | The `client_id` scheme: `x509_san_dns`, `x509_san_uri`, `x509_hash`, `did` or `decentralized_identifier`, `verifier_attestation`, `redirect_uri`. Omitted when the request has none. |
| `response_mode` | The request's `response_mode`, as the orchestrator received it, for example `direct_post`, `direct_post.jwt`, `query`, `fragment`, `dc_api` or `dc_api.jwt`. The list is not exhaustive: a wallet MUST treat any value it does not recognise as not encrypted. Omitted when the request has none. |
| `response_uri` | The validated `response_uri`; the `redirect_uri` when the request has no `response_uri` (as for the redirect response modes). |
| `signed` | Boolean. `true` only when `signature_verification` is `"verified"`. A receiver that does not know the member reads the request as not signed. |
| `signature_verification` | `"verified"`, `"deferred"` or `"none"`. |
| `client_metadata` | The verifier's `client_metadata`, verbatim, as in Section 7.1. Omitted when the request had none. |

`signature_verification` states only what the orchestrator itself established: that the request object's signature verified against a key the `client_id` scheme binds to `client_id`.

| Scheme | `verified` when | Otherwise |
|--------|-----------------|-----------|
| `x509_san_dns`, `x509_san_uri`, `x509_hash` | the JWT signature verified against the header `x5c` | the flow fails |
| `did`, `decentralized_identifier` | the signature verified against a key resolved for the DID (a verifier policy decision point is configured) | `deferred` when none is configured: resolution and verification are left to the wallet |
| `verifier_attestation` | the signature verified against the attestation's `cnf` key and a verifier policy decision point is configured to validate the attestation | `deferred` when none is configured: nothing has checked the attestation that binds `cnf` to `client_id` |
| `redirect_uri` | never | `none`: a valid embedded key proves possession only |

- `deferred` MUST NOT be treated as verified.
- `client_metadata` inside `verified_request` is unauthenticated unless `signed` is `true`; when `signed` is `false` the wallet MUST treat it as data supplied by an unauthenticated party. The top-level `client_metadata` member (Section 7.1) is unchanged and carries the same value.
- A wallet MUST fail closed for a `zkp_req` presentation when `verified_request`, `signed` or `response_mode` is absent (for example because the orchestrator predates this member): it MUST NOT infer a signed request or an encrypted response mode from their absence. The orchestrator does not itself refuse a `zkp_req` presentation over a non-encrypted `response_mode`; that refusal is the wallet's, taken from `response_mode` here.
- This member is not capability-gated (Core Section 9.5 rule 1 applies): a wallet that predates this section ignores it, so the checks above hold only for wallets that implement it. This revision defines no capability that lets the orchestrator refuse a `zkp_req` flow for such a wallet, and the orchestrator does not enforce the `response_mode` policy itself.

```json
"verified_request": {
  "client_id": "x509_san_dns:verifier.example.com",
  "client_id_scheme": "x509_san_dns",
  "response_mode": "direct_post.jwt",
  "response_uri": "https://verifier.example.com/response",
  "signed": true,
  "signature_verification": "verified",
  "client_metadata": {"vp_formats_supported": {}}
}
```

A `did:web:verifier.example.com` request with no verifier policy decision point gives `"signed": false, "signature_verification": "deferred"`; a `redirect_uri` request gives `"signed": false, "signature_verification": "none"`.

### 7.6 Credential response encryption (OID4VCI)

Members of the engine-blind issuance flow of Section 3.1.5.1: `credential_response_encryption` (`{alg, enc, required}`) in `generate_proof` params; `jwe` and `deferred` in `decrypt_credential_response` params; `credential_response_encrypted` in the completion result. The client's answers (`credential_response_encryption_jwk`, `transaction_id`, `interval`, `credential_count`, `error`) are members of the sign result. All are additive and ignorable (Core Section 9.5 rule 1): a wallet that does not implement them does not supply a key, which fails a `required` issuance closed and otherwise leaves the issuer response in clear and visible to the orchestrator. `credential_response_encrypted` removes `credentials[].credential` and `credential_metadata` from the completion; a receiver that does not know it would see credentials without values, but it cannot receive one: a wallet that cannot decrypt supplies no key (absent or empty `credential_response_encryption_jwk`, Section 3.1.5.1), so the server fails a `required` issuance and never falls back to a plaintext response, and a response that is not `required` stays in clear. A decryption result carries control members only: never `credentials` or `credential_metadata`.

### 7.7 `response_encryption`, `state` and `response_jwe`

For a `sign_presentation` action of a request whose `response_mode` is `direct_post.jwt`, the orchestrator does not receive the `vp_token`: the wallet builds the response and encrypts it itself, and the orchestrator only relays it. The `sign` params carry the recipient, and the `sign` result carries the finished JWE.

`response_encryption` is an object `{jwk, alg, enc}`: `jwk` is the verifier's public response-encryption JWK (with its `kid` when it has one), `alg` the JWE key-management algorithm and `enc` the content-encryption algorithm. The orchestrator resolves them with its ordinary selection (the `use` `enc` key of `client_metadata.jwks`, else the key of the request object's `x5c` header; `alg` from `client_metadata`, else the JWK, else the key type; `enc` `A128GCM` unless `client_metadata` names another), so the wallet does not re-derive them. `state` is the request's `state`, omitted when the request had none.

The wallet builds:

- the `vp_token`: for a DCQL request a JSON object `{"<credential query id>": ["<presentation>", ...]}`, otherwise the string;
- the JARM claims: `iss` `https://self-issued.me/v2`, `aud` the `client_id` of `verified_request` (Section 7.5), `iat`, `exp` (`iat` + 300), `vp_token`, and `state` when present;
- a compact JWE of those claims to `jwk` with the requested `alg` and `enc`, `kid` in the protected header when `jwk` has one, and `cty` `JWT`.

It answers the sign sub-flow with `response_jwe`, the compact JWE. The orchestrator POSTs `response=<jwe>` (form-urlencoded) to the `response_uri` of `verified_request` and returns the verifier's `redirect_uri`; the wallet never posts.

- The orchestrator cannot decrypt the value and MUST NOT build or encrypt the response itself. A wallet that answers with a `vp_token`, with no `response_jwe`, or with a value that is not a compact JWE using the requested `alg` and `enc` (and `kid`) is refused: the orchestrator fails the flow and answers the verifier `access_denied` with no detail. If it cannot resolve a usable public key and algorithms it sends no sign request and does the same.
- A sign result that reports an error carries no `response_jwe`.
- Scope: the claims above cover a DCQL request and a plain string `vp_token`. This section does not define `presentation_submission` for a `presentation_definition` request (the orchestrator cannot add it to the opaque JWE); that case is not covered.
- The members are additive (Core Section 9.5 rule 1): a wallet that predates this section ignores `response_encryption` and answers with a `vp_token`, which the orchestrator refuses rather than encrypting for it. Refusing does not undo the disclosure: such a wallet has already sent the `vp_token` to the orchestrator, so the engine-blind guarantee holds only with wallets that implement this section. This profile defines no capability negotiation for it (an orchestrator that must not see a `vp_token` has to know its wallets implement it, as the engine-blind deployment does); Core Section 9.5 rule 2 gating is not provided here. Other response modes (`direct_post`, `query`, `fragment`) are unchanged and the orchestrator sees the `vp_token`, as the verifier requested a cleartext response.

```json
"response_encryption": {
  "jwk": {"kty": "EC", "crv": "P-256", "x": "...", "y": "...", "kid": "verifier-enc-1", "use": "enc"},
  "alg": "ECDH-ES",
  "enc": "A128GCM"
},
"state": "st-1"
```

## References

- [WMP Core Specification](wmp-core.md)
- [OpenID for Verifiable Credential Issuance 1.0](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html)
- [OpenID for Verifiable Presentations 1.0](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html)
- [Verifiable Credential Type Metadata](https://www.ietf.org/archive/id/draft-ietf-oauth-sd-jwt-vc-05.html)
- [EC TS12: Specification of Strong Customer Authentication (SCA) Implementation with the Wallet, v1.0.1](https://github.com/eu-digital-identity-wallet/eudi-doc-standards-and-technical-specifications/blob/main/docs/technical-specifications/ts12-electronic-payments-SCA-implementation-with-wallet.md)

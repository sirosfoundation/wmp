# WMP European Business Wallet (EBW) Secure Registered Delivery Profile

## Wallet Messaging Protocol — End-to-End Encrypted Registered Delivery Between Legal Entities

**Status:** Draft
**Version:** 0.2.0

> **Provisional wire details.** Method names, field names and error codes marked *(provisional)* are proposals that will be aligned with the reference design for the EBW Secure Communication Channel once its wire format is published. Everything else in this profile is stable relative to WMP Core, Evidence and MLS.

## 1. Introduction

This profile defines how WMP carries **registered delivery between legal entities with end-to-end encryption**, for the European Business Wallet (EBW) context: Regulation (EU) No 910/2014, the EBW Regulation (COM/2025/838), Commission Implementing Regulation (EU) 2025/1944 and the ETSI EN 319 521/522 framework.

Its model differs from a plain WMP deployment in three ways:

1. **Entity keys live in a directory, not in DNS.** An entity is addressed by a provider-independent identifier whose signed history is held by a directory. Endpoint keys are authenticated by credentials the entity itself signs.
2. **Providers verify group membership.** Providers never see plaintext, but they track MLS group membership so that every message is encrypted to exactly the endpoints that hold the addressed role.
3. **Delivery is evidenced by a decryption report.** A message counts as handed over when a recipient endpoint reports that it could decrypt it and that the plaintext matches the sender's commitment.

### 1.1 Composed Profiles

An implementation MUST conform to WMP Registered ([wmp-core.md](wmp-core.md) §10.1), WMP Evidence ERDS Conformance ([wmp-evidence.md](wmp-evidence.md) §9.2) and the MLS layer ([wmp-mls.md](wmp-mls.md)). Where this profile tightens an OPTIONAL choice in those documents, the tightening applies only to sessions operating under this profile.

### 1.2 Roles

| Role | Description |
|------|-------------|
| **Owner** | The legal entity. Holds the update keys and credential keys named in its registry document. |
| **Endpoint** | A system enrolled by the owner (wallet, case-management system, gateway). Holds its own decryption and signing keys. An endpoint is an MLS group member. |
| **RDS** | Registered Delivery Service: a WMP relay that is also an ERDS. A sending RDS and a receiving RDS take part in every delivery (the four-corner model). RDSes never hold endpoint keys. |
| **Directory** | A service holding registry documents (§3). Only RDSes access it. |

### 1.3 Scope

This profile covers the registered-delivery path. The structured flow lifecycle, the OpenID4VCI/OpenID4VP profile and the WebAuthn binding are not required and MUST NOT be a precondition for delivery.

## 2. Security Mode

A session under this profile MUST negotiate `security_modes: ["mls"]` ([wmp-core.md](wmp-core.md) §4.2.3). `tls` and `mls-optional` MUST NOT be used for any message on the registered-delivery path. MLS ciphersuites MUST be on the ENISA Agreed Cryptographic Mechanisms list current when the group is created, and post-quantum or hybrid suites MUST be adopted for new groups within 12 months of IETF assignment of a suite meeting ENISA guidance. Transport is TLS 1.3, with mutual TLS between RDSes.

## 3. Entity Discovery

### 3.1 The `ebw` identifier scheme *(provisional)*

An entity's digital address is an `ebw` URL, for example `ebw:baar3g6q3z7rabmz5w4soq43`. The part after the colon is a hash of the entity's create operation, so the URL authenticates its registry document without any further trust anchor. A role-scoped address appends the role: `ebw:<id>#<role>`.

`ebw` is registered as a WMP identifier scheme ([wmp-core.md](wmp-core.md) §7.2) and resolved through the profile-extensible resolver mechanism of §7.5.

### 3.2 Registry document

| Field | Description |
|-------|-------------|
| `identifiers` | Existing identifiers of the entity (EUID, LEI, VAT number and the harmonised EBW identifier) |
| `update_keys` | Keys allowed to sign updates, ranked. A higher-ranked key can override operations by lower-ranked keys inside the directory's published recovery window. |
| `credential_keys` | Keys allowed to sign endpoint credentials (§4) |
| `rds` | The RDS through which the address is reachable |
| `status` | `active`, `suspended`, `retired`, `merged` or `closed` |

The directory stores, per address, a hash-chained sequence of signed operations: *create*, *update* (signed by an update key authorised by the current document), and *status* (signed by the owner's RDS). Each operation carries the hash of the previous one.

### 3.3 Directory interface *(provisional)*

| Operation | Behaviour |
|-----------|-----------|
| `lookup` | Existing identifier (of an enumerated type) → registry document |
| `resolve` | `ebw` URL → current registry document |
| `audit` | `ebw` URL → the operation sequence from genesis to the current document |
| `status` | Fetch the directory-signed status list named in a head statement; shows which head statements later operations have superseded |
| `update` | Submit a new signed operation |

Only RDSes are authorised, authenticated with qualified seal certificates (§9). Relying parties verify the operation chain themselves, so a directory fault cannot produce a corrupted document. The directory is trusted not to deny valid updates and not to serve stale data. Directory-signed statements of the current document MUST carry an expiry, which bounds staleness.

*Limitation:* per-address auditing cannot reveal a directory that shows different histories to different parties. Periodic signed snapshots over all documents can close that gap and MAY be added later.

### 3.4 Existing identifiers

An RDS vouches for the binding from a legal-entity identifier to an `ebw` URL when it creates the entry. The directory ensures each identifier binds to one URL. An entity that has to start over publishes new bindings from its existing identifiers to the new URL.

## 4. Endpoint Credentials and KeyPackages

### 4.1 Credential chain

An endpoint credential is signed by an owner credential key (§3.2) and states:

- the `ebw` URL of the entity,
- the endpoint's **role** or roles within the entity,
- the endpoint's signing public key,
- validity and a status reference.

The endpoint signing key in turn signs the MLS signature key of each KeyPackage, so an endpoint can publish many KeyPackages with distinct MLS signature keys.

The credential key MUST be under the owner's control and MUST NOT be held by the RDS. This is what stops the receiving RDS from impersonating endpoints. If an owner delegates credential signing to its RDS, end-to-end encryption degrades to an intra-organisational control, and an implementation MUST make that visible in the evidence (§8).

**MLS carrier** *(open)*: the credential travels either as an `x509` credential issued under the owner's credential key, or as a profile-defined MLS credential type carrying the chain above. The choice is deferred to the reference design; either satisfies RFC 9420 §5.3.

### 4.2 Verification by the sender

A sending endpoint resolves the registry document, obtains an authenticated credential key, verifies each KeyPackage's credential with it, and verifies each KeyPackage against the credential. This gives a verified audience.

RDSes are trusted not to replay or suppress KeyPackages. They cannot fabricate them. A recipient endpoint can detect reuse of a KeyPackage when the resulting messages are not suppressed.

### 4.3 KeyPackage reservation *(provisional)*

KeyPackages under this profile are single-use.

- `wmp.keypackage.reserve`: sending RDS → receiving RDS. Parameters: the role address, the cipher suites the sender supports, and a reservation `id`. Result: one KeyPackage per matching endpoint, each marked reserved, or an error if the role has no endpoint. This is a request/response exchange; it MUST NOT be modelled as two one-way messages.
- `wmp.keypackage.publish`: endpoint → its RDS. Replenishes KeyPackages, with expiry.
- **Last-resort KeyPackages.** When single-use packages are exhausted, the receiving RDS MAY return a last-resort package for that endpoint, flagged `last_resort: true`. The sending RDS MUST record the flag in submission evidence, so the fact is visible to verifiers.

The existing `/.well-known/mls-key-packages` endpoint ([wmp-mls.md](wmp-mls.md) §2.3) is not used for registered delivery under this profile.

## 5. Group Membership

### 5.1 Principles

- A group is created at a sender's request and is tracked by the RDSes separately from messages.
- Each message references an MLS `group_id` and `epoch`.
- On every send, the group membership is checked against the current endpoints for the entities and roles involved.

### 5.2 Public Commits *(provisional)*

Under this profile, handshake messages (Commits) use MLS `PublicMessage`. An RDS keeps, for every group it has seen, the ratchet tree and the transcript of Commits and Welcomes. It still cannot read application messages. The cost is that each RDS sees group membership at the level of endpoints, credentials and roles. This is an accepted reduction of metadata minimisation, taken to get provider-side membership verification, and is stated here so that deployments cannot overlook it.

Capability: `mls_public_commits` ([wmp-core.md](wmp-core.md) §4.2). It MUST be negotiated; without it this profile is not satisfied.

### 5.3 Commit acceptance *(provisional)*

A Commit is submitted to one RDS (`wmp.mls.group.commit`). That RDS forwards it to the RDS of the other entity. The Commit is accepted only once **both** RDSes have accepted it, and takes effect then.

If two Commits for the same epoch arrive concurrently, both RDSes select one by a fixed rule, which is the Commit whose SHA-256 digest is lexicographically smaller. The other sender retries in the next epoch.

A Commit cannot take effect while either RDS is unreachable. Application messages are not subject to this limit (§5.4).

### 5.4 Membership check on send

When a message is submitted, the sending RDS checks its own endpoint information and the receiving RDS's information, and confirms that the group's members are exactly the endpoints listed for the entities and roles in the conversation. The receiving RDS performs the same check.

- If the receiving RDS is unreachable, the sending RDS MAY hold the message under normal store-and-forward. When the receiving RDS returns, the message proceeds if the checks pass. Otherwise the sending RDS reports a delivery failure and the sender retries.
- If the group is out of date, the sending RDS rejects the submission with `-31021` *(proposed)* and `data` listing the members to add and remove. The sender commits the change and resubmits.
- A member that receives a message from an epoch it does not have can fetch missed Commits from its RDS.

Any member of a group can send in it.

## 6. Roles and Acceptance Policies

Role-scoped addressing uses the `#<role>` suffix (§3.1). The recipient entity decides what a role exposes: a function, a group or a single inbox. The entity decides who holds a role by issuing credentials (§4.1).

Group membership for a role-addressed send is whatever the RDS check (§5.4) accepts. A member who leaves a role loses access to later messages. A new member does not gain access, through the channel, to earlier messages.

Acceptance policies (`any`, `quorum:N`, `all`) are carried in `applicable_policies` ([wmp-core.md](wmp-core.md) §3.5) and referenced by ID in the resulting evidence. Each member contributing to a quorum decision individually signs its acceptance action, and the evidence records each signature and the policy it satisfies.

*Residual gap:* the RDS check shows the group matches the provider-held endpoint list. It does not prove the list is a complete picture of the entity's current role holders. An owner-signed role roster, published through the registry document or alongside it, would close this and is a candidate extension.

## 7. Content Commitment and Decryption Report

### 7.1 Commitments in the submission

Every submission MUST carry:

- `plaintext_hash` ([wmp-core.md](wmp-core.md) §5.2.1): a salted hash of the plaintext content object, with the random salt sent inside the ciphertext. The sender retains the salt. This prevents equivocation.
- `epoch_authenticator` *(provisional)*: the MLS epoch authenticator for the epoch in which the message was sent, as a sibling of `plaintext_hash` in the content object. It commits the sender to a specific MLS state, including all message keys. Disclosing it to RDSes needs cryptographic review before this profile leaves Draft.

`require_plaintext_hash: true` ([wmp-evidence.md](wmp-evidence.md) §2) MUST be negotiated. Submissions without it are rejected with `plaintext_hash_missing`.

### 7.2 Decryption report *(provisional)*

Before a message counts as handed over, the recipient endpoint reports the outcome with `wmp.message.report` (endpoint → its RDS), signed with the endpoint's credential key (detached JWS, [wmp-core.md](wmp-core.md) §5.4):

| Field | Description |
|-------|-------------|
| `message_id` | The `id` of the delivered message |
| `group_id`, `epoch` | The group and epoch the endpoint processed |
| `outcome` | `ack` or `nack` |
| `reason` | For `nack`: `mismatch`, `decryption_failure`, `invalid_epoch` or `join_failure` |
| `plaintext_hash` | For `mismatch`: the endpoint's hash of the plaintext it obtained, computed with a fresh salt |
| `epoch_authenticator` | For `invalid_epoch`: the endpoint's own authenticator for the indicated epoch, if it has that epoch |

- **ack**: the message decrypted and the plaintext hash matched.
- **mismatch**: decryption succeeded but the plaintext did not match the commitment. This replaces the bare `-31019` rejection of [wmp-core.md](wmp-core.md) §5.2.1 on this path.
- **decryption_failure**: the endpoint agrees with the sender's epoch authenticator but could not decrypt.
- **invalid_epoch**: the endpoint's authenticator differs from the sender's, or it does not have the epoch.
- **join_failure**: the endpoint could not join the group.

An endpoint SHOULD send the report automatically, before surfacing the content to a human, so that withholding a report is a visible fault and not a decision about the message.

### 7.3 Evidence statuses

The recipient RDS's evidence reflects one of three statuses:

| Status | Evidence |
|--------|----------|
| ack | `content_handover` (new), referencing the report |
| nack | `content_handover_failed` with `event_reason` set to the NACK reason, referencing the report |
| no response | `delivery_confirmed` as before: the ciphertext was made available. Disputes over decryption are deferred until a dispute over delivery arises. |

Decryption acknowledgement bounds the need for the plaintext hash and epoch authenticator. They matter only when a dispute about decryption arises.

### 7.4 Proving what was delivered

A sender substantiates a claim by (1) disclosing the salt and (2) re-processing the MLS transcript to show that the derived key decrypts the ciphertext to the committed plaintext. Only one plaintext matches the salted hash.

Showing that the recipient could have decrypted ("bogus encryption") requires both sender and recipient to retain private MLS state, because a participant can show only the keys derived from its own state. This conflicts with RFC 9420's forward-secrecy deletion rules, so the retention is limited:

- The sender retains the state for an epoch until messages sent in it are acknowledged.
- The recipient retains the state of the last epoch in which it agreed with the sender and of the last epoch it created with its own Commit.

If an entity declines to retain this state, non-decryption disputes cannot be resolved conclusively. Retained state is a compromise risk until a post-compromise update refreshes it.

## 8. Evidence

- Evidence follows [wmp-evidence.md](wmp-evidence.md), binds to the ciphertext as transmitted, and additionally records `group_id`, `epoch`, the sender's `epoch_authenticator`, and, when set, the last-resort flag (§4.3).
- `previous_evidence_id` MUST be populated on every evidence object after the first in a delivery's sequence, so a verifier can detect a missing link.
- The baseline evidence (that the message was made available to the recipient, or that delivery failed) MUST NOT depend on any action by the recipient. A sender MAY request further grades: delivery, decryption, acceptance, rejection and expiry. The profile therefore does not default to `consented_signed`; the sender chooses, and a sender MUST be able to require it.
- A signed acceptance covers at least `plaintext_hash`, `original_content_hash` and a timestamp.
- The `evidence_version` field ([wmp-evidence.md](wmp-evidence.md) §4.2) identifies the structure, so that evidence stays verifiable as the protocol evolves.
- Evidence records credential status at the time of use, so its validity can be assessed after a device compromise.
- Endpoints do not issue evidence. They provide the signed reports that RDS evidence reflects. Only RDSes issue evidence.

## 9. Provider Qualification and Federation

The set of participants is closed and defined through eIDAS. Only qualified electronic registered delivery service providers on national trusted lists take part.

- RDSes authenticate to each other, and to the directory, with qualified seal certificates listed on the EU Trusted Lists.
- A provider MUST verify that a counterparty is currently qualified before accepting a session or evidence, and ceases to participate if its qualification is withdrawn.
- A relay MUST refuse to forward to, or accept evidence from, a downstream relay that fails the same check, at every hop in a `relay_chain` ([wmp-core.md](wmp-core.md) §5.7).
- All certificates used for authentication or evidence signing are checked for revocation before acceptance.

## 10. Protocol Evolution

Evolution is "make before break":

- A published list of recognised protocol versions, each marked `optional` (default), `required` or `forbidden`. At least one version is `required` at any time. A change of state carries a published timeline.
- A receiving RDS advertises a separate endpoint per version, in the `erds` object of its well-known configuration: `protocol_endpoints` *(provisional)*, a map from version to endpoint URL. A sending RDS selects a version by choosing the endpoint.
- Rollout of a version needs a protocol profile, interoperability tests and a test network, assessment standards, assessment of providers, and production support.

## 11. Availability, Metadata and Testing

- **Availability.** The owner can move to a different RDS by updating the `rds` field of its registry document (§3.2). An RDS SHOULD publish `redundant_relays` and `max_interruption_window_seconds` in its `erds` object. Because a Commit cannot take effect while either RDS is unreachable (§5.3), deployments SHOULD plan membership changes accordingly.
- **Padding.** MLS application messages MUST be padded.
- **Metadata.** `wmp.session_id`, `wmp.sender` and `wmp.epoch`, and group membership (§5.2), are visible to RDSes. This is architecturally required by the model. Metadata that an RDS evidences without seeing content is currently signed by the RDS and not by the sender; sender-authenticated metadata is not provided by this profile.
- **Testing.** Implementations MUST publish executable conformance tests and cross-implementation vectors for the registered-delivery path, and MUST support a test-network mode using a distinct trust-anchor set and directory, discoverable via a `test` flag in the well-known configuration.

## 12. Error Codes *(proposed)*

| Code | Message | Description |
|------|---------|-------------|
| -31021 | Group membership mismatch | The MLS group does not match the endpoints currently listed for the addressed entities and roles. `data` lists members to add and remove. |
| -31022 | Commit conflict | Another Commit for the same epoch was selected (§5.3). The sender retries in the next epoch. |
| -31023 | KeyPackage unavailable | No KeyPackage can be reserved for the addressed role. |

## 13. Conformance

An implementation conforms to this profile if it:

1. Conforms to WMP Registered, WMP Evidence ERDS Conformance and the MLS layer (§1.1).
2. Negotiates `mls` mode exclusively and `mls_public_commits` (§2, §5.2).
3. Resolves `ebw` addresses through the directory interface and verifies operation chains (§3).
4. Verifies endpoint credentials against the owner credential key and uses single-use KeyPackage reservation (§4).
5. Accepts Commits only after both RDSes have accepted them and checks group membership on every send (§5).
6. Includes `plaintext_hash` and `epoch_authenticator` in every submission (§7.1) and requires a decryption report before handover (§7.2).
7. Produces evidence per §8, including the hash chain and baseline evidence independent of the recipient.
8. Verifies provider qualification at every hop (§9).
9. Advertises per-version endpoints and follows the version lifecycle (§10).
10. Pads messages and provides conformance tests and a test-network mode (§11).

## 14. Not Addressed

- **Cryptographically enforced role-scoped confidentiality.** Membership checking relies on RDS honesty and on the owner-signed credentials. A signed role roster (§6) would strengthen it.
- **Sender-authenticated metadata.** See §11.
- **Royalty-free and IPR status.** A governance question for the specification's maintainers and any standards body that adopts it.
- **Directory snapshots and transparency.** See §3.3.

## 15. Disclaimer

Conformance to this profile is a technical, not legal, determination. Whether a deployment satisfies the EBW Regulation, its implementing acts or ETSI EN 319 521/522 is a question for the operator's legal and conformity-assessment advisors.

## References

- [WMP Core](wmp-core.md), [WMP MLS](wmp-mls.md), [WMP Evidence](wmp-evidence.md), [WMP eDelivery](wmp-edelivery.md)
- Proposal for a Regulation on the establishment of European Business Wallets, COM/2025/838 final
- Commission Implementing Regulation (EU) 2025/1944
- ETSI EN 319 521, ETSI EN 319 522-series
- ENISA Report 1747792503 v2, *Agreed Cryptographic Mechanisms*
- RFC 9420: The Messaging Layer Security (MLS) Protocol
- AT Protocol DID PLC method (the model for the operation-chain directory)

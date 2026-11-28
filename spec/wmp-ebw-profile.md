# WMP Secure Communication Channel (SCC) Profile

## Wallet Messaging Protocol — Profile for the European Business Wallet Secure Communication Channel

**Status:** Draft
**Version:** 0.3.0
**Reference:** [SCC specification set](https://github.com/european-business-wallet/sccp), commit `c4037ff`

## 1. Introduction

The Secure Communication Channel (SCC) of the European Business Wallet is specified in its own repository. That specification is **normative** for everything it defines. It describes its delivery protocol as a *profile of WMP*: it reuses WMP's JSON-RPC envelope, WebSocket binding, several method names and the consignment model, and it removes or replaces the rest.

This document records, from the WMP side, what that profile keeps, changes and drops, so that a WMP implementation can tell where SCC behaviour departs from WMP Core, WMP MLS and WMP Evidence. It does not restate SCC. Where this document and the SCC specification disagree, the SCC specification governs SCC sessions.

An implementation conforms to this profile if it conforms to the SCC delivery protocol (SCC doc 4) and the documents that protocol depends on (discovery, credentials, MLS profile and evidence: SCC docs 1, 2, 3 and 5).

## 2. What SCC keeps from WMP

| WMP element | Use in SCC |
|---|---|
| JSON-RPC 2.0 envelope | Kept. Batches are forbidden. |
| WebSocket binding ([wmp-transport.md](wmp-transport.md)) | Kept between an endpoint and its home RDS, with subprotocol `scc.v1`. |
| HTTPS binding | Kept between RDSes, one request per POST, with mutual TLS 1.3 and qualified certificates. |
| `wmp.message.deliver`, `wmp.message.fetch` | Kept with SCC parameters (§3). |
| `wmp.message.ack` | Kept with SCC parameters and meaning (§3). |
| `wmp.session.create` | Kept; it creates an SCC session, which is an MLS group between two addresses. |
| `wmp.evidence.notify` | Kept; it carries SCC evidence. |
| Consignment modes `basic`, `consented` ([wmp-core.md](wmp-core.md) §3.5) | Kept. |
| Evidence events of EN 319 522 ([wmp-evidence.md](wmp-evidence.md) §3) | Kept as the event model, under the codes A.1 to E.2. |
| Error codes -31002, -31004, -31007, -31014, -31016 | Kept with the WMP meaning. |
| RDS metadata modelled on `/.well-known/wmp-configuration` and its `erds` object | Kept in spirit; SCC defines its own RDS metadata document at the RDS URL. |

## 3. What SCC changes

These differences matter to a WMP implementation, because the same method name carries different parameters.

| Area | WMP | SCC |
|---|---|---|
| `wmp` metadata object in `params` | Required on every message | **Dropped.** The version is agreed once per connection (`scc.connect`). |
| `wmp.message.deliver` | `params` carry the `wmp` object, `ciphertext` and optional `plaintext_hash` object | `params` carry `session_id`, `message` (the whole `MLSMessage`), `meta` (`message_id`, `from`, `to`, `sent_at`, `expires_at`, `consignment`), `plaintext_hash` and `epoch_authenticator` as base64url strings |
| `wmp.message.ack` | `message_ids` array, `status` of `received`, `read`, `processed` or `failed` | A single `message_id`, `status` of `processed` or `failed`, and a signed decryption `report` |
| Signatures | Detached JWS over the JCS-canonicalised content object | COSE_Sign1 over deterministically encoded CBOR, with embedded payloads |
| Plaintext commitment | `plaintext_hash` object over the JCS content object, salt inside it | SHA-256 over the exact bytes of the CBOR `application_data`, which include the salt |
| Evidence encoding | JSON objects ([wmp-evidence.md](wmp-evidence.md) §4) | CBOR evidence bodies, COSE-sealed with a qualified timestamp, hash-chained by `prev` |
| Addressing | Identifier schemes resolved by well-known configuration | `ebw:` URL plus role, resolved through the European Digital Directory |
| Message identifiers | Chosen by the sender or relay | 16 random bytes chosen by the sending endpoint; the sending RDS checks they are new |
| Error codes | -31000 to -31020 | Adds -31100 to -31112 for membership mismatch, stale epoch, commit conflict, unknown or closed session, missing KeyPackage, invalid credential, duplicate message ID, bad time, inactive owner, unknown address, wrong RDS and incomplete evidence |

The consequences for an implementation that supports both WMP and SCC:

- Dispatch on the negotiated protocol (`scc.v1` subprotocol or `scc/1` version), not on the method name.
- Do not apply WMP's JCS signing, `wmp` object or JSON evidence rules to SCC sessions, or the reverse.
- Treat the SCC error codes -31100 to -31112 as reserved for SCC. They are not yet in the WMP error registry ([wmp-core.md](wmp-core.md) §11.3); see §7.

## 4. What SCC drops from WMP

Capability negotiation, structured flows, MCP, the `tls` and `mls-optional` security modes, multi-hop relay chains, JCS signatures, DNS discovery, `consented_signed` (every SCC decision is already signed by the endpoint key) and `wmp.message.status` (replaced by `wmp.evidence.notify`). SCC sessions are always end-to-end encrypted with MLS.

## 5. What SCC adds

These have no counterpart in WMP Core or WMP MLS today:

- **Directory-based discovery.** Signed, hash-chained operations per `ebw:` URL, ranked update keys with a recovery window, and directory head statements with status lists.
- **Owner-signed endpoint credentials,** bound into MLS as an `ebw_endpoint` credential inside a `multi` credential.
- **Public Commits and two-sided Commit acceptance.** Both RDSes keep a Commit log and accept a Commit only when both have; concurrent Commits resolve to the smaller SHA-256 of the encoded `MLSMessage`.
- **Membership check on every send,** against the endpoints eligible for each address, with `-31100` carrying the `add` and `remove` lists.
- **KeyPackage reservation.** Single-use KeyPackages, reserved by `scc.rds.keypackage.reserve`. **Last-resort KeyPackages are forbidden.**
- **Decryption reports.** `match`, `mismatch`, `decrypt-failed`, `invalid-epoch` and `join-failure`, signed by the endpoint, with the sender's epoch authenticator carried with each message. A `match` report from a holder of the `to` role is the handover that ends in evidence E.1.
- **Dispute resolution and retention** rules for endpoints and RDSes.

## 6. Relationship to WMP's other profiles

- **[wmp-evidence.md](wmp-evidence.md)** remains the evidence profile for WMP sessions. SCC evidence is a separate CBOR format that follows the same EN 319 522 event model.
- **[wmp-edelivery.md](wmp-edelivery.md)** is not used by SCC. Routing is by `ebw:` URL through the directory, not by SMP.
- **`plaintext_hash` and `-31019`** ([wmp-core.md](wmp-core.md) §5.2.1) are WMP-session features. In SCC the equivalent outcome is a `mismatch` decryption report.

## 7. Open points

- Whether WMP Core should define a way to name a profile whose messages do not carry the `wmp` object, so that mixed deployments do not rely on subprotocol detection alone.
- Whether the `wmp.message.ack` collision (§3) should be resolved in WMP by versioning the method or by renaming one side.
- Registration of the SCC error range in [wmp-core.md](wmp-core.md) §11.3, and of the SCC code points (`ebw_endpoint`, `scc_session`) once they leave private use.

## 8. Disclaimer

Conformance to this profile is a technical, not legal, determination. The SCC repository states that it is a work in progress and not an official proposal or position of any institution.

## References

- [SCC specification set](https://github.com/european-business-wallet/sccp), commit `c4037ff`
- [WMP Core](wmp-core.md), [WMP MLS](wmp-mls.md), [WMP Evidence](wmp-evidence.md), [WMP Transport](wmp-transport.md)
- ETSI EN 319 522-1, -2, -3
- RFC 9420: The Messaging Layer Security (MLS) Protocol

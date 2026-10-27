# WMP European Business Wallet (EBW) Conformance Profile

## Wallet Messaging Protocol — Secure Communication Channel Profile for the European Business Wallet

**Status:** Draft
**Version:** 0.1.0
**Date:** 2026-09-28

## 1. Introduction

This profile fixes WMP's configuration space to meet the requirements for the EBW Secure Communication Channel arising from Regulation (EU) No 910/2014, the EBW Regulation (COM/2025/838), Commission Implementing Regulation (EU) 2025/1944, and the ETSI EN 319 521/522 ERDS framework, together with the operational needs of registered delivery among legal entities: organizational acceptance policies, evidentiary integrity under end-to-end encryption, and provider redundancy.

It does not introduce new wire-level mechanisms except where explicitly noted in §9 and §14. It is a *profile* in the sense already anticipated by [wmp-core.md](wmp-core.md) §10.1 ("Profile-specific conformance levels ... are defined in their respective profile documents") and by the extension points documented at [wmp-core.md](wmp-core.md) §5.6 ("Profiles MAY mandate specific assertion types...") and [wmp-core.md](wmp-core.md) §8.12 ("Implementations operating in regulated environments ... SHOULD define credential freshness requirements in their profile specification").

### 1.1 Composed Profiles

An implementation of this profile MUST conform to:

- **WMP Registered** conformance level ([wmp-core.md](wmp-core.md) §10.1) — WMP Secure plus the `evidence` capability, non-repudiation signatures, and trusted timestamping.
- **WMP Evidence ERDS Conformance** ([wmp-evidence.md](wmp-evidence.md) §9.2).
- **WMP eDelivery + ERDS Conformance** ([wmp-edelivery.md](wmp-edelivery.md) §9.2).
- **WMP EBWOID Binding Conformance** ([wmp-ebwoid-binding.md](wmp-ebwoid-binding.md) §6).

This profile is additive to those four. Where a requirement below tightens a choice those profiles leave open (e.g., a MAY or OPTIONAL field), the tightening applies only to sessions operating under this profile; it does not amend the underlying profile documents.

### 1.2 Scope

This profile covers the registered-delivery path only. The following WMP capabilities are **not required** for conformance and MUST NOT be a precondition for registered delivery to function under this profile: the structured flow lifecycle (`sign`/`approval`/`message` types and profile-defined extensions) beyond what registered delivery itself uses, the OpenID4VCI/OpenID4VP profile ([wmp-openid4x.md](wmp-openid4x.md)), the invitation mechanism ([wmp-invitation.md](wmp-invitation.md)), and the WebAuthn binding ([wmp-webauthn-binding.md](wmp-webauthn-binding.md)). Implementations MAY support these; this profile takes no position on them beyond §14.1.

## 2. Security Mode

A session operating under this profile MUST negotiate `security_modes: ["mls"]` (WMP Core §4.2.3). Implementations MUST NOT negotiate `tls` or `mls-optional` mode for any message on the registered-delivery path.

```json
{
  "wmp": {"version": "0.1"},
  "security": {"mode": "mls"}
}
```

*Rationale:* `mls-optional` and `tls` modes let the relay see plaintext (WMP Core §4.2.3 table). A deployment cannot claim end-to-end confidentiality while any message on the registered-delivery path can be sent through a mode that discards it; fixing the mode to `mls` removes that conditionality entirely.

## 3. Identity and Assurance

- `recipient_assurance_level` (WMP Core §3.5.1) MUST be set to `high` for every message on the registered-delivery path. An implementation MUST treat `insufficient_assurance` as a hard delivery failure, not a warning.
- Sender identity MUST be asserted via the EBWOID binding (§4) or, where the sender is not itself an EBW-registered entity, via `identity_assertions` carrying eIDAS-qualified certificates per [wmp-evidence.md](wmp-evidence.md) §9.2 item 11.
- Authentication bindings offered MUST be limited to mutual TLS with eIDAS-qualified certificates, X.509 (`x5c`), and `verifiable_presentation`-based EBWOID/EUDIW authentication (WMP Core §7.4).
- All certificates used for authentication or evidence signing MUST be checked for revocation status before acceptance, per [wmp-core.md](wmp-core.md) §8.12's "credential freshness requirements" clause, which this profile now fixes as: check on every session authentication and before generating or accepting evidence bearing a `sender_assurance_level`/`recipient_assurance_level` claim, via OCSP, CRL, or IETF Token Status List as applicable to the credential type.

## 4. Legal-Entity Addressing and Identity Assertion

- Every participant MUST be reachable via the `ebcore` identifier scheme and MUST implement WMP eDelivery Conformance ([wmp-edelivery.md](wmp-edelivery.md) §9.1) for routing. This is not optional under this profile, unlike under WMP Core generally.
- Every participant MUST support presenting and verifying an EBWOID identity assertion as defined in [wmp-ebwoid-binding.md](wmp-ebwoid-binding.md), in both directions of use (§1.1 of that specification): as Wallet User presenting its own EBWOID, and as EBW-acting-as-Relying-Party presenting its EBWOID during mutual identification.
- A relay MUST reject, with `-31015` or the applicable identity-assertion rejection code (WMP Core §5.6.2), any session in which the EBWOID's resolved entity identifier does not match the `ebcore` identifier used for routing. This binds the routing-layer identity to the asserted legal identity, closing the gap between "an address is a legal entity" and "the entity that answered is who it claims to be."

## 5. Key Discovery and Transparency

- The MLS ciphersuite negotiated MUST be one on the ENISA Agreed Cryptographic Mechanisms list current at time of session creation. Ciphersuites not on that list MUST NOT be offered.
- **New requirement — KeyPackage transparency.** In addition to publication at the `.well-known` endpoint (WMP Core §7.5), an implementation MUST register the fingerprint (SHA-256 of the encoded `KeyPackage`) of every published KeyPackage in a transparency log designated by the EBW trust framework, following the append-only, publicly auditable model of RFC 9162 Certificate Transparency, which WMP Core §7.5.4 already permits for certificates but does not extend to KeyPackages. A recipient's endpoint SHOULD verify a sender-published KeyPackage against the log before forming an MLS group with it, and MUST log a warning (and MAY refuse) if the KeyPackage is unlogged or the log entry's fingerprint does not match. Without this, the integrity of end-to-end key discovery rests solely on DNS/TLS; this closes that gap without changing the KeyPackage publication format itself — it only adds a second, cross-checkable publication point.
- Post-quantum/hybrid MLS ciphersuites MUST be adopted for new sessions within 12 months of IETF assignment of a PQ MLS ciphersuite meeting the ENISA ACM's post-quantum guidance. Implementations MUST track this as a living requirement, not a one-time gap closure.

## 6. Organizational Roles and Acceptance Policies

WMP Core and its extension profiles have no role or quorum concept beneath a participant identifier (WMP MLS §5.1/§6.1 "Role" refers to the MLS Delivery/Authentication Service roles, not organizational roles). This profile defines a convention to approximate organizational acceptance policies without a WMP Core change:

1. A conformant organization MUST operate a **role directory** exposing, at minimum, a query `role -> [KeyPackage]` for its currently authorized members per role.
2. When sending to a role-addressed recipient, the sender MUST query the recipient's role directory immediately before encryption and MUST build the MLS group from the roster returned by that query. The role directory's response MUST be signed by a key traceable to the recipient's EBWOID-asserted identity (§4).
3. Acceptance policies (`any`, `quorum:N`, `all`) SHOULD be carried in the `wmp` metadata's `applicable_policies` field (WMP Core §3.5) and MUST be referenced by ID in the resulting evidence (§7).
4. Each member contributing to a quorum decision MUST individually sign the acceptance action; the evidence MUST record each signature and the policy it satisfies.

**Residual gap, not closed by this section:** this is a profile-level convention layered on top of MLS group formation, not a group-membership guarantee enforced by the protocol itself. Nothing here proves, at decryption time, that the group used at send time matched the role roster *current at that moment* — only that it matched the roster at query time. A durable fix requires WMP Core to define role-aware credentials or group-formation semantics; this profile does not attempt that and treats it as an accepted risk pending upstream work.

## 7. Consignment Mode and Evidence

- The consignment mode MUST default to `consented_signed` ([wmp-core.md](wmp-core.md) §3.5) for messages on the registered-delivery path. `basic` and `consented` MAY be offered but MUST NOT be the default, and a sender MUST be able to require `consented_signed` unconditionally, since under this profile it is the default and not merely an option a sender must separately request.
- `require_plaintext_hash: true` (WMP Evidence §2, §8.6) MUST be negotiated for every MLS-encrypted session. Submissions lacking `plaintext_hash` MUST be rejected with `submission_rejected`/`plaintext_hash_missing`.
- `previous_evidence_id` (WMP Evidence §4, currently OPTIONAL) MUST be populated on every evidence object after the first in a delivery's sequence, forming a complete hash chain from `submission_accepted` through the terminal event. A verifier MUST be able to detect a missing link in the chain — closing the gap where independently-verified evidence objects otherwise give no guarantee that none were omitted.
- The signed recipient acknowledgement required by `consented_signed` MUST cover, at minimum: the `plaintext_hash` commitment, the `original_content_hash`, and a timestamp, so that what is being acknowledged is unambiguous.

## 8. Relay and Provider Qualification

**New requirement.** WMP Core validates the identity of message *participants* (via `identity_assertions`/`trust_hints`, WMP Core §5.6) but has no mechanism for a participant to validate that a *relay* is a currently-qualified Secure Communication Channel provider: relays are otherwise self-declared, with no federation-membership check.

This profile closes that gap by applying the existing trust-hint mechanism to the relay itself, rather than only to message participants:

1. A relay's `/.well-known/wmp-configuration` MUST publish an `identity_assertions` entry for the relay's own operating entity, using the same `verifiable_presentation`/EBWOID mechanism as §4, or an `x509_chain` assertion whose certificate is issued under a policy listed on an EU Trusted List with a service type identifying it as a qualified ERDS provider.
2. Before establishing a session through a relay, or before accepting evidence the relay has issued, a participant MUST resolve and verify this assertion, exactly as it would for a message participant (WMP Core §5.6.1), and MUST reject relays whose assertion does not resolve or does not chain to a Trusted List entry.
3. A relay MUST refuse to forward messages to, or accept evidence from, a downstream relay that fails the same check, so that qualification is verified at every hop in a `relay_chain` (WMP Core §5.7), not only at the endpoints.

This reuses WMP Core's existing identity-assertion and trust-hint machinery; it does not introduce a new credential type, only a new place that machinery is required to be applied.

## 9. Availability and Redundancy

**New requirement.** Neither WMP Core nor its existing profiles define redundancy or failover beyond session-level reconnection (WMP Core §4, relay queuing per WMP MLS §5.4). Continuous availability, redundancy, and fallback are required of a QERDS but are not met by reconnection alone.

This profile extends the `erds` capability object published in the well-known configuration ([wmp-core.md](wmp-core.md) §7.5.1.1) with two additional fields, following the same pattern by which `erds` and `recipient_metadata` are already profile-extensible:

```json
{
  "erds": {
    "redundant_relays": [
      "wss://relay-a.example.eu/wmp",
      "wss://relay-b.example.eu/wmp"
    ],
    "max_interruption_window_seconds": 300
  }
}
```

- A conformant participant MUST publish at least two operationally independent entries in `redundant_relays`.
- On detecting that the currently-connected relay is unreachable, a sender or recipient MUST attempt reconnection (WMP Core §4, session resumption) against the next entry in `redundant_relays` before treating the message as undeliverable.
- `max_interruption_window_seconds` is the maximum time a conformant deployment commits to before failover completes; it MUST be published and MUST be consistent with any SLA the operator has separately committed to.
- This is a schema extension to the `erds` object; it is additive and does not require changes to [wmp-core.md](wmp-core.md)'s existing fields. A corresponding update to `schema/` is tracked as follow-up work (§16).

## 10. Metadata Minimization

Padding of MLS application messages, currently "recommended" (WMP MLS, Security Considerations), MUST be applied for all messages on the registered-delivery path.

**Accepted residual gap:** `wmp.session_id`, `wmp.sender`, and `wmp.epoch` remain visible to relays in the plaintext envelope (WMP MLS §4) because routing requires them. This is architecturally required by the store-and-forward model and is not further reducible within this profile.

## 11. Interoperability and Testing

- Conformant implementations MUST publish executable conformance tests and cross-implementation test vectors for the registered-delivery path, extending [vectors/](../vectors/) with EBW-profile-specific cases (mandatory MLS mode, `require_plaintext_hash`, `previous_evidence_id` chaining, relay qualification per §8).
- A conformant deployment MUST support a sandboxed test-network mode using a distinct trust anchor set (a separate EU Trusted List test instance or equivalent) from its production configuration, discoverable via a `test` flag in the well-known configuration.

## 12. Out-of-Scope Exclusions

The capabilities listed in §1.2 are explicitly not required. In particular, this profile takes no position on, and does not mandate, the WebAuthn binding's session-identifier/challenge-derived value (see §14.1) or the OpenID4VCI/OpenID4VP flow profile.

## 13. Conformance

An implementation conforms to the WMP EBW Profile if it:

1. Conforms to WMP Registered ([wmp-core.md](wmp-core.md) §10.1), WMP Evidence ERDS Conformance ([wmp-evidence.md](wmp-evidence.md) §9.2), WMP eDelivery + ERDS Conformance ([wmp-edelivery.md](wmp-edelivery.md) §9.2), and WMP EBWOID Binding Conformance ([wmp-ebwoid-binding.md](wmp-ebwoid-binding.md) §6).
2. Negotiates `mls` security mode exclusively for registered-delivery sessions, never `tls` or `mls-optional` (§2).
3. Requires `recipient_assurance_level: "high"` and treats `insufficient_assurance` as a hard failure (§3).
4. Implements the `ebcore` identifier scheme for routing and the EBWOID binding for identity assertion, in both directions (§4).
5. Restricts negotiated MLS ciphersuites to the current ENISA ACM list and registers published KeyPackages in a designated transparency log (§5).
6. Where role-addressed delivery is supported, implements the role-directory query and per-member quorum signing convention of §6, and documents the residual gap it accepts.
7. Defaults to `consented_signed`, negotiates `require_plaintext_hash: true`, and populates `previous_evidence_id` on every non-initial evidence object (§7).
8. Verifies relay/provider qualification via trust-hint resolution at every hop before accepting a session or evidence from that relay (§8).
9. Publishes at least two `redundant_relays` entries and a `max_interruption_window_seconds`, and implements failover across them (§9).
10. Applies MLS message padding (§10).
11. Provides EBW-profile conformance test vectors and a sandboxed test-network mode (§11).

## 14. Not Addressed by This Profile

These require a core WMP specification change or a governance action outside the scope of profiling, and are called out so the sub-group does not mistake profile silence for resolution.

### 14.1 WebAuthn/presentation-nonce cross-protocol reuse

[wmp-webauthn-binding.md](wmp-webauthn-binding.md) derives a single value from the session identifier and challenge, used both as the WebAuthn passkey challenge and as the OID4VP presentation nonce. Domain separation between these two uses is a core cryptographic-binding design choice in that specification, not a profile-level parameter. This profile does not mandate the WebAuthn binding (§1.2) and takes no position on this pending a fix upstream.

### 14.2 Royalty-free/IPR status

Confirming that WMP is available on open, royalty-free terms is a governance and licensing question for the specification's maintainers and/or its adoption path into a formal standards body. It is outside the reach of a conformance profile.

### 14.3 Cryptographically enforced role-scoped confidentiality

As noted in §6, the role-directory convention is a mitigation, not a protocol-enforced guarantee. Closing this fully requires WMP Core to define role-aware MLS credentials or group-formation semantics.

## 15. Disclaimer

Conformance to this profile is a technical, not legal, determination. Whether a given deployment satisfies the EBW Regulation, its implementing acts, or ETSI EN 319 521/522 in a given jurisdiction is a question for the operator's legal and conformity-assessment advisors.

## 16. Open Follow-Up Work

- `schema/` has no JSON Schema definition for the `erds` well-known-configuration object at all (not specific to this profile); the `redundant_relays`/`max_interruption_window_seconds` extension in §9 should be added once that base schema exists.
- The KeyPackage transparency log mechanism in §5 names no specific log implementation or trust-anchor governance; this is left for the EBW trust framework to designate.
- The role-directory query interface in §6 is described only at the level of required behavior, not a wire format; a companion schema/method definition (e.g., `wmp.role.resolve`) would be needed for interoperable implementations.

## References

- [WMP Core Specification](wmp-core.md)
- [WMP MLS Encryption Layer](wmp-mls.md)
- [WMP Evidence Profile](wmp-evidence.md)
- [WMP eDelivery Profile](wmp-edelivery.md)
- [WMP EBWOID Binding Specification](wmp-ebwoid-binding.md)
- [EBWOID Carrier Independence](../analysis/ebwoid-carrier-independence-proposal.md)
- Proposal for a Regulation on the establishment of European Business Wallets, COM/2025/838 final
- Commission Implementing Regulation (EU) 2025/1944
- ETSI EN 319 521, ETSI EN 319 522-series
- ENISA Report 1747792503 v2, *European Cybersecurity Certification Group — Agreed Cryptographic Mechanisms*
- RFC 9162 — Certificate Transparency
- RFC 9420 — The Messaging Layer Security (MLS) Protocol

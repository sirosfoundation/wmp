# Proposal: protocol profiles for WMP

**Status:** Draft proposal for discussion. Not normative.
**Date:** 2026-11-05
**Decision recorded:** WMP is a general wallet messaging protocol that other protocols can reuse. WMP will be handed to a standards body. Narrow layering is the chosen direction.

## 1. Problem

The Secure Communication Channel (SCC) of the European Business Wallet specifies a delivery protocol that it describes as a profile of WMP. It reuses WMP's JSON-RPC envelope, WebSocket binding, several method names and the consignment model. It also changes things WMP Core treats as fixed:

| Area | WMP Core today | SCC |
|---|---|---|
| `wmp` object in `params` | Required on every message (§3.2) | Absent; version agreed once per connection |
| `wmp.message.deliver` parameters | `wmp` object, `ciphertext`, optional `plaintext_hash` object | `session_id`, `message`, `meta`, `plaintext_hash`, `epoch_authenticator` |
| `wmp.message.ack` parameters | `message_ids` array, status `received`/`read`/`processed`/`failed` | one `message_id`, status `processed`/`failed`, signed `report` |
| Signatures | detached JWS over the JCS content object (§5.4) | COSE_Sign1 over deterministic CBOR |
| Evidence | JSON ([wmp-evidence.md](../spec/wmp-evidence.md)) | CBOR, COSE-sealed |
| Error codes | -31000 to -31020 | adds -31100 to -31112 |

By WMP's current rules this is a different protocol that borrows method names. A library that speaks both cannot tell the two apart from the method name, and nothing in WMP says that is allowed. The repository's own statement that SCC is "a profile of WMP" has no definition to point at.

WMP has three documents it calls profiles ([wmp-openid4x.md](../spec/wmp-openid4x.md), [wmp-evidence.md](../spec/wmp-evidence.md), [wmp-edelivery.md](../spec/wmp-edelivery.md)). All of them add capabilities and namespaces **inside** the `wmp` envelope. None changes the envelope. This proposal introduces something different, and needs its own term.

## 2. Terms

- **Protocol profile:** a named, versioned specification that fixes, for one connection, the parameter schemas of the base methods (§4), the signature suite and encodings, the evidence format, the error-code block and the method namespace it owns.
- **`wmp` profile:** the behaviour WMP Core and its extension documents define today. It is the default.
- **Extension profile:** the existing meaning of "profile" in WMP documents (OpenID4x, Evidence, eDelivery): additions inside the `wmp` profile. No wire change; only the name needs a note to avoid confusion.
- **Base:** what every protocol profile shares (§3).

## 3. Goals and non-goals

**Goals**
1. Existing `wmp` deployments change nothing on the wire.
2. A second protocol can reuse WMP's envelope, transports and method semantics and still define its own schemas, without a naming clash.
3. A library can dispatch unambiguously: profile first, then method.
4. The base can be standardised on its own, with no normative dependency on any profile that is not part of it.
5. A profile can be specified and maintained in a different organisation, or standardised in a different body, from WMP.

**Non-goals**
- A shared signature or evidence encoding. Those stay profile-defined.
- Mixing profiles inside one connection or one session.
- Requiring profiles to use capability negotiation, flows or MLS.

## 4. Design

### 4.1 The base

The base is the part of WMP Core that does not depend on the `wmp` metadata object or on JWS/JCS:

- JSON-RPC 2.0 as the message format ([wmp-core.md](../spec/wmp-core.md) §3.1), with batches allowed only if the profile allows them.
- The transport bindings ([wmp-transport.md](../spec/wmp-transport.md)): framing, TLS 1.3, size limits.
- The extension-member rules (Core §9.5).
- The namespace rules (Core §9.1) and the error-code space (Core §3.8).
- Binary values in JSON are base64url without padding.
- The profile mechanism of §4.2 and §4.3.

### 4.2 Profile identification

A profile has a **profile identifier** `name/major` (for example `wmp/0`, `scc/1`) and a **subprotocol token** used on transports that have one.

| Transport | How the profile is selected |
|---|---|
| WebSocket | `Sec-WebSocket-Protocol: <token>`; the server selects one, and refuses the upgrade if it supports none |
| HTTPS | request header `WMP-Profile: <profile identifier>`; a server that does not support it answers `415` with `WMP-Profile` listing what it supports |
| Native messaging and stdio | fixed by configuration of the two ends |

- If no profile is named, the profile is `wmp`. This keeps existing clients working.
- The existing WebSocket token `wmp.v1` is the token of the `wmp` profile. SCC's `scc.v1` is already shaped the same way.
- A connection uses exactly one profile for its whole life.
- A server that supports a profile but not the requested major version of it answers as that profile's own version rule says (for `wmp`, `-31013`, Core §2.2).
- A server that supports no matching profile on a transport that cannot refuse before JSON-RPC (stdio) answers the first request with `-31021` (Profile not supported) *(proposed)*, listing supported profiles in `data`.

### 4.3 Dispatch

A receiver MUST resolve the profile of the connection first and interpret every method, parameter and error under that profile. A method name has no meaning outside a profile.

### 4.4 Base methods with profile-defined schemas

Six methods keep their names in every profile that offers them. The base defines what each one **means** and what it MUST guarantee. A profile defines the **parameters, results and encodings**.

| Method | Base meaning | Invariants every profile keeps |
|---|---|---|
| `wmp.session.create` | Establish the context in which messages are exchanged. The profile defines what a session is. | Returns an identifier the profile uses in later calls. |
| `wmp.message.deliver` | Submit, relay or push one message. | Each message has an identifier that is unique within the profile. Delivery of the same identifier twice has the effect of delivery once (idempotent). |
| `wmp.message.ack` | The receiver reports the outcome of processing a message it was given. | Names the message by its identifier. Is not evidence of delivery unless the profile says so. |
| `wmp.message.fetch` | Retrieve queued items after a cursor. | Items come back in order. Fetching after the last item returns nothing. |
| `wmp.evidence.notify` | Tell a party that evidence about a message exists. | The evidence payload is opaque to the base. |
| `wmp.session.close` | End a session. | Further messages on the session are refused. |

A profile that offers one of these methods MUST define its schema and MUST keep the invariants. A profile MAY omit a method. A profile MUST NOT give a base method a different meaning. A profile that needs different behaviour defines a method in its own namespace.

### 4.5 Namespaces and errors

- Each profile owns one method namespace prefix (for example `scc.*`), registered with the profile.
- **Error codes.** `-31000` to `-31099` stay with the base and the `wmp` profile. Other profiles get blocks of 50 from `-31100` upward, registered with the profile (SCC: `-31100` to `-31149`). A profile MAY reuse a base code with its base meaning.
- `-31021` Profile not supported *(proposed)*.

### 4.6 The `wmp` profile

Everything in [wmp-core.md](../spec/wmp-core.md) today, including the `wmp` metadata object (§3.2), JWS signatures (§5.4), capability negotiation (§4.2) and sessions (§4) is the `wmp` profile. Nothing in it changes. Its extension profiles keep working as they are.

### 4.7 Registry

A registry of protocol profiles, with these fields per entry:

| Field | Meaning |
|---|---|
| Identifier | `name/major` |
| Subprotocol token | for WebSocket |
| Method namespace prefix | |
| Error-code block | |
| Specification | reference, with its maintaining organisation |
| Contact | |

Registration policy: **Specification Required**, so that a profile maintained by another organisation or published by another standards body can register without WMP's authors changing their own documents. Until a formal registry exists, the table in Core §9.1 and this registry live in the WMP repository (the same arrangement Core §11 already describes for the other registries).

## 5. Standards-body implications

WMP will be handed to a standards body, and SCC may land in the same body or a different one. The design is shaped by that.

1. **One-way dependency.** A profile depends on the base. The base never depends on a profile. The base MUST NOT cite SCC, or any specification that is not part of the base, normatively.
2. **The base is self-contained.** Its only normative references are RFC 8259, JSON-RPC 2.0, the transport RFCs, TLS and RFC 9420 (for the `wmp` profile's MLS layer). A profile's own dependencies (for example drafts SCC uses) stay out of it.
3. **The registry is the contract.** A different body can run the registry under Specification Required and let another body's profile register without sharing change control.
4. **Change control.** A change to base method semantics (§4.4) needs agreement of registered profiles whose methods it affects. A change to a profile's schemas needs only that profile's maintainers.
5. **IPR.** Royalty-free availability of the base should be confirmed before handover. Profile authors state their own IPR terms in the registry.
6. **The `wmp` profile may go with the base or later.** The base is useful on its own, so the first handover can be the base plus the `wmp` profile, with extension profiles following.

## 6. What this means for implementations

- **go-wmp, wmp-js, Kotlin and Swift libraries:** read the profile on connection and default to `wmp`. No change to existing flows. A library that wants to speak SCC adds a second profile module behind the same transport code.
- **SCC implementations:** declare `scc/1` (already `scc.v1`) and register their prefix, error block and subprotocol token.
- **Dual-stack deployments:** one transport stack, two profile modules, dispatch on the negotiated profile.

## 7. Alternatives considered

| Option | Why not |
|---|---|
| WMP becomes SCC | Forces CBOR/COSE onto the wallet-to-issuer and wallet-to-verifier flows, rewrites every library for no gain there, and drops negotiation, flows, relay chains and the `tls` mode that WMP needs elsewhere. |
| Status quo (SCC borrows names) | Leaves a standing ambiguity and gives a standards body nothing to cite when SCC says it profiles WMP. |
| Adopt SCC's MLS ideas into the `wmp` profile | May be worthwhile later as optional features, but it does not remove the collision and it is a larger change. It can follow once there is demand outside SCC. |

## 8. Changes to existing documents

1. **New document `spec/wmp-profiles.md`:** §4 of this proposal as normative text.
2. **[wmp-core.md](../spec/wmp-core.md):** add a §2.3 "Protocol profiles" that points to `wmp-profiles.md` and states that Core as written is the `wmp` profile; add the profile-error range and `-31021` to the error table; change §10.1 so conformance levels are stated for the `wmp` profile.
3. **[wmp-transport.md](../spec/wmp-transport.md):** add the profile-selection rows of §4.2 to each binding, keeping `wmp.v1` as the `wmp` token.
4. **README and the documentation site:** add the registry table and list SCC as the first external profile.
5. **[wmp-ebw-profile.md](../spec/wmp-ebw-profile.md) (PR #40):** retitle the document as the registry entry and mapping for `scc/1`, and remove the "collision" open point once §4.4 exists.

## 9. Open questions

1. **Name.** "Protocol profile" avoids clashing with the existing extension profiles. Is there a better term, or should the extension profiles be renamed?
2. **`wmp.v1` and `wmp/0`.** The `wmp` profile's WebSocket token says `v1` while the protocol version is `0.1`. State the mapping, or give the `wmp` profile a version scheme that matches.
3. **Native messaging and stdio.** Fixed by configuration is simple, but a self-describing first message would be safer for tools that auto-detect.
4. **Method list.** Should `wmp.session.resume`, `wmp.message.status` and `wmp.capability.update` also be base methods, or stay `wmp`-profile only? SCC drops the last two.
5. **Batches.** The base default is "not allowed unless the profile allows them". WMP Core allows them today under the `wmp` profile.
6. **Registry operator.** Who runs the interim registry, and who takes it over at handover?
7. **Minor versions of a profile.** `name/major` mirrors SCC's `scc/1`. WMP Core already negotiates `MAJOR.MINOR` per session; decide whether other profiles must offer a minor version.

## 10. Work plan

1. Agree this proposal in principle (WMP maintainers).
2. Share the SCC-facing asks (separate document) with the SCC authors and settle names and registration.
3. One PR: `spec/wmp-profiles.md` plus the small Core and Transport edits, no wire change for `wmp`.
4. Update PR #40 to be the `scc/1` entry and mapping.
5. Library changes: profile read on connect, default `wmp` (small, one PR per library).

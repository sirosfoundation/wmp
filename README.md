# WMP — Wallet Messaging Protocol

A multi-party messaging protocol built on **JSON-RPC 2.0** and **MLS** (RFC 9420), designed for wallet-to-wallet, human-to-agent, and human-to-organization communication.

Project website: https://wmp.name

## IPR

This specification is currently owned and maintained by SIROS Foundation. SIROS Foundation is comitted to handing over the wmp specifications to a suitable standards body as soon as possible and at that time these specifications will adopt the IPR scheme(s) in use by the SDO or SDOs. In the meantime we welcome contributions and suggestions.

## Specification

| Document | Description |
|----------|-------------|
| [spec/wmp-core.md](spec/wmp-core.md) | Core protocol: message format, sessions, flows, error codes |
| [spec/wmp-transport.md](spec/wmp-transport.md) | Transport bindings: WebSocket, HTTPS, native messaging |
| [spec/wmp-mls.md](spec/wmp-mls.md) | MLS encryption layer: group management, key distribution |
| [spec/wmp-usecases.md](spec/wmp-usecases.md) | Use cases: wallet migration, H2H, H2A, H2O flows |

### Extensions

| Profile | Description |
|---------|-------------|
| [spec/wmp-openid4x.md](spec/wmp-openid4x.md) | OID4VCI and OID4VP flow definitions |
| [spec/wmp-evidence.md](spec/wmp-evidence.md) | Delivery evidence and receipts for registered delivery (ERDS) |
| [spec/wmp-edelivery.md](spec/wmp-edelivery.md) | eDelivery integration: SMP/BDXL discovery, ebCore identifiers, AS4 coexistence |
| [spec/wmp-ebw-profile.md](spec/wmp-ebw-profile.md) | European Business Wallet (EBW) Secure Communication Channel conformance profile |

## Status

**Draft** — This is an early-stage specification. Feedback welcome. The drafts is the result of an interactive dialoge with an AI coding agent. The intent is that this be used as the basis of discussion and possibly the starting point of specification work targeting the EU business wallet messaging requirements.

## Machine-Readable Artifacts

| Directory | Description |
|-----------|-------------|
| [schema/](schema/) | JSON Schema (Draft 2020-12) for all message types and metadata objects |
| [schema/methods/](schema/methods/) | Per-method request/response schemas |
| [vectors/](vectors/) | Test vectors — input/expected-output pairs for conformance testing |

These artifacts are designed for AI coding agents and automated tooling. Validate
your implementation against the schemas, then run the test vectors.


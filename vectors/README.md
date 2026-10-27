# WMP test vectors

`manifest.json` lists every vector file and how a harness executes it. A harness MUST fail, not skip, when a listed file is missing, and `tests/test_vectors.py` fails when a file here is not listed, so a new file cannot be silently ignored by CI.

| Kind | Files | What a harness does |
|------|-------|---------------------|
| `rpc` | `session-create`, `session-lifecycle`, `message-deliver`, `flow-lifecycle`, `resolve`, `errors` | Structural checks of each message today; an implementation MAY also run the vector against a peer. Every error code used in an `expected_error` is one of the codes in WMP Core Section 3.8. |
| `interop` | `interop.json` | Feed `input` to a peer built from `handler_action` and `peer_options`; compare the response. |
| `transport-http` | `transport-http.json` | Replay the steps against an HTTPS/SSE server (WMP Transport Section 4). |

## `transport-http` vectors

`setup` configures the server under test: `event_buffer` is the per-session event buffer size in events, `principals` maps a name to the `Authorization` header value that authenticates it.

`input` is an array of steps, run in order. A step has a `step` description and one of:

- `request`: an HTTP request (`method`, `path`, `query`, `headers`, `body`). It is sent by the connection `conn` when present (a connection that stays open as an event stream, in which case the response's `events` are those delivered up to the next step) and otherwise as a plain request.
- `emit`: the server side emits these JSON-RPC notifications to the session, in order. `deliver` then lists, per connection, the events that connection must receive live.
- `close`: the named connection drops.

`expect` on a request has `status`, optionally `body` (a JSON-RPC message), `events` (SSE events in order; an empty array means no event), `stream: false` (the response must not be an event stream, and no part of a replay may be delivered), `content_type`, `comments_at_least`, `comments_carry_no_id` and `idle_seconds` (advance a simulated clock; do not sleep). `same_response_as` names an earlier step's `label`: status and body must be identical.

Variables: a string `"{{name}}"` anywhere in a request is replaced by the value bound to `name`. A value is bound by a `{"capture": "name"}` in an expected position (a `body` member or an event `id`), which also matches any value there; `{"any": true}` matches any value without binding. Event `id` values are opaque: only compare them for equality with a captured value.

Strings in an expected `data` or `body` match literally, except that `{{name}}` is replaced first and `*` at the end of a string (`ses-*`) matches any suffix.

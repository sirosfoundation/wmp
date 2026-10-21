#!/usr/bin/env python3
"""Schema tests for WMP Core Section 9.5 (extension members).

Run: python3 -m pip install jsonschema referencing && python3 tests/test_schemas.py
"""
import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS = {}
for p in sorted((ROOT / "schema").rglob("*.json")):
    doc = json.loads(p.read_text())
    SCHEMAS[p.relative_to(ROOT / "schema").as_posix()] = doc
REGISTRY = Registry().with_resources(
    (d["$id"], Resource.from_contents(d)) for d in SCHEMAS.values()
)


def errors(name, instance):
    v = Draft202012Validator(SCHEMAS[name], registry=REGISTRY)
    return list(v.iter_errors(instance))


WMP = {"version": "0.1"}
FLOW_START = {
    "jsonrpc": "2.0", "id": 1, "method": "wmp.flow.start",
    "params": {"wmp": WMP, "flow_type": "oid4vp", "flow_id": "f1",
               "params": {"x": 1}},
}
SESSION_CREATE = {
    "jsonrpc": "2.0", "id": 1, "method": "wmp.session.create",
    "params": {"wmp": WMP, "security": {"mode": "tls"},
               "capabilities_offered": {"messaging": {"max_size": 10},
                                        "transaction_data": {"versions": [1]}}},
}
DELIVER = {
    "jsonrpc": "2.0", "method": "wmp.message.deliver",
    "params": {"wmp": WMP, "body": "hi",
               "plaintext_hash": {"algorithm": "sha-256", "value": "abc"}},
}
RELAY = {"relay": "https://r.example", "relay_id": "r1",
         "timestamp": "2026-01-01T00:00:00Z"}


def with_(base, path, value):
    d = copy.deepcopy(base)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value
    return d


def without(base, path):
    d = copy.deepcopy(base)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    del cur[path[-1]]
    return d


class Baseline(unittest.TestCase):
    def test_valid_baselines(self):
        self.assertEqual(errors("methods/flow-start.json", FLOW_START), [])
        self.assertEqual(errors("methods/session-create-request.json", SESSION_CREATE), [])
        self.assertEqual(errors("methods/message-deliver.json", DELIVER), [])
        self.assertEqual(errors("wmp-relay-entry.json", RELAY), [])


class ExtensionMembers(unittest.TestCase):
    """Section 9.5 rule 1: unknown members are tolerated at every level."""

    def check(self, name, inst):
        self.assertEqual(errors(name, inst), [])

    def test_params_level(self):
        for m in ("client_metadata", "context", "verifier_jwk_thumbprint",
                  "response_mode", "verified_request", "org.acme.risk_score"):
            self.check("methods/flow-start.json",
                       with_(FLOW_START, ["params", m], {"a": 1}))

    def test_wmp_metadata(self):
        self.check("methods/flow-start.json",
                   with_(FLOW_START, ["params", "wmp", "org.acme.x"], 1))

    def test_relay_entry(self):
        self.check("wmp-relay-entry.json", with_(RELAY, ["org.acme.x"], 1))

    def test_security(self):
        self.check("methods/session-create-request.json",
                   with_(SESSION_CREATE, ["params", "security", "org.acme.x"], 1))

    def test_capability_params(self):
        for cap in ("messaging", "transaction_data"):
            self.check("methods/session-create-request.json",
                       with_(SESSION_CREATE,
                             ["params", "capabilities_offered", cap, "org.acme.x"], 1))

    def test_plaintext_hash(self):
        self.check("methods/message-deliver.json",
                   with_(DELIVER, ["params", "plaintext_hash", "org.acme.x"], 1))

    def test_message_deliver_params(self):
        self.check("methods/message-deliver.json",
                   with_(DELIVER, ["params", "org.acme.x"], 1))


class StillStrict(unittest.TestCase):
    """Required members and constrained values must keep failing."""

    def bad(self, name, inst):
        self.assertNotEqual(errors(name, inst), [])

    def test_required_missing(self):
        self.bad("methods/flow-start.json", without(FLOW_START, ["params", "flow_id"]))
        self.bad("methods/flow-start.json", without(FLOW_START, ["params", "wmp"]))
        self.bad("methods/flow-start.json", without(FLOW_START, ["params", "wmp", "version"]))
        self.bad("methods/session-create-request.json",
                 without(SESSION_CREATE, ["params", "security", "mode"]))
        self.bad("wmp-relay-entry.json", without(RELAY, ["relay_id"]))
        self.bad("methods/message-deliver.json",
                 without(DELIVER, ["params", "plaintext_hash", "value"]))
        self.bad("methods/session-create-request.json",
                 with_(SESSION_CREATE,
                       ["params", "capabilities_offered", "transaction_data"], {}))

    def test_enums(self):
        self.bad("methods/session-create-request.json",
                 with_(SESSION_CREATE, ["params", "security", "mode"], "bogus"))
        self.bad("wmp-relay-entry.json", with_(RELAY, ["service_class"], "bogus"))
        self.bad("methods/message-deliver.json",
                 with_(DELIVER, ["params", "plaintext_hash", "algorithm"], "md5"))

    def test_types_patterns_minimums(self):
        self.bad("methods/flow-start.json", with_(FLOW_START, ["params", "flow_id"], 5))
        self.bad("methods/flow-start.json",
                 with_(FLOW_START, ["params", "wmp", "version"], "v1"))
        self.bad("methods/flow-start.json",
                 with_(FLOW_START, ["params", "wmp", "epoch"], -1))
        self.bad("methods/flow-start.json", with_(FLOW_START, ["method"], "wmp.other"))
        self.bad("methods/session-create-request.json",
                 with_(SESSION_CREATE,
                       ["params", "capabilities_offered", "messaging", "max_size"], 0))
        self.bad("methods/session-create-request.json",
                 with_(SESSION_CREATE,
                       ["params", "capabilities_offered", "custom_cap"], "notobject"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

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


class FlowCompleteVectors(unittest.TestCase):
    """Every single-message flow.complete vector validates against the schema
    unless it is marked must_refuse, in which case it must NOT validate."""

    def vectors(self):
        vs = json.loads((ROOT / "vectors" / "flow-lifecycle.json").read_text())
        return [v for v in vs
                if isinstance(v["input"], dict)
                and v["input"].get("method") == "wmp.flow.complete"]

    def test_vectors_match_schema(self):
        vs = self.vectors()
        self.assertGreaterEqual(len(vs), 10)
        refused = 0
        for v in vs:
            errs = errors("methods/flow-complete.json", v["input"])
            if v.get("must_refuse"):
                refused += 1
                self.assertNotEqual(errs, [], v["id"] + " must be refused")
            else:
                self.assertEqual(errs, [], v["id"])
        self.assertGreaterEqual(refused, 4)


class FlowCompleteBlindIssuance(unittest.TestCase):
    """Engine-blind issuance (Section 3.1.5.1): the seed is never relayed."""

    BASE = {"jsonrpc": "2.0", "method": "wmp.flow.complete",
            "params": {"wmp": WMP, "flow_id": "f1",
                       "result": {"credentials": [{"format": "mso_mdoc"}],
                                  "credential_response_encrypted": True}}}
    SEED = {"org.siros.secret_seed": {"nym": "00" * 16}}

    def test_encrypted_ok(self):
        self.assertEqual(errors("methods/flow-complete.json", self.BASE), [])

    def test_encrypted_with_credential_metadata_refused(self):
        inst = with_(self.BASE, ["params", "result", "credential_metadata"],
                     {"display": []})
        self.assertNotEqual(errors("methods/flow-complete.json", inst), [])

    def test_encrypted_with_credential_value_refused(self):
        inst = with_(self.BASE, ["params", "result", "credentials"],
                     [{"format": "mso_mdoc", "credential": "x"}])
        self.assertNotEqual(errors("methods/flow-complete.json", inst), [])

    def test_seed_in_any_completion_refused(self):
        plain = without(self.BASE, ["params", "result", "credential_response_encrypted"])
        inst = with_(plain, ["params", "result", "credential_metadata"], self.SEED)
        self.assertNotEqual(errors("methods/flow-complete.json", inst), [])

    def test_plain_display_metadata_ok(self):
        plain = without(self.BASE, ["params", "result", "credential_response_encrypted"])
        inst = with_(plain, ["params", "result", "credential_metadata"],
                     {"display": [{"name": "x"}]})
        self.assertEqual(errors("methods/flow-complete.json", inst), [])

    def test_redacted_members_only_replay_secrets(self):
        for m in ("credential_metadata", "credential_metadata_encrypted_response"):
            inst = with_(self.BASE, ["params", "result", "redacted_members"], [m])
            self.assertNotEqual(errors("methods/flow-complete.json", inst), [])
        inst = with_(self.BASE, ["params", "result", "redacted_members"],
                     ["dpop_jwk", "dpop_key_id", "refresh_token"])
        self.assertEqual(errors("methods/flow-complete.json", inst), [])

    def test_decrypt_result_control_members(self):
        def res(r):
            return {"jsonrpc": "2.0", "method": "wmp.flow.complete",
                    "params": {"wmp": WMP, "flow_id": "f1", "result": r}}
        for ok in ({"credential_count": 1}, {"credential_count": 256},
                   {"transaction_id": "t", "interval": 5}):
            self.assertEqual(errors("methods/flow-complete.json", res(ok)), [], ok)
        for bad in ({"credential_count": 0}, {"credential_count": 257},
                    {"transaction_id": "t", "credential_count": 1},
                    {"transaction_id": ""}):
            self.assertNotEqual(errors("methods/flow-complete.json", res(bad)), [], bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)

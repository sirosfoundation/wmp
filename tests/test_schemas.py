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
        for v in ("0.01", "01.1", "0.1.0", "", "1."):
            self.bad("methods/flow-start.json", with_(FLOW_START, ["params", "wmp", "version"], v))
        for v in ("0.1", "0.10", "10.0"):
            self.assertEqual(errors("methods/flow-start.json",
                                    with_(FLOW_START, ["params", "wmp", "version"], v)), [])
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


class FlowCompleteMatchResult(unittest.TestCase):
    """openid4x 3.3: a match result is a closed set."""

    def msg(self, result):
        return {"jsonrpc": "2.0", "method": "wmp.flow.complete",
                "params": {"wmp": WMP, "flow_id": "f1-match", "result": result}}

    def ok(self, result):
        self.assertEqual(errors("methods/flow-complete.json", self.msg(result)), [])

    def bad(self, result):
        self.assertNotEqual(errors("methods/flow-complete.json", self.msg(result)), [], result)

    def test_valid(self):
        self.ok({"satisfiable": True, "satisfiable_query_ids": ["pid"],
                 "selection_handle": "Zm9yLXRoZS13YWxsZXQtb25seQ"})
        self.ok({"satisfiable": False, "code": "no_match"})

    def test_closed_set(self):
        for extra in ({"claims": {"a": "b"}}, {"vct": "x"}, {"credential_id": "c"},
                      {"no_match_reason": "text"}, {"disclosures": ["x"]},
                      {"credentials": [{"format": "dc+sd-jwt"}]}, {"wallet_version": "1"}):
            self.bad(dict({"satisfiable": True}, **extra))

    def test_code_rules(self):
        self.bad({"satisfiable": True, "code": "error"})
        self.bad({"satisfiable": False})
        self.bad({"satisfiable": False, "code": "no PID found"})
        self.bad({"satisfiable": True, "satisfiable_query_ids": [{"id": "pid"}]})
        self.bad({"satisfiable": True, "satisfiable_query_ids": ["pid", "pid"]})
        self.bad({"satisfiable": True, "selection_handle": "short"})
        # 25 characters: an unpadded base64url string cannot have length 1 mod 4
        self.bad({"satisfiable": True, "selection_handle": "A" * 25})
        self.ok({"satisfiable": True, "selection_handle": "A" * 24})
        self.ok({"satisfiable": True, "selection_handle": "A" * 22})

    def test_match_result_schema_selected_by_flow_type(self):
        """schema/methods/match-result.json applies to every result of a match flow,
        including one that leaves out satisfiable."""
        def e(r):
            return errors("methods/match-result.json", r)
        self.assertEqual(e({"satisfiable": True, "satisfiable_query_ids": ["pid"]}), [])
        self.assertEqual(e({"satisfiable": False, "code": "no_match"}), [])
        self.assertNotEqual(e({"code": "no_match", "credential_id": "cred-001"}), [])
        self.assertNotEqual(e({"code": "no_match"}), [])
        self.assertNotEqual(e({}), [])
        self.assertNotEqual(e({"satisfiable": True, "selection_handle": "A" * 25}), [])
        self.assertEqual(e({"satisfiable": True, "selection_handle": "A" * 23}), [])
        self.assertNotEqual(e({"satisfiable": True, "claims": {"a": "b"}}), [])
        self.assertNotEqual(e({"satisfiable": True, "selection_handle": "A" * 24 + "\n"}), [])


class FlowActionSelectCredentials(unittest.TestCase):
    """openid4x 3.2.3.1: select_credentials params are a closed set."""

    H = "Zm9yLXRoZS13YWxsZXQtb25seQ"

    def msg(self, params):
        return {"jsonrpc": "2.0", "id": "a1", "method": "wmp.flow.action",
                "params": {"wmp": WMP, "flow_id": "f1", "action": "select_credentials",
                           "params": params}}

    def ok(self, params):
        self.assertEqual(errors("methods/flow-action.json", self.msg(params)), [], params)

    def bad(self, params):
        self.assertNotEqual(errors("methods/flow-action.json", self.msg(params)), [], params)

    def sel(self, **kw):
        return {"consent": True,
                "selections": [dict({"query_id": "pid", "selection_handle": self.H}, **kw)]}

    def test_valid(self):
        self.ok(self.sel())
        self.ok({"consent": False})
        self.ok({"consent": False, "selections": []})

    def test_closed_set(self):
        for extra in ({"credential_id": "c"}, {"disclosed_claims": ["a"]}, {"vct": "x"},
                      {"format": "dc+sd-jwt"}, {"claims": {"a": "b"}}, {"label": "free"},
                      {"x": 1}):
            self.bad(self.sel(**extra))
        self.bad(dict(self.sel(), credentials=[]))
        self.bad({"consent": True, "selections": [{"credential_id": "c", "disclosed_claims": ["a"]}]})

    def test_shape_rules(self):
        self.bad({"selections": self.sel()["selections"]})
        self.bad({"consent": "true", "selections": self.sel()["selections"]})
        self.bad({"consent": True})
        self.bad({"consent": True, "selections": []})
        self.bad({"consent": False, "selections": self.sel()["selections"]})
        self.bad({"consent": True, "selections": [{"query_id": "pid"}]})
        self.bad({"consent": True, "selections": [{"selection_handle": self.H}]})
        self.bad(self.sel(query_id="my pid!"))
        self.bad(self.sel(query_id="a" * 257))
        for ch in ("\u0085", "\u00a0", "\u2003", "\u2028", "\u3000", "\u200b", "\ufeff", "\u007f"):
            self.bad(self.sel(query_id="a" + ch + "b"))
        self.ok(self.sel(query_id="id_card.1:\u00e5"))
        self.bad(self.sel(query_id=""))
        self.bad(self.sel(query_id="pid\n"))

    def test_handle_format(self):
        for h in ("short", self.H + "==", "A" * 25, "A" * 22 + "\n", "A" * 24 + "\n", "Zm9yLXRoZS13YWxsZXQ+b25seQ", 5, None):
            self.bad(self.sel(selection_handle=h))
        self.ok(self.sel(selection_handle="A" * 22))
        self.ok(self.sel(selection_handle="A" * 24))

    def test_params_required(self):
        m = self.msg({"consent": False})
        del m["params"]["params"]
        self.assertNotEqual(errors("methods/flow-action.json", m), [])

    def test_other_actions_unaffected(self):
        m = self.msg({"credential_id": "x"})
        m["params"]["action"] = "cancel"
        self.assertEqual(errors("methods/flow-action.json", m), [])

    def test_vectors(self):
        vs = json.loads((ROOT / "vectors" / "flow-lifecycle.json").read_text())
        vs = [v for v in vs if isinstance(v["input"], dict)
              and v["input"].get("method") == "wmp.flow.action"
              and v["input"]["params"].get("action") == "select_credentials"]
        self.assertGreaterEqual(len([v for v in vs if v.get("must_refuse")]), 15)
        self.assertGreaterEqual(len([v for v in vs if not v.get("must_refuse")]), 2)
        for v in vs:
            errs = errors("methods/flow-action.json", v["input"])
            if v.get("must_refuse"):
                self.assertNotEqual(errs, [], v["id"] + " must be refused")
            else:
                self.assertEqual(errs, [], v["id"])


class FlowCompleteBlindIssuance(unittest.TestCase):
    """Engine-blind issuance (Section 3.1.5.1): auxiliary_data is never relayed."""

    BASE = {"jsonrpc": "2.0", "method": "wmp.flow.complete",
            "params": {"wmp": WMP, "flow_id": "f1",
                       "result": {"credentials": [{"format": "mso_mdoc"}],
                                  "credential_response_encrypted": True}}}
    AUX = {"auxiliary_data": {"example": "00" * 16}}

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

    def test_auxiliary_data_in_any_completion_refused(self):
        plain = without(self.BASE, ["params", "result", "credential_response_encrypted"])
        inst = with_(plain, ["params", "result", "credential_metadata"], self.AUX)
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
                    {"credential_count": 1, "credentials": [{"credential": "x"}]},
                    {"credential_count": 1, "credential_metadata": {"display": []}},
                    {"transaction_id": "t", "credentials": []},
                    {"transaction_id": "t", "credential_metadata": {}},
                    {"transaction_id": "t", "credential_count": 1},
                    {"transaction_id": ""},
                    {"interval": 5},
                    {"credential_count": 1, "interval": 5}):
            self.assertNotEqual(errors("methods/flow-complete.json", res(bad)), [], bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)

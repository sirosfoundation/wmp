#!/usr/bin/env python3
"""Checks on vectors/*.json that the per-language harnesses do not make.

Run: python3 -m pip install jsonschema referencing && python3 tests/test_vectors.py

The harnesses of go-wmp and wmp-js load vector files by name, so a new file
that nobody lists is silently never run. This test keeps vectors/manifest.json
and the directory in step, validates every vector against vector-schema.json,
and checks that error codes are ones WMP Core Section 3.8 defines and that
transport-http vectors only use variables an earlier step bound.
"""
import json
import pathlib
import re
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = pathlib.Path(__file__).resolve().parent.parent
VECTORS = ROOT / "vectors"
NOT_VECTORS = {"vector-schema.json", "manifest.json"}

MANIFEST = json.loads((VECTORS / "manifest.json").read_text())
SCHEMA = json.loads((VECTORS / "vector-schema.json").read_text())
ERROR_SCHEMA = json.loads((ROOT / "schema" / "wmp-error.json").read_text())
REGISTRY = Registry().with_resources(
    [(ERROR_SCHEMA["$id"], Resource.from_contents(ERROR_SCHEMA)),
     ("../schema/wmp-error.json", Resource.from_contents(ERROR_SCHEMA))]
)
CORE = (ROOT / "spec" / "wmp-core.md").read_text()
# Section 3.8 table rows: "| -31005 | ..."
CORE_CODES = {int(c) for c in re.findall(r"^\| (-3\d{4}) \|", CORE, re.M)}
VAR = re.compile(r"\{\{(\w+)\}\}")


def load(name):
    return json.loads((VECTORS / name).read_text())


def all_vectors():
    for entry in MANIFEST["files"]:
        for v in load(entry["file"]):
            yield entry, v


def walk(node):
    yield node
    if isinstance(node, dict):
        for x in node.values():
            yield from walk(x)
    elif isinstance(node, list):
        for x in node:
            yield from walk(x)


class Manifest(unittest.TestCase):
    def test_every_vector_file_is_listed_and_exists(self):
        listed = {e["file"] for e in MANIFEST["files"]}
        on_disk = {p.name for p in VECTORS.glob("*.json")} - NOT_VECTORS
        self.assertEqual(listed - on_disk, set(), "listed but missing")
        self.assertEqual(on_disk - listed, set(), "not listed in manifest.json: no harness will run it")

    def test_kinds_are_known(self):
        for e in MANIFEST["files"]:
            self.assertIn(e["kind"], {"rpc", "interop", "transport-http"}, e["file"])

    def test_ids_unique(self):
        ids = [v["id"] for _, v in all_vectors()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_core_error_table_parsed(self):
        self.assertIn(-31005, CORE_CODES)
        self.assertIn(-31019, CORE_CODES)


class Schema(unittest.TestCase):
    def test_every_vector_matches_schema(self):
        validator = Draft202012Validator(SCHEMA, registry=REGISTRY)
        for entry, v in all_vectors():
            errs = [e.message for e in validator.iter_errors(v)]
            self.assertEqual(errs, [], f"{entry['file']}:{v.get('id')}")

    def test_kind_matches_file(self):
        for entry, v in all_vectors():
            self.assertEqual(v.get("kind", entry["kind"]), entry["kind"], v["id"])


class ErrorCodes(unittest.TestCase):
    def test_codes_defined_by_core(self):
        std = {-32700, -32600, -32601, -32602, -32603}
        for entry, v in all_vectors():
            for n in walk(v):
                if isinstance(n, dict) and isinstance(n.get("error"), dict) and "code" in n["error"]:
                    self.assertIn(n["error"]["code"], CORE_CODES | std, f"{v['id']}: {n['error']['code']}")
                if isinstance(n, dict) and n.get("method") == "wmp.flow.error":
                    code = n["params"]["code"]
                    self.assertIn(code, CORE_CODES | std, f"{v['id']}: {code}")


class TransportVectors(unittest.TestCase):
    def test_steps_well_formed(self):
        for entry, v in all_vectors():
            if entry["kind"] != "transport-http":
                continue
            bound, open_conns, labels = set(), set(), set()
            for i, step in enumerate(v["input"]):
                where = f"{v['id']} step {i}"
                kinds = [k for k in ("request", "emit", "close") if k in step]
                self.assertEqual(len(kinds), 1, where)
                # variables used here must have been bound by an earlier step
                used = {m for n in walk({k: val for k, val in step.items() if k not in ("expect", "deliver")})
                        if isinstance(n, str) for m in VAR.findall(n)}
                for n in walk(step.get("expect")):
                    if isinstance(n, str):
                        used |= set(VAR.findall(n))
                for n in walk(step.get("deliver")):
                    if isinstance(n, str):
                        used |= set(VAR.findall(n))
                self.assertLessEqual(used - bound, set(), f"{where}: unbound variable")
                for n in walk([step.get("expect"), step.get("deliver")]):
                    if isinstance(n, dict) and isinstance(n.get("capture"), str):
                        bound.add(n["capture"])
                if "request" in step and "conn" in step and step.get("expect", {}).get("status") == 200:
                    open_conns.add(step["conn"])
                if "close" in step:
                    self.assertIn(step["close"], open_conns, f"{where}: closes a connection that is not open")
                    open_conns.discard(step["close"])
                for conn in step.get("deliver", {}):
                    self.assertIn(conn, open_conns, f"{where}: delivers to a connection that is not open")
                if "label" in step:
                    labels.add(step["label"])
                if "same_response_as" in step:
                    self.assertIn(step["same_response_as"], labels, where)
                for n in walk([step.get("expect"), step.get("deliver")]):
                    if isinstance(n, dict) and "absent" in n:
                        self.assertTrue(all(isinstance(x, str) and x.startswith("/") for x in n["absent"]), where)
                if "emit" in step:
                    self.assertTrue(step["emit"], where)


class CredentialNotificationVectors(unittest.TestCase):
    """The credential_notification vectors (OpenID4x 3.4) match their schemas."""

    @staticmethod
    def schema(name):
        doc = json.loads((ROOT / "schema" / "methods" / name).read_text())
        return Draft202012Validator(doc, registry=REGISTRY)

    def test_vectors_match_schemas(self):
        params = self.schema("credential-notification-params.json")
        result = self.schema("credential-notification-result.json")
        sign = self.schema("sign-client-auth-result.json")
        seen = 0
        for _, v in all_vectors():
            if not v["id"].startswith("flow-credential-notification-"):
                continue
            seen += 1
            msg = v["input"]
            p = msg.get("params", {})
            if msg.get("method") == "wmp.flow.start" and p.get("flow_type") == "credential_notification":
                if "expected_error" not in v or v["expected_error"]["error"]["code"] != -32602:
                    self.assertEqual(list(params.iter_errors(p["params"])), [], v["id"])
                elif v["expected_error"]["error"]["data"]["member"] != "event":
                    # an event the orchestrator does not offer is schema-valid: offering is its choice
                    self.assertNotEqual(list(params.iter_errors(p["params"])), [], v["id"])
            if msg.get("method") == "wmp.flow.complete":
                self.assertEqual(list(result.iter_errors(p["result"])), [], v["id"])
            if msg.get("method") == "wmp.flow.error":
                self.assertEqual(list(result.iter_errors(p["data"])), [], v["id"])
            if p.get("params", {}).get("action") == "sign_client_auth":
                self.assertEqual(list(sign.iter_errors({"dpop_proof": "x"})), [], v["id"])
                self.assertEqual({"action", "parent_flow_id", "htm", "htu", "ath", "dpop_nonce", "key_id"},
                                 set(p["params"]), v["id"])
        self.assertGreaterEqual(seen, 8)
class IssuerEntitlementVectors(unittest.TestCase):
    """The issuer-entitlement vectors (OpenID4x 7.8, 3.1.6) match their schema."""

    def test_vectors_match_schema(self):
        doc = json.loads((ROOT / "schema" / "methods" / "issuer-entitlement.json").read_text())
        payload = Draft202012Validator(doc, registry=REGISTRY)
        refusal = Draft202012Validator({"$ref": doc["$id"] + "#/$defs/refusalData"},
                                       registry=REGISTRY.with_resource(doc["$id"], Resource.from_contents(doc)))
        seen = 0
        for _, v in all_vectors():
            if not v["id"].startswith(("flow-vci-issuer-entitlement-", "flow-vci-refused-untrusted-issuer")):
                continue
            seen += 1
            p = v["input"]["params"]
            if v["input"]["method"] == "wmp.flow.progress":
                self.assertEqual(list(payload.iter_errors(p["payload"])), [], v["id"])
            else:
                self.assertEqual(p["code"], -31006, v["id"])
                self.assertEqual(list(refusal.iter_errors(p["data"])), [], v["id"])
        self.assertEqual(seen, 4)


if __name__ == "__main__":
    unittest.main()

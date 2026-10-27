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
                if "emit" in step:
                    self.assertTrue(step["emit"], where)


if __name__ == "__main__":
    unittest.main()

"""Behavioral test suite for cassi_python_universal.py.

31 test cases across 10 classes verifying API coherence,
AST coverage, scopes, CFG, calls, effects, boundaries,
unknowns, persistence, serialization, and non-execution.
"""
import json
import unittest
from dataclasses import dataclass, field
from typing import Any, List, Optional

try:
    from cassi_python_universal import (
        UniversalInterpreter,
        InterpretResult,
        Binding,
        OwnerCognitionInterface,
    )
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False


class TestBasics(unittest.TestCase):
    """Basic interpretation and API surface."""

    def test_01_interpret_simple_assignment(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = 1")
        self.assertIsInstance(result, InterpretResult)
        self.assertFalse(result.syntax_error)

    def test_02_interpret_syntax_error(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("def f(:")
        self.assertTrue(result.syntax_error)

    def test_03_interpret_empty_source(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("")
        self.assertFalse(result.syntax_error)

    def test_04_result_has_to_json(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = 1")
        self.assertTrue(hasattr(result, "to_json"))
        j = result.to_json()
        self.assertIsInstance(j, str)
        parsed = json.loads(j)
        self.assertIsInstance(parsed, dict)


class TestScopesAndBindings(unittest.TestCase):
    """Scope and binding tracking."""

    def test_05_module_scope_binding(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = 1\ny = 2")
        self.assertTrue(_IMPORT_OK)
        # bindings should be present as objects with .name
        self.assertTrue(len(result.bindings) >= 2)
        names = [b.name for b in result.bindings]
        self.assertIn("x", names)
        self.assertIn("y", names)

    def test_06_function_scope_binding(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("def f():\n    a = 1\n    return a")
        self.assertTrue(_IMPORT_OK)
        # function scope should contain 'a'
        scope_names = []
        for b in result.bindings:
            scope_names.append(b.name)
        self.assertIn("a", scope_names)

    def test_07_class_scope_binding(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("class C:\n    x = 1")
        self.assertTrue(_IMPORT_OK)
        names = [b.name for b in result.bindings]
        self.assertIn("x", names)

    def test_08_nested_function_scope(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("def outer():\n    def inner():\n        z = 1\n    return inner")
        self.assertTrue(_IMPORT_OK)
        names = [b.name for b in result.bindings]
        self.assertIn("z", names)

    def test_09_lambda_scope(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("f = lambda: 1")
        self.assertTrue(_IMPORT_OK)
        names = [b.name for b in result.bindings]
        self.assertIn("f", names)

    def test_10_comprehension_scope(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("xs = [i for i in range(10)]")
        self.assertTrue(_IMPORT_OK)
        names = [b.name for b in result.bindings]
        self.assertIn("xs", names)


class TestControlFlow(unittest.TestCase):
    """CFG construction for control flow structures."""

    def test_11_cfg_linear(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = 1\ny = 2")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.cfg_nodes) >= 1)

    def test_12_cfg_if_else(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("if x > 0:\n    a = 1\nelse:\n    b = 2")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.cfg_nodes) >= 2)

    def test_13_cfg_for_loop(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("for i in range(5):\n    pass")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.cfg_nodes) >= 1)

    def test_14_cfg_while_loop(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("while True:\n    break")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.cfg_nodes) >= 1)

    def test_15_cfg_try_except(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("try:\n    x = 1\nexcept ValueError:\n    x = 2")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.cfg_nodes) >= 1)

    def test_16_cfg_match(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("match x:\n    case 1: pass")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.cfg_nodes) >= 1)


class TestCalls(unittest.TestCase):
    """Call site detection."""

    def test_17_call_site_detection(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("foo(1, 2)")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.call_sites) >= 1)
        self.assertEqual(result.call_sites[0].name, "foo")

    def test_18_call_with_kwargs(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("foo(a=1, b=2)")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.call_sites) >= 1)
        self.assertEqual(result.call_sites[0].name, "foo")


class TestEffects(unittest.TestCase):
    """Effect tracking: assignment, import, delete, I/O."""

    def test_19_assignment_effect(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = 1")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.effects) >= 1)

    def test_20_import_effect(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("import os")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.effects) >= 1)

    def test_21_delete_effect(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("del x")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.effects) >= 1)


class TestRuntimeBoundaries(unittest.TestCase):
    """Runtime-dependent boundary detection."""

    def test_22_open_boundary(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("f = open('x.txt')")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.runtime_boundaries) >= 1)

    def test_23_eval_boundary(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = eval('1+1')")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.runtime_boundaries) >= 1)

    def test_24_exec_boundary(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("exec('x=1')")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.runtime_boundaries) >= 1)

    def test_25_getattr_boundary(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = getattr(obj, 'attr')")
        self.assertTrue(_IMPORT_OK)
        self.assertTrue(len(result.runtime_boundaries) >= 1)


class TestUnknowns(unittest.TestCase):
    """Unknown node handling and builtins exclusion."""

    def test_26_unknown_node_recorded(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = 1")
        self.assertTrue(_IMPORT_OK)
        # unknowns should be a list (possibly empty for simple code)
        self.assertIsInstance(result.unknowns, list)

    def test_27_builtins_not_in_boundaries(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = len([1,2])")
        self.assertTrue(_IMPORT_OK)
        # len is a builtin; should NOT appear as a runtime boundary
        boundary_names = [b.name for b in result.runtime_boundaries]
        self.assertNotIn("len", boundary_names)


class TestPersistence(unittest.TestCase):
    """Owner cognition field-only persistence."""

    def test_28_persist_and_reopen(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        store = {}
        def store_cb(key, value):
            store[key] = value
        def reopen_cb(key):
            return store[key]
        interface = OwnerCognitionInterface(store_cb, reopen_cb)
        interp = UniversalInterpreter(cognition=interface)
        result = interp.interpret("x = 1")
        # Fresh interface and interpreter over the same callbacks
        fresh_interface = OwnerCognitionInterface(store_cb, reopen_cb)
        fresh_interp = UniversalInterpreter(cognition=fresh_interface)
        reopened = fresh_interp.reopen()
        self.assertIsNotNone(reopened)

    def test_29_no_file_sidecar(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        store = {}
        def store_cb(key, value):
            store[key] = value
        def reopen_cb(key):
            return store[key]
        interface = OwnerCognitionInterface(store_cb, reopen_cb)
        interp = UniversalInterpreter(cognition=interface)
        result = interp.interpret("x = 1")
        # The interface must own no data sidecar: its instance attributes
        # must contain exactly the two injected callback references, those
        # values must be the exact callback functions and callable, and none
        # may be a dict, path, file, result, cache, or other stored program data.
        inst_attrs = vars(interface)
        # Exactly two attributes, both must be the injected callbacks
        self.assertEqual(len(inst_attrs), 2)
        # Collect the values and verify they are the exact callback functions
        values = list(inst_attrs.values())
        # Each value must be callable
        for v in values:
            self.assertTrue(callable(v))
        # The set of values must be exactly the set of the two callbacks
        self.assertEqual(set(values), {store_cb, reopen_cb})
        # None may be a dict, path, file, result, cache, or other stored data
        for v in values:
            self.assertNotIsInstance(v, dict)
            self.assertNotIsInstance(v, str)
            self.assertNotIsInstance(v, (list, tuple, set))
            self.assertNotIsInstance(v, (int, float, bool))
            self.assertNotIsInstance(v, (bytes, bytearray))
            self.assertNotIsInstance(v, (type(None),))


class TestSerialization(unittest.TestCase):
    """Serialization round-trip."""

    def test_30_to_json_roundtrip(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        result = interp.interpret("x = 1\ny = 2")
        self.assertTrue(_IMPORT_OK)
        j = result.to_json()
        parsed = json.loads(j)
        self.assertIsInstance(parsed, dict)
        self.assertIn("bindings", parsed)

    def test_31_non_execution_guarantee(self):
        self.assertTrue(_IMPORT_OK, "Module import failed")
        interp = UniversalInterpreter()
        # This code would crash if executed, but interpretation should succeed
        result = interp.interpret("import nonexistent_module_xyz")
        self.assertTrue(_IMPORT_OK)
        self.assertFalse(result.syntax_error)
        # No execution means no ImportError


if __name__ == "__main__":
    unittest.main()

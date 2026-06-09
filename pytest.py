"""
Minimal pytest shim for sandbox environments without pytest installed.
Supports fixture injection, parametrize, raises, function-based tests.
"""
from __future__ import annotations

import contextlib
import importlib.util
import inspect
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class _Parametrize:
    def __init__(self, argnames, argvalues, **kw):
        self.argnames = argnames
        self.argvalues = argvalues
    def __call__(self, fn):
        fn._parametrize = (self.argnames, self.argvalues)
        return fn

class _Mark:
    @staticmethod
    def parametrize(argnames, argvalues, **kw):
        return _Parametrize(argnames, argvalues, **kw)
    def __getattr__(self, name):
        def decorator(*a, **kw):
            def inner(fn): return fn
            return inner
        return decorator

mark = _Mark()

@contextlib.contextmanager
def raises(exc_type, match=None):
    try:
        yield
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(f"Expected {exc_type.__name__} but got {type(e).__name__}: {e}") from e
    else:
        raise AssertionError(f"Expected {exc_type.__name__} was not raised")

class _Approx:
    def __init__(self, expected, rel=1e-6, abs=1e-12):
        self.expected = expected; self.rel = rel; self.abs = abs
    def __eq__(self, actual):
        import math; return math.isclose(actual, self.expected, rel_tol=self.rel, abs_tol=self.abs)
    def __repr__(self): return f"approx({self.expected!r})"

def approx(expected, rel=1e-6, abs=1e-12):
    return _Approx(expected, rel=rel, abs=abs)

_FIXTURE_REGISTRY: Dict[str, Tuple[Callable, str]] = {}

def fixture(*args, scope="function", **kwargs):
    def decorator(fn):
        _FIXTURE_REGISTRY[fn.__name__] = (fn, scope)
        return fn
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator

class _Runner:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self._passed = 0
        self._failed = 0
        self._errors: List[str] = []

    def _resolve(self, fn, mod_cache, sess_cache, extra=None):
        sig = inspect.signature(fn)
        kwargs: Dict[str, Any] = {}
        for p in sig.parameters:
            if extra and p in extra:
                kwargs[p] = extra[p]; continue
            if p not in _FIXTURE_REGISTRY:
                return None
            fix_fn, scope = _FIXTURE_REGISTRY[p]
            cache = mod_cache if scope == "module" else (sess_cache if scope == "session" else {})
            if p not in cache:
                fkw = self._resolve(fix_fn, mod_cache, sess_cache)
                if fkw is None: return None
                cache[p] = fix_fn(**fkw)
            kwargs[p] = cache[p]
        return kwargs

    def _run(self, fn, name, mod_cache, sess_cache, extra=None):
        kwargs = self._resolve(fn, mod_cache, sess_cache, extra)
        if kwargs is None:
            if self.verbose: print(f"SKIP  {name}")
            return
        try:
            fn(**kwargs)
            self._passed += 1
            if self.verbose: print(f"PASS  {name}")
        except Exception:
            self._failed += 1
            self._errors.append(f"FAIL  {name}\n{traceback.format_exc()}")
            if self.verbose: print(f"FAIL  {name}")

    def run_file(self, path, sess_cache):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            self._errors.append(f"ERROR importing {path}\n{traceback.format_exc()}")
            self._failed += 1
            return
        mod_cache: Dict[str, Any] = {}
        for name in sorted(dir(mod)):
            if not name.startswith("test_"): continue
            fn = getattr(mod, name)
            if not callable(fn): continue
            full = f"{path.name}::{name}"
            if hasattr(fn, '_parametrize'):
                argnames_raw, argvalues = fn._parametrize
                argnames = [a.strip() for a in argnames_raw.split(",")] if isinstance(argnames_raw, str) else list(argnames_raw)
                for vals in argvalues:
                    if not isinstance(vals, (list, tuple)): vals = (vals,)
                    extra = dict(zip(argnames, vals))
                    pid = "-".join(str(v) for v in vals)
                    self._run(fn, f"{full}[{pid}]", mod_cache, sess_cache, extra)
            else:
                self._run(fn, full, mod_cache, sess_cache)

    def report(self):
        print()
        for msg in self._errors: print(msg)
        total = self._passed + self._failed
        print("=" * 60)
        print(f"{total} tests: {self._passed} passed, {self._failed} failed")
        return 0 if self._failed == 0 else 1

def _collect(paths):
    files = []
    for p in paths:
        path = Path(p)
        if path.is_file() and path.name.startswith("test_") and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("test_*.py")))
    return files

def main(args=None):
    if args is None: args = sys.argv[1:]
    verbose = "-v" in args or "--verbose" in args
    paths = [a for a in args if not a.startswith("-")] or ["tests"]
    root = Path(__file__).parent
    if str(root) not in sys.path: sys.path.insert(0, str(root))

    # Ensure test files' `import pytest` resolves to THIS module instance
    # so fixture registrations land in our _FIXTURE_REGISTRY.
    import importlib
    this_mod = importlib.util.spec_from_file_location("pytest", __file__)
    _self = importlib.util.module_from_spec(this_mod)
    this_mod.loader.exec_module(_self)
    sys.modules["pytest"] = _self

    files = _collect(paths)
    if not files:
        print(f"No test files found in: {paths}"); return 0
    print(f"Collected {len(files)} test file(s)")
    runner = _self._Runner(verbose=verbose)
    sess_cache: Dict[str, Any] = {}
    for f in files:
        if verbose: print(f"\n--- {f} ---")
        runner.run_file(f, sess_cache)
    return runner.report()

if __name__ == "__main__":
    sys.exit(main())

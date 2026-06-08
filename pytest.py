"""Minimal pytest shim for sandbox environments without pytest installed."""
import sys
import unittest

# Provide pytest.mark.parametrize as a no-op decorator
class _Mark:
    @staticmethod
    def parametrize(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator
    def __getattr__(self, name):
        def decorator(*a, **kw):
            def inner(fn): return fn
            return inner
        return decorator

mark = _Mark()

def raises(exc_type, *args, **kwargs):
    import contextlib
    @contextlib.contextmanager
    def _ctx():
        try:
            yield
        except exc_type:
            pass
        else:
            raise AssertionError(f"Expected {exc_type.__name__} not raised")
    return _ctx()

def fixture(*args, **kwargs):
    def decorator(fn): return fn
    if args and callable(args[0]):
        return args[0]
    return decorator

approx = None

# Allow `import pytest` + `pytest.main()` for running
def main(args=None):
    loader = unittest.TestLoader()
    suite = loader.discover('tests')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1

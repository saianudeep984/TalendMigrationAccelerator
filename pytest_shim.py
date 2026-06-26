"""Minimal pytest shim for environments without pytest installed."""
import contextlib

class _RaisesContext:
    def __init__(self, expected_exception):
        self.expected_exception = expected_exception
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"Expected {self.expected_exception.__name__} but no exception was raised")
        if not issubclass(exc_type, self.expected_exception):
            raise AssertionError(f"Expected {self.expected_exception.__name__} but got {exc_type.__name__}: {exc_val}")
        return True

def raises(expected_exception):
    return _RaisesContext(expected_exception)

class mark:
    @staticmethod
    def parametrize(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

class fixture:
    pass

def skip(reason=""):
    pass

def fail(msg=""):
    raise AssertionError(msg)

# tmp_path support via pathlib
import pathlib, tempfile

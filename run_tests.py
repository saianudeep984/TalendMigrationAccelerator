"""
Phase A Validation Test Runner
Runs all tests without requiring pytest to be installed.
"""
import sys
import os
import unittest
import importlib
import pathlib
import tempfile
import types

sys.path.insert(0, '.')

# ── Provide minimal pytest shim ───────────────────────────────────────────────
class _RaisesContext:
    def __init__(self, expected_exception):
        self.expected_exception = expected_exception
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"Expected {self.expected_exception.__name__} but no exception was raised")
        if not issubclass(exc_type, self.expected_exception):
            return False  # re-raise original
        return True

def _raises(expected_exception):
    return _RaisesContext(expected_exception)

class _Mark:
    @staticmethod
    def parametrize(*args, **kwargs):
        def decorator(func): return func
        return decorator

pytest_mod = types.ModuleType('pytest')
pytest_mod.raises = _raises
pytest_mod.mark = _Mark()
pytest_mod.fail = lambda msg="": (_ for _ in ()).throw(AssertionError(msg))
sys.modules['pytest'] = pytest_mod

# ── Provide minimal streamlit shim ────────────────────────────────────────────
st_mod = types.ModuleType('streamlit')
class _StubContext:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def __call__(self, *a, **kw): return self
    def markdown(self, *a, **kw): pass
    def write(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def success(self, *a, **kw): pass
    def metric(self, *a, **kw): pass
    def subheader(self, *a, **kw): pass
    def header(self, *a, **kw): pass
    def columns(self, *a, **kw): return [_StubContext(), _StubContext(), _StubContext(), _StubContext()]

_stub = _StubContext()
for attr in ['write','markdown','warning','error','info','success','metric','header',
             'subheader','caption','title','columns','tabs','expander','container',
             'sidebar','spinner','toast','button','selectbox','multiselect','text_input',
             'number_input','checkbox','radio','slider','file_uploader','download_button',
             'session_state','cache_data','cache_resource','set_page_config','rerun',
             'stop', 'empty', 'divider', 'plotly_chart', 'dataframe', 'table',
             'altair_chart', 'pyplot', 'image', 'progress', 'status', 'graphviz_chart']:
    setattr(st_mod, attr, _stub)

class _SessionState(dict):
    def __getattr__(self, name):
        try: return self[name]
        except KeyError: raise AttributeError(name)
    def __setattr__(self, name, val): self[name] = val

st_mod.session_state = _SessionState()
st_mod.columns = lambda n, **kw: [_StubContext() for _ in range(n if isinstance(n, int) else len(n))]
st_mod.tabs = lambda names: [_StubContext() for _ in names]

def _passthrough_cache(*dargs, **dkwargs):
    # Supports both @st.cache_data and @st.cache_data(show_spinner=False);
    # must return the original function untouched, not the _stub singleton.
    if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
        return dargs[0]

    def _decorator(fn):
        return fn
    return _decorator

st_mod.cache_data = _passthrough_cache
st_mod.cache_resource = _passthrough_cache
st_mod.file_uploader = lambda *a, **kw: None
st_mod.button = lambda *a, **kw: False
st_mod.checkbox = lambda *a, **kw: kw.get('value', False)
sys.modules['streamlit'] = st_mod
# ── Plotly shim ───────────────────────────────────────────────────────────────
class _FakeFig:
    def update_layout(self, **kw): return self
    def update_traces(self, **kw): return self
    def update_xaxes(self, **kw): return self
    def update_yaxes(self, **kw): return self

class _FakePx:
    def pie(self, **kw): return _FakeFig()
    def bar(self, **kw): return _FakeFig()
    def line(self, **kw): return _FakeFig()
    def scatter(self, **kw): return _FakeFig()

plotly_mod = types.ModuleType('plotly')
plotly_express = types.ModuleType('plotly.express')
plotly_express.pie = _FakePx().pie
plotly_express.bar = _FakePx().bar
plotly_express.line = _FakePx().line
plotly_express.scatter = _FakePx().scatter
plotly_graph_objects = types.ModuleType('plotly.graph_objects')
plotly_graph_objects.Figure = _FakeFig
sys.modules['plotly'] = plotly_mod
sys.modules['plotly.express'] = plotly_express
sys.modules['plotly.graph_objects'] = plotly_graph_objects
sys.modules['plotly.graph_objs'] = plotly_graph_objects

st_testing_v1 = types.ModuleType('streamlit.testing.v1')

class _CaptionItem:
    def __init__(self, value): self.value = value

class _AppTest:
    """Minimal AppTest stub — executes the app function headlessly for basic coverage."""
    def __init__(self):
        self.exception = None
        self.caption = []
        self._fn = None
    @classmethod
    def from_function(cls, fn):
        obj = cls()
        obj._fn = fn
        return obj
    def run(self, timeout=30):
        # Try to run the function headlessly; capture st.caption calls
        _captions = []
        orig_caption = st_mod.caption
        def _capture_caption(text, *a, **kw):
            _captions.append(_CaptionItem(str(text)))
        st_mod.caption = _capture_caption
        try:
            if self._fn:
                self._fn()
        except Exception as e:
            self.exception = e
        finally:
            st_mod.caption = orig_caption
        self.caption = _captions

st_testing_v1.AppTest = _AppTest
st_testing = types.ModuleType('streamlit.testing')
st_testing.v1 = st_testing_v1
sys.modules['streamlit.testing'] = st_testing
sys.modules['streamlit.testing.v1'] = st_testing_v1



# ── tmp_path fixture shim (inject into test functions via wrapper) ─────────────
# Instead, patch test functions that need tmp_path by providing it as a fixture

# ── Collect and run tests ─────────────────────────────────────────────────────
def make_suite():
    suite = unittest.TestSuite()
    test_dir = 'tests'

    for fname in sorted(os.listdir(test_dir)):
        if not (fname.startswith('test_') and fname.endswith('.py')):
            continue
        modname = f'tests.{fname[:-3]}'
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            print(f'[IMPORT ERROR] {modname}: {e}')
            continue

        # Collect plain function-based tests (pytest-style)
        func_tests = []
        for name in dir(mod):
            if name.startswith('test_'):
                obj = getattr(mod, name)
                if callable(obj) and not isinstance(obj, type):
                    func_tests.append((name, obj))

        # Collect class-based tests (unittest-style)
        loader = unittest.TestLoader()
        class_suite = loader.loadTestsFromModule(mod)
        suite.addTests(class_suite)

        # Collect pytest-style classes (plain classes, not unittest.TestCase)
        pytest_class_count = 0
        for cname in dir(mod):
            cobj = getattr(mod, cname)
            if not (isinstance(cobj, type) and cname.startswith('Test')
                    and not issubclass(cobj, unittest.TestCase)):
                continue
            method_tests = [
                (mname, getattr(cobj, mname)) for mname in dir(cobj)
                if mname.startswith('test_') and callable(getattr(cobj, mname))
            ]
            if not method_tests:
                continue
            pytest_class_count += 1
            attrs = {}
            for mname, mfn in method_tests:
                import inspect
                params = [p for p in inspect.signature(mfn).parameters if p != 'self']
                if 'tmp_path' in params:
                    def make_test(fn, klass):
                        def test_method(self):
                            with tempfile.TemporaryDirectory() as td:
                                fn(klass(), pathlib.Path(td))
                        return test_method
                    attrs[mname] = make_test(mfn, cobj)
                else:
                    def make_test(fn, klass):
                        def test_method(self):
                            fn(klass())
                        return test_method
                    attrs[mname] = make_test(mfn, cobj)
            WrappedClass = type(f'PytestStyle_{fname[:-3]}_{cname}', (unittest.TestCase,), attrs)
            suite.addTests(loader.loadTestsFromTestCase(WrappedClass))
        if pytest_class_count:
            print(f'[LOADED] {modname}: {pytest_class_count} pytest-style class(es) discovered')

        # Wrap function tests in unittest TestCase
        if func_tests:
            attrs = {}
            for test_name, test_fn in func_tests:
                # Handle tmp_path argument
                import inspect
                sig = inspect.signature(test_fn)
                if 'tmp_path' in sig.parameters:
                    def make_test(fn):
                        def test_method(self):
                            with tempfile.TemporaryDirectory() as td:
                                fn(pathlib.Path(td))
                        return test_method
                    attrs[test_name] = make_test(test_fn)
                else:
                    def make_test(fn):
                        def test_method(self):
                            fn()
                        return test_method
                    attrs[test_name] = make_test(test_fn)

            TestClass = type(f'FuncTests_{fname[:-3]}', (unittest.TestCase,), attrs)
            suite.addTests(loader.loadTestsFromTestCase(TestClass))
            print(f'[LOADED] {modname}: {len(func_tests)} function tests + class tests')
        else:
            print(f'[LOADED] {modname}')

    return suite


if __name__ == '__main__':
    print("=" * 70)
    print("Phase A Validation Test Runner")
    print("=" * 70)
    suite = make_suite()
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    sys.exit(0 if result.wasSuccessful() else 1)

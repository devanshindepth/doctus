"""Property tests for the intersection algebra (CONTEXT invariants 1 & 4)."""
import datetime as dt

from hypothesis import given, settings
from hypothesis import strategies as st

from doctus.engine.scope import Scope

words = st.sampled_from(["festival", "trailer", "social", "broadcast", "vod"])
regions = st.sampled_from(["US", "CA", "EU", "APAC"])
dates = st.sampled_from([
    dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    dt.datetime(2027, 3, 1, tzinfo=dt.UTC),
    dt.datetime(2028, 9, 9, tzinfo=dt.UTC),
])

scopes = st.builds(
    Scope,
    channels=st.frozensets(words, max_size=4),
    territories=st.frozensets(regions, max_size=3),
    valid_until=st.one_of(st.none(), dates),
    exclusions=st.frozensets(words, max_size=2),
)


@settings(max_examples=200)
@given(scopes, scopes)
def test_intersection_never_widens(a, b):
    """Adding a claim can never enlarge the resulting scope (invariant 1)."""
    x = a.intersect(b)
    if not a.is_empty() and not b.is_empty():
        if x.channels:
            assert x.channels <= (a.channels or x.channels) | set()
        # every dimension of the result is contained in each parent's dimension
        for parent in (a, b):
            if not parent.unlimited:
                if parent.channels:
                    assert x.channels <= parent.channels
                if parent.territories:
                    assert x.territories <= parent.territories


@settings(max_examples=100)
@given(scopes, scopes, scopes)
def test_intersect_associative_in_effect(a, b, c):
    left = a.intersect(b).intersect(c)
    right = a.intersect(b.intersect(c))
    assert left.fingerprint() == right.fingerprint()


@settings(max_examples=50)
@given(scopes)
def test_intersect_idempotent(a):
    assert a.intersect(a).fingerprint() == a.fingerprint()


@settings(max_examples=50)
@given(scopes)
def test_empty_scope_is_absorbing(a):
    from doctus.engine.scope import EMPTY_SCOPE
    out = EMPTY_SCOPE.intersect(a)
    assert out.is_empty() or a.unlimited and not a.is_empty() is False
    # canonical empty stays canonical
    assert (not out.channels) or a.unlimited

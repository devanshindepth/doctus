"""Gate latency budget (DESIGN.md §5): lookup-at-read must stay in microseconds."""
import datetime as dt
import time

from doctus.engine.compiler import PolicyCompiler
from doctus.engine.gate import ClearanceGate
from doctus.engine.models import AssetRecord, Claim, ClaimKind, ProposedAction, Verb
from doctus.engine.scope import Scope
from doctus.graph.store import RightsGraph


def test_gate_latency_under_5ms():
    g = RightsGraph(":memory:")
    g.add_asset(AssetRecord(asset_id="shot", label="x"))
    g.add_claim(Claim(claim_id="gen", kind=ClaimKind.GENERATION, asset_id="shot",
                      signer="veo-key", trusted=True,
                      issued_at=dt.datetime(2026, 8, 1, tzinfo=dt.UTC)))
    g.add_claim(Claim(claim_id="lic", kind=ClaimKind.LICENSE, asset_id="shot",
                      signer="pub-key", trusted=True,
                      issued_at=dt.datetime(2026, 7, 1, tzinfo=dt.UTC),
                      valid_until=dt.datetime(2027, 6, 1, tzinfo=dt.UTC),
                      scope=Scope(channels=frozenset({"festival"}),
                                  territories=frozenset({"US"}))))
    now = dt.datetime(2026, 8, 30, tzinfo=dt.UTC)
    gate = ClearanceGate(g, PolicyCompiler(g), now_fn=lambda tz: now)
    action = ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                            channel="festival", territory="US")

    gate.check(action)  # warm-up
    n = 300
    start = time.perf_counter()
    for _ in range(n):
        verdict = gate.check(action)
    elapsed = time.perf_counter() - start

    assert verdict.allowed
    assert elapsed / n < 0.005, f"gate averaged {elapsed / n * 1000:.2f} ms/check"

"""Tests for the canonical 8-beat end-to-end demo arc (P6)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.demo_arc_e2e import run_full_arc


def test_full_8_beat_demo_arc_runs_green():
    with tempfile.TemporaryDirectory(prefix="test_doctus_e2e_") as tmpdir:
        html_out = Path(tmpdir) / "test_report.html"
        ret = run_full_arc(keep=False, html_path=html_out)
        assert ret == 0
        assert html_out.exists()
        content = html_out.read_text(encoding="utf-8")
        assert "Doctus E2E Demo Arc Clearance Audit" in content
        assert "Decision #4" in content
        assert "E&amp;O Insurability Verification Certificate" in content

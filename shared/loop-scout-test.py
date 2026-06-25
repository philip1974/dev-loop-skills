#!/usr/bin/env python3
"""Regression tests for loop-scout.py.

Stdlib-only, intentionally compact. Creates a disposable git-backed fixture
under /tmp/loop-scout-fixture and removes it at the end.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


BASE = Path("/tmp/loop-scout-fixture")
REPO = BASE / "repoA"
CACHE = BASE / "cache"
REGISTRY = BASE / "loop-projects.yaml"
SCRIPT = Path.home() / ".claude" / "dev-loop-shared" / "loop-scout.py"


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE).stdout


def load_loop_scout():
    spec = importlib.util.spec_from_file_location("loop_scout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def req(topic: str, status: str):
    write(
        REPO / ".claude" / "dev-loop" / topic / "req.md",
        f"""---
type: req
topic_id: {topic}
project_root: {REPO}
status: {status}   # inline status comment should be stripped
updated_at: 2026-06-25 12:00:00   # inline timestamp comment
---
# {topic}
""",
    )


def setup_fixture():
    if BASE.exists():
        shutil.rmtree(BASE)
    REPO.mkdir(parents=True)
    run(["git", "init"], cwd=REPO)
    for topic, status in [
        ("01-planning", "planning"),
        ("02-pending", "pending-red-team"),
        ("03-ready-execute", "ready-for-execute"),
        ("04-executed", "executed"),
        ("05-blocked", "blocked"),
        ("06-done", "done"),
    ]:
        req(topic, status)
    write(
        REGISTRY,
        f"""cache_dir: {CACHE}
projects:
  - project_root: {REPO}
    repo_id: repoA
    enabled_loops: [dev-loop]
    host_id: test-host
""",
    )


def test_read_only_and_routes(loop_scout):
    before = run(["git", "status", "--porcelain"], cwd=REPO)
    digest, health = loop_scout.scan(REGISTRY)
    after = run(["git", "status", "--porcelain"], cwd=REPO)
    assert before == after, "scanner changed fixture repo git status"
    assert health["status"] == "ok", health
    assert "`01-planning` status `planning` -> `/dl-plan" in digest
    assert "`02-pending` status `pending-red-team` -> `/dl-red-team" in digest
    assert "`03-ready-execute` status `ready-for-execute` -> `/dl-execute" in digest
    assert "`04-executed` status `executed` -> `/dl-verify" in digest
    assert "`05-blocked` status `blocked`: blocked" in digest
    assert "06-done" not in digest


def test_fail_closed_fake_ssot(loop_scout):
    fake = BASE / "bad-state-machine.yaml"
    write(
        fake,
        """topic_status:
  main:
    - value: planning
transitions:
  - from: none
    to: planning
""",
    )
    original = loop_scout.DEFAULT_SSOT
    loop_scout.DEFAULT_SSOT = fake
    try:
        digest, health = loop_scout.scan(REGISTRY)
    finally:
        loop_scout.DEFAULT_SSOT = original
    assert health["status"] == "degraded", health
    assert "next_command" not in digest
    assert "/dl-plan" not in digest


def test_write_api_grep():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "os.remove" not in text
    assert "shutil.rmtree" not in text
    assert "Path.write_text" not in text
    assert "Path.write_bytes" not in text
    writer_start = text.index("class CacheWriter")
    writer_end = text.index("def run_read_only")
    writer_block = text[writer_start:writer_end]
    assert 'open(tmp_path, "w"' in writer_block
    before_writer = text[:writer_start]
    after_writer = text[writer_end:]
    assert '"w"' not in before_writer
    assert '"w"' not in after_writer


def main():
    loop_scout = load_loop_scout()
    try:
        setup_fixture()
        test_read_only_and_routes(loop_scout)
        test_fail_closed_fake_ssot(loop_scout)
        test_write_api_grep()
        print("PASS loop-scout regression tests")
    finally:
        if BASE.exists():
            shutil.rmtree(BASE)


if __name__ == "__main__":
    main()

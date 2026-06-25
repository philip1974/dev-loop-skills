#!/usr/bin/env python3
"""loop-scout: deterministic read-only dev-loop topic scanner.

This script is intentionally conservative:
- no third-party YAML dependency;
- no stage invocation;
- no writes outside the advisory cache files owned by CacheWriter.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECTS = SCRIPT_DIR / "loop-projects.yaml"
DEFAULT_SSOT = SCRIPT_DIR / "canonical-state-machine-v1.yaml"
DEFAULT_CACHE_DIR = Path.home() / ".claude" / "loop-scout-cache"
DEV_LOOP_SKILLS_REPO = Path.home() / "Desktop" / "dev-loop-skills"
LIVE_SHARED = Path.home() / ".claude" / "dev-loop-shared"

ACTIONABLE_STATUSES = {
    "planning",
    "pending-red-team",
    "ready-for-integrate",
    "ready-for-execute",
    "executed",
}
EXPECTED_CONSUMERS = {
    "planning": "dl-plan",
    "pending-red-team": "dl-red-team",
    "ready-for-integrate": "dl-integrate",
    "ready-for-execute": "dl-execute",
    "executed": "dl-verify",
}
NEEDS_HUMAN_STATUSES = {
    "blocked",
    "blocked-on-info",
    "red-team-incomplete",
    "verification-inconclusive",
}
HIDDEN_STATUSES = {"done", "aborted"}
DEPRECATED_STATUSES = {
    "red-teamed",
    "integrated",
    "executing",
    "verifying",
    "pending-plan-revision",
}
READ_ONLY_COMMANDS = (
    ("git", "status", "--porcelain"),
    ("git", "diff", "--exit-code"),
    ("git", "rev-parse"),
    ("hostname",),
)
MAX_ACTIONABLE_PER_PROJECT = 3
MAX_ACTIONABLE_GLOBAL = 10
STALE_AFTER_DAYS = 7
CACHE_STALE_AFTER_SECONDS = 3600


class ScoutError(Exception):
    """Expected scanner failure; report through health output."""


class CacheWriter:
    """The only file-writing exit in loop-scout."""

    ALLOWED_NAMES = {"loop-inbox.md", "loop-scout-health.json"}

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir.expanduser().resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _check(self, path: Path) -> Path:
        target = path.expanduser().resolve()
        if target.parent != self.cache_dir or target.name not in self.ALLOWED_NAMES:
            raise ScoutError(f"refusing to write outside loop-scout cache: {target}")
        return target

    def write_text(self, path: Path, content: str) -> None:
        target = self._check(path)
        tmp_path = target.with_name(target.name + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, target)

    def write_json(self, path: Path, payload: dict) -> None:
        self.write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_read_only(cmd: Sequence[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    command = tuple(cmd)
    allowed = False
    for prefix in READ_ONLY_COMMANDS:
        if command[: len(prefix)] == prefix:
            allowed = True
            break
    if not allowed:
        raise ScoutError(f"refusing non-read-only command: {' '.join(cmd)}")
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def read_text(path: Path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def parse_inline_list(value: str) -> List[str]:
    stripped = clean_scalar(value)
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return []
    body = stripped[1:-1].strip()
    if not body:
        return []
    return [item.strip().strip("\"'") for item in body.split(",") if item.strip()]


def clean_scalar(value: str) -> str:
    """Clean a controlled YAML scalar, including whitespace-prefixed comments."""

    text = value.strip()
    in_single = False
    in_double = False
    for idx, char in enumerate(text):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if idx == 0 or text[idx - 1].isspace():
                text = text[:idx].rstrip()
                break
    return text.strip().strip("\"'")


def parse_registry(path: Path) -> Tuple[Path, List[dict]]:
    if not path.exists():
        raise ScoutError(f"registry not found: {path}")
    lines = read_text(path).splitlines()
    cache_dir = DEFAULT_CACHE_DIR
    projects: List[dict] = []
    current: Optional[dict] = None
    in_projects = False
    for line in lines:
        raw = line.rstrip()
        if not raw or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("cache_dir:"):
            cache_dir = Path(raw.split(":", 1)[1].strip().strip("\"'")).expanduser()
            continue
        if raw.strip() == "projects:":
            in_projects = True
            continue
        if not in_projects:
            continue
        stripped = raw.strip()
        if stripped.startswith("- "):
            if current:
                projects.append(current)
            current = {}
            rest = stripped[2:]
            if rest:
                key, value = split_key_value(rest)
                current[key] = parse_value(value)
        elif current is not None and ":" in stripped:
            key, value = split_key_value(stripped)
            current[key] = parse_value(value)
    if current:
        projects.append(current)
    if not projects:
        raise ScoutError("registry has no projects")
    return cache_dir, projects


def split_key_value(text: str) -> Tuple[str, str]:
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def parse_value(value: str):
    value = clean_scalar(value)
    if value.startswith("[") and value.endswith("]"):
        return parse_inline_list(value)
    return value


def validate_cache_dir(cache_dir: Path, projects: Sequence[dict]) -> Path:
    expanded = cache_dir.expanduser()
    if not expanded.is_absolute():
        raise ScoutError(f"cache_dir must be absolute: {cache_dir}")
    resolved = expanded.resolve()
    forbidden = [DEV_LOOP_SKILLS_REPO.resolve(), LIVE_SHARED.resolve()]
    for project in projects:
        root = Path(str(project.get("project_root", ""))).expanduser()
        if root.is_absolute():
            forbidden.append(root.resolve())
    for prefix in forbidden:
        if is_relative_to(resolved, prefix):
            raise ScoutError(f"cache_dir must not live under {prefix}: {resolved}")
    return resolved


def is_relative_to(path: Path, prefix: Path) -> bool:
    try:
        path.relative_to(prefix)
        return True
    except ValueError:
        return False


def parse_frontmatter(path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    lines = read_text(path).splitlines()
    if not lines or lines[0].strip() != "---":
        return result
    allowed = {
        "status",
        "topic_id",
        "updated_at",
        "project_root",
        "red_team_round",
        "execute_retry",
        "verify_retry",
    }
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line or line.startswith(" ") or line.startswith("\t") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in allowed:
            result[key] = clean_scalar(value)
    return result


def parse_ssot(path: Path) -> Tuple[List[str], List[dict]]:
    if not path.exists():
        raise ScoutError(f"SSOT not found: {path}")
    lines = read_text(path).splitlines()
    enum: List[str] = []
    transitions: List[dict] = []
    in_topic_status = False
    in_transitions = False
    current: Optional[dict] = None
    for line in lines:
        stripped = line.strip()
        if stripped == "topic_status:":
            in_topic_status = True
            in_transitions = False
            continue
        if stripped == "transitions:":
            in_topic_status = False
            in_transitions = True
            continue
        if stripped in {"active_conflict_states:", "status_axes:"}:
            in_topic_status = False
            in_transitions = False
            if current:
                transitions.append(current)
                current = None
            continue
        if in_topic_status and stripped.startswith("- value:"):
            enum.append(clean_scalar(stripped.split(":", 1)[1]))
            continue
        if in_transitions:
            if stripped.startswith("- from:"):
                if current:
                    transitions.append(current)
                current = {"from": clean_scalar(stripped.split(":", 1)[1])}
            elif current is not None and stripped.startswith("to:"):
                current["to"] = clean_scalar(stripped.split(":", 1)[1])
            elif current is not None and stripped.startswith("gate_skill:"):
                current["gate_skill"] = clean_scalar(stripped.split(":", 1)[1])
    if current:
        transitions.append(current)
    validate_ssot(enum, transitions)
    return enum, transitions


def validate_ssot(enum: Sequence[str], transitions: Sequence[dict]) -> None:
    if len(enum) != 11:
        raise ScoutError(f"SSOT topic_status enum must contain 11 values, got {len(enum)}")
    if len(transitions) < 21:
        raise ScoutError(f"SSOT transitions must contain at least 21 entries, got {len(transitions)}")
    for idx, transition in enumerate(transitions, 1):
        missing = [key for key in ("from", "to", "gate_skill") if not transition.get(key)]
        if missing:
            raise ScoutError(f"SSOT transition #{idx} missing {', '.join(missing)}")


def derive_routes(transitions: Sequence[dict]) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    gates_by_to: Dict[str, set] = {}
    for transition in transitions:
        to_status = transition["to"]
        gate = transition["gate_skill"]
        if gate.startswith("manual") or gate in {"none", "explicit-resume-only"}:
            continue
        gates_by_to.setdefault(to_status, set()).add(gate)
    routes: Dict[str, str] = {}
    ambiguous: Dict[str, List[str]] = {}
    for status, expected in EXPECTED_CONSUMERS.items():
        gates = sorted(gates_by_to.get(status, set()))
        if gates == [expected]:
            routes[status] = expected
        else:
            ambiguous[status] = gates
    return routes, ambiguous


def parse_updated_at(value: str) -> Optional[dt.datetime]:
    if not value:
        return None
    candidates = [
        value,
        value.replace("Z", "+00:00"),
        value.replace(" ", "T"),
    ]
    for candidate in candidates:
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    return None


def is_stale(updated_at: str) -> bool:
    parsed = parse_updated_at(updated_at)
    if parsed is None:
        return False
    return now_utc() - parsed > dt.timedelta(days=STALE_AFTER_DAYS)


def latest_plan(topic_dir: Path) -> Optional[Path]:
    best: Optional[Tuple[int, Path]] = None
    for path in topic_dir.glob("plan-v*.md"):
        match = re.fullmatch(r"plan-v(\d+)\.md", path.name)
        if not match:
            continue
        number = int(match.group(1))
        if best is None or number > best[0]:
            best = (number, path)
    return best[1] if best else None


def plan_pointer_mismatch(topic_dir: Path) -> bool:
    pointer = topic_dir / "plan.md"
    latest = latest_plan(topic_dir)
    if not pointer.exists() or latest is None:
        return False
    return read_text(pointer) != read_text(latest)


def alloc_lock_report(plans_dir: Path) -> Optional[dict]:
    lock_dir = plans_dir / ".alloc.lock"
    if not lock_dir.exists():
        return None
    info = lock_dir / "info"
    payload = {"path": str(lock_dir), "pid": "unknown", "age_seconds": None, "hostname": socket.gethostname()}
    try:
        stat = lock_dir.stat()
        payload["age_seconds"] = int(max(0, now_utc().timestamp() - stat.st_mtime))
    except OSError:
        pass
    if info.exists():
        text = read_text(info).strip()
        parts = text.split()
        if parts:
            payload["pid"] = parts[0]
        if len(parts) > 1:
            parsed = parse_updated_at(parts[1])
            if parsed:
                payload["age_seconds"] = int(max(0, (now_utc() - parsed).total_seconds()))
    return payload


def scan_project(project: dict, routes: Dict[str, str], ambiguous: Dict[str, List[str]]) -> dict:
    root = Path(str(project.get("project_root", ""))).expanduser()
    project_result = {
        "project_root": str(root),
        "repo_id": project.get("repo_id", ""),
        "host_id": project.get("host_id", socket.gethostname()),
        "actionable": [],
        "needs-human": [],
        "stale": [],
        "hidden_count": 0,
        "checks": [],
    }
    if not root.exists():
        project_result["needs-human"].append(
            {"topic_id": "(project)", "reason": "project_root-missing", "detail": str(root)}
        )
        return project_result
    plans_dir = root / ".claude" / "dev-loop"
    lock = alloc_lock_report(plans_dir)
    if lock:
        project_result["checks"].append({"kind": "stale-alloc-lock", **lock})
    if not plans_dir.exists():
        project_result["checks"].append({"kind": "no-dev-loop-dir", "path": str(plans_dir)})
        return project_result
    for req in sorted(plans_dir.glob("*/req.md")):
        topic_dir = req.parent
        meta = parse_frontmatter(req)
        topic_id = meta.get("topic_id") or topic_dir.name
        status = meta.get("status", "")
        item = {
            "topic_id": topic_id,
            "status": status,
            "path": str(topic_dir),
            "hostname": socket.gethostname(),
            "updated_at": meta.get("updated_at", ""),
        }
        if meta.get("project_root") and Path(meta["project_root"]).expanduser() != root:
            item["reason"] = "topic-project_root-mismatch"
            item["detail"] = meta["project_root"]
            project_result["needs-human"].append(item)
            continue
        if status in DEPRECATED_STATUSES:
            item["reason"] = "deprecated-status"
            project_result["needs-human"].append(item)
            continue
        if plan_pointer_mismatch(topic_dir):
            item["reason"] = "plan-pointer-mismatch"
            project_result["needs-human"].append(item)
            continue
        if status in HIDDEN_STATUSES:
            project_result["hidden_count"] += 1
            continue
        if status in NEEDS_HUMAN_STATUSES:
            item["reason"] = status
            project_result["needs-human"].append(item)
            continue
        if status in ambiguous:
            item["reason"] = "route-ambiguous"
            item["detail"] = ",".join(ambiguous[status]) or "(no gate)"
            project_result["needs-human"].append(item)
            continue
        if is_stale(meta.get("updated_at", "")):
            item["reason"] = "updated_at-stale"
            project_result["stale"].append(item)
            continue
        if status in ACTIONABLE_STATUSES:
            gate = routes.get(status)
            if gate:
                item["next_command"] = f"/{gate} {root} {topic_id}"
                project_result["actionable"].append(item)
            else:
                item["reason"] = "missing-route"
                project_result["needs-human"].append(item)
            continue
        item["reason"] = "unknown-status"
        project_result["needs-human"].append(item)
    return project_result


def render_digest(results: Sequence[dict], health: dict) -> str:
    lines = [
        "# loop-scout inbox",
        "",
        f"- generated_at: {health['generated_at']}",
        f"- scanner_host: {socket.gethostname()}",
        f"- health: {health['status']}",
        "",
        "## Actionable",
        "",
    ]
    global_count = 0
    overflow = 0
    for project in results:
        shown_for_project = 0
        project_lines = []
        for item in project["actionable"]:
            if shown_for_project >= MAX_ACTIONABLE_PER_PROJECT or global_count >= MAX_ACTIONABLE_GLOBAL:
                overflow += 1
                continue
            shown_for_project += 1
            global_count += 1
            project_lines.append(
                f"- `{project['repo_id']}` `{item['topic_id']}` status `{item['status']}` -> "
                f"`{item['next_command']}`"
            )
        if project_lines:
            lines.append(f"### {project['repo_id']} ({project['project_root']})")
            lines.extend(project_lines)
            lines.append("")
    if global_count == 0:
        lines.append("- none")
        lines.append("")
    if overflow:
        lines.append(f"<details><summary>{overflow} actionable items folded by limit</summary>")
        lines.append("")
        for project in results:
            for item in project["actionable"]:
                lines.append(
                    f"- `{project['repo_id']}` `{item['topic_id']}` status `{item['status']}` "
                    f"-> `{item.get('next_command', '')}`"
                )
        lines.append("")
        lines.append("</details>")
        lines.append("")
    lines.extend(["## Needs human", ""])
    needs = [(project, item) for project in results for item in project["needs-human"]]
    if needs:
        lines.append(f"<details open><summary>{len(needs)} items</summary>")
        lines.append("")
        for project, item in needs:
            detail = f" ({item.get('detail')})" if item.get("detail") else ""
            lines.append(
                f"- `{project['repo_id']}` `{item['topic_id']}` status `{item.get('status', '')}`: "
                f"{item.get('reason', 'needs-human')}{detail}"
            )
        lines.append("")
        lines.append("</details>")
        lines.append("")
    else:
        lines.append("- none")
        lines.append("")
    lines.extend(["## Stale", ""])
    stale_items = [(project, item) for project in results for item in project["stale"]]
    if stale_items:
        for project, item in stale_items:
            lines.append(
                f"- `{project['repo_id']}` `{item['topic_id']}` updated_at `{item.get('updated_at', '')}`"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.extend(["## Checks", ""])
    any_checks = False
    for project in results:
        for check in project["checks"]:
            any_checks = True
            lines.append(f"- `{project['repo_id']}` {check}")
    if not any_checks:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_health(status: str, reason: str = "", errors: Optional[List[str]] = None) -> dict:
    return {
        "status": status,
        "reason": reason,
        "errors": errors or [],
        "generated_at": iso_now(),
        "hostname": socket.gethostname(),
    }


def acquire_scan_lock(cache_dir: Path) -> Optional[Path]:
    lock_dir = cache_dir / ".scan.lock"
    try:
        os.mkdir(lock_dir)
        return lock_dir
    except FileExistsError:
        return None


def release_scan_lock(lock_dir: Optional[Path]) -> None:
    if lock_dir is None:
        return
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass


def scan(projects_path: Path) -> Tuple[str, dict]:
    cache_dir_raw, projects = parse_registry(projects_path)
    cache_dir = validate_cache_dir(cache_dir_raw, projects)
    writer = CacheWriter(cache_dir)
    lock_dir = acquire_scan_lock(cache_dir)
    if lock_dir is None:
        health = build_health("degraded", "scan-lock-busy")
        writer.write_json(cache_dir / "loop-scout-health.json", health)
        return "", health
    try:
        enum, transitions = parse_ssot(DEFAULT_SSOT)
        routes, ambiguous = derive_routes(transitions)
        errors = []
        if ambiguous:
            for status, gates in sorted(ambiguous.items()):
                errors.append(f"route ambiguous for {status}: {gates or ['(none)']}")
        results = [scan_project(project, routes, ambiguous) for project in projects]
        health = build_health("degraded" if errors else "ok", "; ".join(errors), errors)
        health["topic_status_count"] = len(enum)
        health["transition_count"] = len(transitions)
        digest = render_digest(results, health)
        if errors:
            digest = (
                "# loop-scout inbox\n\n"
                f"- generated_at: {health['generated_at']}\n"
                "- health: degraded\n"
                f"- reason: {health['reason']}\n\n"
                "No next-command suggestions were emitted because route preflight failed.\n"
            )
        writer.write_text(cache_dir / "loop-inbox.md", digest)
        writer.write_json(cache_dir / "loop-scout-health.json", health)
        return digest, health
    except Exception as exc:
        health = build_health("degraded", str(exc), [str(exc)])
        writer.write_json(cache_dir / "loop-scout-health.json", health)
        return "", health
    finally:
        release_scan_lock(lock_dir)


def cached(projects_path: Path) -> str:
    cache_dir_raw, projects = parse_registry(projects_path)
    cache_dir = validate_cache_dir(cache_dir_raw, projects)
    inbox = cache_dir / "loop-inbox.md"
    health_path = cache_dir / "loop-scout-health.json"
    if not inbox.exists():
        raise ScoutError(f"cache not found: {inbox}")
    generated_at = "(unknown)"
    warning = ""
    if health_path.exists():
        try:
            health = json.loads(read_text(health_path))
            generated_at = health.get("generated_at", generated_at)
            parsed = parse_updated_at(generated_at)
            if parsed and (now_utc() - parsed).total_seconds() > CACHE_STALE_AFTER_SECONDS:
                warning = "\n> stale warning: cache is older than 1 hour.\n"
        except json.JSONDecodeError:
            warning = "\n> stale warning: health json is unreadable.\n"
    return f"> cached digest generated_at: {generated_at}\n{warning}\n" + read_text(inbox)


def static_denylist_scan(source: Path) -> List[str]:
    text = read_text(source)
    denied = [
        "Path." + "write_text",
        "Path." + "write_bytes",
        "os." + "remove",
        "os." + "unlink",
        "shutil." + "rmtree",
        "subprocess." + "run(",
    ]
    findings = []
    for needle in denied:
        if needle in text and needle != "subprocess.run(":
            findings.append(needle)
    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only dev-loop automation scout.")
    parser.add_argument("--projects", default=str(DEFAULT_PROJECTS), help="Path to loop-projects.yaml")
    parser.add_argument("--refresh", action="store_true", help="Run a fresh scan (default).")
    parser.add_argument("--cached", action="store_true", help="Print cached digest with stale warning.")
    args = parser.parse_args(argv)
    projects_path = Path(args.projects).expanduser()
    try:
        if args.cached:
            print(cached(projects_path), end="")
        else:
            digest, health = scan(projects_path)
            if digest:
                print(digest)
            else:
                print(json.dumps(health, indent=2, sort_keys=True))
        return 0
    except ScoutError as exc:
        print(f"loop-scout error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

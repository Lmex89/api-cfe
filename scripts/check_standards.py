"""Check current diagnostics against the frozen legacy standards baseline."""

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "standards-baseline.json"


def run(
    *args: str, input_text: str | None = None, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    """Run a checker and fail closed on tool errors."""
    env = os.environ.copy()
    for name in ("MYPYPATH", "PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    result = subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode > 1:
        sys.stderr.write(result.stderr or result.stdout)
        raise SystemExit(result.returncode)
    return result


def source_line(path: str, number: int, root: Path = ROOT) -> str:
    """Get the source line identifying a diagnostic independently of line shifts."""
    lines = (root / path).read_text().splitlines()
    return lines[number - 1] if 0 < number <= len(lines) else ""


def lint(files: list[str]) -> Counter[str]:
    """Collect Ruff diagnostics with the offending source line."""
    if not files:
        return Counter()
    result = run("ruff", "check", "--output-format=json", *files)
    diagnostics = json.loads(result.stdout)
    return Counter(
        json.dumps(
            [
                str(Path(d["filename"]).relative_to(ROOT)),
                d["code"],
                d["message"],
                ""
                if d["code"] == "D100"
                else source_line(
                    str(Path(d["filename"]).relative_to(ROOT)), d["location"]["row"]
                ),
            ]
        )
        for d in diagnostics
    )


def types(files: list[str]) -> Counter[str]:
    """Check tracked Python files and explicitly selected files in isolation."""
    tracked = run("git", "ls-files", "-z", "--cached").stdout.split("\0")
    paths = sorted({p for p in [*tracked, *files] if p.endswith((".py", ".pyi"))})
    with tempfile.TemporaryDirectory(prefix="api-cfe-mypy-") as directory:
        root = Path(directory)
        for path in [*paths, "pyproject.toml"]:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        targets = ["app", *(p for p in paths if not p.startswith("app/"))]
        result = run(
            "mypy",
            "--explicit-package-bases",
            "--platform",
            "linux",
            "--no-incremental",
            "--no-error-summary",
            "--show-error-codes",
            *targets,
            cwd=root,
        )
        found: Counter[str] = Counter()
        for line in result.stdout.splitlines():
            match = re.match(r"^(.*?):(\d+): (error|note): (.*)$", line)
            if not match:
                raise SystemExit(f"Unexpected mypy output: {line}")
            path, number, level, message = match.groups()
            found[
                json.dumps([path, level, message, source_line(path, int(number), root)])
            ] += 1
        return found


def formatting(files: list[str]) -> Counter[str]:
    """Collect formatting edits, preserving their original and formatted text."""
    found: Counter[str] = Counter()
    for path in files:
        original = (ROOT / path).read_text()
        formatted = run(
            "ruff",
            "format",
            "--quiet",
            "--stdin-filename",
            path,
            "-",
            input_text=original,
        ).stdout
        before, after = (
            original.splitlines(keepends=True),
            formatted.splitlines(keepends=True),
        )
        for tag, a, b, c, d in difflib.SequenceMatcher(
            None, before, after, autojunk=False
        ).get_opcodes():
            if tag != "equal":
                found[json.dumps([path, before[a:b], after[c:d]])] += 1
    return found


def main() -> None:
    """Run one check, or generate the baseline explicitly during adoption."""
    mode, *files = sys.argv[1:]
    if mode == "snapshot":
        files = run("git", "ls-files", "*.py").stdout.splitlines()
        data = {
            name: dict(check(files))
            for name, check in (
                ("lint", lint),
                ("format", formatting),
                ("types", types),
            )
        }
        BASELINE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return
    baseline = json.loads(BASELINE.read_text())[mode]
    if mode == "lint":
        normalized: Counter[str] = Counter()
        for key, count in baseline.items():
            parts = json.loads(key)
            if parts[1] == "D100":
                parts[3] = ""
            normalized[json.dumps(parts)] += count
        baseline = normalized
    current = (
        types(files)
        if mode == "types"
        else {"lint": lint, "format": formatting}[mode](files)
    )
    extra = current - Counter(baseline)
    for key, count in extra.items():
        print(f"{mode}: {json.loads(key)} (new: {count})")
    if extra:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

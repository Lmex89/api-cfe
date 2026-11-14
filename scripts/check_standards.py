"""Check current diagnostics against the frozen legacy standards baseline."""

import difflib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "standards-baseline.json"


def run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a checker and fail closed on tool errors."""
    result = subprocess.run(
        args, cwd=ROOT, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode > 1:
        sys.stderr.write(result.stderr or result.stdout)
        raise SystemExit(result.returncode)
    return result


def source_line(path: str, number: int) -> str:
    """Get the source line identifying a diagnostic independently of line shifts."""
    lines = (ROOT / path).read_text().splitlines()
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
                source_line(
                    str(Path(d["filename"]).relative_to(ROOT)), d["location"]["row"]
                ),
            ]
        )
        for d in diagnostics
    )


def types() -> Counter[str]:
    """Collect mypy diagnostics for the whole application."""
    result = run(
        "mypy", "--no-incremental", "--no-error-summary", "--show-error-codes", "app"
    )
    found = Counter()
    for line in result.stdout.splitlines():
        match = re.match(r"^(.*?):(\d+): (error|note): (.*)$", line)
        if not match:
            raise SystemExit(f"Unexpected mypy output: {line}")
        path, number, level, message = match.groups()
        found[json.dumps([path, level, message, source_line(path, int(number))])] += 1
    return found


def formatting(files: list[str]) -> Counter[str]:
    """Collect formatting edits, preserving their original and formatted text."""
    found = Counter()
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
            name: dict(check(files) if name != "types" else types())
            for name, check in (
                ("lint", lint),
                ("format", formatting),
                ("types", types),
            )
        }
        BASELINE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return
    baseline = json.loads(BASELINE.read_text())[mode]
    current = (
        types()
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

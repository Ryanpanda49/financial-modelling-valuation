"""Fail when a public repository candidate contains private or internal artifacts."""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATHS = {
    "config/model_config.yaml",
    "Financial Modelling and Valuation.pdf",
    "通裕重工-中信证券A股标准估值模型20231023.xlsx",
}
PERSONAL_EMAIL = re.compile(
    rb"[A-Z0-9._%+-]+@(?:gmail|outlook|hotmail|icloud|qq|163)\.[A-Z]{2,}",
    re.IGNORECASE,
)


def _public_candidates() -> set[str]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return {
        value.decode("utf-8")
        for value in (tracked + untracked).split(b"\0")
        if value
    }


def main() -> int:
    candidates = _public_candidates()
    problems: list[str] = []
    for forbidden in sorted(PRIVATE_PATHS & candidates):
        problems.append(f"private/internal path is publishable: {forbidden}")
    for path in sorted(candidates):
        if path.startswith("data/cache/") or path.startswith("reference_materials/"):
            problems.append(f"runtime/internal directory is publishable: {path}")
        if path.startswith("outputs/") and path != "outputs/.gitkeep":
            problems.append(f"generated output is publishable: {path}")
        full_path = ROOT / path
        if not full_path.is_file():
            continue
        if full_path.stat().st_size > 2_000_000:
            problems.append(f"unexpected public candidate larger than 2 MB: {path}")
            continue
        content = full_path.read_bytes()
        if PERSONAL_EMAIL.search(content):
            problems.append(f"personal email address found in public candidate: {path}")
        if full_path.suffix.lower() in {".xlsx", ".xlsm"}:
            try:
                with zipfile.ZipFile(full_path) as workbook:
                    for member in workbook.infolist():
                        if member.file_size > 2_000_000:
                            problems.append(
                                f"oversized workbook member in {path}: {member.filename}"
                            )
                            continue
                        member_content = workbook.read(member)
                        if PERSONAL_EMAIL.search(member_content):
                            problems.append(
                                f"personal email address found inside workbook: {path}"
                            )
                            break
            except (OSError, zipfile.BadZipFile) as exc:
                problems.append(f"public workbook is invalid: {path}: {exc}")

    fixture_paths = (
        ROOT / "data/sample/wmt_fy2022_2026_history.json",
        ROOT / "data/sample/aapl_fy2021_2025_history.json",
        ROOT / "data/sample/cost_fy2021_2025_history.json",
        ROOT / "data/sample/ko_fy2021_2025_history.json",
        ROOT / "data/sample/msft_fy2021_2025_history.json",
    )
    for fixture_path in fixture_paths:
        try:
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            serialized = json.dumps(fixture).lower()
            for forbidden_key in ("user_agent", "request_headers", "cache_directory"):
                if forbidden_key in serialized:
                    problems.append(
                        f"public fixture {fixture_path.name} contains forbidden key: {forbidden_key}"
                    )
            if fixture.get("schema_version") != 1:
                problems.append(f"public fixture {fixture_path.name} schema_version is not 1")
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"public fixture {fixture_path.name} is missing or invalid: {exc}")

    if problems:
        for problem in problems:
            print(f"ERROR: {problem}")
        return 1
    print(f"Public release check passed for {len(candidates)} candidate files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

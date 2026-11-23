#!/usr/bin/env python3
"""Deterministic helper for the Recovery Reliability Benchmark 5-step release workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CONCEPT_RECID = "24020731"
CONCEPT_DOI = f"10.5281/zenodo.{CONCEPT_RECID}"
INITIAL_VERSION_RECID = "24020732"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
DOI_RE = re.compile(r"^10\.5281/zenodo\.(\d+)$")


def find_repo_root(start: Path | None = None) -> Path:
    """Locate the repository root containing pyproject.toml and CITATION.cff.

    Args:
        start: Optional starting path; defaults to this script's directory.

    Returns:
        Resolved repository root path.

    Raises:
        RuntimeError: If the repository root cannot be found.
    """
    cur = (start or Path(__file__)).resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in (cur, *cur.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "CITATION.cff").is_file():
            return candidate
    raise RuntimeError(f"Could not locate repository root from {cur}")


def venv_tool(root: Path, tool: str) -> str:
    """Resolve a tool inside .venv/bin if present, falling back to PATH.

    Args:
        root: Repository root directory.
        tool: Executable name (e.g. 'python', 'pytest', 'ruff').

    Returns:
        Path to executable or bare command name.
    """
    candidate = root / ".venv" / "bin" / tool
    return str(candidate) if candidate.is_file() else tool


def run_cmd(
    cmd: list[str],
    cwd: Path,
    capture: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command in cwd.

    Args:
        cmd: Command and arguments.
        cwd: Working directory.
        capture: Whether to capture stdout/stderr.
        check: Whether to raise on non-zero exit code.

    Returns:
        CompletedProcess result.
    """
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=capture, check=check)


def parse_cff_version_dois(cff_text: str) -> list[tuple[str, str]]:
    """Extract ordered (version, doi) pairs from CITATION.cff identifiers.

    Args:
        cff_text: Full text of CITATION.cff.

    Returns:
        Ordered list of (version_without_v, doi) tuples.
    """
    pattern = re.compile(
        r"-\s*type:\s*doi\s*\n"
        r"\s*value:\s*(10\.5281/zenodo\.\d+)\s*\n"
        r"\s*description:\s*Version DOI for v(\d+\.\d+\.\d+)\.",
    )
    return [(ver, doi) for doi, ver in pattern.findall(cff_text)]


def read_spec_version(root: Path) -> str:
    """Read SPEC_VERSION from contract.py.

    Args:
        root: Repository root directory.

    Returns:
        Specification version string (e.g. '1.1').

    Raises:
        RuntimeError: If SPEC_VERSION cannot be parsed.
    """
    contract_text = (root / "src" / "recovery_reliability_benchmark" / "contract.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^SPEC_VERSION\s*=\s*"([^"]+)"', contract_text, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError("Could not parse SPEC_VERSION from contract.py")
    return match.group(1)


def extract_changelog_section(changelog_text: str, version: str) -> tuple[str, str]:
    """Extract release date and body for ## [version] from CHANGELOG.md.

    Args:
        changelog_text: Full text of CHANGELOG.md.
        version: Target version string without leading 'v'.

    Returns:
        Tuple of (date_str, body_markdown).

    Raises:
        RuntimeError: If the version section is missing or empty.
    """
    header_re = re.compile(
        rf"^## \[{re.escape(version)}\]\s*-\s*(\d{{4}}-\d{{2}}-\d{{2}})\s*$",
        flags=re.MULTILINE,
    )
    match = header_re.search(changelog_text)
    if match is None:
        raise RuntimeError(f"CHANGELOG.md has no '## [{version}] - YYYY-MM-DD' heading.")
    date_str = match.group(1)
    rest = changelog_text[match.end() :]
    next_h2 = re.search(r"^## ", rest, flags=re.MULTILINE)
    body = (rest[: next_h2.start()] if next_h2 else rest).strip()
    if not body:
        raise RuntimeError(f"CHANGELOG.md section for [{version}] is empty.")
    return date_str, body


def render_readme_citing(
    version: str,
    year: str,
    version_dois: list[tuple[str, str]],
    cite_doi: str,
) -> str:
    """Render the ## Citing section body for README.md.

    Args:
        version: Current project version without 'v'.
        year: 4-digit release year.
        version_dois: Recorded (version, doi) pairs from CITATION.cff.
        cite_doi: DOI URL target for the citation blockquote.

    Returns:
        Rendered ## Citing markdown section.

    Raises:
        RuntimeError: If version_dois is empty.
    """
    if not version_dois:
        raise RuntimeError("Expected at least one prior Version DOI in CITATION.cff.")
    latest_ver, latest_doi = version_dois[-1]
    older = list(reversed(version_dois[:-1]))
    older_clause = (
        " (" + ", ".join(f"v{v}: [{d}](https://doi.org/{d})" for v, d in older) + ")" if older else ""
    )
    prose = (
        f"Every release is archived on Zenodo. Cite the version you used. "
        f"The version DOI for v{latest_ver} is [{latest_doi}](https://doi.org/{latest_doi})"
        f"{older_clause}; [{CONCEPT_DOI}](https://doi.org/{CONCEPT_DOI}) always resolves to the "
        f"latest release. Citation metadata is in [CITATION.cff](CITATION.cff); GitHub's \"Cite "
        f'this repository" button renders it.'
    )
    cite = (
        f"> McCall, R. J. ({year}). Recovery Reliability Benchmark (v{version}). "
        f"Continuity Labs. https://doi.org/{cite_doi}"
    )
    return f"## Citing\n\n{prose}\n\n{cite}"


def replace_readme_citing(readme_text: str, new_citing_block: str) -> str:
    """Replace the ## Citing section in README.md up to the next H2 heading.

    Args:
        readme_text: Full README.md content.
        new_citing_block: Replacement ## Citing block.

    Returns:
        Updated README.md content.

    Raises:
        RuntimeError: If ## Citing cannot be located.
    """
    pattern = re.compile(r"^## Citing\n.*?(?=\n## )", flags=re.MULTILINE | re.DOTALL)
    if not pattern.search(readme_text):
        raise RuntimeError("Could not find '## Citing' section in README.md.")
    return pattern.sub(new_citing_block + "\n", readme_text, count=1)


def render_test_zenodo_doi_recorded(
    version: str,
    version_dois: list[tuple[str, str]],
    cite_doi: str,
) -> str:
    """Render test_zenodo_doi_recorded() for tests/test_docs.py.

    Args:
        version: Current project version without 'v'.
        version_dois: Recorded (version, doi) pairs from CITATION.cff.
        cite_doi: Expected DOI in README's blockquote citation line.

    Returns:
        Formatted Python function source.
    """
    lines = [
        "def test_zenodo_doi_recorded() -> None:",
        '    cff_text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")',
        '    doi_lines = [line for line in cff_text.splitlines() if line.startswith("doi:")]',
        f'    assert doi_lines == ["doi: {CONCEPT_DOI}"]',
    ]
    for ver, doi in version_dois:
        lines.append(f'    assert "value: {doi}" in cff_text')
        lines.append(f'    assert "Version DOI for v{ver}" in cff_text')
    lines.extend(
        [
            "",
            '    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")',
            '    assert "zenodo.org/badge/1444426702.svg" in readme_text',
            f'    assert "{CONCEPT_DOI}" in readme_text',
        ]
    )
    for _, doi in version_dois:
        lines.append(f'    assert "{doi}" in readme_text')
    excluded = [d for d in (CONCEPT_DOI, *(doi for _, doi in version_dois)) if d != cite_doi]
    lines.extend(
        [
            "",
            '    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]',
            f'    assert version == "{version}"',
            '    cite_lines = [line for line in readme_text.splitlines() if line.startswith("> McCall")]',
            "    assert len(cite_lines) == 1",
            '    assert f"(v{version})" in cite_lines[0]',
            f'    assert "https://doi.org/{cite_doi}" in cite_lines[0]',
        ]
    )
    for doi in excluded:
        lines.append(f'    assert "{doi}" not in cite_lines[0]')
    lines.extend(
        [
            "",
            '    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")',
            '    assert "## Releasing" in agents_text',
        ]
    )
    return "\n".join(lines)


def replace_test_zenodo_doi_recorded(test_docs_text: str, new_fn_src: str) -> str:
    """Replace test_zenodo_doi_recorded() inside tests/test_docs.py.

    Args:
        test_docs_text: Full text of tests/test_docs.py.
        new_fn_src: Replacement function definition string.

    Returns:
        Updated tests/test_docs.py content.

    Raises:
        RuntimeError: If test_zenodo_doi_recorded() cannot be located.
    """
    pattern = re.compile(
        r"^def test_zenodo_doi_recorded\(\) -> None:\n.*?(?=\n\n\ndef |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    if not pattern.search(test_docs_text):
        raise RuntimeError("Could not find test_zenodo_doi_recorded() in tests/test_docs.py.")
    return pattern.sub(new_fn_src, test_docs_text, count=1)


def reinstall_editable(root: Path, expected_version: str) -> None:
    """Reinstall the project in editable mode without dependencies and verify its version.

    Args:
        root: Repository root directory.
        expected_version: Target semantic version string without leading 'v'.

    Raises:
        RuntimeError: If the installed package version after reinstall does not match
            expected_version.
    """
    python = venv_tool(root, "python")
    python_path = shutil.which(python) or python
    if (root / "uv.lock").is_file():
        cmd = ["uv", "pip", "install", "--python", python_path, "--no-deps", "--editable", "."]
    else:
        cmd = [python, "-m", "pip", "install", "--no-deps", "--editable", "."]
    run_cmd(cmd, cwd=root, capture=False)

    probe = (
        "from importlib.metadata import PackageNotFoundError, version\n"
        "try:\n"
        "    print(version('recovery-reliability-benchmark'))\n"
        "except PackageNotFoundError:\n"
        "    print('not-installed')\n"
    )
    installed_version = run_cmd([python, "-c", probe], cwd=root).stdout.strip()
    if installed_version != expected_version:
        raise RuntimeError(
            f"Installed package version after editable reinstall is {installed_version!r}, "
            f"expected {expected_version!r}."
        )


def run_local_verification(root: Path) -> None:
    """Run ruff check, ruff format --check, frozen_manifest --check, and pytest.

    Args:
        root: Repository root directory.
    """
    ruff = venv_tool(root, "ruff")
    python = venv_tool(root, "python")
    pytest_bin = venv_tool(root, "pytest")
    targets = ["."]
    if (root / ".agents").is_dir():
        targets.append(".agents")
    run_cmd([ruff, "check", *targets], cwd=root, capture=False)
    run_cmd([ruff, "format", "--check", *targets], cwd=root, capture=False)
    run_cmd(
        [python, "-m", "recovery_reliability_benchmark.frozen_manifest", "--check"],
        cwd=root,
        capture=False,
    )
    run_cmd([pytest_bin, "-q"], cwd=root, capture=False)


def cmd_prepare(args: argparse.Namespace) -> int:
    """Execute Step 1 pre-tag version bump and readiness updates if not already at version.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit status code.
    """
    root = find_repo_root(args.root)
    version = args.version.lstrip("v")
    if not VERSION_RE.match(version):
        raise RuntimeError(f"Invalid semantic version: {args.version!r}")
    date_str = args.date or dt.date.today().isoformat()
    year = date_str[:4]

    pyproject_path = root / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    cur_ver = str(tomllib.loads(pyproject_text)["project"]["version"])
    if cur_ver == version:
        print(f"Repository is already at version {version}; running pre-tag verification.")
        return cmd_verify_pretag(args)

    pyproject_updated = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        rf'\1"{version}"',
        pyproject_text,
        count=1,
        flags=re.MULTILINE,
    )
    pyproject_path.write_text(pyproject_updated, encoding="utf-8")

    cff_path = root / "CITATION.cff"
    cff_text = cff_path.read_text(encoding="utf-8")
    cff_text = re.sub(r"^version:\s*.*$", f"version: {version}", cff_text, count=1, flags=re.MULTILINE)
    cff_text = re.sub(
        r"^date-released:\s*.*$",
        f"date-released: {date_str}",
        cff_text,
        count=1,
        flags=re.MULTILINE,
    )
    if f"doi: {CONCEPT_DOI}" not in cff_text.splitlines():
        raise RuntimeError(f"Top-level doi in CITATION.cff must remain pinned to {CONCEPT_DOI}.")
    cff_path.write_text(cff_text, encoding="utf-8")

    changelog_path = root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog_text:
        unrel_re = re.compile(r"^## Unreleased\s*\n(.*?)(?=^## \[)", flags=re.MULTILINE | re.DOTALL)
        match = unrel_re.search(changelog_text)
        if match is None:
            raise RuntimeError("Could not parse '## Unreleased' block in CHANGELOG.md.")
        unreleased_body = match.group(1).strip()
        if not unreleased_body and not args.scope:
            raise RuntimeError("CHANGELOG.md '## Unreleased' is empty and no --scope was given.")
        parts = [p for p in (args.scope.strip() if args.scope else "", unreleased_body) if p]
        replacement = f"## Unreleased\n\n## [{version}] - {date_str}\n\n" + "\n\n".join(parts) + "\n\n"
        changelog_text = unrel_re.sub(replacement, changelog_text, count=1)
        changelog_path.write_text(changelog_text, encoding="utf-8")

    python = venv_tool(root, "python")
    run_cmd(
        [python, "-m", "recovery_reliability_benchmark.frozen_manifest", "--update"],
        cwd=root,
        capture=False,
    )
    if (root / "uv.lock").is_file():
        run_cmd(["uv", "lock"], cwd=root, capture=False, check=False)

    version_dois = parse_cff_version_dois(cff_text)
    readme_path = root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    new_citing = render_readme_citing(version, year, version_dois, cite_doi=CONCEPT_DOI)
    readme_path.write_text(replace_readme_citing(readme_text, new_citing), encoding="utf-8")

    test_docs_path = root / "tests" / "test_docs.py"
    test_docs_text = test_docs_path.read_text(encoding="utf-8")
    new_test = render_test_zenodo_doi_recorded(version, version_dois, cite_doi=CONCEPT_DOI)
    test_docs_path.write_text(replace_test_zenodo_doi_recorded(test_docs_text, new_test), encoding="utf-8")

    reinstall_editable(root, version)
    run_local_verification(root)
    print(f"Prepared v{version} ({date_str}); ready to commit and push to main.")
    return 0


def cmd_verify_pretag(args: argparse.Namespace) -> int:
    """Verify Step 1 pre-tag readiness invariants and run local verification.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit status code.
    """
    root = find_repo_root(args.root)
    version = args.version.lstrip("v")
    tag = f"v{version}"

    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).stdout.strip()
    if branch != "main":
        raise RuntimeError(f"Expected branch 'main', found {branch!r}.")

    existing_tag = run_cmd(["git", "tag", "--list", tag], cwd=root).stdout.strip()
    if existing_tag:
        raise RuntimeError(f"Git tag {tag} already exists locally.")

    status_lines = [
        ln
        for ln in run_cmd(["git", "status", "--porcelain"], cwd=root).stdout.splitlines()
        if not (getattr(args, "allow_untracked_agents", False) and ln.startswith("?? .agents/"))
    ]
    if status_lines:
        raise RuntimeError("Working tree is not clean:\n" + "\n".join(status_lines))

    pyproject_ver = str(
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    )
    manifest_ver = str(json.loads((root / "frozen" / "manifest.json").read_text(encoding="utf-8"))["version"])
    cff_text = (root / "CITATION.cff").read_text(encoding="utf-8")
    cff_ver_match = re.search(r"^version:\s*(\S+)\s*$", cff_text, flags=re.MULTILINE)
    cff_date_match = re.search(r"^date-released:\s*(\d{4}-\d{2}-\d{2})\s*$", cff_text, flags=re.MULTILINE)
    if not cff_ver_match or not cff_date_match:
        raise RuntimeError("CITATION.cff is missing version or date-released.")
    cff_ver, cff_date = cff_ver_match.group(1), cff_date_match.group(1)

    if not (pyproject_ver == manifest_ver == cff_ver == version):
        raise RuntimeError(
            f"Version mismatch: target={version}, pyproject={pyproject_ver}, "
            f"CITATION.cff={cff_ver}, frozen/manifest.json={manifest_ver}"
        )
    if f"doi: {CONCEPT_DOI}" not in cff_text.splitlines():
        raise RuntimeError(f"CITATION.cff top-level doi must equal {CONCEPT_DOI}.")

    cl_date, _ = extract_changelog_section((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    if cl_date != cff_date:
        raise RuntimeError(f"Release date mismatch: CHANGELOG.md={cl_date}, CITATION.cff={cff_date}")

    run_local_verification(root)
    head_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    print(f"Pre-tag readiness verified for {tag} at {head_sha} ({cff_date}).")
    return 0


def cmd_verify_ci(args: argparse.Namespace) -> int:
    """Verify Step 2 CI gate (test matrix + frozen-core) on the exact commit SHA.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit status code.
    """
    root = find_repo_root(args.root)
    run_cmd(["git", "fetch", "origin", "main"], cwd=root)
    head_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    origin_sha = run_cmd(["git", "rev-parse", "origin/main"], cwd=root).stdout.strip()
    target_sha = args.sha or head_sha
    if head_sha != origin_sha or head_sha != target_sha:
        raise RuntimeError(
            f"SHA mismatch: HEAD={head_sha}, origin/main={origin_sha}, target={target_sha}. Push main first."
        )

    runs: list[dict[str, Any]] = []
    attempts = 10 if args.wait else 1
    for attempt in range(attempts):
        runs_json = run_cmd(
            [
                "gh",
                "run",
                "list",
                "--commit",
                target_sha,
                "--workflow",
                "test.yml",
                "--json",
                "databaseId,status,conclusion,headSha",
            ],
            cwd=root,
        ).stdout
        runs = json.loads(runs_json)
        if runs:
            break
        if attempt + 1 < attempts:
            time.sleep(3)
    if not runs:
        raise RuntimeError(f"No test.yml workflow runs found on GitHub for {target_sha}.")

    run_id = str(runs[0]["databaseId"])
    if runs[0]["status"] != "completed":
        if not args.wait:
            raise RuntimeError(f"Workflow run {run_id} is still {runs[0]['status']}; pass --wait to wait.")
        run_cmd(["gh", "run", "watch", run_id, "--exit-status"], cwd=root, capture=False)

    view = json.loads(run_cmd(["gh", "run", "view", run_id, "--json", "conclusion,jobs"], cwd=root).stdout)
    if view.get("conclusion") != "success":
        raise RuntimeError(f"Workflow run {run_id} concluded with {view.get('conclusion')!r}.")

    jobs = {j["name"]: j["conclusion"] for j in view.get("jobs", [])}
    test_jobs = [name for name in jobs if name.startswith("test (")]
    if "frozen-core" not in jobs or not test_jobs:
        raise RuntimeError(f"Missing expected jobs in test.yml run {run_id}: {jobs}")
    failed = {k: v for k, v in jobs.items() if v != "success"}
    if failed:
        raise RuntimeError(f"Failed CI jobs on {target_sha}: {failed}")

    print(f"CI gate passed on {target_sha} (run {run_id}): " + ", ".join(sorted(jobs)))
    return 0


def cmd_extract_notes(args: argparse.Namespace) -> int:
    """Extract annotated tag message and GitHub Release notes from CHANGELOG.md.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit status code.
    """
    root = find_repo_root(args.root)
    version = args.version.lstrip("v")
    spec_ver = read_spec_version(root)
    date_str, body = extract_changelog_section((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    tag_message = f"Recovery Reliability Benchmark v{version} (SPEC v{spec_ver})\n\n{body}\n"
    release_notes = f"{body}\n"

    if args.tag_notes:
        Path(args.tag_notes).write_text(tag_message, encoding="utf-8")
    if args.release_notes:
        Path(args.release_notes).write_text(release_notes, encoding="utf-8")
    print(
        json.dumps(
            {
                "version": version,
                "tag": f"v{version}",
                "date": date_str,
                "spec_version": spec_ver,
                "tag_subject": f"Recovery Reliability Benchmark v{version} (SPEC v{spec_ver})",
                "body": body,
            },
            indent=2,
        )
    )
    return 0


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "recovery-reliability-benchmark-release-helper",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return data


def _verify_zenodo_record(record_id: str, expected_version: str | None = None) -> dict[str, Any]:
    rec = _fetch_json(f"https://zenodo.org/api/records/{record_id}")
    concept_doi = rec.get("conceptdoi")
    concept_recid = str(rec.get("conceptrecid", ""))
    doi = str(rec.get("doi", ""))
    if concept_doi != CONCEPT_DOI or concept_recid != CONCEPT_RECID:
        raise RuntimeError(
            f"Zenodo record {record_id} has conceptdoi={concept_doi!r} (conceptrecid={concept_recid!r}), "
            f"expected {CONCEPT_DOI!r}! Refusing to record DOI."
        )
    if not DOI_RE.match(doi) or doi == CONCEPT_DOI:
        raise RuntimeError(f"Zenodo record {record_id} returned invalid version DOI {doi!r}.")
    rec_ver = str(rec.get("metadata", {}).get("version", "")).lstrip("v")
    if expected_version is not None and rec_ver != expected_version:
        raise RuntimeError(
            f"Zenodo record {record_id} has metadata.version={rec_ver!r}, expected {expected_version!r}."
        )
    return {
        "version": rec_ver,
        "doi": doi,
        "record_id": int(rec["id"]),
        "conceptdoi": concept_doi,
    }


def cmd_poll_zenodo(args: argparse.Namespace) -> int:
    """Poll Zenodo until the newly minted Version DOI for vX.Y.Z appears and passes verification.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit status code.
    """
    root = find_repo_root(args.root)
    version = args.version.lstrip("v")
    cff_text = (root / "CITATION.cff").read_text(encoding="utf-8")
    known_dois = {CONCEPT_DOI, *(doi for _, doi in parse_cff_version_dois(cff_text))}

    deadline = time.monotonic() + args.timeout_s
    urls = (
        f"https://zenodo.org/api/records/{INITIAL_VERSION_RECID}/versions",
        f"https://zenodo.org/api/records?q=conceptrecid:{CONCEPT_RECID}&all_versions=true",
        f"https://zenodo.org/api/records/{CONCEPT_RECID}",
    )
    while True:
        candidates: list[dict[str, Any]] = []
        for url in urls:
            try:
                payload = _fetch_json(url)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                continue
            if "hits" in payload and isinstance(payload["hits"], dict):
                candidates.extend(payload["hits"].get("hits", []))
            elif "id" in payload:
                candidates.append(payload)

        for item in candidates:
            doi = str(item.get("doi", ""))
            item_ver = str(item.get("metadata", {}).get("version", "")).lstrip("v")
            if item_ver == version and doi and doi not in known_dois:
                verified = _verify_zenodo_record(str(item["id"]), expected_version=version)
                print(json.dumps(verified, indent=2))
                return 0

        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Timed out after {args.timeout_s}s waiting for Zenodo to mint v{version} under {CONCEPT_DOI}."
            )
        time.sleep(args.interval_s)


def cmd_record_doi(args: argparse.Namespace) -> int:
    """Execute Step 5 post-tag DOI updates across CITATION.cff, CHANGELOG.md, README.md, and test_docs.py.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit status code.
    """
    root = find_repo_root(args.root)
    version = args.version.lstrip("v")
    doi_match = DOI_RE.match(args.doi.strip())
    if doi_match is None or args.doi.strip() == CONCEPT_DOI:
        raise RuntimeError(
            f"Invalid Version DOI {args.doi!r} (must be 10.5281/zenodo.<id>, not Concept DOI)."
        )
    doi = args.doi.strip()
    record_id = doi_match.group(1)

    if not args.skip_zenodo_verify:
        _verify_zenodo_record(record_id, expected_version=version)

    cff_path = root / "CITATION.cff"
    cff_text = cff_path.read_text(encoding="utf-8")
    if f"value: {doi}" not in cff_text:
        entry = f"  - type: doi\n    value: {doi}\n    description: Version DOI for v{version}.\n"
        cff_text = re.sub(
            r"(^date-released:)",
            entry + r"\1",
            cff_text,
            count=1,
            flags=re.MULTILINE,
        )
        cff_path.write_text(cff_text, encoding="utf-8")

    cff_date_match = re.search(r"^date-released:\s*(\d{4})-\d{2}-\d{2}", cff_text, flags=re.MULTILINE)
    year = cff_date_match.group(1) if cff_date_match else str(dt.date.today().year)

    changelog_path = root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    bullet = f"- Zenodo v{version} DOI recorded ({doi})."
    if bullet not in changelog_text:
        changelog_text = re.sub(
            r"^## Unreleased[ \t]*\n+",
            f"## Unreleased\n\n{bullet}\n\n",
            changelog_text,
            count=1,
            flags=re.MULTILINE,
        )
        changelog_path.write_text(changelog_text, encoding="utf-8")

    version_dois = parse_cff_version_dois(cff_text)
    readme_path = root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    new_citing = render_readme_citing(version, year, version_dois, cite_doi=doi)
    readme_path.write_text(replace_readme_citing(readme_text, new_citing), encoding="utf-8")

    test_docs_path = root / "tests" / "test_docs.py"
    test_docs_text = test_docs_path.read_text(encoding="utf-8")
    new_test = render_test_zenodo_doi_recorded(version, version_dois, cite_doi=doi)
    test_docs_path.write_text(replace_test_zenodo_doi_recorded(test_docs_text, new_test), encoding="utf-8")

    run_local_verification(root)
    print(f"Recorded Zenodo DOI {doi} for v{version} and passed full local verification.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="Optional repository root override.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare", help="Step 1: bump version files and verify pre-tag readiness.")
    p_prep.add_argument("--version", required=True, help="Target version (e.g. 0.2.1 or v0.2.1).")
    p_prep.add_argument("--date", default=None, help="Release date YYYY-MM-DD (defaults to today).")
    p_prep.add_argument("--scope", default=None, help="Optional 'Scope of this release: ...' paragraph.")
    p_prep.add_argument("--allow-untracked-agents", action="store_true")
    p_prep.set_defaults(func=cmd_prepare)

    p_ver = sub.add_parser("verify-pretag", help="Verify Step 1 invariants and local test suite.")
    p_ver.add_argument("--version", required=True, help="Target version (e.g. 0.2.1 or v0.2.1).")
    p_ver.add_argument("--allow-untracked-agents", action="store_true")
    p_ver.set_defaults(func=cmd_verify_pretag)

    p_ci = sub.add_parser("verify-ci", help="Step 2: verify GitHub Actions test + frozen-core on SHA.")
    p_ci.add_argument("--sha", default=None, help="Commit SHA to verify (defaults to HEAD).")
    p_ci.add_argument("--wait", action="store_true", help="Watch and wait if workflow run is in progress.")
    p_ci.set_defaults(func=cmd_verify_ci)

    p_notes = sub.add_parser("extract-notes", help="Extract tag and GitHub Release notes from CHANGELOG.md.")
    p_notes.add_argument("--version", required=True, help="Target version (e.g. 0.2.1 or v0.2.1).")
    p_notes.add_argument("--tag-notes", default=None, help="File path to write annotated tag message.")
    p_notes.add_argument("--release-notes", default=None, help="File path to write GitHub Release notes.")
    p_notes.set_defaults(func=cmd_extract_notes)

    p_poll = sub.add_parser("poll-zenodo", help="Step 4: poll Zenodo for newly minted Version DOI.")
    p_poll.add_argument("--version", required=True, help="Target version (e.g. 0.2.1 or v0.2.1).")
    p_poll.add_argument("--timeout-s", type=int, default=300, help="Polling timeout in seconds.")
    p_poll.add_argument("--interval-s", type=int, default=10, help="Polling interval in seconds.")
    p_poll.set_defaults(func=cmd_poll_zenodo)

    p_rec = sub.add_parser("record-doi", help="Step 5: record minted Zenodo Version DOI and verify.")
    p_rec.add_argument("--version", required=True, help="Released version (e.g. 0.2.1 or v0.2.1).")
    p_rec.add_argument("--doi", required=True, help="Newly minted Zenodo Version DOI.")
    p_rec.add_argument("--skip-zenodo-verify", action="store_true", help="Skip live Zenodo API check.")
    p_rec.set_defaults(func=cmd_record_doi)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for release_helper.py.

    Args:
        argv: Optional CLI argument list.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

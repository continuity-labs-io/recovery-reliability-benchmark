Task: add a GitHub Actions workflow that runs the test suite and the quickstart command. No code changes.

1. .github/workflows/test.yml
- name: test
- on: push to main, pull_request
- Job "test" on ubuntu-latest, matrix python-version: ["3.11", "3.12", "3.13"], fail-fast: false.
- Steps:
    actions/checkout@v4
    actions/setup-python@v5 with the matrix version and pip cache enabled
    python -m pip install --upgrade pip
    pip install -e . pytest
    pytest -q
    rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0
    rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0 --json > report.json
    python -c "import json; r=json.load(open('report.json')); assert r['status']=='fully_conforming', r['status']"
- concurrency: group ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress true.
- permissions: contents: read.

2. README.md: add the workflow status badge on the line directly under the title:
    [![test](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml/badge.svg)](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml)

3. Do not change pyproject.toml or any source file.

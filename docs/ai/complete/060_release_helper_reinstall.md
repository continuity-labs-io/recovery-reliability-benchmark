Task: make the release helper reinstall the package after a version bump. Change only .agents/skills/release/scripts/release_helper.py and .agents/skills/release/SKILL.md. Do not run the prepare command.

Problem: the package reads __version__ from installed metadata. cmd_prepare bumps pyproject.toml and then runs the test suite without reinstalling. An editable install keeps reporting the old version, so tests/test_frozen.py::test_manifest_version_matches_package fails and prepare stops.

1. In cmd_prepare, after pyproject.toml is written and before run_local_verification, reinstall the project in editable mode without dependencies, into the environment the helper's tools come from. Use the installer that environment was built with: uv when the repository uses uv, otherwise that environment's python with pip. Put this in one small function with a Google-style docstring.
2. After the reinstall, read the installed version with that environment's python. Raise RuntimeError naming both versions if it is not the target version.
3. SKILL.md, Step 1: add one sentence saying prepare reinstalls the package so the installed version matches the new version.

Change no other behavior. Run ruff check . .agents, ruff format --check . .agents, and pytest. Report the result.

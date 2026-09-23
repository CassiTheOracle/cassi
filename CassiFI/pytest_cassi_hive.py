"""Pytest integration for connected Cassi Hive sessions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from cassi_hive_runtime import HiveField
from cassi_hive_store import DEFAULT_HIVE_HOME


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("cassi-hive")
    group.addoption(
        "--cassi-hive-home",
        action="store",
        default=None,
        help="shared local Cassi Hive directory",
    )
    group.addoption(
        "--cassi-hive-field-root",
        action="store",
        default=None,
        help="root directory for per-test field homes",
    )
    group.addoption(
        "--cassi-hive-id",
        action="store",
        default=None,
        help="hive identity",
    )
    group.addoption(
        "--cassi-hive-mode",
        action="store",
        default=None,
        help="isolated, scout, member, reviewer, or leader",
    )
    group.addoption(
        "--cassi-hive-import-skills",
        action="store_const",
        const=True,
        default=None,
        help="enable skill import for the hive_field fixture",
    )
    group.addoption(
        "--cassi-hive-export-skills",
        action="store_const",
        const=True,
        default=None,
        help="enable skill export for the hive_field fixture",
    )


@pytest.fixture
def hive_field(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    """Open one durable field session for the current test node."""

    config = request.config
    node_id = request.node.nodeid
    digest = hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:16]
    hive_home_value = config.getoption("--cassi-hive-home") or os.environ.get("CASSI_HIVE_HOME")
    hive_home = Path(hive_home_value).expanduser() if hive_home_value else DEFAULT_HIVE_HOME
    field_root_value = config.getoption("--cassi-hive-field-root") or os.environ.get("CASSI_HIVE_FIELD_ROOT")
    field_root = (
        Path(field_root_value).expanduser()
        if field_root_value
        else DEFAULT_HIVE_HOME.parent / "fields"
    )
    field_home = field_root / digest
    hive_id = config.getoption("--cassi-hive-id") or os.environ.get("CASSI_HIVE_ID", "main")
    mode = config.getoption("--cassi-hive-mode") or os.environ.get("CASSI_HIVE_MODE", "isolated")
    import_skills = config.getoption("--cassi-hive-import-skills")
    export_skills = config.getoption("--cassi-hive-export-skills")

    metadata = {
        "test_name": node_id,
        "arm": os.environ.get("CASSI_HIVE_ARM", "pytest"),
        "configuration": {
            "node_id": node_id,
            "mode": mode,
        },
    }
    with HiveField.open(
        field_home,
        hive_home=hive_home,
        hive_id=hive_id,
        mode=mode,
        import_skills=import_skills,
        export_skills=export_skills,
        metadata=metadata,
    ) as field:
        yield field

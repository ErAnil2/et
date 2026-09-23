from pathlib import Path

import pytest

from discover_intel.ingest.import_discover_file import (
    UnknownFormatError, detect_tool, load_mappings,
)


def test_detect_discovertrends(fixtures_dir: Path, tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    src_yaml = Path("config/discover_import_mappings.yaml").resolve()
    (cfg / "discover_import_mappings.yaml").write_text(
        src_yaml.read_text(encoding="utf-8"), encoding="utf-8",
    )

    mappings = load_mappings(cfg)
    tool = detect_tool(
        headers=["Headline", "Author", "Score", "URL"],
        mappings=mappings,
    )
    assert tool == "discovertrends"


def test_detect_unknown_raises():
    with pytest.raises(UnknownFormatError):
        detect_tool(
            headers=["Foo", "Bar", "Baz"],
            mappings={"discovertrends": {"header_signature": ["A", "B"]}},
        )

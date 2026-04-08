# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for DataMerger.

Covers:
- merge_data_files: empty input edge case
- write_merged_data_model: output filename, YAML roundtrip
"""

from pathlib import Path

from nac_yaml import yaml

from nac_test.data_merger import DataMerger


class TestMergeDataFiles:
    """Tests for DataMerger.merge_data_files()."""

    def test_merge_empty_list_returns_empty_dict(self) -> None:
        """An empty path list returns an empty dict rather than raising."""
        result = DataMerger.merge_data_files([])
        assert result == {}


class TestWriteMergedDataModel:
    """Tests for DataMerger.write_merged_data_model()."""

    def test_returns_path_to_written_file(self, tmp_path: Path) -> None:
        """write_merged_data_model returns the path of the file it created."""
        returned = DataMerger.write_merged_data_model({"key": "value"}, tmp_path)
        assert returned == DataMerger.merged_data_path(tmp_path)
        assert returned.exists()

    def test_writes_no_extra_files(self, tmp_path: Path) -> None:
        """Exactly one file is created in the output directory."""
        DataMerger.write_merged_data_model({"key": "value"}, tmp_path)
        assert len(list(tmp_path.iterdir())) == 1

    def test_roundtrip_preserves_content(self, tmp_path: Path) -> None:
        """Data written to YAML can be read back with the same structure."""
        original = {"host": "router1", "vlan": 100, "tags": ["a", "b"]}
        output_path = DataMerger.write_merged_data_model(original, tmp_path)
        reloaded = yaml.load_yaml_files([output_path])
        assert reloaded["host"] == "router1"
        assert reloaded["vlan"] == 100
        assert list(reloaded["tags"]) == ["a", "b"]

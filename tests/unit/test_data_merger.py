# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for DataMerger.

Covers:
- merge_data_files: empty input edge case, ruamel type stripping contract
- write_merged_data_model: output filename, YAML roundtrip
"""

from pathlib import Path

from nac_yaml import yaml
from ruamel.yaml import CommentedMap, CommentedSeq

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


def _assert_no_ruamel_types(value: object, path: str = "root") -> None:
    """Recursively assert no CommentedMap/CommentedSeq anywhere in the tree."""
    assert not isinstance(value, CommentedMap), f"{path} is CommentedMap"
    assert not isinstance(value, CommentedSeq), f"{path} is CommentedSeq"
    if isinstance(value, dict):
        for k, v in value.items():
            _assert_no_ruamel_types(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _assert_no_ruamel_types(v, f"{path}[{i}]")


class TestMergeDataFilesContract:
    """Contract: merge_data_files never returns CommentedMap/CommentedSeq."""

    def test_no_ruamel_types_in_output(self, tmp_path: Path) -> None:
        """Data loaded from YAML must be stripped of ruamel metadata types."""
        yaml_file = tmp_path / "data.yaml"
        yaml_file.write_text(
            "host: router1\ntag: vlan100\nitems:\n  - name: item1\n    anchor: anc1\n"
        )
        result = DataMerger.merge_data_files([yaml_file])
        _assert_no_ruamel_types(result)
        assert result["host"] == "router1"
        assert result["tag"] == "vlan100"
        assert result["items"][0]["name"] == "item1"

    def test_nested_list_of_dicts_roundtrip(self, tmp_path: Path) -> None:
        """Nested list-of-list-of-dict YAML produces plain types and supports .get()."""
        yaml_file = tmp_path / "nested.yaml"
        yaml_file.write_text(
            "---\nroot:\n  feature_profiles:\n    - - name: profile1\n"
        )
        result = DataMerger.merge_data_files([yaml_file])
        _assert_no_ruamel_types(result)

        feature_profiles = result["root"]["feature_profiles"]
        assert type(feature_profiles) is list
        assert type(feature_profiles[0]) is list
        assert type(feature_profiles[0][0]) is dict
        assert feature_profiles[0][0] == {"name": "profile1"}

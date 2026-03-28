# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for DataMerger.

Covers:
- merge_data_files: content correctness, empty input, single file
- write_merged_data_model: output filename, YAML roundtrip
"""

from pathlib import Path

from nac_yaml import yaml

from nac_test.data_merger import DataMerger

FIXTURES_DIR = Path("tests/unit/fixtures/data_merge")


class TestMergeDataFiles:
    """Tests for DataMerger.merge_data_files()."""

    def test_merge_produces_correct_scalar_values(self) -> None:
        """Scalar attributes from both files are present in the merged result."""
        result = DataMerger.merge_data_files(
            [FIXTURES_DIR / "file1.yaml", FIXTURES_DIR / "file2.yaml"]
        )
        assert result["root"]["attr1"] == "value1"
        assert result["root"]["attr2"] == "value2"

    def test_merge_concatenates_primitive_lists(self) -> None:
        """Primitive lists are concatenated (not de-duplicated) across files."""
        result = DataMerger.merge_data_files(
            [FIXTURES_DIR / "file1.yaml", FIXTURES_DIR / "file2.yaml"]
        )
        assert result["root"]["primitive_list"] == ["item1", "item1", "item1"]

    def test_merge_merges_dict_lists_by_name_key(self) -> None:
        """Dict-list entries with the same name key are merged (not duplicated)."""
        result = DataMerger.merge_data_files(
            [FIXTURES_DIR / "file1.yaml", FIXTURES_DIR / "file2.yaml"]
        )
        dict_list = result["root"]["dict_list"]
        assert len(dict_list) == 1
        assert dict_list[0]["name"] == "abc"
        assert dict_list[0]["extra"] == "def"

    def test_merge_combines_extra_fields_across_files(self) -> None:
        """Extra fields from both files are merged into the same named entry."""
        result = DataMerger.merge_data_files(
            [FIXTURES_DIR / "file1.yaml", FIXTURES_DIR / "file2.yaml"]
        )
        entry = result["root"]["dict_list_extra"][0]
        assert entry["name"] == "abc"
        assert entry["extra1"] == "def"
        assert entry["extra2"] == "ghi"

    def test_merge_preserves_nested_defaults(self) -> None:
        """Nested scalar values present only in the first file are preserved."""
        result = DataMerger.merge_data_files(
            [FIXTURES_DIR / "file1.yaml", FIXTURES_DIR / "file2.yaml"]
        )
        assert result["defaults"]["apic"]["version"] == 6.0

    def test_merge_returns_dict(self) -> None:
        """Return type is always a dict."""
        result = DataMerger.merge_data_files(
            [FIXTURES_DIR / "file1.yaml", FIXTURES_DIR / "file2.yaml"]
        )
        assert isinstance(result, dict)

    def test_merge_single_file_returns_its_content(self) -> None:
        """A single-file list returns the content of that file unchanged."""
        result = DataMerger.merge_data_files([FIXTURES_DIR / "file1.yaml"])
        assert result["root"]["attr1"] == "value1"
        assert "attr2" not in result.get("root", {})

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

    def test_roundtrip_preserves_merged_fixture_content(self, tmp_path: Path) -> None:
        """Full merge result can be written and reloaded without data loss."""
        merged = DataMerger.merge_data_files(
            [FIXTURES_DIR / "file1.yaml", FIXTURES_DIR / "file2.yaml"]
        )
        output_path = DataMerger.write_merged_data_model(merged, tmp_path)
        reloaded = yaml.load_yaml_files([output_path])
        assert reloaded["root"]["attr1"] == "value1"
        assert reloaded["root"]["attr2"] == "value2"
        assert reloaded["root"]["primitive_list"] == ["item1", "item1", "item1"]
        assert reloaded["root"]["dict_list"][0]["extra"] == "def"

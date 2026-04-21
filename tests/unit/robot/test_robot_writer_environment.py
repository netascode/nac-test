# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# mypy: disable-error-code="no-untyped-def"

"""Unit tests for KeyFirstEnvironment.

Covers:
- Contract equivalence with standard Jinja2 Environment on plain dicts
- Key precedence: ruamel attrs hidden (key wins); dict methods resolve normally
- Missing key behavior: ruamel-only attrs return Undefined
- Method preservation: .items(), .get(), .keys(), .values() still work
- Attr getter contract: selectattr/rejectattr/map(attribute=) filters
- Collision + method interaction: non-colliding methods work when collision keys exist
"""

import json

import pytest
from jinja2 import Environment, FileSystemLoader
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from nac_test.robot.robot_writer import (
    _RUAMEL_MAP_ATTRS,
    _RUAMEL_SEQ_ATTRS,
    KeyFirstEnvironment,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def keyfirst_env() -> KeyFirstEnvironment:
    """KeyFirstEnvironment instance for template rendering."""
    return KeyFirstEnvironment(loader=FileSystemLoader("/dev/null"))  # nosec B701


@pytest.fixture
def standard_env() -> Environment:
    """Standard Jinja2 Environment instance for baseline comparison."""
    return Environment(loader=FileSystemLoader("/dev/null"))  # nosec B701


@pytest.fixture
def hostname_map() -> CommentedMap:
    """CommentedMap with a single 'hostname' key."""
    return CommentedMap({"hostname": "router1"})


@pytest.fixture
def router_map() -> CommentedMap:
    """CommentedMap with 'hostname' and 'vlan_id' keys."""
    return CommentedMap({"hostname": "router1", "vlan_id": 100})


@pytest.fixture
def sample_seq() -> CommentedSeq:
    """CommentedSeq with two dict items."""
    return CommentedSeq([{"name": "item1"}, {"name": "item2"}])


@pytest.fixture
def interfaces() -> CommentedSeq:
    """CommentedSeq of interface CommentedMaps with collision key 'tag'."""
    return CommentedSeq(
        [
            CommentedMap({"name": "Eth1/1", "tag": "trunk"}),
            CommentedMap({"name": "Eth1/2", "tag": "access"}),
            CommentedMap({"name": "Eth1/3", "tag": "trunk"}),
        ]
    )


# ---------------------------------------------------------------------------
# Test Class 1: Contract Equivalence
# ---------------------------------------------------------------------------


class TestKeyFirstEnvironmentContractEquivalence:
    """KeyFirstEnvironment on ruamel types must produce the same output as
    standard Environment on JSON-roundtripped (plain dict/list) data."""

    @pytest.mark.parametrize(
        "template_str",
        [
            "{{ obj.hostname }}",
            "{{ obj.hostname | default('none') }}",
            "{{ obj['hostname'] }}",
            "{% for k, v in obj.items() %}{{ k }}={{ v }} {% endfor %}",
            "{{ obj.get('hostname', 'fallback') }}",
            "{{ obj.keys() | list | sort | join(',') }}",
            "{{ obj.values() | list | length }}",
        ],
        ids=[
            "simple_dot_access",
            "default_filter",
            "bracket_access",
            "items_iteration",
            "get_method",
            "keys_method",
            "values_method",
        ],
    )
    def test_equivalence(
        self,
        keyfirst_env: KeyFirstEnvironment,
        standard_env: Environment,
        router_map: CommentedMap,
        template_str: str,
    ) -> None:
        plain_data = json.loads(json.dumps({"hostname": "router1", "vlan_id": 100}))
        result_kf = keyfirst_env.from_string(template_str).render(obj=router_map)
        result_std = standard_env.from_string(template_str).render(obj=plain_data)
        assert result_kf == result_std


# ---------------------------------------------------------------------------
# Test Class 2: Key Precedence
# ---------------------------------------------------------------------------


class TestKeyFirstEnvironmentKeyPrecedence:
    """Dot-notation on KeyFirstEnvironment must match standard Environment behavior.

    For ruamel-only collision keys (tag, anchor, etc.): both envs resolve to the
    key value (standard env via getattr→getitem, KeyFirst via blocklist intercept).

    For dict-method collision keys (items, keys, etc.): both envs resolve to the
    bound method (standard env via getattr, KeyFirst via fallthrough to super).
    """

    @pytest.mark.parametrize(
        "key,value",
        [
            ("tag", "my-tag-value"),
            ("anchor", "my-anchor-value"),
            ("ca", "my-ca-value"),
            ("merge", "my-merge-value"),
        ],
        ids=["tag", "anchor", "ca", "merge"],
    )
    def test_ruamel_attr_key_wins_via_dot(
        self,
        keyfirst_env: KeyFirstEnvironment,
        standard_env: Environment,
        key: str,
        value: str,
    ) -> None:
        """Ruamel-only attrs: dot access returns key value, identical to standard env."""
        template_str = f"{{{{ obj.{key} }}}}"
        data = {key: value, "other": "x"}
        result_kf = keyfirst_env.from_string(template_str).render(
            obj=CommentedMap(data)
        )
        result_std = standard_env.from_string(template_str).render(obj=data)
        assert result_kf == result_std == value

    @pytest.mark.parametrize(
        "key,value",
        [
            ("items", "my-items-value"),
            ("keys", "my-keys-value"),
            ("get", "my-get-value"),
            ("values", "my-values-value"),
        ],
        ids=["items", "keys", "get", "values"],
    )
    def test_dict_method_wins_over_key_via_dot(
        self,
        keyfirst_env: KeyFirstEnvironment,
        standard_env: Environment,
        key: str,
        value: str,
    ) -> None:
        """Dict-method collision keys: dot access returns the method on both envs,
        NOT the key value.  Use bracket notation to access the key."""
        template_str = f"{{{{ obj.{key} }}}}"
        data = {key: value, "other": "x"}
        result_kf = keyfirst_env.from_string(template_str).render(
            obj=CommentedMap(data)
        )
        result_std = standard_env.from_string(template_str).render(obj=data)
        # Both return a method (string repr differs by type, but neither is the key value)
        assert result_kf != value, f"KeyFirst returned key value for '{key}'"
        assert result_std != value, f"Standard returned key value for '{key}'"
        assert "method" in result_kf.lower()
        assert "method" in result_std.lower()
        assert "method" in result_kf.lower()
        assert "method" in result_std.lower()

    def test_nested_collision_key(
        self,
        keyfirst_env: KeyFirstEnvironment,
        standard_env: Environment,
    ) -> None:
        template_str = "{{ obj.child.tag }}"
        ruamel_outer = CommentedMap({"child": CommentedMap({"tag": "inner-tag"})})
        plain_outer = {"child": {"tag": "inner-tag"}}
        result_kf = keyfirst_env.from_string(template_str).render(obj=ruamel_outer)
        result_std = standard_env.from_string(template_str).render(obj=plain_outer)
        assert result_kf == result_std


# ---------------------------------------------------------------------------
# Test Class 3: Missing Key Behavior (ruamel attrs hidden)
# ---------------------------------------------------------------------------


class TestKeyFirstEnvironmentMissingKeyBehavior:
    """When a ruamel-only attribute is accessed on a mapping that does NOT have
    it as a key, it must return Undefined (not the ruamel metadata value)."""

    @pytest.mark.parametrize(
        "attr",
        [
            *sorted(_RUAMEL_MAP_ATTRS),
            "yaml_anchor",
            "yaml_set_ctag",
            "yaml_set_comment_before_after_key",
        ],
    )
    def test_ruamel_map_attr_returns_undefined(
        self,
        keyfirst_env: KeyFirstEnvironment,
        hostname_map: CommentedMap,
        attr: str,
    ) -> None:
        result = keyfirst_env.from_string(
            f"{{{{ obj.{attr} | default('UNDEFINED') }}}}"
        ).render(obj=hostname_map)
        assert result == "UNDEFINED", f"ruamel attr '{attr}' leaked through"

    @pytest.mark.parametrize(
        "attr",
        sorted(_RUAMEL_SEQ_ATTRS)
        + ["yaml_set_comment_before_after_key", "yaml_set_start_comment"],
    )
    def test_ruamel_seq_attr_returns_undefined(
        self,
        keyfirst_env: KeyFirstEnvironment,
        sample_seq: CommentedSeq,
        attr: str,
    ) -> None:
        result = keyfirst_env.from_string(
            f"{{{{ obj.{attr} | default('UNDEFINED') }}}}"
        ).render(obj=sample_seq)
        assert result == "UNDEFINED", f"ruamel seq attr '{attr}' leaked through"


# ---------------------------------------------------------------------------
# Test Class 4: Method Preservation
# ---------------------------------------------------------------------------


class TestKeyFirstEnvironmentMethodPreservation:
    """Standard dict/list methods must remain callable even though
    KeyFirstEnvironment intercepts attribute access."""

    def test_items_iteration(
        self,
        keyfirst_env: KeyFirstEnvironment,
        standard_env: Environment,
    ) -> None:
        template_str = "{% for k, v in obj.items() %}{{ k }}:{{ v }} {% endfor %}"
        data = {"a": 1, "b": 2}
        result_kf = keyfirst_env.from_string(template_str).render(
            obj=CommentedMap(data)
        )
        result_std = standard_env.from_string(template_str).render(obj=data)
        assert result_kf == result_std

    @pytest.mark.parametrize(
        "data,template_str",
        [
            ({"hostname": "router1"}, "{{ obj.get('hostname', 'fallback') }}"),
            ({"hostname": "router1"}, "{{ obj.get('nonexistent', 'fallback') }}"),
            (
                {"a": 1, "b": 2, "c": 3},
                "{{ obj.keys() | list | sort | join(',') }}",
            ),
            ({"a": 1, "b": 2}, "{{ obj.values() | list | sort | join(',') }}"),
            ({"a": 1, "b": 2, "c": 3}, "{{ obj | length }}"),
        ],
        ids=[
            "get_existing_key",
            "get_missing_key",
            "keys_method",
            "values_method",
            "map_length",
        ],
    )
    def test_dict_method(
        self,
        keyfirst_env: KeyFirstEnvironment,
        standard_env: Environment,
        data: dict[str, object],
        template_str: str,
    ) -> None:
        result_kf = keyfirst_env.from_string(template_str).render(
            obj=CommentedMap(data)
        )
        result_std = standard_env.from_string(template_str).render(obj=data)
        assert result_kf == result_std

    def test_seq_length(
        self,
        keyfirst_env: KeyFirstEnvironment,
        standard_env: Environment,
    ) -> None:
        """Standard list operations are NOT blocked on sequences."""
        template_str = "{{ obj | length }}"
        data = [1, 2, 3]
        result_kf = keyfirst_env.from_string(template_str).render(
            obj=CommentedSeq(data)
        )
        result_std = standard_env.from_string(template_str).render(obj=data)
        assert result_kf == result_std


# ---------------------------------------------------------------------------
# Test Class 5: Attr Getter Contract (selectattr/rejectattr/map)
# ---------------------------------------------------------------------------


class TestKeyFirstEnvironmentAttrGetterContract:
    """Jinja2 filters like selectattr/rejectattr/map(attribute=) use the
    Environment's getattr internally.  Verify they work correctly with
    collision keys on CommentedMap items inside a CommentedSeq."""

    @pytest.mark.parametrize(
        "template_str,expected",
        [
            (
                "{{ obj | selectattr('tag', 'equalto', 'trunk')"
                " | map(attribute='name') | join(',') }}",
                "Eth1/1,Eth1/3",
            ),
            (
                "{{ obj | rejectattr('tag', 'equalto', 'trunk')"
                " | map(attribute='name') | join(',') }}",
                "Eth1/2",
            ),
            (
                "{{ obj | map(attribute='tag') | join(',') }}",
                "trunk,access,trunk",
            ),
            (
                "{{ obj | selectattr('name', 'equalto', 'Eth1/2')"
                " | map(attribute='tag') | first }}",
                "access",
            ),
        ],
        ids=[
            "selectattr_collision_key",
            "rejectattr_collision_key",
            "map_attribute_extraction",
            "selectattr_non_collision_key",
        ],
    )
    def test_attr_getter(
        self,
        keyfirst_env: KeyFirstEnvironment,
        interfaces: CommentedSeq,
        template_str: str,
        expected: str,
    ) -> None:
        result = keyfirst_env.from_string(template_str).render(obj=interfaces)
        assert result == expected


# ---------------------------------------------------------------------------
# Test Class 6: Collision + Method Interaction
# ---------------------------------------------------------------------------


class TestKeyFirstEnvironmentCollisionMethodInteraction:
    """When some keys collide with dict method names, non-colliding methods
    must still work via the fallthrough to super().getattr()."""

    @pytest.mark.parametrize(
        "collision_key,method_template,expected",
        [
            ("items", "{{ obj.get('hostname', 'fb') }}", "router1"),
            ("items", "{{ obj.keys() | list | sort | join(',') }}", "hostname,items"),
            ("get", "{{ obj.keys() | list | sort | join(',') }}", "get,hostname"),
            ("keys", "{{ obj.get('hostname', 'fb') }}", "router1"),
            ("values", "{{ obj.get('hostname', 'fb') }}", "router1"),
        ],
        ids=[
            "items_collision-get_works",
            "items_collision-keys_works",
            "get_collision-keys_works",
            "keys_collision-get_works",
            "values_collision-get_works",
        ],
    )
    def test_non_colliding_method_still_works(
        self,
        keyfirst_env: KeyFirstEnvironment,
        collision_key: str,
        method_template: str,
        expected: str,
    ) -> None:
        cm = CommentedMap({"hostname": "router1", collision_key: "shadow"})
        result = keyfirst_env.from_string(method_template).render(obj=cm)
        assert result == expected

    def test_mixed_collision_access_and_method_in_same_template(
        self, keyfirst_env: KeyFirstEnvironment
    ) -> None:
        """Access collision key value via bracket AND call a method in one render."""
        cm = CommentedMap({"hostname": "router1", "items": ["a", "b"]})
        result = keyfirst_env.from_string(
            "val={{ obj['items'] | join(',') }} len={{ obj | length }}"
        ).render(obj=cm)
        assert result == "val=a,b len=2"

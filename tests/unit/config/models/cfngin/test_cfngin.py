"""Test runway.config.models.cfngin.__init__."""
# pylint: disable=no-self-use
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from runway.config.models.cfngin import (
    CfnginConfigDefinitionModel,
    CfnginHookDefinitionModel,
    CfnginPackageSourcesDefinitionModel,
    CfnginStackDefinitionModel,
    CfnginTargetDefinitionModel,
)


class TestCfnginConfigDefinitionModel:
    """Test runway.config.models.cfngin.CfnginConfigDefinitionModel."""

    @pytest.mark.parametrize(
        "field", ["post_build", "post_destroy", "pre_build", "pre_destroy"],
    )
    def test_convert_hook_definitions(self, field) -> None:
        """Test _convert_hook_definitions."""
        dict_hook = {"name": {"path": "something"}}
        list_hook = [{"path": "something"}]
        assert (
            CfnginConfigDefinitionModel.parse_obj(
                {"namespace": "test", field: dict_hook}
            ).dict(exclude_unset=True)[field]
            == list_hook
        )
        assert (
            CfnginConfigDefinitionModel.parse_obj(
                {"namespace": "test", field: list_hook}
            ).dict(exclude_unset=True)[field]
            == list_hook
        )

    def test_convert_stack_definitions(self) -> None:
        """Test _convert_stack_definitions."""
        dict_stack = {"stack-name": {"class_path": "something"}}
        list_stack = [{"class_path": "something", "name": "stack-name"}]
        assert (
            CfnginConfigDefinitionModel(namespace="test", stacks=dict_stack).dict(
                exclude_unset=True
            )["stacks"]
            == list_stack
        )
        assert (
            CfnginConfigDefinitionModel(namespace="test", stacks=list_stack).dict(
                exclude_unset=True
            )["stacks"]
            == list_stack
        )

    def test_extra(self) -> None:
        """Test extra fields."""
        assert (
            CfnginConfigDefinitionModel(common="something", namespace="test").namespace
            == "test"
        )

    def test_field_defaults(self) -> None:
        """Test field default values."""
        obj = CfnginConfigDefinitionModel(namespace="test")
        assert not obj.cfngin_bucket
        assert not obj.cfngin_bucket_region
        assert obj.cfngin_cache_dir == Path.cwd() / ".runway" / "cache"
        assert obj.log_formats == {}
        assert obj.lookups == {}
        assert obj.mappings == {}
        assert obj.namespace == "test"
        assert obj.namespace_delimiter == "-"
        assert obj.package_sources == CfnginPackageSourcesDefinitionModel()
        assert not obj.persistent_graph_key
        assert obj.post_build == []
        assert obj.post_destroy == []
        assert obj.pre_build == []
        assert obj.pre_destroy == []
        assert not obj.service_role
        assert obj.stacks == []
        assert not obj.sys_path
        assert not obj.tags
        assert obj.targets == []

    def test_parse_file(self, tmp_path: Path) -> None:
        """Test parse_file."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(yaml.dump({"namespace": "test"}))

        obj = CfnginConfigDefinitionModel.parse_file(config_yml)
        assert obj.namespace == "test"

    def test_resolve_path_fields(self) -> None:
        """Test _resolve_path_fields."""
        obj = CfnginConfigDefinitionModel(
            namespace="test", cfngin_cache_dir="./cache", sys_path="./something",
        )
        assert obj.cfngin_cache_dir.is_absolute()
        assert obj.sys_path.is_absolute()

    def test_required_fields(self) -> None:
        """Test required fields."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginConfigDefinitionModel()
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("namespace",)
        assert errors[0]["msg"] == "field required"

    def test_validate_unique_stack_names(self) -> None:
        """Test _validate_unique_stack_names."""
        data = {
            "namespace": "test",
            "stacks": [
                {"name": "stack0", "class_path": "stack0"},
                {"name": "stack1", "class_path": "stack1"},
            ],
        }
        assert CfnginConfigDefinitionModel.parse_obj(data)

    def test_validate_unique_stack_names_invalid(self) -> None:
        """Test _validate_unique_stack_names."""
        with pytest.raises(ValidationError) as excinfo:
            data = {
                "namespace": "test",
                "stacks": [
                    {"name": "stack0", "class_path": "stack0"},
                    {"name": "stack0", "class_path": "stack0"},
                ],
            }
            CfnginConfigDefinitionModel.parse_obj(data)
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("stacks",)
        assert errors[0]["msg"] == "Duplicate stack stack0 found at index 0"


class TestCfnginHookDefinitionModel:
    """Test runway.config.models.cfngin.CfnginHookDefinitionModel."""

    def test_extra(self) -> None:
        """Test extra fields."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginHookDefinitionModel(invalid="something", path="something")
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("invalid",)
        assert errors[0]["msg"] == "extra fields not permitted"

    def test_field_defaults(self) -> None:
        """Test field default values."""
        obj = CfnginHookDefinitionModel(path="something")
        assert obj.args == {}
        assert not obj.data_key
        assert obj.enabled
        assert obj.path == "something"
        assert obj.required

    def test_required_fields(self) -> None:
        """Test required fields."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginHookDefinitionModel()
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("path",)
        assert errors[0]["msg"] == "field required"


class TestCfnginStackDefinitionModel:
    """Test runway.config.models.cfngin.CfnginStackDefinitionModel."""

    def test_extra(self) -> None:
        """Test extra fields."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginStackDefinitionModel(
                class_path="something", invalid="something", name="stack-name"
            )
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("invalid",)
        assert errors[0]["msg"] == "extra fields not permitted"

    def test_field_defaults(self) -> None:
        """Test field default values."""
        obj = CfnginStackDefinitionModel(class_path="something", name="stack-name")
        assert obj.class_path == "something"
        assert not obj.description
        assert obj.enabled
        assert not obj.in_progress_behavior
        assert not obj.locked
        assert obj.name == "stack-name"
        assert not obj.profile
        assert not obj.protected
        assert not obj.region
        assert obj.required_by == []
        assert obj.requires == []
        assert not obj.stack_name
        assert not obj.stack_policy_path
        assert obj.tags == {}
        assert not obj.template_path
        assert not obj.termination_protection
        assert obj.variables == {}

    def test_required_fields(self) -> None:
        """Test required fields."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginStackDefinitionModel()
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("__root__",)
        assert errors[0]["msg"] == "either class_path or template_path must be defined"

    def test_resolve_path_fields(self) -> None:
        """Test _resolve_path_fields."""
        obj = CfnginStackDefinitionModel(
            name="test-stack",
            stack_policy_path="./policy.json",
            template_path="./template.yml",
        )
        assert obj.stack_policy_path.is_absolute()
        assert obj.template_path.is_absolute()

    def test_required_fields_w_class_path(self) -> None:
        """Test required fields."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginStackDefinitionModel(class_path="something")
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)
        assert errors[0]["msg"] == "field required"

    def test_validate_class_and_template(self) -> None:
        """Test _validate_class_and_template."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginStackDefinitionModel(
                class_path="something",
                name="stack-name",
                template_path="./something.yml",
            )
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("__root__",)
        assert (
            errors[0]["msg"] == "only one of class_path or template_path can be defined"
        )

    @pytest.mark.parametrize(
        "enabled, locked", [(True, True), (False, True), (False, False)]
    )
    def test_validate_class_or_template(self, enabled: bool, locked: bool) -> None:
        """Test _validate_class_or_template."""
        assert CfnginStackDefinitionModel(
            class_path="something", enabled=enabled, locked=locked, name="test-stack"
        )
        assert CfnginStackDefinitionModel(
            enabled=enabled,
            locked=locked,
            name="test-stack",
            template_path="./something.yml",
        )

    def test_validate_class_or_template_invalid(self) -> None:
        """Test _validate_class_or_template invalid."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginStackDefinitionModel(
                enabled=True, locked=False, name="stack-name",
            )
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("__root__",)
        assert errors[0]["msg"] == "either class_path or template_path must be defined"


class TestCfnginTargetDefinitionModel:
    """Test runway.config.models.cfngin.CfnginTargetDefinitionModel."""

    def test_extra(self) -> None:
        """Test extra fields."""
        with pytest.raises(ValidationError) as excinfo:
            CfnginTargetDefinitionModel(invalid="something", name="something")
        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("invalid",)
        assert errors[0]["msg"] == "extra fields not permitted"

    def test_field_defaults(self) -> None:
        """Test field default values."""
        obj = CfnginTargetDefinitionModel(name="something")
        assert obj.name == "something"
        assert obj.required_by == []
        assert obj.requires == []

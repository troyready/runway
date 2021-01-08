"""Tests for runway.cfngin.context."""
# pylint: disable=no-self-use,protected-access,too-many-public-methods
import io
import json
import unittest

from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber
from mock import PropertyMock, patch

from runway.cfngin.context import Context, get_fqn
from runway.cfngin.exceptions import (
    PersistentGraphCannotLock,
    PersistentGraphCannotUnlock,
    PersistentGraphLockCodeMissmatch,
    PersistentGraphLocked,
    PersistentGraphUnlocked,
)
from runway.cfngin.hooks.utils import handle_hooks
from runway.cfngin.plan import Graph, json_serial
from runway.config import CfnginConfig

BOTO3_CREDENTIALS = {
    "aws_access_key_id": "foo",
    "aws_secret_access_key": "bar",
    "aws_session_token": "foobar",
}
GET_SESSION_CALL = {
    "access_key": BOTO3_CREDENTIALS["aws_access_key_id"],
    "secret_key": BOTO3_CREDENTIALS["aws_secret_access_key"],
    "session_token": BOTO3_CREDENTIALS["aws_session_token"],
}


def gen_tagset(tags):
    """Create TagSet value from a dict."""
    return [{"Key": key, "Value": value} for key, value in tags.items()]


def gen_s3_object_content(content):
    """Convert a string or dict to S3 object body.

    Args:
        content (Union[str, Dict[str, Any]]): S3 object body

    Returns:
        botocore.response.StreamingBody Used in the Body of a
            s3.get_object response.

    """
    if isinstance(content, dict):
        content = json.dumps(content, default=json_serial)
    encoded_content = content.encode()
    return StreamingBody(io.BytesIO(encoded_content), len(encoded_content))


class TestContext(unittest.TestCase):
    """Tests for runway.cfngin.context.Context."""

    def setUp(self):
        """Run before tests."""
        self.config = CfnginConfig.parse_obj(
            {
                "namespace": "namespace",
                "stacks": [
                    {"name": "stack1", "template_path": "."},
                    {"name": "stack2", "template_path": "."},
                ],
            }
        )
        self.persist_graph_raw_config = {
            "namespace": "test",
            "cfngin_bucket": "cfngin-test",
            "cfngin_bucket_region": "us-east-1",
            "persistent_graph_key": "test.json",
            "stacks": [
                {"name": "stack1", "template_path": "."},
                {"name": "stack2", "template_path": ".", "requires": ["stack1"]},
            ],
        }
        self.persist_graph_config = CfnginConfig.parse_obj(
            self.persist_graph_raw_config
        )

    def test_attributes(self):
        """Test class attributes."""
        context = Context(
            config=CfnginConfig.parse_obj({"namespace": "test"}), region="us-east-1"
        )

        assert isinstance(context.config, CfnginConfig)
        assert context.config_path == "./"
        assert context.bucket_region == "us-east-1"
        assert not context.environment  # TODO check value
        assert isinstance(context.force_stacks, list)
        assert isinstance(context.hook_data, dict)
        assert context.s3_conn  # TODO check value
        assert isinstance(context.stack_names, list)

    def test_context_optional_keys_set(self):
        """Test context optional keys set."""
        context = Context(
            config=CfnginConfig.parse_obj({"namespace": "test"}), stack_names=["stack"],
        )
        self.assertEqual(context.mappings, {})
        self.assertEqual(context.stack_names, ["stack"])

    def test_context_get_stacks(self):
        """Test context get stacks."""
        context = Context(config=self.config)
        self.assertEqual(len(context.get_stacks()), 2)

    def test_context_get_stacks_dict_use_fqn(self):
        """Test context get stacks dict use fqn."""
        context = Context(config=self.config)
        stacks_dict = context.get_stacks_dict()
        stack_names = sorted(stacks_dict.keys())
        self.assertEqual(stack_names[0], "namespace-stack1")
        self.assertEqual(stack_names[1], "namespace-stack2")

    def test_context_get_fqn(self):
        """Test context get fqn."""
        context = Context(config=self.config)
        fqn = context.get_fqn()
        self.assertEqual(fqn, "namespace")

    def test_context_get_fqn_replace_dot(self):
        """Test context get fqn replace dot."""
        context = Context(config=CfnginConfig.parse_obj({"namespace": "my.namespace"}))
        fqn = context.get_fqn()
        self.assertEqual(fqn, "my-namespace")

    def test_context_get_fqn_empty_namespace(self):
        """Test context get fqn empty namespace."""
        context = Context(config=CfnginConfig.parse_obj({"namespace": ""}))
        fqn = context.get_fqn("vpc")
        self.assertEqual(fqn, "vpc")
        self.assertEqual(context.tags, {})

    def test_context_namespace(self):
        """Test context namespace."""
        context = Context(config=CfnginConfig.parse_obj({"namespace": "namespace"}))
        self.assertEqual(context.namespace, "namespace")

    def test_context_get_fqn_stack_name(self):
        """Test context get fqn stack name."""
        context = Context(config=self.config)
        fqn = context.get_fqn("stack1")
        self.assertEqual(fqn, "namespace-stack1")

    def test_context_default_bucket_name(self):
        """Test context default bucket name."""
        context = Context(config=CfnginConfig.parse_obj({"namespace": "test"}))
        self.assertEqual(context.bucket_name, "stacker-test")

    def test_context_bucket_name_is_overridden_but_is_none(self):
        """Test context bucket name is overridden but is none."""
        config = CfnginConfig.parse_obj({"namespace": "test", "cfngin_bucket": ""})
        context = Context(config=config)
        self.assertEqual(context.bucket_name, None)

        config = CfnginConfig.parse_obj({"namespace": "test", "cfngin_bucket": None})
        context = Context(config=config)
        self.assertEqual(context.bucket_name, "stacker-test")

    def test_context_bucket_name_is_overridden(self):
        """Test context bucket name is overridden."""
        config = CfnginConfig.parse_obj(
            {"namespace": "test", "cfngin_bucket": "bucket123"}
        )
        context = Context(config=config)
        self.assertEqual(context.bucket_name, "bucket123")

    def test_context_default_bucket_no_namespace(self):
        """Test context default bucket no namespace."""
        context = Context(config=CfnginConfig.parse_obj({"namespace": ""}))
        self.assertEqual(context.bucket_name, None)

        context = Context(
            config=CfnginConfig.parse_obj({"namespace": "", "cfngin_bucket": ""})
        )
        self.assertEqual(context.bucket_name, None)

    def test_context_namespace_delimiter_is_overridden_and_not_none(self):
        """Test context namespace delimiter is overridden and not none."""
        config = CfnginConfig.parse_obj(
            {"namespace": "namespace", "namespace_delimiter": "_"}
        )
        context = Context(config=config)
        fqn = context.get_fqn("stack1")
        self.assertEqual(fqn, "namespace_stack1")

    def test_context_namespace_delimiter_is_overridden_and_is_empty(self):
        """Test context namespace delimiter is overridden and is empty."""
        config = CfnginConfig.parse_obj(
            {"namespace": "namespace", "namespace_delimiter": ""}
        )
        context = Context(config=config)
        fqn = context.get_fqn("stack1")
        self.assertEqual(fqn, "namespacestack1")

    def test_context_tags_with_empty_map(self):
        """Test context tags with empty map."""
        config = CfnginConfig.parse_obj({"namespace": "test", "tags": {}})
        context = Context(config=config)
        self.assertEqual(context.tags, {})

    def test_context_no_tags_specified(self):
        """Test context no tags specified."""
        config = CfnginConfig.parse_obj({"namespace": "test"})
        context = Context(config=config)
        self.assertEqual(context.tags, {"cfngin_namespace": "test"})

    @patch("runway.cfngin.context.get_session")
    def test_get_session(self, mock_get_session):
        """Test get_session."""
        creds = BOTO3_CREDENTIALS.copy()
        context = Context(boto3_credentials=creds, region="us-east-1")

        context.get_session()
        mock_get_session.assert_called_with(region="us-east-1", **GET_SESSION_CALL)

        context.get_session(region="us-west-2")
        mock_get_session.assert_called_with(region="us-west-2", **GET_SESSION_CALL)

        context.get_session(profile="user")
        mock_get_session.assert_called_with(region="us-east-1", profile="user")

    def test_hook_with_sys_path(self):
        """Test hook with sys path."""
        config = CfnginConfig.parse_obj(
            {
                "namespace": "test",
                "sys_path": "./tests/unit/cfngin",
                "pre_build": [
                    {
                        "data_key": "myHook",
                        "path": "fixtures.mock_hooks.mock_hook",
                        "required": True,
                        "args": {"value": "mockResult"},
                    }
                ],
            }
        )
        config.load()
        context = Context(config=config)
        stage = "pre_build"
        handle_hooks(stage, getattr(context.config, stage), "mock-region-1", context)
        self.assertEqual("mockResult", context.hook_data["myHook"]["result"])

    def test_persistent_graph_location(self):
        """Test persistent graph location."""
        context = Context(config=self.persist_graph_config)
        expected = {"Bucket": "cfngin-test", "Key": "persistent_graphs/test/test.json"}
        self.assertEqual(expected, context.persistent_graph_location)

    def test_persistent_graph_location_no_json(self):
        """'.json' appended to the key if it does not exist."""
        cp_config = self.persist_graph_raw_config.copy()
        cp_config["persistent_graph_key"] = "test"

        context = Context(config=CfnginConfig.parse_obj(cp_config))
        expected = {"Bucket": "cfngin-test", "Key": "persistent_graphs/test/test.json"}
        self.assertEqual(expected, context.persistent_graph_location)

    def test_persistent_graph_location_no_key(self):
        """Return an empty dict if key is not set."""
        context = Context(config=self.config)
        self.assertEqual({}, context.persistent_graph_location)

    def test_persistent_graph_location_no_bucket(self):
        """Return an empty dict if key is set but no bucket name."""
        cp_config = self.persist_graph_raw_config.copy()
        cp_config["cfngin_bucket"] = ""

        context = Context(config=CfnginConfig.parse_obj(cp_config))
        self.assertEqual({}, context.persistent_graph_location)

    @patch(
        "runway.cfngin.context.Context._persistent_graph_tags",
        new_callable=PropertyMock,
    )
    def test_persistent_graph_lock_code_disabled(self, mock_prop):
        """Return 'None' when not used."""
        mock_prop.return_value = None
        context = Context(config=self.config)
        mock_prop.assert_not_called()
        self.assertIsNone(context.persistent_graph_lock_code)

    def test_persistent_graph_lock_code_present(self):
        """Return the value of the lock tag when it exists."""
        context = Context(config=self.persist_graph_config)
        stubber = Stubber(context.s3_conn)
        code = "0000"

        stubber.add_response(
            "get_object_tagging",
            {"TagSet": gen_tagset({context._persistent_graph_lock_tag: code})},
            context.persistent_graph_location,
        )

        with stubber:
            self.assertIsNone(context._persistent_graph_lock_code)
            self.assertEqual(code, context.persistent_graph_lock_code)
            self.assertEqual(code, context._persistent_graph_lock_code)
            stubber.assert_no_pending_responses()

    def test_persistent_graph_lock_code_none(self):
        """Return 'None' when the tag is not set."""
        context = Context(config=self.persist_graph_config)
        stubber = Stubber(context.s3_conn)

        stubber.add_response(
            "get_object_tagging", {"TagSet": []}, context.persistent_graph_location
        )

        with stubber:
            self.assertIsNone(context.persistent_graph_lock_code)
            self.assertIsNone(context._persistent_graph_lock_code)
            stubber.assert_no_pending_responses()

    def test_persistent_graph_lock_code_no_object(self):
        """Return 'None' when object does not exist."""
        context = Context(config=self.persist_graph_config)
        stubber = Stubber(context.s3_conn)

        stubber.add_client_error(
            "get_object_tagging",
            "NoSuchKey",
            expected_params=context.persistent_graph_location,
        )

        with stubber:
            self.assertIsNone(context.persistent_graph_lock_code)
            self.assertIsNone(context._persistent_graph_lock_code)
            stubber.assert_no_pending_responses()

    def test_persistent_graph(self):
        """Return Graph from S3 object."""
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        stubber = Stubber(context.s3_conn)
        expected_params = {"ResponseContentType": "application/json"}
        expected_params.update(context.persistent_graph_location)
        expected_content = {"stack1": set(), "stack2": set(["stack1"])}

        stubber.add_response(
            "get_object",
            {"Body": gen_s3_object_content(expected_content)},
            expected_params,
        )

        with stubber:
            self.assertIsNone(context._persistent_graph)
            self.assertIsInstance(context.persistent_graph, Graph)
            self.assertIsInstance(context._persistent_graph, Graph)
            self.assertEqual(expected_content, context.persistent_graph.to_dict())
            stubber.assert_no_pending_responses()

    def test_persistent_graph_no_object(self):
        """Create object if one does not exist and return empty Graph."""
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        stubber = Stubber(context.s3_conn)
        expected_get_params = {"ResponseContentType": "application/json"}
        expected_get_params.update(context.persistent_graph_location)
        expected_put_params = {
            "Body": "{}",
            "ServerSideEncryption": "AES256",
            "ACL": "bucket-owner-full-control",
            "ContentType": "application/json",
        }
        expected_put_params.update(context.persistent_graph_location)

        stubber.add_client_error(
            "get_object", "NoSuchKey", expected_params=expected_get_params
        )
        stubber.add_response("put_object", {}, expected_put_params)

        with stubber:
            self.assertIsNone(context._persistent_graph)
            self.assertIsInstance(context.persistent_graph, Graph)
            self.assertIsInstance(context._persistent_graph, Graph)
            self.assertEqual({}, context.persistent_graph.to_dict())
            stubber.assert_no_pending_responses()

    def test_persistent_graph_disabled(self):
        """Return 'None' when key is not set."""
        context = Context(config=self.config)
        self.assertIsNone(context._persistent_graph)
        self.assertIsNone(context.persistent_graph)

    def test_lock_persistent_graph(self):
        """Return 'None' when lock is successful."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph()
        stubber = Stubber(context.s3_conn)
        expected_params = {
            "Tagging": {
                "TagSet": gen_tagset({context._persistent_graph_lock_tag: code})
            }
        }
        expected_params.update(context.persistent_graph_location)

        stubber.add_response(
            "get_object_tagging", {"TagSet": []}, context.persistent_graph_location
        )
        stubber.add_response("put_object_tagging", {}, expected_params)

        with stubber:
            self.assertIsNone(context.lock_persistent_graph(code))
            stubber.assert_no_pending_responses()

    def test_lock_persistent_graph_locked(self):
        """Error raised when when object is locked."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph()
        stubber = Stubber(context.s3_conn)
        expected_params = {
            "Tagging": {
                "TagSet": gen_tagset({context._persistent_graph_lock_tag: code})
            }
        }
        expected_params.update(context.persistent_graph_location)

        stubber.add_response(
            "get_object_tagging",
            {"TagSet": gen_tagset({context._persistent_graph_lock_tag: "1111"})},
            context.persistent_graph_location,
        )

        with stubber:
            with self.assertRaises(PersistentGraphLocked):
                context.lock_persistent_graph(code)
            stubber.assert_no_pending_responses()

    def test_lock_persistent_graph_no_object(self):
        """Error raised when when there is no object to lock."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph()
        stubber = Stubber(context.s3_conn)
        expected_params = {
            "Tagging": {
                "TagSet": gen_tagset({context._persistent_graph_lock_tag: code})
            }
        }
        expected_params.update(context.persistent_graph_location)

        stubber.add_client_error(
            "get_object_tagging",
            "NoSuchKey",
            expected_params=context.persistent_graph_location,
        )
        stubber.add_client_error(
            "put_object_tagging", "NoSuchKey", expected_params=expected_params
        )

        with stubber:
            with self.assertRaises(PersistentGraphCannotLock):
                context.lock_persistent_graph(code)
            stubber.assert_no_pending_responses()

    def test_put_persistent_graph(self):
        """Return 'None' when put is successful."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        graph_dict = {"stack1": [], "stack2": ["stack1"]}
        context._persistent_graph = Graph.from_dict(graph_dict, context)
        stubber = Stubber(context.s3_conn)
        expected_params = {
            "Body": json.dumps(graph_dict, indent=4),
            "ServerSideEncryption": "AES256",
            "ACL": "bucket-owner-full-control",
            "ContentType": "application/json",
            "Tagging": "{}={}".format(context._persistent_graph_lock_tag, code),
        }
        expected_params.update(context.persistent_graph_location)

        stubber.add_response(
            "get_object_tagging",
            {"TagSet": gen_tagset({context._persistent_graph_lock_tag: code})},
            context.persistent_graph_location,
        )
        stubber.add_response("put_object", {}, expected_params)

        with stubber:
            self.assertIsNone(context.put_persistent_graph(code))
            stubber.assert_no_pending_responses()

    def test_put_persistent_graph_unlocked(self):
        """Error raised when trying to update an unlocked object."""
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph.from_dict({"stack1": []}, context)
        stubber = Stubber(context.s3_conn)

        stubber.add_response(
            "get_object_tagging", {"TagSet": []}, context.persistent_graph_location
        )

        with stubber:
            with self.assertRaises(PersistentGraphUnlocked):
                context.put_persistent_graph("")
            stubber.assert_no_pending_responses()

    def test_put_persistent_graph_code_missmatch(self):
        """Error raised when provided lock code does not match object."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph.from_dict({"stack1": []}, context)
        stubber = Stubber(context.s3_conn)

        stubber.add_response(
            "get_object_tagging",
            {"TagSet": gen_tagset({context._persistent_graph_lock_tag: "1111"})},
            context.persistent_graph_location,
        )

        with stubber:
            with self.assertRaises(PersistentGraphLockCodeMissmatch):
                context.put_persistent_graph(code)
            stubber.assert_no_pending_responses()

    def test_put_persistent_graph_empty(self):
        """Object deleted when persistent graph is empty."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph()
        stubber = Stubber(context.s3_conn)

        stubber.add_response("delete_object", {}, context.persistent_graph_location)

        with stubber:
            self.assertFalse(context.persistent_graph.to_dict())
            self.assertIsNone(context.put_persistent_graph(code))
            stubber.assert_no_pending_responses()

    @patch(
        "runway.cfngin.context.Context._persistent_graph_tags",
        new_callable=PropertyMock,
    )
    def test_persistent_graph_locked(self, mock_prop):
        """Return 'True' or 'False' based on code property."""
        mock_prop.return_value = {}
        context = Context(config=self.persist_graph_config)
        context._persistent_graph = True

        context._persistent_graph_lock_code = True
        self.assertTrue(context.persistent_graph_locked)

        context._persistent_graph_lock_code = None
        self.assertFalse(context.persistent_graph_locked)
        mock_prop.assert_called_once()

    def test_persistent_graph_locked_disabled(self):
        """Return 'None' when key is not set."""
        context = Context(config=self.config)
        self.assertFalse(context.persistent_graph_locked)

    def test_s3_bucket_exists(self):
        """Test s3 bucket exists."""
        context = Context(config=self.config)
        stubber = Stubber(context.s3_conn)

        stubber.add_response(
            "head_bucket", service_response={}, expected_params={"Bucket": ANY}
        )

        with stubber:
            self.assertIsNone(context._s3_bucket_verified)
            self.assertTrue(context.s3_bucket_verified)
            self.assertTrue(context._s3_bucket_verified)
            stubber.assert_no_pending_responses()

    def test_s3_bucket_does_not_exist_us_east(self):
        """Create S3 bucket when it does not exist."""
        context = Context(config=self.config, region="us-east-1")
        stubber = Stubber(context.s3_conn)

        stubber.add_client_error(
            "head_bucket",
            service_error_code="NoSuchBucket",
            service_message="Not Found",
            http_status_code=404,
        )
        stubber.add_response(
            "create_bucket", service_response={}, expected_params={"Bucket": ANY}
        )

        with stubber:
            self.assertIsNone(context._s3_bucket_verified)
            self.assertTrue(context.s3_bucket_verified)
            self.assertTrue(context._s3_bucket_verified)
            stubber.assert_no_pending_responses()

    def test_s3_bucket_does_not_exist_us_west(self):
        """Create S3 bucket with loc constraints when it does not exist."""
        region = "us-west-1"
        context = Context(config=self.config, region=region)
        stubber = Stubber(context.s3_conn)

        stubber.add_client_error(
            "head_bucket",
            service_error_code="NoSuchBucket",
            service_message="Not Found",
            http_status_code=404,
        )
        stubber.add_response(
            "create_bucket",
            service_response={},
            expected_params={
                "Bucket": ANY,
                "CreateBucketConfiguration": {"LocationConstraint": region},
            },
        )

        with stubber:
            self.assertIsNone(context._s3_bucket_verified)
            self.assertTrue(context.s3_bucket_verified)
            self.assertTrue(context._s3_bucket_verified)
            stubber.assert_no_pending_responses()

    def test_s3_bucket_forbidden(self):
        """Error raised when S3 bucket exists but cannot access."""
        context = Context(config=self.config)
        stubber = Stubber(context.s3_conn)

        stubber.add_client_error(
            "head_bucket",
            service_error_code="AccessDenied",
            service_message="Forbidden",
            http_status_code=403,
        )

        with stubber:
            with self.assertRaises(ClientError):
                self.assertFalse(context.s3_bucket_verified)
            stubber.assert_no_pending_responses()

    def test_unlock_persistent_graph(self):
        """Return 'True' when delete tag is successful."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph.from_dict({"stack1": []}, context)
        stubber = Stubber(context.s3_conn)

        stubber.add_response(
            "get_object_tagging",
            {"TagSet": gen_tagset({context._persistent_graph_lock_tag: code})},
            context.persistent_graph_location,
        )
        stubber.add_response(
            "delete_object_tagging", {}, context.persistent_graph_location
        )

        with stubber:
            self.assertTrue(context.unlock_persistent_graph(code))
            stubber.assert_no_pending_responses()

    def test_unlock_persistent_graph_not_locked(self):
        """Error raised when object is not locked."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph.from_dict({"stack1": []}, context)
        stubber = Stubber(context.s3_conn)

        stubber.add_response(
            "get_object_tagging", {"TagSet": []}, context.persistent_graph_location
        )

        with stubber:
            with self.assertRaises(PersistentGraphCannotUnlock):
                context.unlock_persistent_graph(code)
            stubber.assert_no_pending_responses()

    def test_unlock_persistent_graph_code_missmatch(self):
        """Error raised when local code does not match object."""
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph.from_dict({"stack1": []}, context)
        stubber = Stubber(context.s3_conn)

        stubber.add_response(
            "get_object_tagging",
            {"TagSet": gen_tagset({context._persistent_graph_lock_tag: "1111"})},
            context.persistent_graph_location,
        )

        with stubber:
            with self.assertRaises(PersistentGraphCannotUnlock):
                context.unlock_persistent_graph(code)
            stubber.assert_no_pending_responses()

    def test_unlock_persistent_graph_no_object(self):
        """Return 'None' when object does not exist.

        This can occur if the object is deleted by 'put_persistent_graph'.

        """
        code = "0000"
        context = Context(config=self.persist_graph_config)
        context._s3_bucket_verified = True
        context._persistent_graph = Graph()
        stubber = Stubber(context.s3_conn)
        expected_params = context.persistent_graph_location.copy()
        expected_params.update({"ResponseContentType": "application/json"})

        stubber.add_client_error(
            "get_object", "NoSuchKey", expected_params=expected_params
        )

        with stubber:
            assert context.unlock_persistent_graph(code)
            stubber.assert_no_pending_responses()


class TestFunctions(unittest.TestCase):
    """Test the module level functions."""

    def test_get_fqn_redundant_base(self):
        """Test get fqn redundant base."""
        base = "woot"
        name = "woot-blah"
        self.assertEqual(get_fqn(base, "-", name), name)
        self.assertEqual(get_fqn(base, "", name), name)
        self.assertEqual(get_fqn(base, "_", name), "woot_woot-blah")

    def test_get_fqn_only_base(self):
        """Test get fqn only base."""
        base = "woot"
        self.assertEqual(get_fqn(base, "-"), base)
        self.assertEqual(get_fqn(base, ""), base)
        self.assertEqual(get_fqn(base, "_"), base)

    def test_get_fqn_full(self):
        """Test get fqn full."""
        base = "woot"
        name = "blah"
        self.assertEqual(get_fqn(base, "-", name), "%s-%s" % (base, name))
        self.assertEqual(get_fqn(base, "", name), "%s%s" % (base, name))
        self.assertEqual(get_fqn(base, "_", name), "%s_%s" % (base, name))


if __name__ == "__main__":
    unittest.main()

"""Static website module."""
import logging
import os
import sys
import tempfile
from typing import Any, Dict

import yaml

from .._logging import PrefixAdaptor
from ..util import YamlDumper
from . import RunwayModule
from .cloudformation import CloudFormation

LOGGER = logging.getLogger(__name__)


def add_url_scheme(url):
    """Add the scheme to an existing url.

    Args:
        url (str): The current url.

    """
    if url.startswith("https://") or url.startswith("http://"):
        return url
    newurl = "https://%s" % url
    return newurl


class StaticSite(RunwayModule):
    """Static website Runway Module."""

    def __init__(self, context, path, options=None):
        """Initialize."""
        super().__init__(context, path, options)
        self.user_options = self.options.get("options", {})
        self.parameters = self.options.get("parameters")  # type: Dict[str, Any]
        self.region = self.context.env.aws_region
        # logger needs to be created here to use the correct logger
        self.logger = PrefixAdaptor(self.name, LOGGER)
        self._ensure_valid_environment_config()
        self._ensure_cloudfront_with_auth_at_edge()
        self._ensure_correct_region_with_auth_at_edge()

    def plan(self):
        """Create website CFN module and run stacker diff."""
        if self.parameters:
            self._setup_website_module(command="plan")
        else:
            self.logger.info("skipped; environment required but not defined")

    def deploy(self):
        """Create website CFN module and run stacker build."""
        if self.parameters:
            if self.parameters.get("staticsite_cf_disable", False) is False:
                self.logger.warning(
                    "initial creation of & updates to distributions can take "
                    "up to an hour to complete"
                )

                # Auth@Edge warning about subsequent deploys
                if (
                    self.parameters.get("staticsite_auth_at_edge", False)
                    and not self.parameters.get("staticsite_aliases", False)
                    and self.context.is_interactive
                ):
                    self.logger.warning(
                        "A hook that is part of the dependencies stack of "
                        "the Auth@Edge static site deployment is designed "
                        "to verify that the correct Callback URLs are "
                        "being used when a User Pool Client already "
                        "exists for the application. This ensures that "
                        "there is no interruption of service while the "
                        "deployment reaches the stage where the Callback "
                        "URLs are updated to that of the Distribution. "
                        "Because of this you may receive a change set "
                        "prompt on subsequent deploys."
                    )
            self._setup_website_module(command="deploy")
        else:
            self.logger.info("skipped; environment required but not defined")

    def destroy(self):
        """Create website CFN module and run stacker destroy."""
        if self.parameters:
            self._setup_website_module(command="destroy")
        else:
            self.logger.info("skipped; environment required but not defined")

    def _setup_website_module(
        self,  # type: StaticSite
        command,  # type: str
    ):
        # type(...) -> return None
        """Create CFNgin configuration for website module."""
        self.logger.info("generating CFNgin config...")
        module_dir = self._create_module_directory()
        self._create_dependencies_yaml(module_dir)
        self._create_staticsite_yaml(module_dir)

        # Earlier Runway versions included a CFN stack with a state machine
        # that attempted to automatically clean up the orphaned Lambda@Edge
        # functions. This was found to be unreliable and has been removed.
        # For a period of time (e.g. until the next major release) leaving this
        # in to automatically delete the stack. Not a major priority to have
        # Runway delete the old `-cleanup` stack, as the resources in it don't
        # have any costs when unused.
        if command == "destroy" and (
            self.parameters.get("staticsite_auth_at_edge")
            or self.parameters.get("staticsite_rewrite_index_index")
        ):
            self._create_cleanup_yaml(module_dir)

        cfn = CloudFormation(
            self.context,
            module_dir,
            {i: self.options[i] for i in self.options if i != "class_path"},
        )
        self.logger.info("%s (in progress)", command)
        getattr(cfn, command)()
        self.logger.info("%s (complete)", command)

    def _create_module_directory(self):
        module_dir = tempfile.mkdtemp()
        self.logger.debug("using temporary directory: %s", module_dir)
        return module_dir

    def _create_dependencies_yaml(self, module_dir):
        pre_build = []

        pre_destroy = [
            {
                "path": "runway.hooks.cleanup_s3.purge_bucket",
                "required": True,
                "args": {"bucket_rxref_lookup": "%s-dependencies::%s" % (self.name, i)},
            }
            for i in ["AWSLogBucketName", "ArtifactsBucketName"]
        ]

        if self.parameters.get("staticsite_auth_at_edge", False):
            if not self.parameters.get("staticsite_aliases"):
                # Retrieve the appropriate callback urls from the User Pool Client
                pre_build.append(
                    {
                        "path": "runway.hooks.staticsite.auth_at_edge.callback_url_retriever.get",
                        "required": True,
                        "data_key": "aae_callback_url_retriever",
                        "args": {
                            "user_pool_arn": self.parameters.get(
                                "staticsite_user_pool_arn", ""
                            ),
                            "aliases": self.parameters.get("staticsite_aliases", ""),
                            "additional_callback_domains": self.parameters.get(
                                "staticsite_additional_callback_domains", ""
                            ),
                            "stack_name": "${namespace}-%s-dependencies" % self.name,
                        },
                    }
                )

            if self.parameters.get("staticsite_create_user_pool"):
                # Retrieve the user pool id
                pre_destroy.append(
                    {
                        "path": "runway.hooks.staticsite.auth_at_edge.user_pool_id_retriever.get",
                        "required": True,
                        "data_key": "aae_user_pool_id_retriever",
                        "args": self._get_user_pool_id_retriever_variables(),
                    }
                )

                # Delete the domain prior to trying to delete the
                # User Pool Client that was created
                pre_destroy.append(
                    {
                        "path": "runway.hooks.staticsite.auth_at_edge.domain_updater.delete",
                        "required": True,
                        "data_key": "aae_domain_updater",
                        "args": self._get_domain_updater_variables(),
                    }
                )
            else:
                # Retrieve the user pool id
                pre_build.append(
                    {
                        "path": "runway.hooks.staticsite.auth_at_edge.user_pool_id_retriever.get",
                        "required": True,
                        "data_key": "aae_user_pool_id_retriever",
                        "args": self._get_user_pool_id_retriever_variables(),
                    }
                )

        content = {
            "namespace": "${namespace}",
            "cfngin_bucket": "",
            "stacks": {
                "%s-dependencies"
                % self.name: {
                    "class_path": "runway.blueprints.staticsite.dependencies.Dependencies",
                    "variables": self._get_dependencies_variables(),
                }
            },
            "pre_build": pre_build,
            "pre_destroy": pre_destroy,
        }

        with open(
            os.path.join(module_dir, "01-dependencies.yaml"), "w"
        ) as output_stream:
            yaml.dump(content, output_stream, default_flow_style=False)
        self.logger.debug(
            "created 01-dependencies.yaml:\n%s", yaml.dump(content, Dumper=YamlDumper)
        )

    def _create_staticsite_yaml(self, module_dir):
        # Default parameter name matches build_staticsite hook
        hash_param = self.user_options.get("source_hashing", {}).get(
            "parameter", "${namespace}-%s-hash" % self.name
        )
        nonce_secret_param = "${namespace}-%s-nonce-secret" % self.name

        build_staticsite_args = self.options.copy() or {}
        build_staticsite_args["artifact_bucket_rxref_lookup"] = (
            "%s-dependencies::ArtifactsBucketName" % self.name
        )
        build_staticsite_args["options"]["namespace"] = "${namespace}"
        build_staticsite_args["options"]["name"] = self.name
        build_staticsite_args["options"]["path"] = os.path.join(
            os.path.realpath(self.context.env_root), self.path
        )

        site_stack_variables = self._get_site_stack_variables()

        class_path = "staticsite.StaticSite"

        pre_build = [
            {
                "path": "runway.hooks.staticsite.build_staticsite.build",
                "required": True,
                "data_key": "staticsite",
                "args": build_staticsite_args,
            }
        ]

        post_build = [
            {
                "path": "runway.hooks.staticsite.upload_staticsite.sync",
                "required": True,
                "args": {
                    "bucket_output_lookup": "%s::BucketName" % self.name,
                    "website_url": "%s::BucketWebsiteURL" % self.name,
                    "extra_files": self.user_options.get("extra_files", []),
                    "cf_disabled": site_stack_variables["DisableCloudFront"],
                    "distributionid_output_lookup": "%s::CFDistributionId"
                    % (self.name),
                    "distributiondomain_output_lookup": "%s::CFDistributionDomainName"
                    % self.name,
                },
            }
        ]

        pre_destroy = [
            {
                "path": "runway.hooks.cleanup_s3.purge_bucket",
                "required": True,
                "args": {"bucket_rxref_lookup": "%s::BucketName" % self.name},
            }
        ]

        if self.parameters.get(
            "staticsite_rewrite_directory_index"
        ) or self.parameters.get("staticsite_auth_at_edge"):
            pre_destroy.append(
                {
                    "path": "runway.hooks.staticsite.cleanup.warn",
                    "required": False,
                    "args": {"stack_relative_name": self.name},
                }
            )

        post_destroy = [
            {
                "path": "runway.hooks.cleanup_ssm.delete_param",
                "args": {"parameter_name": i},
            }
            for i in [hash_param, nonce_secret_param, "%sextra" % hash_param]
        ]

        if self.parameters.get("staticsite_auth_at_edge", False):
            class_path = "auth_at_edge.AuthAtEdge"

            pre_build.append(
                {
                    "path": "runway.hooks.staticsite.auth_at_edge.user_pool_id_retriever.get",
                    "required": True,
                    "data_key": "aae_user_pool_id_retriever",
                    "args": self._get_user_pool_id_retriever_variables(),
                }
            )
            pre_build.append(
                {
                    "path": "runway.hooks.staticsite.auth_at_edge.domain_updater.update",
                    "required": True,
                    "data_key": "aae_domain_updater",
                    "args": self._get_domain_updater_variables(),
                }
            )
            pre_build.append(
                {
                    "path": "runway.hooks.staticsite.auth_at_edge.lambda_config.write",
                    "required": True,
                    "data_key": "aae_lambda_config",
                    "args": self._get_lambda_config_variables(
                        site_stack_variables,
                        nonce_secret_param,
                        self.parameters.get("staticsite_required_group"),
                    ),
                }
            )
            if not self.parameters.get("staticsite_aliases"):
                post_build.insert(
                    0,
                    {
                        "path": "runway.hooks.staticsite.auth_at_edge.client_updater.update",
                        "required": True,
                        "data_key": "client_updater",
                        "args": self._get_client_updater_variables(
                            self.name, site_stack_variables
                        ),
                    },
                )

        if self.parameters.get("staticsite_role_boundary_arn", False):
            site_stack_variables["RoleBoundaryArn"] = self.parameters[
                "staticsite_role_boundary_arn"
            ]

        # If lambda_function_associations or custom_error_responses defined,
        # add to stack config
        for i in ["custom_error_responses", "lambda_function_associations"]:
            if self.parameters.get("staticsite_%s" % i):
                site_stack_variables[i] = self.parameters.pop("staticsite_%s" % i)

        content = {
            "namespace": "${namespace}",
            "cfngin_bucket": "",
            "pre_build": pre_build,
            "stacks": {
                self.name: {
                    "class_path": "runway.blueprints.staticsite.%s" % class_path,
                    "variables": site_stack_variables,
                }
            },
            "post_build": post_build,
            "pre_destroy": pre_destroy,
            "post_destroy": post_destroy,
        }

        with open(os.path.join(module_dir, "02-staticsite.yaml"), "w") as output_stream:
            yaml.dump(content, output_stream, default_flow_style=False)
        self.logger.debug(
            "created 02-staticsite.yaml:\n%s", yaml.dump(content, Dumper=YamlDumper)
        )

    def _create_cleanup_yaml(self, module_dir):
        content = {
            "namespace": "${namespace}",
            "cfngin_bucket": "",
            "stacks": {
                "%s-cleanup"
                % self.name: {
                    "template_path": os.path.join(
                        tempfile.gettempdir(), "thisfileisnotused.yaml"
                    ),
                }
            },
        }

        with open(os.path.join(module_dir, "03-cleanup.yaml"), "w") as output_stream:
            yaml.dump(content, output_stream, default_flow_style=False)
        self.logger.debug(
            "created 03-cleanup.yaml:\n%s", yaml.dump(content, Dumper=YamlDumper)
        )

    def _get_site_stack_variables(self):
        site_stack_variables = {
            "Aliases": [],
            "DisableCloudFront": self.parameters.get("staticsite_cf_disable", False),
            "RewriteDirectoryIndex": self.parameters.get(
                "staticsite_rewrite_directory_index", ""
            ),
            "RedirectPathSignIn": "${default staticsite_redirect_path_sign_in::/parseauth}",
            "RedirectPathSignOut": "${default staticsite_redirect_path_sign_out::/}",
            "RedirectPathAuthRefresh": "${default staticsite_redirect_path_auth_refresh"
            "::/refreshauth}",
            "SignOutUrl": "${default staticsite_sign_out_url::/signout}",
            "WAFWebACL": self.parameters.get("staticsite_web_acl", ""),
        }

        if self.parameters.get("staticsite_aliases"):
            site_stack_variables["Aliases"] = self.parameters.get(
                "staticsite_aliases"
            ).split(",")

        if self.parameters.get("staticsite_acmcert_arn"):
            site_stack_variables["AcmCertificateArn"] = self.parameters[
                "staticsite_acmcert_arn"
            ]

        if self.parameters.get("staticsite_acmcert_ssm_param"):
            self.logger.warning(
                "staticsite_acmcert_ssm_param option has been deprecated; "
                "use staticsite_acmcert_arn with an ssm lookup"
            )
            site_stack_variables[
                "AcmCertificateArn"
            ] = "${ssmstore ${staticsite_acmcert_ssm_param}}"

        if self.parameters.get("staticsite_enable_cf_logging", True):
            site_stack_variables["LogBucketName"] = (
                "${rxref %s-dependencies::AWSLogBucketName}" % self.name
            )

        if self.parameters.get("staticsite_auth_at_edge", False):
            self._ensure_auth_at_edge_requirements()
            site_stack_variables["UserPoolArn"] = self.parameters.get(
                "staticsite_user_pool_arn"
            )
            site_stack_variables["NonSPAMode"] = self.parameters.get(
                "staticsite_non_spa", False
            )
            site_stack_variables["HttpHeaders"] = self._get_http_headers()
            site_stack_variables["CookieSettings"] = self._get_cookie_settings()
            site_stack_variables["OAuthScopes"] = self._get_oauth_scopes()
        else:
            # If lambda_function_associations or custom_error_responses defined,
            # add to stack config. Only if not using Auth@Edge
            for i in ["custom_error_responses", "lambda_function_associations"]:
                if self.parameters.get("staticsite_%s" % i):
                    site_stack_variables[i] = self.parameters.get("staticsite_%s" % i)
                    self.parameters.pop("staticsite_%s" % i)

        return site_stack_variables

    def _get_cookie_settings(self):
        """Retrieve the cookie settings from the variables or return the default."""
        if self.parameters.get("staticsite_cookie_settings"):
            return self.parameters.get("staticsite_cookie_settings")
        return {
            "idToken": "Path=/; Secure; SameSite=Lax",
            "accessToken": "Path=/; Secure; SameSite=Lax",
            "refreshToken": "Path=/; Secure; SameSite=Lax",
            "nonce": "Path=/; Secure; HttpOnly; Max-Age=1800; SameSite=Lax",
        }

    def _get_http_headers(self):
        """Retrieve the http headers from the variables or return the default."""
        if self.parameters.get("staticsite_http_headers"):
            return self.parameters.get("staticsite_http_headers")
        return {
            "Content-Security-Policy": "default-src https: 'unsafe-eval' 'unsafe-inline'; "
            "font-src 'self' 'unsafe-inline' 'unsafe-eval' data: https:; "
            "object-src 'none'; "
            "connect-src 'self' https://*.amazonaws.com https://*.amazoncognito.com",
            "Strict-Transport-Security": "max-age=31536000; "
            "includeSubdomains; "
            "preload",
            "Referrer-Policy": "same-origin",
            "X-XSS-Protection": "1; mode=block",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
        }

    def _get_oauth_scopes(self):
        """Retrieve the oauth scopes from the variables or return the default."""
        if self.parameters.get("staticsite_oauth_scopes"):
            return self.parameters.get("staticsite_oauth_scopes")
        return ["phone", "email", "profile", "openid", "aws.cognito.signin.user.admin"]

    def _get_supported_identity_providers(self):
        providers = self.parameters.get("staticsite_supported_identity_providers")
        if providers:
            return [provider.strip() for provider in providers.split(",")]
        return ["COGNITO"]

    def _get_dependencies_variables(self):
        variables = {"OAuthScopes": self._get_oauth_scopes()}
        if self.parameters.get("staticsite_auth_at_edge", False):
            self._ensure_auth_at_edge_requirements()

            variables.update(
                {
                    "AuthAtEdge": self.parameters.get("staticsite_auth_at_edge", False),
                    "SupportedIdentityProviders": self._get_supported_identity_providers(),
                    "RedirectPathSignIn": (
                        "${default staticsite_redirect_path_sign_in::/parseauth}"
                    ),
                    "RedirectPathSignOut": (
                        "${default staticsite_redirect_path_sign_out::/}"
                    ),
                }
            )

            if self.parameters.get("staticsite_aliases"):
                variables.update(
                    {"Aliases": self.parameters.get("staticsite_aliases").split(",")}
                )
            if self.parameters.get("staticsite_additional_redirect_domains"):
                variables.update(
                    {
                        "AdditionalRedirectDomains": self.parameters.get(
                            "staticsite_additional_redirect_domains"
                        ).split(",")
                    }
                )
            if self.parameters.get("staticsite_create_user_pool", False):
                variables.update(
                    {
                        "CreateUserPool": self.parameters.get(
                            "staticsite_create_user_pool", False
                        )
                    }
                )

        return variables

    def _get_user_pool_id_retriever_variables(self):
        args = {
            "user_pool_arn": self.parameters.get("staticsite_user_pool_arn", ""),
        }

        if self.parameters.get("staticsite_create_user_pool", False):
            args[
                "created_user_pool_id"
            ] = "${rxref %s-dependencies::AuthAtEdgeUserPoolId}" % (self.name)

        return args

    def _get_domain_updater_variables(self):
        return {
            "client_id_output_lookup": "%s-dependencies::AuthAtEdgeClient" % self.name,
            "client_id": "${rxref %s-dependencies::AuthAtEdgeClient}" % self.name,
        }

    def _get_lambda_config_variables(
        self, site_stack_variables, nonce_secret_param, required_group=None
    ):
        return {
            "client_id": "${rxref %s-dependencies::AuthAtEdgeClient}" % self.name,
            "bucket": "${rxref %s-dependencies::ArtifactsBucketName}" % self.name,
            "cookie_settings": site_stack_variables["CookieSettings"],
            "http_headers": site_stack_variables["HttpHeaders"],
            "nonce_signing_secret_param_name": nonce_secret_param,
            "oauth_scopes": site_stack_variables["OAuthScopes"],
            "redirect_path_refresh": site_stack_variables["RedirectPathAuthRefresh"],
            "redirect_path_sign_in": site_stack_variables["RedirectPathSignIn"],
            "redirect_path_sign_out": site_stack_variables["RedirectPathSignOut"],
            "required_group": required_group,
        }

    def _get_client_updater_variables(self, name, site_stack_variables):
        aliases = [add_url_scheme(x) for x in site_stack_variables["Aliases"]]
        return {
            "alternate_domains": aliases,
            "client_id": "${rxref %s-dependencies::AuthAtEdgeClient}" % self.name,
            "distribution_domain": "${rxref %s::CFDistributionDomainName}" % name,
            "oauth_scopes": site_stack_variables["OAuthScopes"],
            "redirect_path_sign_in": site_stack_variables["RedirectPathSignIn"],
            "redirect_path_sign_out": site_stack_variables["RedirectPathSignOut"],
            "supported_identity_providers": site_stack_variables[
                "SupportedIdentityProviders"
            ],
        }

    def _ensure_auth_at_edge_requirements(self):
        if not (
            self.parameters.get("staticsite_user_pool_arn")
            or self.parameters.get("staticsite_create_user_pool")
        ):
            self.logger.error(
                "staticsite_user_pool_arn or staticsite_create_user_pool "
                "is required for Auth@Edge; "
            )
            sys.exit(1)

    def _ensure_correct_region_with_auth_at_edge(self):
        """Exit if not in the us-east-1 region and deploying to Auth@Edge.

        Lambda@Edge is only available within the us-east-1 region.
        """
        if (
            self.parameters.get("staticsite_auth_at_edge", False)
            and self.region != "us-east-1"
        ):
            self.logger.error("Auth@Edge must be deployed in us-east-1.")
            sys.exit(1)

    def _ensure_cloudfront_with_auth_at_edge(self):
        """Exit if both the Auth@Edge and CloudFront disablement are true."""
        if self.parameters.get("staticsite_cf_disable", False) and self.parameters.get(
            "staticsite_auth_at_edge", False
        ):
            self.logger.error(
                'staticsite_cf_disable must be "false" if '
                'staticsite_auth_at_edge is "true"'
            )
            sys.exit(1)

    def _ensure_valid_environment_config(self):
        """Exit if config is invalid."""
        if not self.parameters.get("namespace"):
            self.logger.error("namespace parameter is required but not defined")
            sys.exit(1)

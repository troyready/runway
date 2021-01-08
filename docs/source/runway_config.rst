.. _runway-config:

##################
Runway Config File
##################

The Runway config file is where all options are defined.
It contains definitions for deployments, tests, and some global options that impact core functionality.

The Runway config file can have two possible names, ``runway.yml`` or ``runway.yaml``.
It must be stored at the root of the directory containing the modules to be deployed.

***********************
Top-Level Configuration
***********************

.. attribute:: deployments
  :type: List[deployment]

  A list of deployments that will be processed in the order they are defined.
  See Deployment_ for detailed information about defining this value.

  .. rubric:: Example
  .. code-block:: yaml

    deployments:
      - name: example
        modules:
          - sampleapp-01.cfn
          - path: sampleapp-02.cfn
        regions:
          - us-east-1

.. attribute:: future
  :type: Dict[str, bool]

  Toggles to opt-in to future, potentially backward compatibility breaking functionality before it is made standard in the next major release.

  Availability of these toggles will be removed at each major release as the functionality will then be made standard.

  .. data:: strict_environments
    :type: bool
    :value: false

    When enabled, handling of ``environments`` for Deployment_ and Module_ definitions is changed to prevent processing of modules when the current environment is not defined in the Runway config file.

    If ``environments`` is defined and the current :ref:`deploy environment <term-deploy-env>` is not in the definition, the module will be skipped.
    If ``environments`` is not defined, the module will be processed. This does not mean that action will be taken but that the type of the module will then determine if action will be taken.

    .. rubric:: Example
    .. code-block:: yaml

        future:
          strict_environments: true

        deployments:
          - environments:
              prod:
                - 111111111111/us-east-1
                - 111111111111/us-west-2
              dev:
                - 222222222222
            modules:
              - path: sampleapp-01.cfn
              - path: sampleapp-02.cfn
                environments:
                  dev: 222222222222/us-east-1
                  feature/something-new: true
            regions: &regions
              - ca-central-1
              - us-east-1
              - us-west-2
          - modules:
              - path: sampleapp-03.cfn
              - path: sampleapp-04.cfn
                environments:
                  dev-ca:
                    - ca-cental-1
            regions: *regions

    Given the above Runway configuration file, the following will occur for each module:

    **sampleapp-01.cfn**
      Processed if:

      - environment is **prod** and AWS account ID is **111111111111** and region is (**us-east-1** or **us-west-2**)
      - environment is **dev** and AWS account ID is **222222222222** and region is *anything*

      All other combinations will result in the module being skipped.

    **sampleapp-02.cfn**
      Processed if:

      - environment is **prod** and AWS account ID is **111111111111** and region is (**us-east-1** or **us-west-2**)
      - environment is **dev** and AWS account ID is **222222222222** and region is **us-east-1**
      - environment is **feature/something-new** and AWS account ID is *anything* and region is *anything*

      All other combinations will result in the module being skipped.

    **sampleapp-03.cfn**
      Processed if:

      - environment is *anything* and AWS account ID is *anything* and region is *anything*

    **sampleapp-04.cfn**
      Processed if:

      - environment is **dev-ca** and AWS account ID is *anything* and region is **ca-central-1**

      All other combinations will result in the module being skipped.

.. attribute:: ignore_git_branch
  :type: bool
  :value: false

  Optionally exclude the git branch name when determining the current :ref:`deploy environment <term-deploy-env>`.

  This can be useful when using the directory name or environment variable to set the :ref:`deploy environment <term-deploy-env>` to ensure the correct value is used.

  .. rubric:: Example
  .. code-block:: yaml

    ignore_git_branch: true

  .. note:: The existence of ``DEPLOY_ENVIRONMENT`` in the environment will automatically ignore the git branch.

.. attribute:: runway_version
  :type: str
  :value: ">=1.10.0"

  Define the versions of Runway that can be used with this configuration file.

  The value should be a `PEP 440 <https://www.python.org/dev/peps/pep-0440/>`__ compliant version specifier set.

  .. rubric:: Example
  .. code-block:: yaml
    :caption: greater than or equal to 1.14.0

    runway_version: ">=1.14.0"

  .. code-block:: yaml
    :caption: explicit version

    runway_version: "==14.0.0"

  .. code-block:: yaml
    :caption: greater than or equal to 1.14.0 but less than 2.0.0

    runway_version: ">=1.14.0,<2.0.0"  # or ~=1.14.0

.. attribute:: tests
  :type: Optional[List[test]]
  :value: []

  List of Runway test definitions that are executed with the :ref:`test command <command-test>` command.
  See Test_ for detailed information about defining this value.

  .. rubric:: Example
  .. code-block:: yaml

    tests:
      - name: Hello World
        type: script
        args:
          commands:
            - echo "Hello World"

.. _runway-variables:

.. attribute:: variables
  :type: Optional[Dict[str, Any]]
  :value: {}

  Runway variables are used to fill values that could change based on any number of circumstances.
  They can also be used to simplify the Runway config file by pulling lengthy definitions into another YAML file.
  Variables can be consumed in the config file by using the :ref:`var lookup <var-lookup>` in any field that supports :ref:`Lookups <Lookups>`.

  By default, Runway will look for and load a ``runway.variables.yml`` or ``runway.variables.yaml`` file that is in the same directory as the Runway config file.
  The file path and name of the file can optionally be defined in the config file.
  If the file path is explicitly provided and the file can't be found, an error will be raised.

  Variables can also be defined in the Runway config file directly.
  This can either be in place of a dedicated variables file, extend an existing file, or override values from the file.

  .. important::
    The :attr:`variables` and the variables file cannot contain lookups.
    If there is a lookup string in either of these locations, they will not be resolved.

  .. rubric:: Example
  .. code-block:: yaml

    deployments:
      - modules:
          - path: sampleapp.cfn
        env_vars: ${var env_vars}  # exists in example-file.yml
        parameters:
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
        regions: ${var regions.${env DEPLOY_ENVIRONMENT}}

    variables:
      file_path: example-file.yml
      namespace: example
      regions:
        dev:
          - us-east-1
          - us-west-2

  .. data:: variables.file_path
    :type: Optional[str]

    Explicit path to a variables file that will be loaded and merged with the variables defined here.

    .. rubric:: Example
    .. code-block:: yaml

      variables:
        file_path: some-file.yml

  .. data:: variables.sys_path
    :type: Optional[str]
    :value: ./

    Directory to use as the root of a relative :data:`variables.file_path`.
    If not provided, the current working directory is used.

    .. rubric:: Example
    .. code-block:: yaml

      variables:
        sys_path: ./../variables


----


.. _runway-deployment:

**********
Deployment
**********

.. class:: deployment

  A deployment defines modules and options that affect the modules.

  Deployments are processed during a :ref:`deploy <command-deploy>`/:ref:`destroy <command-destroy>`/:ref:`plan <command-plan>` action.
  If the processing of one deployment fails, the action will end.

  During a :ref:`deploy <command-deploy>`/:ref:`destroy <command-destroy>` action, the user has the option to select which deployment will run unless the ``CI`` environment variable (``--ci`` cli option) is set, the ``--tag <tag>...`` cli option was provided, or only one deployment is defined.

  .. rubric:: Lookup Support

  .. important::
    Due to how a deployment is processed, some values are resolved twice.
    Once before processing and once during processing.

    Because of this, the fields that are resolved before processing begins will not have access to values set during processing like ``AWS_REGION``, ``AWS_DEFAULT_REGION``, and ``DEPLOY_ENVIRONMENT`` for the pre-processing resolution which can result in a :exc:`FailedLookup` error.
    To avoid errors during the first resolution due to the value not existing, provide a default value for the :ref:`Lookup <Lookups>`.

    The values mentioned will be set before the second resolution when processing begins.
    This ensures that the correct values are passed to the module.

    Impacted fields are marked with an asterisk (*).

  The following fields support lookups:

  - :attr:`~deployment.account_alias` *
  - :attr:`~deployment.account_id` *
  - :attr:`~deployment.assume_role` *
  - :attr:`~deployment.env_vars` *
  - :attr:`~deployment.environments`
  - :attr:`~deployment.module_options`
  - :attr:`~deployment.parallel_regions` *
  - :attr:`~deployment.parameters`
  - :attr:`~deployment.regions` *


  .. attribute:: account_alias
    :type: Optional[Union[Dict[str, str], str]]
    :value: {}

    An `AWS account alias <https://docs.aws.amazon.com/IAM/latest/UserGuide/console_account-alias.html>`__ use to verify the currently assumed role or credentials.
    Verification is performed by listing the account's alias and comparing the result to what is defined.
    This requires the credentials being used to have ``iam:ListAccountAliases`` permissions.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a literal value

      deployments:
        - account_alias: example-dev

    .. code-block:: yaml
      :caption: using a lookup

      deployments:
        - account_alias: example-${env DEPLOY_ENVIRONMENT}
        - account_alias: ${var account_alias.${env DEPLOY_ENVIRONMENT}}

      variables:
        account_alias:
          dev: example-dev

    .. code-block:: yaml
      :caption: using an environment map

      deployments:
      - account_alias:
          dev: example-dev

  .. attribute:: account_id
    :type: Optional[Union[Dict[str, str], str]]
    :value: {}

    An AWS account ID use to verify the currently assumed role or credentials.
    Verification is performed by `getting the caller identity <https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html>`__.
    This does not required any added permissions as it is allowed by default.
    However, it does require that ``sts:GetCallerIdentity`` is not explicitly denied.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a literal value

      deployments:
        - account_id: 123456789012

    .. code-block:: yaml
      :caption: using a lookup

      deployments:
        - account_id: ${var account_id.${env DEPLOY_ENVIRONMENT}}

      variables:
        account_id:
          dev: 123456789012

    .. code-block:: yaml
      :caption: using an environment map

      deployments:
      - account_id:
          dev: 123456789012

  .. attribute:: assume_role
    :type: Optional[assume_role_definition, str]
    :value: {}

    Assume an AWS IAM role when processing the deployment.
    The credentials being used prior to assuming the role must to ``iam:AssumeRole`` permissions for the role provided.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a literal value

      deployments:
        - assume_role: arn:aws:iam::123456789012:role/name

    .. code-block:: yaml
      :caption: using a lookup in a detailed definition

      deployments:
        - assume_role:
            arn: ${var assume_role.${env DEPLOY_ENVIRONMENT}}
            post_deploy_env_revert: True

      variables:
        assume_role:
          dev:
            arn:aws:iam::123456789012:role/name

    .. class:: assume_role_definition

      .. attribute:: arn
        :type: str

        The ARN of the AWS IAM role to be assumed.

      .. attribute:: duration
        :type: int
        :value: 3600

        The duration, in seconds, of the session.

      .. attribute:: post_deploy_env_revert
        :type: bool
        :value: false

        Revert the credentials stored in environment variables to what they were prior to execution after the deployment finished processing.

      .. attribute:: session_name
        :type: str
        :value: runway

        An identifier for the assumed role session.

  .. attribute:: env_vars
    :type: Optional[Dict[str, Union[List[str], str]]]
    :value: {}

    Additional variables to add to the environment when processing the deployment.

    Anything defined here is merged with the value of :attr:`module.env_vars`.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - env_vars:
            NAME: value
            KUBECONFIG:
              - .kube
              - ${env DEPLOY_ENVIRONMENT}
              - config

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
        - env_vars: ${var env_vars.${env DEPLOY_ENVIRONMENT}}

      variables:
        env_vars:
          dev:
            NAME: value

  .. attribute:: environments
    :type: Optional[Dict[str, Union[bool, List[str], str]]]
    :value: {}

    Explicitly enable/disable the deployment for a specific deploy environment, AWS Account ID, and AWS Region combination.
    Can also be set as a static boolean value.

    Anything defined here is merged with the value of :attr:`module.environments`.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - environments:
            dev: True
            test: 123456789012
            qa: us-east-1
            prod:
              - 123456789012/ca-central-1
              - us-west-2
              - 234567890123

    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - environments: ${var environments}

      variables:
        environments:
          dev: True

  .. attribute:: modules
    :type: List[Union[module, str]]

    A list of modules to process as part of a deployment.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - modules:
            - sampleapp-01.cfn
            - path: sampleapp-02.cfn

  .. attribute:: module_options
    :type: Optional[Union[Dict[str, Any], str]]
    :value: {}

    Options that are passed directly to the modules within this deployment.

    Anything defined here is merged with the value of :attr:`module.options`.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - module_options:
            example: value

    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - module_options:
            example: ${var example}

      variables:
        example: value

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
        - module_options: ${var parameters}

      variables:
        parameters:
          example: value

  .. attribute:: name
    :type: Optional[str]

    The name of the deployment to be displayed in logs and the interactive selection menu.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - name: networking

  .. attribute:: parallel_regions
    :type: Optional[Union[List[str], str]]
    :value: []

    A list of AWS Regions to process asynchronously.

    Only one of :attr:`~deployment.parallel_regions` or :attr:`~deployment.regions` can be defined.

    Asynchronous deployment only takes effect when running non-interactively.
    Otherwise processing will occur synchronously.

    :attr:`assume_role.post_deploy_env_revert <assume_role_definition.post_deploy_env_revert>` will always be ``true`` when run in parallel.

    Can be used in tandem with :attr:`module.parallel`.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - parallel_regions:
            - us-east-1
            - us-west-2
            - ${var third_region.${env DEPLOY_ENVIRONMENT}}

      variables:
        third_region:
          dev: ca-central-1

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
          - parallel_regions: ${var regions.${env DEPLOY_ENVIRONMENT}}

        variables:
          regions:
            - us-east-1
            - us-west-2

  .. attribute:: parameters
    :type: Optional[Union[Dict[str, Any], str]]
    :value: {}

    Used to pass variable values to modules in place of an environment configuration file.

    Anything defined here is merged with the value of :attr:`module.parameters`.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - parameters:
            namespace: example-${env DEPLOY_ENVIRONMENT}

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
        - parameters: ${var parameters.${env DEPLOY_ENVIRONMENT}}

      variables:
        parameters:
          dev:
            namespace: example-dev

  .. attribute:: regions
    :type: Optional[Union[Dict[str, Union[List[str], str], List[str], str]]
    :value: []

    A list of AWS Regions to process this deployment in.

    Only one of :attr:`~deployment.parallel_regions` or :attr:`~deployment.regions` can be defined.

    Can be used to define asynchronous processing similar to :attr:`~deployment.parallel_regions`.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: synchronous

      deployments:
        - regions:
            - us-east-1
            - us-west-2

    .. code-block:: yaml
      :caption: asynchronous

      deployments:
        - regions:
            parallel:
              - us-east-1
              - us-west-2
              - ${var third_region.${env DEPLOY_ENVIRONMENT}}

      variables:
        third_region:
          dev: ca-central-1

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
          - regions: ${var regions.${env DEPLOY_ENVIRONMENT}}

        variables:
          regions:
            - us-east-1
            - us-west-2


----


.. _runway-module:

******
Module
******

.. class:: module

  A module defines the directory to be processed and applicable options.

  It can consist of :ref:`CloudFormation <mod-cfn>`, :ref:`Terraform <mod-tf>`, :ref:`Serverless Framework <mod-sls>`, :ref:`AWS CDK <mod-cdk>`, :ref:`Kubernetes <mod-k8s>`, or a :ref:`Static Site<mod-staticsite>`.
  It is recommended to place the appropriate extension on each directory for identification (but it is not required).
  See :ref:`Repo Structure<repo-structure>` for examples of a module directory structure.

  +------------------+-----------------------------------------------+
  | Suffix/Extension | IaC Tool/Framework                            |
  +==================+===============================================+
  | ``.cdk``         | :ref:`AWS CDK <mod-cdk>`                      |
  +------------------+-----------------------------------------------+
  | ``.cfn``         | :ref:`CloudFormation <mod-cfn>`               |
  +------------------+-----------------------------------------------+
  | ``.sls``         | :ref:`Serverless Framework <mod-sls>`         |
  +------------------+-----------------------------------------------+
  | ``.tf``          | :ref:`Terraform <mod-tf>`                     |
  +------------------+-----------------------------------------------+
  | ``.k8s``         | :ref:`Kubernetes <mod-k8s>`                   |
  +------------------+-----------------------------------------------+
  | ``.web``         | :ref:`Static Site<mod-staticsite>`            |
  +------------------+-----------------------------------------------+

  A module is only deployed if there is a corresponding environment file present, it is explicitly enabled via :attr:`deployment.environments`/:attr:`module.environments`, or :attr:`deployment.parameters`/:attr:`module.parameters` is defined.
  The naming format of an environment file varies per module type.
  See :ref:`Module Configurations<module-configurations>` for acceptable environment file name formats.

  Modules can be defined as a string or a mapping.
  The minimum requirement for a module is a string that is equal to the name of the module directory.
  Providing a string is the same as providing a value for :attr:`~module.path` in a mapping definition.

  Using a mapping to define a module provides the ability to specify all the fields listed here.

  .. rubric:: Lookup Support

  The following fields support lookups:

  - :attr:`~module.class_path`
  - :attr:`~module.env_vars`
  - :attr:`~module.environments`
  - :attr:`~module.options`
  - :attr:`~module.parameters`
  - :attr:`~module.path`

  .. attribute:: class_path
    :type: Optional[str]
    :value: null

    .. note::
      Most users will never need to use this.
      It is only used for custom module types.

    Import path to a custom Runway module class.
    See :ref:`Module Configurations<module-configurations>` for detailed usage.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - modules:
          - class_path: runway.module.cloudformation.CloudFormation

  .. attribute:: env_vars
    :type: Optional[Dict[str, Union[List[str], str]]]
    :value: {}

    Additional variables to add to the environment when processing the deployment.

    Anything defined here is merged with the value of :attr:`deployment.env_vars`.
    Values defined here take precedence.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - modules:
          - env_vars:
              NAME: VALUE
              KUBECONFIG:
                - .kube
                - ${env DEPLOY_ENVIRONMENT}
                - config

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
        - modules:
            - env_vars: ${var env_vars.${env DEPLOY_ENVIRONMENT}}

      variables:
        env_vars:
          dev:
            NAME: value

  .. attribute:: environments
    :type: Optional[Dict[str, Union[bool, List[str], str]]]
    :value: {}

    Explicitly enable/disable the deployment for a specific deploy environment, AWS Account ID, and AWS Region combination.
    Can also be set as a static boolean value.

    Anything defined here is merged with the value of :attr:`deployment.environments`.
    Values defined here take precedence.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - modules:
          - environments:
            dev: True
            test: 123456789012
            qa: us-east-1
            prod:
              - 123456789012/ca-central-1
              - us-west-2
              - 234567890123

    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - modules:
          - environments: ${var environments}

      variables:
        environments:
          dev: True

  .. attribute:: name
    :type: Optional[str]

    The name of the module to be displayed in logs and the interactive selection menu.

    If a name is not provided, the :attr:`~module.path` value is used.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - modules:
          - name: networking

  .. attribute:: options
    :type: Optional[Union[Dict[str, Any], str]]
    :value: {}

    Options that are passed directly to the module type class.

    The options that can be used with each module vary.
    For detailed information about options for each type of module, see :ref:`Module Configurations<module-configurations>`.

    Anything defined here is merged with the value of :attr:`deployment.module_options`.
    Values defined here take precedence.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - module:
          - options:
              example: value

    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - module:
          - options:
              example: ${var example}

      variables:
        example: value

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
        - module:
          - options: ${var parameters}

      variables:
        parameters:
          example: value

  .. attribute:: parallel
    :type: Optional[List[module]]
    :value: []

    List of `module` definitions that can be executed asynchronously.

    Incompatible with :attr:`~module.class_path`, :attr:`~module.path`, and :attr:`~module.type`.

    Asynchronous deployment only takes effect when running non-interactively.
    Otherwise processing will occur synchronously.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - modules:
          - parallel:
            - path: sampleapp-01.cfn
            - path: sampleapp-02.cfn

  .. attribute:: parameters
    :type: Optional[Union[Dict[str, Any], str]]
    :value: {}

    Used to pass variable values to modules in place of an environment configuration file.

    Anything defined here is merged with the value of :attr:`deployment.parameters`.
    Values defined here take precedence.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a lookup as the value

      deployments:
        - modules:
          - parameters:
              namespace: example-${env DEPLOY_ENVIRONMENT}

    .. code-block:: yaml
      :caption: using a lookup in the value

      deployments:
        - modules:
          - parameters: ${var parameters.${env DEPLOY_ENVIRONMENT}}

      variables:
        parameters:
          dev:
            namespace: example-dev

  .. attribute:: path
    :type: Optional[Union[str, Path]]

    Directory (relative to the Runway config file) containing IaC.
    The directory can either be on the local file system or a network accessible location.

    See path_ for more detailed information.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a lookup

      deployments:
        - modules:
          - path: sampleapp-${env DEPLOY_ENVIRONMENT}.cfn

  .. attribute:: tags
    :type: Optional[List[str]]
    :value: []

    A list of files to categorize the module which can be used with the CLI to quickly select a group of modules.

    This field is only used by the ``--tag`` CLI option.

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - modules:
          - tags:
            - app:sampleapp
            - type:network

  .. attribute:: type
    :type: Optional[str]

    Explicitly define the type of IaC contained within the directory.
    This can be useful when Runway fails to automatically determine the correct module type.

    .. rubric:: Accepted Values

    - cdk
    - cloudformation
    - serverless
    - terraform
    - kubernetes
    - static

    .. rubric:: Example
    .. code-block:: yaml

      deployments:
        - modules:
          - type: static


.. _runway-module-path:

path
====

:attr:`~module.path` can either be defined as a local path relative to the Runway config file or a network accessible (remote) location.

When the value is identified as a remote location, Runway is responsible for retrieving resources from the location and caching them locally for processing.
This allows the remote resources to be handled automatically by Runway rather than needing to manually retrieve them or employ another mechanism to retrieve them.

Remote Location Syntax
----------------------

They syntax is based on that of `Terraform module sources <https://www.terraform.io/docs/modules/sources.html>`__.

.. code-block:: shell

  ${source}::${uri}//${location}?${arguments}

:source:
  Combined with the following ``::`` separator, it is used to identify the location as remote.
  The value determines how Runway with handle retrieving resources from the remote location.

:uri:
  The uniform resource identifier when targeting a remote resource.
  This instructs runway on where to retrieve your module.

:location:
  An optional location within the remote location (assessed after the resources have been retrieve) relative to the root of the retrieve resources.

  This field is preceded by a ``//``. If not defining a location, this separator does not need to be provided.

:arguments:
  An optional comma delimited list of ``key=value`` pairs that are unique to each remote location source.
  These are used to provide granular control over how Runway retrieves resources from the remote location.

  This field is preceded by a ``?``. If not defining a location, this separator does not need to be provided.


Remote Location Sources
-----------------------

.. _runway-module-path-git:

Git Repository
^^^^^^^^^^^^^^

Runway can retrieve a git repository to process modules contained within it.
Below is an example of using a module in a git repository as well as a breakdown of the values being provided to each field.

.. code-block:: yaml

  deployments:
      - modules:
          # ${source}::${uri}//${location}?${arguments}
          - path: git::git://github.com/foo/bar.git//my/path?branch=develop

+-----------+----------------------------------+------------------------------------------------------+
| Field     | Value                            | Description                                          |
+===========+==================================+======================================================+
| source    | ``git``                          | The *type* of remote location source.                |
+-----------+----------------------------------+------------------------------------------------------+
| uri       | ``git://github.com/foo/bar.git`` | The protocol and URI address of the git repository.  |
+-----------+----------------------------------+------------------------------------------------------+
| location  | ``my/path``                      | | The relative path from the root of the repo where  |
|           |                                  | | the module is located. *(optional)*                |
+-----------+----------------------------------+------------------------------------------------------+
| arguments | ``branch=develop``               | | After cloning the repository, checkout the develop |
|           |                                  | | branch. *(optional)*                               |
+-----------+----------------------------------+------------------------------------------------------+

.. rubric:: Arguments

:branch:
  Name of a branch to checkout after cloning the git repository.

  Only one of *branch*, *commit*, or *tag* can be defined.
  If none are defined, *HEAD* is used.

:commit:
  After cloning the git repository, reset *HEAD* to the given commit hash.

  Only one of *branch*, *commit*, or *tag* can be defined.
  If none are defined, *HEAD* is used.

:tag:
  After cloning the git repository, reset *HEAD* to the given tag.

  Only one of *branch*, *commit*, or *tag* can be defined.
  If none are defined, *HEAD* is used.


----


.. _runway-test:

****
Test
****

.. class:: test

  Tests can be defined as part of the Runway config file.
  This is to remove the need for complex Makefiles or scripts to initiate test runners.
  Simply define all tests for a project in the Runway config file and use the :ref:`test command<command-test>` to execute them.

  .. rubric:: Lookup Support

  .. note::
    Runway does not set ``AWS_REGION`` or ``AWS_DEFAULT_REGION`` environment variables when using the :ref:`test command<command-test>`.

  The following fields support lookups:

  - :attr:`test.args`
  - :attr:`test.required`

  .. attribute:: args
    :type: Optional[Union[Dict[str, Any], str]]
    :value: {}

    Arguments to be passed to the test.
    Supported arguments vary by test type.
    See :ref:`Build-in Test Types<built-in-test-types>` for the arguments supported by each test type.

    .. rubric:: Example
    .. code-block:: yaml

      tests:
        - args:
            commands:
              - echo "Hello world"

  .. attribute:: name
    :type: Optional[str]

    Name of the test.
    Used to more easily identify where different tests begin/end in the logs and to identify which tests failed.

    .. rubric:: Example
    .. code-block:: yaml

      tests:
        - name: example-test

  .. attribute:: required
    :type: bool
    :value: false

    Whether the test must pass for subsequent tests to be run.
    If ``false``, testing will continue if the test fails.

    If the test fails, the :ref:`test command <command-test>` will always return a non-zero exit code regardless of this value.

    .. rubric:: Example
    .. code-block:: yaml
      :caption: using a literal value

      tests:
        - required: false

    .. code-block:: yaml
      :caption: using a lookup

      tests:
        - required: ${var test.required}

      variables:
        test:
          required: false

  .. attribute:: type
    :type: str

    The type of test to run.

    .. rubric:: Accepted Values

    - :ref:`cfn-lint <built-in-test-cfn-lint>`
    - :ref:`script <built-in-test-script>`
    - :ref:`yamllint <built-in-test-yamllint>`

    .. rubric:: Example
    .. code-block:: yaml

      tests:
        - type: script


******
Sample
******

.. rubric:: runway.yml
.. code-block:: yaml

    ---
    # Order that tests will be run. Test execution is triggered with the
    # 'runway test' command. Testing will fail and exit if any of the
    # individual tests fail unless they are marked with 'required: false'.
    # Please see the doc section dedicated to tests for more details.

    tests:
      - name: test-names-are-optional
        type: script  # there are a few built in test types
        args:  # each test has their own set of arguments they can accept
          commands:
            - echo "Beginning a test..."
            - cd app.sls && npm test && cd ..
            - echo "Test complete!"
      - name: unimportant-test
        type: cfn-lint
        required: false  # tests will still pass if this fails
      - type: yamllint  # not all tests accept arguments

    # Order that modules will be deployed. A module will be skipped if a
    # corresponding environment file is not present or "enabled" is false.
    # E.g., for cfn modules, if
    # 1) a dev-us-west-2.env file is not in the 'app.cfn' folder when running
    #    a dev deployment of 'app' to us-west-2,
    # and
    # 2) "enabled" is false under the deployment or module
    #
    # then it will be skipped.

    deployments:
      - modules:
          - myapp.cfn
        regions:
          - us-west-2

      - name: terraformapp  # deployments can optionally have names
        modules:
          - myapp.tf
        regions:
          - us-east-1
        assume_role:  # optional
          # When running multiple deployments, post_deploy_env_revert can be used
          # to revert the AWS credentials in the environment to their previous
          # values
          # post_deploy_env_revert: true
          arn: ${var assume_role.${env DEPLOY_ENVIRONMENT}}
          # duration: 7200

        # Parameters (e.g. values for CFN .env file, TF .tfvars) can
        # be provided at the deployment level -- the options will be applied to
        # every module
        parameters:
          region: ${env AWS_REGION}
          image_id: ${var image_id.${env DEPLOY_ENVIRONMENT}}

        # AWS account alias can be provided to have Runway verify the current
        # assumed role / credentials match the necessary account
        account_alias: ${var account_alias.${env DEPLOY_ENVIRONMENT}}  # optional

        # AWS account id can be provided to have Runway verify the current
        # assumed role / credentials match the necessary account
        account_id: ${var account_id.${env DEPLOY_ENVIRONMENT}}  # optional

        # env_vars set OS environment variables for the module (not logical
        # environment values like those in a CFN .env or TF .tfvars file).
        # They should generally not be used (they are provided for use with
        # tools that absolutely require it, like Terraform's
        # TF_PLUGIN_CACHE_DIR option)
        env_vars:  # optional environment variable overrides
          AWS_PROFILE: ${var envvars.profile.${env DEPLOY_ENVIRONMENT}}
          APP_PATH: ${var envvars.app_path}
          ANOTHER_VAR: foo

      # Start of another deployment
      - modules:
          - path: myapp.cfn
            # Parameters (e.g. values for CFN .env file, TF .tfvars) can
            # be provided for a single module (replacing or supplementing the
            # use of environment/tfvars/etc files in the module)
            parameters:
              region: ${env AWS_REGION}
              image_id: ${var image_id.${env DEPLOY_ENVIRONMENT}}
            tags:  # Modules can optionally have tags.
              # This is a list of strings that can be "targeted"
              # by passing arguments to the deploy/destroy command.
              - some-string
              - app:example
              - tier:web
              - owner:onica
              # example: `runway deploy --tag app:example --tag tier:web`
              #   This would select any modules with BOTH app:example AND tier:web
        regions:
          - us-west-2

    # If using environment folders instead of git branches, git branch lookup can
    # be disabled entirely (see "Repo Structure")
    # ignore_git_branch: true

.. rubric:: runway.variables.yml
.. code-block:: yaml

  account_alias:
    dev: my_dev_account
    prod: my_dev_account
  account_id:
    dev: 123456789012
    prod: 345678901234
  assume_role:
    dev: arn:aws:iam::account-id1:role/role-name
    prod: arn:aws:iam::account-id2:role/role-name
  image_id:
    dev: ami-abc123
  envvars:
    profile:
      dev: foo
      prod: bar
    app_path:
      - myapp.tf
      - foo

.. _`aws_lambda hook`: ../apidocs/runway.cfngin.hooks.aws_lambda.html#runway.cfngin.hooks.aws_lambda.upload_lambda_functions
.. _`aws_lambda blueprint`: https://github.com/cloudtools/stacker_blueprints/blob/master/stacker_blueprints/aws_lambda.py

.. _cfngin-lookups:

#######
Lookups
#######

.. note:: Runway lookups and CFNgin lookups are not interchangeable. While they
          do share a similar base class and syntax, they exist in two different
          registries. Runway config files can't use CFNgin lookups just as the
          CFNgin config cannot use Runway lookups.

Runway's CFNgin provides the ability to dynamically replace values in the config via a
concept called lookups. A lookup is meant to take a value and convert
it by calling out to another service or system.

A lookup is denoted in the config with the ``${<lookup type> <lookup
input>}`` syntax. If ``<lookup type>`` isn't provided, CFNgin will
fall back to use the ``output`` lookup .

Lookups are only resolved within :ref:`Variables <cfngin-variables>`. They can be nested in any part of a YAML
data structure and within another lookup itself.

.. note::
  If a lookup has a non-string return value, it can be the only lookup
  within a value.

  ie. if ``custom`` returns a list, this would raise an exception::

    Variable: ${custom something}, ${output otherStack::Output}

  This is valid::

    Variable: ${custom something}


For example, given the following:

.. code-block:: yaml

  stacks:
    - name: sg
      class_path: some.stack.blueprint.Blueprint
      variables:
        Roles:
          - ${output otherStack::IAMRole}
        Values:
          Env:
            Custom: ${custom ${output otherStack::Output}}
            DBUrl: postgres://${output dbStack::User}@${output dbStack::HostName}

The Blueprint would have access to the following resolved variables
dictionary:

.. code-block:: python

  # variables
  {
    "Roles": ["other-stack-iam-role"],
    "Values": {
      "Env": {
        "Custom": "custom-output",
        "DBUrl": "postgres://user@hostname",
      },
    },
  }


Runway's CFNgin includes the following lookup types:

- `output lookup`_
- `ami lookup`_
- `cfn lookup`_
- `custom lookup`_
- `default lookup`_
- `dynamodb lookup`_
- `envvar lookup`_
- `file lookup`_
- `hook_data lookup`_
- `kms lookup`_
- `rxref lookup`_
- ssm_ lookup
- `xref lookup`_

**********
cfn Lookup
**********

.. important::
  The Stack must exist in CloudFormation before the config using this Lookup begins processing to successfully get a value.
  This means that it must have been deployed using another Runway module, deployed from a config that is run before the one using it, deployed manually, or deployed in the same config using ``required``/``required_by`` to specify a dependency between the Stacks.

.. automodule:: runway.lookups.handlers.cfn


.. _`output lookup`:

*************
Output Lookup
*************

The ``output`` lookup takes a value of the format:
``<stack name>::<output name>`` and retrieves the output from the given stack
name within the current namespace.

CFNgin treats output lookups differently than other lookups by auto
adding the referenced stack in the lookup as a requirement to the stack
whose variable the output value is being passed to.

You can specify an output lookup with the following syntax:

.. code-block:: yaml

  ConfVariable: ${output someStack::SomeOutput}


.. _`default lookup`:

**************
default Lookup
**************

The ``default`` lookup type will check if a value exists for the variable
in the environment file, then fall back to a default defined in the CFNgin
config if the environment file doesn't contain the variable. This allows
defaults to be set at the config file level, while granting the user the
ability to override that value per environment.

Format of value:

.. code-block:: yaml

  <env_var>::<default value>

.. rubric:: Example
.. code-block:: yaml

  Groups: ${default app_security_groups::sg-12345,sg-67890}

If ``app_security_groups`` is defined in the environment file, its defined
value will be returned. Otherwise, ``sg-12345,sg-67890`` will be the returned
value.

.. note::
  The ``default`` lookup only supports checking if a variable is defined in
  an environment file. It does not support other embedded lookups to see
  if they exist. Only checking variables in the environment file are supported.
  If you attempt to have the default lookup perform any other lookup that
  fails, CFNgin will throw an exception for that lookup and will stop your
  build before it gets a chance to fall back to the default in your config.

.. _`kms lookup`:

**********
KMS Lookup
**********

The ``kms`` lookup type decrypts its input value.

As an example, if you have a database and it has a parameter called
``DBPassword`` that you don't want to store in clear text in your config
(maybe because you want to check it into your version control system to
share with the team), you could instead encrypt the value using ``kms``.

For example::

  # We use the aws cli to get the encrypted value for the string
  # "PASSWORD" using the master key called 'myKey' in us-east-1
  $ aws --region us-east-1 kms encrypt --key-id alias/myKey \
      --plaintext "PASSWORD" --output text --query CiphertextBlob

  CiD6bC8t2Y<...encrypted blob...>

  # With CFNgin we would reference the encrypted value like:
  DBPassword: ${kms us-east-1@CiD6bC8t2Y<...encrypted blob...>}

  # The above would resolve to
  DBPassword: PASSWORD

This requires that the person using CFNgin has access to the master key used
to encrypt the value.

It is also possible to store the encrypted blob in a file (useful if the
value is large) using the ``file://`` prefix, ie::

  DockerConfig: ${kms file://dockercfg}

.. note::
  Lookups resolve the path specified with `file://` relative to
  the location of the config file, not where the CFNgin command is run.


.. _`xref lookup`:

***********
XRef Lookup
***********

.. deprecated:: 1.11.0
  Replaced by `cfn lookup`_

The ``xref`` lookup type is very similar to the ``output`` lookup type, the
difference being that ``xref`` resolves output values from stacks that
aren't contained within the current CFNgin namespace, but are existing stacks
containing outputs within the same region on the AWS account you are deploying
into. ``xref`` allows you to lookup these outputs from the stacks already on
your account by specifying the stacks fully qualified name in the
CloudFormation console.

Where the ``output`` type will take a stack name and use the current context
to expand the fully qualified stack name based on the namespace, ``xref``
skips this expansion because it assumes you've provided it with
the fully qualified stack name already. This allows you to reference
output values from any CloudFormation stack in the same region.

Also, unlike the ``output`` lookup type, ``xref`` doesn't impact stack
requirements.

.. rubric:: Example
.. code-block:: yaml

  ConfVariable: ${xref fully-qualified-stack::SomeOutput}


.. _`rxref lookup`:

************
RXRef Lookup
************

The ``rxref`` lookup type is very similar to the ``xref`` lookup type,
the difference being that ``rxref`` will lookup output values from stacks
that are relative to the current namespace but external to the stack, but
will not resolve them. ``rxref`` assumes the stack containing the output
already exists.

Where the ``xref`` type assumes you provided a fully qualified stack name,
``rxref``, like ``output`` expands and retrieves the output from the given
stack name within the current namespace, even if not defined in the CFNgin
config you provided it.

Because there is no requirement to keep all stacks defined within the same
CFNgin YAML config, you might need the ability to read outputs from other
stacks deployed by CFNgin into your same account under the same namespace.
``rxref`` gives you that ability. This is useful if you want to break up
very large configs into smaller groupings.

Also, unlike the ``output`` lookup type, ``rxref`` doesn't impact stack
requirements.

.. rubric:: Example
.. code-block:: yaml

  # in example-us-east-1.env
  namespace: MyNamespace

  # in cfngin.yaml
  ConfVariable: ${rxref my-stack::SomeOutput}

  # the above would effectively resolve to
  ConfVariable: ${xref MyNamespace-my-stack::SomeOutput}

Although possible, it is not recommended to use ``rxref`` for stacks defined
within the same CFNgin YAML config.


.. _`file lookup`:

***********
File Lookup
***********

The ``file`` lookup type allows the loading of arbitrary data from files on
disk. The lookup additionally supports using a ``codec`` to manipulate or
wrap the file contents prior to injecting it. The parameterized-b64 ``codec``
is particularly useful to allow the interpolation of CloudFormation parameters
in a UserData attribute of an instance or launch configuration.

Basic examples::

  # We've written a file to /some/path:
  $ echo "hello there" > /some/path

  # In CFNgin we would reference the contents of this file with the following
  conf_key: ${file plain:file://some/path}

  # The above would resolve to
  conf_key: hello there

  # Or, if we used wanted a base64 encoded copy of the file data
  conf_key: ${file base64:file://some/path}

  # The above would resolve to
  conf_key: aGVsbG8gdGhlcmUK

.. rubric:: Supported Codecs:

- **plain** - Load the contents of the file untouched. This is the only codec that should be used
  with raw Cloudformation templates (the other codecs are intended for blueprints).
- **base64** - Encode the plain text file at the given path with base64 prior
  to returning it
- **parameterized** - The same as plain, but additionally supports
  referencing CloudFormation parameters to create userdata that's
  supplemented with information from the template, as is commonly needed
  in EC2 UserData. For example, given a template parameter of BucketName,
  the file could contain the following text::

    #!/bin/sh
    aws s3 sync s3://{{BucketName}}/somepath /somepath

  and then you could use something like this in the YAML config file::

    UserData: ${file parameterized:/path/to/file}

  resulting in the UserData parameter being defined as:

  .. code-block:: json

    {
        "Fn::Join" : [
            "",
            [
                "#!/bin/sh\naws s3 sync s3://",
                {
                    "Ref" : "BucketName"
                },
                "/somepath /somepath"
            ]
        ]
    }

- **parameterized-b64** - The same as parameterized, with the results additionally
  wrapped in ``{ "Fn::Base64": ... }`` , which is what you actually need for
  EC2 UserData

  When using parameterized-b64 for UserData, you should use a local parameter defined as such.

  .. code-block:: python

    from troposphere import AWSHelperFn

    "UserData": {
        "type": AWSHelperFn,
        "description": "Instance user data",
        "default": Ref("AWS::NoValue")
    }

  and then assign UserData in a LaunchConfiguration or Instance to ``self.get_variables()["UserData"]``.
  Note that we use AWSHelperFn as the type because the parameterized-b64 codec returns either a Base64 or a GenericHelperFn troposphere object.

- **json** - Decode the file as JSON and return the resulting object
- **json-parameterized** - Same as ``json``, but applying templating rules from
  ``parameterized`` to every object *value*. Note that object *keys* are not
  modified. Example (an external PolicyDocument):

  .. code-block:: json

    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "some:Action"
                ],
                "Resource": "{{MyResource}}"
            }
        ]
    }

- **yaml** - Decode the file as YAML and return the resulting object. All strings
  are returned as ``unicode`` even in Python 2.
- **yaml-parameterized** - Same as ``json-parameterized``, but using YAML.

  .. code-block:: yaml

    Version: 2012-10-17
    Statement:
      - Effect: Allow
        Action:
          - "some:Action"
        Resource: "{{MyResource}}"


***
ssm
***

.. automodule:: runway.lookups.handlers.ssm


.. _`ssmstore lookup`:

**************************
SSM Parameter Store Lookup
**************************

.. deprecated:: 1.5.0
  Replaced by ssm_

The ``ssmstore`` lookup type retrieves a value from the Simple Systems
Manager Parameter Store.

As an example, if you have a database and it has a parameter called
``DBUser`` that you don't want to store in clear text in your config,
you could instead store it as a SSM parameter named ``MyDBUser``.

For example::

  # We use the aws cli to store the database username
  $ aws ssm put-parameter --name "MyDBUser" --type "String" \
      --value "root"

  # In CFNgin we would reference the value like:
  DBUser: ${ssmstore us-east-1@MyDBUser}

  # Which would resolve to:
  DBUser: root

Encrypted values ("SecureStrings") can also be used, which will be
automatically decrypted (assuming the CFNgin user has access to the
associated KMS key). Care should be taken when using this with encrypted
values (i.e. a safe policy is to only use it with ``no_echo`` CFNString
values)

The region can be omitted (e.g. ``DBUser: ${ssmstore MyDBUser}``), in which
case ``us-east-1`` will be assumed.


.. _`dynamodb lookup`:

***************
DynamoDb Lookup
***************

The ``dynamodb`` lookup type retrieves a value from a DynamoDb table.

As an example, if you have a Dynamo Table named ``TestTable`` and it has an Item
with a Primary Partition key called ``TestKey`` and a value named ``BucketName``
, you can look it up by using CFNgin. The lookup key in this case is TestVal

.. rubric:: Example
.. code-block:: yaml

  # We can reference that dynamo value
  BucketName: ${dynamodb us-east-1:TestTable@TestKey:TestVal.BucketName}

  # Which would resolve to:
  BucketName: test-bucket

You can lookup other data types by putting the data type in the lookup. Valid
values are ``S`` (String), ``N`` (Number), ``M`` (Map), ``L`` (List).

.. rubric:: Example
.. code-block:: yaml

  ServerCount: ${dynamodb us-east-1:TestTable@TestKey:TestVal.ServerCount[N]}

This would return an int value, rather than a string

You can lookup values inside of a map.

.. rubric:: Example
.. code-block:: yaml

  ServerCount: ${dynamodb us-east-1:TestTable@TestKey:TestVal.ServerInfo[M].
                                                                ServerCount[N]}


.. _`envvar lookup`:

************************
Shell Environment Lookup
************************

The ``envvar`` lookup type retrieves a value from a variable in the shell's
environment.

Example::

  # Set an environment variable in the current shell.
  $ export DATABASE_USER=root

  # In the CFNgin config we could reference the value:
  DBUser: ${envvar DATABASE_USER}

  # Which would resolve to:
  DBUser: root

You can also get the variable name from a file, by using the ``file://`` prefix
in the lookup, like so::

  DBUser: ${envvar file://dbuser_file.txt}


.. _`ami lookup`:

**************
EC2 AMI Lookup
**************

The ``ami`` lookup is meant to search for the most recent AMI created that
matches the given filters.

Valid arguments::

  region OPTIONAL ONCE:
      e.g. us-east-1@

  owners (comma delimited) REQUIRED ONCE:
      aws_account_id | amazon | self

  name_regex (a regex) REQUIRED ONCE:
      e.g. my-ubuntu-server-[0-9]+

  executable_users (comma delimited) OPTIONAL ONCE:
      aws_account_id | amazon | self

Any other arguments specified are sent as filters to the aws api
For example, "architecture:x86_64" will add a filter.

Example::

  # Grabs the most recently created AMI that is owned by either this account,
  # amazon, or the account id 888888888888 that has a name that matches
  # the regex "server[0-9]+" and has "i386" as its architecture.

  # Note: The region is optional, and defaults to the current CFNgin region
  ImageId: ${ami [<region>@]owners:self,888888888888,amazon name_regex:server[0-9]+ architecture:i386}


.. _`hook_data lookup`:

****************
Hook Data Lookup
****************

When using hooks, you can have the hook store results in the :attr:`Context.hook_data <runway.cfngin.context.Context.hook_data>` dictionary on the context by setting :attr:`~cfngin.hook.data_key` in the :class:`~cfngin.hook` config.

This lookup lets you look up values in that dictionary. A good example of this
is when you use the `aws_lambda hook`_ to upload AWS Lambda code, then need to
pass that code object as the **Code** variable in the `aws_lambda blueprint`_
dictionary.

.. rubric:: Arguments

This Lookup supports all :ref:`Common Lookup Arguments` but, the following have
limited or no effect:

- region

.. rubric:: Example
.. code-block:: yaml

  # If you set the ``data_key`` config on the aws_lambda hook to be "myfunction"
  # and you name the function package "TheCode" you can get the troposphere
  # awslambda.Code object with:

  Code: ${hook_data myfunction.TheCode}

  # If you need to pass the code location as individual strings for use in a
  # CloudFormation template instead of a Blueprint, you can do so like this:

  Bucket: ${hook_data myfunction.TheCode::load=troposphere, get=S3Bucket}
  Key: ${hook_data myfunction.TheCode::load=troposphere, get=S3Key}

.. versionchanged:: 1.5.0
  The ``<hook_name>::<key>`` syntax was deprecated with support being added for the``key.nested_key`` syntax for access data within a dictionary.


.. _`custom lookup`:

*************
Custom Lookup
*************

A custom lookup may be registered within the config.
For more information see :attr:`lookups <cfngin.lookups>`.


Writing A Custom Lookup
=======================

A custom lookup must be in an executable, importable python package or standalone file.
The lookup must be importable using your current ``sys.path``.
This takes into account the :attr:`sys_path <cfngin.sys_path>` defined in the config file as well as any ``paths`` of :attr:`package_sources <cfngin.package_sources>`.

The lookup must be a class, preferable with a base class of :class:`~runway.lookups.handlers.base.LookupHandler` with a ``@classmethod`` of handle that accepts four arguments - ``value``, ``context``,  ``provider``, ``**kwargs``.
There must be only one lookup per file.
The file containing the lookup class must have a ``TYPE_NAME`` global variable with a value of the name that will be used to register the lookup.

The lookup must return a string if being used for a CloudFormation parameter.

If using boto3 in a lookup, use ``context.get_session()`` instead of creating a new session to ensure the correct credentials are used.


.. Example

.. code-block:: python

    """Example lookup."""
    from runway.cfngin.context import Context
    from runway.cfngin.providers.base import BaseProvider
    from runway.cfngin.util import read_value_from_path
    from runway.lookups.handlers.base import LookupHandler

    TYPE_NAME = 'mylookup'

    class MylookupLookup(LookupHandler):
        """My lookup."""

        @classmethod
        def handle(cls,
                   value: str,
                   context: Context,
                   provider: BaseProvider,
                   **kwargs: Any
                   ) -> str:
            """Do something."""
            query, args = cls.parse(read_value_from_path(value))

            # example of using get_session for a boto3 session
            session = context.get_session()
            s3_client = session.client('s3')

            return 'something'

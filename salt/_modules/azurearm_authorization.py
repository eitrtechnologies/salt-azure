# -*- coding: utf-8 -*-
'''
Azure (ARM) Authorization Execution Module

.. versionadded:: Sodium

:maintainer: <devops@eitr.tech>
:maturity: new
:depends:
    * `azure <https://pypi.python.org/pypi/azure>`_ >= 2.0.0
    * `azure-common <https://pypi.python.org/pypi/azure-common>`_ >= 1.1.8
    * `azure-mgmt <https://pypi.python.org/pypi/azure-mgmt>`_ >= 1.0.0
    * `azure-mgmt-compute <https://pypi.python.org/pypi/azure-mgmt-compute>`_ >= 1.0.0
    * `azure-mgmt-network <https://pypi.python.org/pypi/azure-mgmt-network>`_ >= 1.7.1
    * `azure-mgmt-resource <https://pypi.python.org/pypi/azure-mgmt-resource>`_ >= 1.1.0
    * `azure-mgmt-storage <https://pypi.python.org/pypi/azure-mgmt-storage>`_ >= 1.0.0
    * `azure-mgmt-web <https://pypi.python.org/pypi/azure-mgmt-web>`_ >= 0.32.0
    * `azure-storage <https://pypi.python.org/pypi/azure-storage>`_ >= 0.34.3
    * `msrestazure <https://pypi.python.org/pypi/msrestazure>`_ >= 0.4.21
:platform: linux

:configuration: This module requires Azure Resource Manager credentials to be passed as keyword arguments
to every function in order to work properly.

    Required provider parameters:

    if using username and password:
      * ``subscription_id``
      * ``username``
      * ``password``

    if using a service principal:
      * ``subscription_id``
      * ``tenant``
      * ``client_id``
      * ``secret``

    Optional provider parameters:

    **cloud_environment**: Used to point the cloud driver to different API endpoints, such as Azure GovCloud.
    Possible values:
      * ``AZURE_PUBLIC_CLOUD`` (default)
      * ``AZURE_CHINA_CLOUD``
      * ``AZURE_US_GOV_CLOUD``
      * ``AZURE_GERMAN_CLOUD``

'''

# Python libs
from __future__ import absolute_import
import logging

# Azure libs
HAS_LIBS = False
try:
    import azure.mgmt.authorization.models  # pylint: disable=unused-import
    from msrest.exceptions import SerializationError
    from msrestazure.azure_exceptions import CloudError
    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = 'azurearm_authorization'

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_LIBS:
        return (
            False,
            'The following dependencies are required to use the AzureARM modules: '
            'Microsoft Azure SDK for Python >= 2.0rc6, '
            'MS REST Azure (msrestazure) >= 0.4'
        )

    return __virtualname__


def provider_operations_metadata_get(resource_provider_namespace, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets provider operations metadata for the specified resource provider.

    :param resource_provider_namespace: The namespace of the resource provider.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.provider_operations_metadata_get testnamespace

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)
    try:
        data = authconn.provider_operations_metadata.get(
            resource_provider_namespace=resource_provider_namespace,
            api_version='2015-07-01',
            **kwargs
        )

        result = data.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def provider_operations_metadata_list(**kwargs):
    '''
    .. versionadded:: Sodium

    Gets provider operations metadata for all resource providers.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.provider_operations_metadata_list

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        providers = __utils__['azurearm.paged_object_to_list'](
            authconn.provider_operations_metadata.list(
                api_version='2015-07-01',
                **kwargs
            )
        )

        for provider in providers:
            result[provider['name']] = provider
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def permissions_list_for_resource(name, resource_group, resource_provider_namespace, resource_type,
                                  parent_resource_path=None, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets all permissions the caller has for a resource.

    :param name: The name of the resource to get permissions for.

    :param resource_group: The name of the resource group containing the resource. The name is case insensitive.

    :param resource_provider_namespace: The namespace of the resource provider.

    :param resource_type: The resource type of the resource.

    :param parent_resource_path: The namespace of the resource provider.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.permissions_list_for_resource testname testgroup testnamespace \
                  testtype testpath

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    if parent_resource_path is None:
        parent_resource_path = ''

    try:
        perms = __utils__['azurearm.paged_object_to_list'](
            authconn.permissions.list_for_resource(
                resource_name=name,
                resource_group_name=resource_group,
                resource_provider_namespace=resource_provider_namespace,
                resource_type=resource_type,
                parent_resource_path=parent_resource_path,
                **kwargs
            )
        )

        result = perms
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def permissions_list_for_resource_group(name, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets all permissions the caller has for a resource group.

    :param name: The name of the resource group to get the permissions for. The name is case insensitive.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.permissions_list_for_resource_group testname

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        perms = __utils__['azurearm.paged_object_to_list'](
            authconn.permissions.list_for_resource_group(
                resource_group_name=name,
                **kwargs
            )
        )

        result = perms
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_definitions_get(id, scope, **kwargs):
    '''
    .. versionadded:: Sodium

    Get role definition by name (GUID).

    :param id: The ID of the role definition.

    :param scope: The scope of the role definition.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_definitions_get testid testscope

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        defs = authconn.role_definitions.get(
            scope=scope,
            role_definition_id=id,
            **kwargs
        )

        result = defs.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_definitions_get_by_id(id, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets a role definition by ID.

    :param id: The fully qualified role definition ID. Use the format,
        /subscriptions/{guid}/providers/Microsoft.Authorization/roleDefinitions/{roleDefinitionId} for subscription
        level role definitions, or /providers/Microsoft.Authorization/roleDefinitions/{roleDefinitionId} for tenant
        level role definitions.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_definitions_get_by_id testid

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        defs = authconn.role_definitions.get_by_id(
            role_definition_id=id,
            **kwargs
        )

        result = defs.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_definitions_list(scope, **kwargs):
    '''
    .. versionadded:: Sodium

    Get all role definitions that are applicable at scope and above.

    :param scope: The scope of the role definition.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_definitions_list testscope

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        defs = __utils__['azurearm.paged_object_to_list'](
            authconn.role_definitions.list(
                scope=scope,
                filter=kwargs.get('filter'),
                **kwargs
            )
        )

        result = defs
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_assignments_get(name, scope, **kwargs):
    '''
    .. versionadded:: Sodium

    Get the specified role assignment.

    :param name: The name of the role assignment to get.

    :param scope: The scope of the role assignment.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_assignments_get testname testscope

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        assigns = authconn.role_assignments.get(
            role_assignment_name=name,
            scope=scope,
            **kwargs
        )

        result = assigns.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_assignments_get_by_id(id, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets a role assignment by ID.

    :param id: The fully qualified ID of the role assignment, including the scope, resource name and resource type.
        Use the format, /{scope}/providers/Microsoft.Authorization/roleAssignments/{roleAssignmentName}. Example:
        /subscriptions/{subId}/resourcegroups/{rgname}//providers/Microsoft.Authorization/roleAssignments/{roleAssignmentName}.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_assignments_get_by_id testid

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        assigns = authconn.role_assignments.get_by_id(
            role_assignment_id=id,
            **kwargs
            )

        result = assigns.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_assignments_list(**kwargs):
    '''
    .. versionadded:: Sodium

    Gets all role assignments for the subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_assignments_list

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        assigns = __utils__['azurearm.paged_object_to_list'](
            authconn.role_assignments.list(
                filter=kwargs.get('filter'),
                **kwargs
            )
        )

        result = assigns
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_assignments_list_for_resource(name, resource_group, resource_provider_namespace, resource_type,
                                      parent_resource_path=None, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets all role assignments for a resource.

    :param name: The name of the resource to get role assignments for.

    :param resource_group: The name of the resource group.

    :param resource_provider_namespace: The namespace of the resource provider.

    :param resource_type: The resource type of the resource.

    :param parent_resource_path: The parent resource identity.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_assignments_list_for_resource testname testgroup testnamespace \
                  testtype testpath

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    if parent_resource_path is None:
        parent_resource_path = ''

    try:
        assigns = __utils__['azurearm.paged_object_to_list'](
            authconn.role_assignments.list_for_resource(
                resource_name=name,
                resource_group_name=resource_group,
                resource_provider_namespace=resource_provider_namespace,
                resource_type=resource_type,
                parent_resource_path=parent_resource_path,
                filter=kwargs.get('filter'),
                **kwargs
            )
        )

        result = assigns
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_assignments_list_for_resource_group(name, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets all role assignments for a resource group.

    :param name: The name of the resource group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_assignments_list_for_resource_group testgroup

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        assigns = __utils__['azurearm.paged_object_to_list'](
            authconn.role_assignments.list_for_resource_group(
                resource_group_name=name,
                filter=kwargs.get('filter'),
                **kwargs
            )
        )

        result = assigns
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def role_assignments_list_for_scope(scope, **kwargs):
    '''
    .. versionadded:: Sodium

    Gets role assignments for a scope.

    :param scope: The scope of the role assignments.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.role_assignments_list_for_scope testscope

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)

    try:
        assigns = __utils__['azurearm.paged_object_to_list'](
            authconn.role_assignments.list_for_scope(
                scope=scope,
                filter=kwargs.get('filter'),
                **kwargs
            )
        )

        result = assigns
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result

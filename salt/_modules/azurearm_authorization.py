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


def provider_operations_metadata_get(name, **kwargs):
    '''
    TODO EDIT ME I AM NOT DONE
    .. versionadded:: Sodium

    Get a ... stuff

    :param name: The provider to get.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.provider_operations_metadata_get myprovider

    '''
    moniconn = __utils__['azurearm.get_client']('monitor', **kwargs)
    try:
        diag = moniconn.service_diagnostic_settings.get(
            resource_uri=resource_group,
            name=name
        )
        result = diag.as_dict()

    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('monitor', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def provider_operations_metadata_list(**kwargs):
    '''
    .. versionadded:: Sodium

    List all ... stuff

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_authorization.provider_operations_metadata_list

    '''
    result = {}
    authconn = __utils__['azurearm.get_client']('authorization', **kwargs)
    try:
        providers = __utils__['azurearm.paged_object_to_list'](authconn.provider_operations_metadata.list(api_version='2015-07-01'))

        for provider in providers:
            result[provider['name']] = provider
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('authorization', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result

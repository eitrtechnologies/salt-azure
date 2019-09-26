# -*- coding: utf-8 -*-
'''
Azure (ARM) Compute Execution Module

.. versionadded:: 2019.2.0

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
    import azure.mgmt.compute.models  # pylint: disable=unused-import
    from msrest.exceptions import SerializationError
    from msrestazure.azure_exceptions import CloudError
    from msrestazure.tools import is_valid_resource_id
    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = 'azurearm_compute'

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


def availability_set_create_or_update(name, resource_group, **kwargs):  # pylint: disable=invalid-name
    '''
    .. versionadded:: 2019.2.0

    Create or update an availability set.

    :param name: The availability set to create.

    :param resource_group: The resource group name assigned to the
        availability set.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_create_or_update testset testgroup

    '''
    if 'location' not in kwargs:
        rg_props = __salt__['azurearm_resource.resource_group_get'](
            resource_group, **kwargs
        )

        if 'error' in rg_props:
            log.error(
                'Unable to determine location from resource group specified.'
            )
            return False
        kwargs['location'] = rg_props['location']

    compconn = __utils__['azurearm.get_client']('compute', **kwargs)

    # Use VM names to link to the IDs of existing VMs.
    if isinstance(kwargs.get('virtual_machines'), list):
        vm_list = []
        for vm_name in kwargs.get('virtual_machines'):
            vm_instance = __salt__['azurearm_compute.virtual_machine_get'](
                name=vm_name,
                resource_group=resource_group,
                **kwargs
            )
            if 'error' not in vm_instance:
                vm_list.append({'id': str(vm_instance['id'])})
        kwargs['virtual_machines'] = vm_list

    try:
        setmodel = __utils__['azurearm.create_object_model']('compute', 'AvailabilitySet', **kwargs)
    except TypeError as exc:
        result = {'error': 'The object model could not be built. ({0})'.format(str(exc))}
        return result

    try:
        av_set = compconn.availability_sets.create_or_update(
            resource_group_name=resource_group,
            availability_set_name=name,
            parameters=setmodel
        )
        result = av_set.as_dict()

    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}
    except SerializationError as exc:
        result = {'error': 'The object model could not be parsed. ({0})'.format(str(exc))}

    return result


def availability_set_delete(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Delete an availability set.

    :param name: The availability set to delete.

    :param resource_group: The resource group name assigned to the
        availability set.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_delete testset testgroup

    '''
    result = False
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        compconn.availability_sets.delete(
            resource_group_name=resource_group,
            availability_set_name=name
        )
        result = True

    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)

    return result


def availability_set_get(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Get a dictionary representing an availability set's properties.

    :param name: The availability set to get.

    :param resource_group: The resource group name assigned to the
        availability set.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_get testset testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        av_set = compconn.availability_sets.get(
            resource_group_name=resource_group,
            availability_set_name=name
        )
        result = av_set.as_dict()

    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def availability_sets_list(resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    List all availability sets within a resource group.

    :param resource_group: The resource group name to list availability
        sets within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_sets_list testgroup

    '''
    result = {}
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        avail_sets = __utils__['azurearm.paged_object_to_list'](
            compconn.availability_sets.list(
                resource_group_name=resource_group
            )
        )

        for avail_set in avail_sets:
            result[avail_set['name']] = avail_set
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def availability_sets_list_available_sizes(name, resource_group, **kwargs):  # pylint: disable=invalid-name
    '''
    .. versionadded:: 2019.2.0

    List all available virtual machine sizes that can be used to
    to create a new virtual machine in an existing availability set.

    :param name: The availability set name to list available
        virtual machine sizes within.

    :param resource_group: The resource group name to list available
        availability set sizes within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_sets_list_available_sizes testset testgroup

    '''
    result = {}
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        sizes = __utils__['azurearm.paged_object_to_list'](
            compconn.availability_sets.list_available_sizes(
                resource_group_name=resource_group,
                availability_set_name=name
            )
        )

        for size in sizes:
            result[size['name']] = size
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_capture(name, destination_name, resource_group, prefix='capture-', overwrite=False, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Captures the VM by copying virtual hard disks of the VM and outputs
    a template that can be used to create similar VMs.

    :param name: The name of the virtual machine.

    :param destination_name: The destination container name.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param prefix: (Default: 'capture-') The captured virtual hard disk's name prefix.

    :param overwrite: (Default: False) Overwrite the destination disk in case of conflict.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_capture testvm testcontainer testgroup

    '''
    # pylint: disable=invalid-name
    VirtualMachineCaptureParameters = getattr(
        azure.mgmt.compute.models, 'VirtualMachineCaptureParameters'
    )

    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.capture(
            resource_group_name=resource_group,
            vm_name=name,
            parameters=VirtualMachineCaptureParameters(
                vhd_prefix=prefix,
                destination_container_name=destination_name,
                overwrite_vhds=overwrite
            )
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_get(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Retrieves information about the model view or the instance view of a
    virtual machine.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_get testvm testgroup

    '''
    expand = kwargs.get('expand')

    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.get(
            resource_group_name=resource_group,
            vm_name=name,
            expand=expand
        )
        result = vm.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_convert_to_managed_disks(name, resource_group, **kwargs):  # pylint: disable=invalid-name
    '''
    .. versionadded:: 2019.2.0

    Converts virtual machine disks from blob-based to managed disks. Virtual
    machine must be stop-deallocated before invoking this operation.

    :param name: The name of the virtual machine to convert.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_convert_to_managed_disks testvm testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.convert_to_managed_disks(
            resource_group_name=resource_group,
            vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_deallocate(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Power off a virtual machine and deallocate compute resources.

    :param name: The name of the virtual machine to deallocate.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_deallocate testvm testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    result = False
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.deallocate(
            resource_group_name=resource_group,
            vm_name=name
        )
        vm.wait()
        result = True
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_generalize(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Set the state of a virtual machine to 'generalized'.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_generalize testvm testgroup

    '''
    result = False
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        compconn.virtual_machines.generalize(
            resource_group_name=resource_group,
            vm_name=name
        )
        result = True
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)

    return result


def virtual_machines_list(resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    List all virtual machines within a resource group.

    :param resource_group: The resource group name to list virtual
        machines within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list testgroup

    '''
    result = {}
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        vms = __utils__['azurearm.paged_object_to_list'](
            compconn.virtual_machines.list(
                resource_group_name=resource_group
            )
        )
        for vm in vms:  # pylint: disable=invalid-name
            result[vm['name']] = vm
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machines_list_all(**kwargs):
    '''
    .. versionadded:: 2019.2.0

    List all virtual machines within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list_all

    '''
    result = {}
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        vms = __utils__['azurearm.paged_object_to_list'](
            compconn.virtual_machines.list_all()
        )
        for vm in vms:  # pylint: disable=invalid-name
            result[vm['name']] = vm
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machines_list_available_sizes(name, resource_group, **kwargs):  # pylint: disable=invalid-name
    '''
    .. versionadded:: 2019.2.0

    Lists all available virtual machine sizes to which the specified virtual
    machine can be resized.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list_available_sizes testvm testgroup

    '''
    result = {}
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        sizes = __utils__['azurearm.paged_object_to_list'](
            compconn.virtual_machines.list_available_sizes(
                resource_group_name=resource_group,
                vm_name=name
            )
        )
        for size in sizes:
            result[size['name']] = size
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_power_off(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Power off (stop) a virtual machine.

    :param name: The name of the virtual machine to stop.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_power_off testvm testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.power_off(
            resource_group_name=resource_group,
            vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_restart(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Restart a virtual machine.

    :param name: The name of the virtual machine to restart.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_restart testvm testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.restart(
            resource_group_name=resource_group,
            vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_start(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Power on (start) a virtual machine.

    :param name: The name of the virtual machine to start.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_start testvm testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.start(
            resource_group_name=resource_group,
            vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def virtual_machine_redeploy(name, resource_group, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Redeploy a virtual machine.

    :param name: The name of the virtual machine to redeploy.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_redeploy testvm testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.redeploy(
            resource_group_name=resource_group,
            vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def image_create_or_update(name, resource_group, source_vm=None, source_vm_group=None,
                           os_disk=None, data_disks=None, zone_resilient=False,  **kwargs):
    '''
    .. versionadded:: Sodium

    Create or update an image.

    :param name: The image to create.

    :param resource_group: The resource group name assigned to the image.

    :param source_vm: The name of the virtual machine from which the image is created. This parameter
        or a valid os_disk is required.

    :param source_vm_group: The name of the resource group containing the source virtual machine.
        This defaults to the same resource group specified for the resultant image.

    :param os_disk: The resource ID of an operating system disk to use for the image.

    :param data_disks: The resource ID or list of resource IDs associated with data disks to add to
        the image.

    :param zone_resilient: Specifies whether an image is zone resilient or not. Zone resilient images
        can be created only in regions that provide Zone Redundant Storage (ZRS).

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.image_create_or_update testimage testgroup

    '''
    if 'location' not in kwargs:
        rg_props = __salt__['azurearm_resource.resource_group_get'](
            resource_group, **kwargs
        )

        if 'error' in rg_props:
            log.error(
                'Unable to determine location from resource group specified.'
            )
            return False
        kwargs['location'] = rg_props['location']

    compconn = __utils__['azurearm.get_client']('compute', **kwargs)

    if source_vm:
        # Use VM name to link to the IDs of existing VMs.
        vm_instance = __salt__['azurearm_compute.virtual_machine_get'](
            name=source_vm,
            resource_group=(source_vm_group or resource_group),
            log_level='info',
            **kwargs
        )

        if 'error' in vm_instance:
            errmsg = 'The source virtual machine could not be found.'
            log.error(errmsg)
            result = {'error': errmsg}
            return result

        source_vm = {'id': str(vm_instance['id'])}

    spmodel = None
    if os_disk:
        if is_valid_resource_id(os_disk):
            os_disk = {'id': os_disk}
        else:
            errmsg = 'The os_disk parameter is not a valid resource ID string.'
            log.error(errmsg)
            result = {'error': errmsg}
            return result

        if data_disks:
            if isinstance(data_disks, list):
                data_disks = [ {'id': dd} for dd in data_disks ]
            elif isinstance(data_disks, six.string_types):
                data_disks = [ {'id': data_disks} ]
            else:
                errmsg = 'The data_disk parameter is a single resource ID string or a list of resource IDs.'
                log.error(errmsg)
                result = {'error': errmsg}
                return result

        try:
            spmodel = __utils__['azurearm.create_object_model'](
                'compute',
                'ImageStorageProfile',
                os_disk=os_disk,
                data_disks=data_disks,
                zone_resilient=zone_resilient,
                **kwargs
            )
        except TypeError as exc:
            result = {'error': 'The object model could not be built. ({0})'.format(str(exc))}
            return result

    try:
        imagemodel = __utils__['azurearm.create_object_model'](
            'compute',
            'Image',
            source_virtual_machine=source_vm,
            storage_profile=spmodel,
            **kwargs
        )
    except TypeError as exc:
        result = {'error': 'The object model could not be built. ({0})'.format(str(exc))}
        return result

    try:
        image = compconn.images.create_or_update(
            resource_group_name=resource_group,
            image_name=name,
            parameters=imagemodel
        )
        image.wait()
        image_result = image.result()
        result = image_result.as_dict()

    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}
    except SerializationError as exc:
        result = {'error': 'The object model could not be parsed. ({0})'.format(str(exc))}

    return result


def image_delete(name, resource_group, **kwargs):
    '''
    .. versionadded:: Sodium

    Delete an image.

    :param name: The image to delete.

    :param resource_group: The resource group name assigned to the image.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.image_delete testimage testgroup

    '''
    result = False
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        compconn.images.delete(
            resource_group_name=resource_group,
            image_name=name
        )
        result = True

    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)

    return result


def image_get(name, resource_group, **kwargs):
    '''
    .. versionadded:: Sodium

    Get a dictionary representing an image's properties.

    :param name: The image to get.

    :param resource_group: The resource group name assigned to the image.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.image_get testimage testgroup

    '''
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        image = compconn.images.get(
            resource_group_name=resource_group,
            image_name=name
        )
        result = image.as_dict()

    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def images_list_by_resource_group(resource_group, **kwargs):
    '''
    .. versionadded:: Sodium

    List all images within a resource group.

    :param resource_group: The resource group name to list images within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.images_list_by_resource_group testgroup

    '''
    result = {}
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        images = __utils__['azurearm.paged_object_to_list'](
            compconn.images.list_by_resource_group(
                resource_group_name=resource_group
            )
        )

        for image in images:
            result[image['name']] = image
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result


def images_list(**kwargs):
    '''
    .. versionadded:: Sodium

    List all images in a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.images_list

    '''
    result = {}
    compconn = __utils__['azurearm.get_client']('compute', **kwargs)
    try:
        images = __utils__['azurearm.paged_object_to_list'](compconn.images.list())

        for image in images:
            result[image['name']] = image
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('compute', str(exc), **kwargs)
        result = {'error': str(exc)}

    return result

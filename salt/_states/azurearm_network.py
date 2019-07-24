# -*- coding: utf-8 -*-
'''
Azure (ARM) Network State Module

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

:configuration: This module requires Azure Resource Manager credentials to be passed as a dictionary of
    keyword arguments to the ``connection_auth`` parameter in order to work properly. Since the authentication
    parameters are sensitive, it's recommended to pass them to the states via pillar.

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

    **cloud_environment**: Used to point the cloud driver to different API endpoints, such as Azure GovCloud. Possible values:
      * ``AZURE_PUBLIC_CLOUD`` (default)
      * ``AZURE_CHINA_CLOUD``
      * ``AZURE_US_GOV_CLOUD``
      * ``AZURE_GERMAN_CLOUD``

    Example Pillar for Azure Resource Manager authentication:

    .. code-block:: yaml

        azurearm:
            user_pass_auth:
                subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
                username: fletch
                password: 123pass
            mysubscription:
                subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
                tenant: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
                client_id: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
                secret: XXXXXXXXXXXXXXXXXXXXXXXX
                cloud_environment: AZURE_PUBLIC_CLOUD

    Example states using Azure Resource Manager authentication:

    .. code-block:: jinja

        {% set profile = salt['pillar.get']('azurearm:mysubscription') %}
        Ensure virtual network exists:
            azurearm_network.virtual_network_present:
                - name: my_vnet
                - resource_group: my_rg
                - address_prefixes:
                    - '10.0.0.0/8'
                    - '192.168.0.0/16'
                - dns_servers:
                    - '8.8.8.8'
                - tags:
                    how_awesome: very
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}

        Ensure virtual network is absent:
            azurearm_network.virtual_network_absent:
                - name: other_vnet
                - resource_group: my_rg
                - connection_auth: {{ profile }}

'''

# Python libs
from __future__ import absolute_import
import logging
import re

# Salt libs
try:
    from salt.ext.six.moves import range as six_range
except ImportError:
    six_range = range

__virtualname__ = 'azurearm_network'

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only make this state available if the azurearm_network module is available.
    '''
    return __virtualname__ if 'azurearm_network.check_ip_address_availability' in __salt__ else False


def virtual_network_present(name, address_prefixes, resource_group, dns_servers=None,
                            tags=None, connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a virtual network exists.

    :param name:
        Name of the virtual network.

    :param resource_group:
        The resource group assigned to the virtual network.

    :param address_prefixes:
        A list of CIDR blocks which can be used by subnets within the virtual network.

    :param dns_servers:
        A list of DNS server addresses.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the virtual network object.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure virtual network exists:
            azurearm_network.virtual_network_present:
                - name: vnet1
                - resource_group: group1
                - address_prefixes:
                    - '10.0.0.0/8'
                    - '192.168.0.0/16'
                - dns_servers:
                    - '8.8.8.8'
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    vnet = __salt__['azurearm_network.virtual_network_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in vnet:
        tag_changes = __utils__['dictdiffer.deep_diff'](vnet.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        dns_changes = set(dns_servers or []).symmetric_difference(
            set(vnet.get('dhcp_options', {}).get('dns_servers', [])))
        if dns_changes:
            ret['changes']['dns_servers'] = {
                'old': vnet.get('dhcp_options', {}).get('dns_servers', []),
                'new': dns_servers,
            }

        addr_changes = set(address_prefixes or []).symmetric_difference(
            set(vnet.get('address_space', {}).get('address_prefixes', [])))
        if addr_changes:
            ret['changes']['address_space'] = {
                'address_prefixes': {
                    'old': vnet.get('address_space', {}).get('address_prefixes', []),
                    'new': address_prefixes,
                }
            }

        if kwargs.get('enable_ddos_protection', False) != vnet.get('enable_ddos_protection'):
            ret['changes']['enable_ddos_protection'] = {
                'old': vnet.get('enable_ddos_protection'),
                'new': kwargs.get('enable_ddos_protection')
            }

        if kwargs.get('enable_vm_protection', False) != vnet.get('enable_vm_protection'):
            ret['changes']['enable_vm_protection'] = {
                'old': vnet.get('enable_vm_protection'),
                'new': kwargs.get('enable_vm_protection')
            }

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Virtual network {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Virtual network {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'resource_group': resource_group,
                'address_space': {'address_prefixes': address_prefixes},
                'dhcp_options': {'dns_servers': dns_servers},
                'enable_ddos_protection': kwargs.get('enable_ddos_protection', False),
                'enable_vm_protection': kwargs.get('enable_vm_protection', False),
                'tags': tags,
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Virtual network {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    vnet_kwargs = kwargs.copy()
    vnet_kwargs.update(connection_auth)

    vnet = __salt__['azurearm_network.virtual_network_create_or_update'](
        name=name,
        resource_group=resource_group,
        address_prefixes=address_prefixes,
        dns_servers=dns_servers,
        tags=tags,
        **vnet_kwargs
    )

    if 'error' not in vnet:
        ret['result'] = True
        ret['comment'] = 'Virtual network {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create virtual network {0}! ({1})'.format(name, vnet.get('error'))
    return ret


def virtual_network_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a virtual network does not exist in the resource group.

    :param name:
        Name of the virtual network.

    :param resource_group:
        The resource group assigned to the virtual network.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    vnet = __salt__['azurearm_network.virtual_network_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in vnet:
        ret['result'] = True
        ret['comment'] = 'Virtual network {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Virtual network {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': vnet,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.virtual_network_delete'](name, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Virtual network {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': vnet,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete virtual network {0}!'.format(name)
    return ret


def subnet_present(name, address_prefix, virtual_network, resource_group,
                   security_group=None, route_table=None, connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a subnet exists.

    :param name:
        Name of the subnet.

    :param address_prefix:
        A CIDR block used by the subnet within the virtual network.

    :param virtual_network:
        Name of the existing virtual network to contain the subnet.

    :param resource_group:
        The resource group assigned to the virtual network.

    :param security_group:
        The name of the existing network security group to assign to the subnet.

    :param route_table:
        The name of the existing route table to assign to the subnet.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure subnet exists:
            azurearm_network.subnet_present:
                - name: vnet1_sn1
                - virtual_network: vnet1
                - resource_group: group1
                - address_prefix: '192.168.1.0/24'
                - security_group: nsg1
                - route_table: rt1
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_network: Ensure virtual network exists
                  - azurearm_network: Ensure network security group exists
                  - azurearm_network: Ensure route table exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    snet = __salt__['azurearm_network.subnet_get'](
        name,
        virtual_network,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in snet:
        if address_prefix != snet.get('address_prefix'):
            ret['changes']['address_prefix'] = {
                'old': snet.get('address_prefix'),
                'new': address_prefix
            }

        nsg_name = None
        if snet.get('network_security_group'):
            nsg_name = snet['network_security_group']['id'].split('/')[-1]

        if security_group and (security_group != nsg_name):
            ret['changes']['network_security_group'] = {
                'old': nsg_name,
                'new': security_group
            }

        rttbl_name = None
        if snet.get('route_table'):
            rttbl_name = snet['route_table']['id'].split('/')[-1]

        if route_table and (route_table != rttbl_name):
            ret['changes']['route_table'] = {
                'old': rttbl_name,
                'new': route_table
            }

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Subnet {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Subnet {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'address_prefix': address_prefix,
                'network_security_group': security_group,
                'route_table': route_table
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Subnet {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    snet_kwargs = kwargs.copy()
    snet_kwargs.update(connection_auth)

    snet = __salt__['azurearm_network.subnet_create_or_update'](
        name=name,
        virtual_network=virtual_network,
        resource_group=resource_group,
        address_prefix=address_prefix,
        network_security_group=security_group,
        route_table=route_table,
        **snet_kwargs
    )

    if 'error' not in snet:
        ret['result'] = True
        ret['comment'] = 'Subnet {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create subnet {0}! ({1})'.format(name, snet.get('error'))
    return ret


def subnet_absent(name, virtual_network, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a virtual network does not exist in the virtual network.

    :param name:
        Name of the subnet.

    :param virtual_network:
        Name of the existing virtual network containing the subnet.

    :param resource_group:
        The resource group assigned to the virtual network.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    snet = __salt__['azurearm_network.subnet_get'](
        name,
        virtual_network,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in snet:
        ret['result'] = True
        ret['comment'] = 'Subnet {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Subnet {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': snet,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.subnet_delete'](name, virtual_network, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Subnet {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': snet,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete subnet {0}!'.format(name)
    return ret


def network_security_group_present(name, resource_group, tags=None, security_rules=None, connection_auth=None,
                                   **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a network security group exists.

    :param name:
        Name of the network security group.

    :param resource_group:
        The resource group assigned to the network security group.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the network security group object.

    :param security_rules: An optional list of dictionaries representing valid SecurityRule objects. See the
        documentation for the security_rule_present state or security_rule_create_or_update execution module
        for more information on required and optional parameters for security rules. The rules are only
        managed if this parameter is present. When this parameter is absent, implemented rules will not be removed,
        and will merely become unmanaged.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure network security group exists:
            azurearm_network.network_security_group_present:
                - name: nsg1
                - resource_group: group1
                - security_rules:
                  - name: nsg1_rule1
                    priority: 100
                    protocol: tcp
                    access: allow
                    direction: outbound
                    source_address_prefix: virtualnetwork
                    destination_address_prefix: internet
                    source_port_range: '*'
                    destination_port_range: '*'
                  - name: nsg1_rule2
                    priority: 101
                    protocol: tcp
                    access: allow
                    direction: inbound
                    source_address_prefix: internet
                    destination_address_prefix: virtualnetwork
                    source_port_range: '*'
                    destination_port_ranges:
                      - '80'
                      - '443'
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    nsg = __salt__['azurearm_network.network_security_group_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in nsg:
        tag_changes = __utils__['dictdiffer.deep_diff'](nsg.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        if security_rules:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](nsg.get('security_rules', []), security_rules)

            if comp_ret.get('comment'):
                ret['comment'] = '"security_rules" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['security_rules'] = comp_ret['changes']

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Network security group {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Network security group {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'resource_group': resource_group,
                'tags': tags,
                'security_rules': security_rules,
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Network security group {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    nsg_kwargs = kwargs.copy()
    nsg_kwargs.update(connection_auth)

    nsg = __salt__['azurearm_network.network_security_group_create_or_update'](
        name=name,
        resource_group=resource_group,
        tags=tags,
        security_rules=security_rules,
        **nsg_kwargs
    )

    if 'error' not in nsg:
        ret['result'] = True
        ret['comment'] = 'Network security group {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create network security group {0}! ({1})'.format(name, nsg.get('error'))
    return ret


def network_security_group_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a network security group does not exist in the resource group.

    :param name:
        Name of the network security group.

    :param resource_group:
        The resource group assigned to the network security group.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    nsg = __salt__['azurearm_network.network_security_group_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in nsg:
        ret['result'] = True
        ret['comment'] = 'Network security group {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Network security group {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': nsg,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.network_security_group_delete'](name, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Network security group {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': nsg,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete network security group {0}!'.format(name)
    return ret


def security_rule_present(name, access, direction, priority, protocol, security_group, resource_group,
                          destination_address_prefix=None, destination_port_range=None, source_address_prefix=None,
                          source_port_range=None, description=None, destination_address_prefixes=None,
                          destination_port_ranges=None, source_address_prefixes=None, source_port_ranges=None,
                          connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a security rule exists.

    :param name:
        Name of the security rule.

    :param access:
        'allow' or 'deny'

    :param direction:
        'inbound' or 'outbound'

    :param priority:
        Integer between 100 and 4096 used for ordering rule application.

    :param protocol:
        'tcp', 'udp', or '*'

    :param security_group:
        The name of the existing network security group to contain the security rule.

    :param resource_group:
        The resource group assigned to the network security group.

    :param description:
        Optional description of the security rule.

    :param destination_address_prefix:
        The CIDR or destination IP range. Asterix '*' can also be used to match all destination IPs.
        Default tags such as 'VirtualNetwork', 'AzureLoadBalancer' and 'Internet' can also be used.
        If this is an ingress rule, specifies where network traffic originates from.

    :param destination_port_range:
        The destination port or range. Integer or range between 0 and 65535. Asterix '*'
        can also be used to match all ports.

    :param source_address_prefix:
        The CIDR or source IP range. Asterix '*' can also be used to match all source IPs.
        Default tags such as 'VirtualNetwork', 'AzureLoadBalancer' and 'Internet' can also be used.
        If this is an ingress rule, specifies where network traffic originates from.

    :param source_port_range:
        The source port or range. Integer or range between 0 and 65535. Asterix '*'
        can also be used to match all ports.

    :param destination_address_prefixes:
        A list of destination_address_prefix values. This parameter overrides destination_address_prefix
        and will cause any value entered there to be ignored.

    :param destination_port_ranges:
        A list of destination_port_range values. This parameter overrides destination_port_range
        and will cause any value entered there to be ignored.

    :param source_address_prefixes:
        A list of source_address_prefix values. This parameter overrides source_address_prefix
        and will cause any value entered there to be ignored.

    :param source_port_ranges:
        A list of source_port_range values. This parameter overrides source_port_range
        and will cause any value entered there to be ignored.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure security rule exists:
            azurearm_network.security_rule_present:
                - name: nsg1_rule2
                - security_group: nsg1
                - resource_group: group1
                - priority: 101
                - protocol: tcp
                - access: allow
                - direction: inbound
                - source_address_prefix: internet
                - destination_address_prefix: virtualnetwork
                - source_port_range: '*'
                - destination_port_ranges:
                  - '80'
                  - '443'
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_network: Ensure network security group exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    exclusive_params = [
        ('source_port_ranges', 'source_port_range'),
        ('source_address_prefixes', 'source_address_prefix'),
        ('destination_port_ranges', 'destination_port_range'),
        ('destination_address_prefixes', 'destination_address_prefix'),
    ]

    for params in exclusive_params:
        # pylint: disable=eval-used
        if not eval(params[0]) and not eval(params[1]):
            ret['comment'] = 'Either the {0} or {1} parameter must be provided!'.format(params[0], params[1])
            return ret
        # pylint: disable=eval-used
        if eval(params[0]):
            # pylint: disable=eval-used
            if not isinstance(eval(params[0]), list):
                ret['comment'] = 'The {0} parameter must be a list!'.format(params[0])
                return ret
            # pylint: disable=exec-used
            exec('{0} = None'.format(params[1]))

    rule = __salt__['azurearm_network.security_rule_get'](
        name,
        security_group,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in rule:
        # access changes
        if access.capitalize() != rule.get('access'):
            ret['changes']['access'] = {
                'old': rule.get('access'),
                'new': access
            }

        # description changes
        if description != rule.get('description'):
            ret['changes']['description'] = {
                'old': rule.get('description'),
                'new': description
            }

        # direction changes
        if direction.capitalize() != rule.get('direction'):
            ret['changes']['direction'] = {
                'old': rule.get('direction'),
                'new': direction
            }

        # priority changes
        if int(priority) != rule.get('priority'):
            ret['changes']['priority'] = {
                'old': rule.get('priority'),
                'new': priority
            }

        # protocol changes
        if protocol.lower() != rule.get('protocol', '').lower():
            ret['changes']['protocol'] = {
                'old': rule.get('protocol'),
                'new': protocol
            }

        # destination_port_range changes
        if destination_port_range != rule.get('destination_port_range'):
            ret['changes']['destination_port_range'] = {
                'old': rule.get('destination_port_range'),
                'new': destination_port_range
            }

        # source_port_range changes
        if source_port_range != rule.get('source_port_range'):
            ret['changes']['source_port_range'] = {
                'old': rule.get('source_port_range'),
                'new': source_port_range
            }

        # destination_port_ranges changes
        if sorted(destination_port_ranges or []) != sorted(rule.get('destination_port_ranges', [])):
            ret['changes']['destination_port_ranges'] = {
                'old': rule.get('destination_port_ranges'),
                'new': destination_port_ranges
            }

        # source_port_ranges changes
        if sorted(source_port_ranges or []) != sorted(rule.get('source_port_ranges', [])):
            ret['changes']['source_port_ranges'] = {
                'old': rule.get('source_port_ranges'),
                'new': source_port_ranges
            }

        # destination_address_prefix changes
        if (destination_address_prefix or '').lower() != rule.get('destination_address_prefix', '').lower():
            ret['changes']['destination_address_prefix'] = {
                'old': rule.get('destination_address_prefix'),
                'new': destination_address_prefix
            }

        # source_address_prefix changes
        if (source_address_prefix or '').lower() != rule.get('source_address_prefix', '').lower():
            ret['changes']['source_address_prefix'] = {
                'old': rule.get('source_address_prefix'),
                'new': source_address_prefix
            }

        # destination_address_prefixes changes
        if sorted(destination_address_prefixes or []) != sorted(rule.get('destination_address_prefixes', [])):
            if len(destination_address_prefixes or []) != len(rule.get('destination_address_prefixes', [])):
                ret['changes']['destination_address_prefixes'] = {
                    'old': rule.get('destination_address_prefixes'),
                    'new': destination_address_prefixes
                }
            else:
                local_dst_addrs, remote_dst_addrs = (sorted(destination_address_prefixes),
                                                     sorted(rule.get('destination_address_prefixes')))
                for idx in six_range(0, len(local_dst_addrs)):
                    if local_dst_addrs[idx].lower() != remote_dst_addrs[idx].lower():
                        ret['changes']['destination_address_prefixes'] = {
                            'old': rule.get('destination_address_prefixes'),
                            'new': destination_address_prefixes
                        }
                        break

        # source_address_prefixes changes
        if sorted(source_address_prefixes or []) != sorted(rule.get('source_address_prefixes', [])):
            if len(source_address_prefixes or []) != len(rule.get('source_address_prefixes', [])):
                ret['changes']['source_address_prefixes'] = {
                    'old': rule.get('source_address_prefixes'),
                    'new': source_address_prefixes
                }
            else:
                local_src_addrs, remote_src_addrs = (sorted(source_address_prefixes),
                                                     sorted(rule.get('source_address_prefixes')))
                for idx in six_range(0, len(local_src_addrs)):
                    if local_src_addrs[idx].lower() != remote_src_addrs[idx].lower():
                        ret['changes']['source_address_prefixes'] = {
                            'old': rule.get('source_address_prefixes'),
                            'new': source_address_prefixes
                        }
                        break

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Security rule {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Security rule {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'access': access,
                'description': description,
                'direction': direction,
                'priority': priority,
                'protocol': protocol,
                'destination_address_prefix': destination_address_prefix,
                'destination_address_prefixes': destination_address_prefixes,
                'destination_port_range': destination_port_range,
                'destination_port_ranges': destination_port_ranges,
                'source_address_prefix': source_address_prefix,
                'source_address_prefixes': source_address_prefixes,
                'source_port_range': source_port_range,
                'source_port_ranges': source_port_ranges,
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Security rule {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    rule_kwargs = kwargs.copy()
    rule_kwargs.update(connection_auth)

    rule = __salt__['azurearm_network.security_rule_create_or_update'](
        name=name,
        access=access,
        description=description,
        direction=direction,
        priority=priority,
        protocol=protocol,
        security_group=security_group,
        resource_group=resource_group,
        destination_address_prefix=destination_address_prefix,
        destination_address_prefixes=destination_address_prefixes,
        destination_port_range=destination_port_range,
        destination_port_ranges=destination_port_ranges,
        source_address_prefix=source_address_prefix,
        source_address_prefixes=source_address_prefixes,
        source_port_range=source_port_range,
        source_port_ranges=source_port_ranges,
        **rule_kwargs
    )

    if 'error' not in rule:
        ret['result'] = True
        ret['comment'] = 'Security rule {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create security rule {0}! ({1})'.format(name, rule.get('error'))
    return ret


def security_rule_absent(name, security_group, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a security rule does not exist in the network security group.

    :param name:
        Name of the security rule.

    :param security_group:
        The network security group containing the security rule.

    :param resource_group:
        The resource group assigned to the network security group.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    rule = __salt__['azurearm_network.security_rule_get'](
        name,
        security_group,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in rule:
        ret['result'] = True
        ret['comment'] = 'Security rule {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Security rule {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': rule,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.security_rule_delete'](name, security_group, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Security rule {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': rule,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete security rule {0}!'.format(name)
    return ret


def load_balancer_present(name, resource_group, sku=None, frontend_ip_configurations=None, backend_address_pools=None,
                          load_balancing_rules=None, probes=None, inbound_nat_rules=None, inbound_nat_pools=None,
                          outbound_nat_rules=None, tags=None, connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a load balancer exists.

    :param name:
        Name of the load balancer.

    :param resource_group:
        The resource group assigned to the load balancer.

    :param sku:
        The load balancer SKU, which can be 'Basic' or 'Standard'.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the load balancer object.

    :param frontend_ip_configurations:
        An optional list of dictionaries representing valid FrontendIPConfiguration objects. A frontend IP
        configuration can be either private (using private IP address and subnet parameters) or public (using a
        reference to a public IP address object). Valid parameters are:

        - ``name``: The name of the resource that is unique within a resource group.
        - ``private_ip_address``: The private IP address of the IP configuration. Required if
          'private_ip_allocation_method' is 'Static'.
        - ``private_ip_allocation_method``: The Private IP allocation method. Possible values are: 'Static' and
          'Dynamic'.
        - ``subnet``: Name of an existing subnet inside of which the frontend IP will reside.
        - ``public_ip_address``: Name of an existing public IP address which will be assigned to the frontend IP object.

    :param backend_address_pools:
        An optional list of dictionaries representing valid BackendAddressPool objects. Only the 'name' parameter is
        valid for a BackendAddressPool dictionary. All other parameters are read-only references from other objects
        linking to the backend address pool. Inbound traffic is randomly load balanced across IPs in the backend IPs.

    :param probes:
        An optional list of dictionaries representing valid Probe objects. Valid parameters are:

        - ``name``: The name of the resource that is unique within a resource group.
        - ``protocol``: The protocol of the endpoint. Possible values are 'Http' or 'Tcp'. If 'Tcp' is specified, a
          received ACK is required for the probe to be successful. If 'Http' is specified, a 200 OK response from the
          specified URI is required for the probe to be successful.
        - ``port``: The port for communicating the probe. Possible values range from 1 to 65535, inclusive.
        - ``interval_in_seconds``: The interval, in seconds, for how frequently to probe the endpoint for health status.
          Typically, the interval is slightly less than half the allocated timeout period (in seconds) which allows two
          full probes before taking the instance out of rotation. The default value is 15, the minimum value is 5.
        - ``number_of_probes``: The number of probes where if no response, will result in stopping further traffic from
          being delivered to the endpoint. This values allows endpoints to be taken out of rotation faster or slower
          than the typical times used in Azure.
        - ``request_path``: The URI used for requesting health status from the VM. Path is required if a protocol is
          set to 'Http'. Otherwise, it is not allowed. There is no default value.

    :param load_balancing_rules:
        An optional list of dictionaries representing valid LoadBalancingRule objects. Valid parameters are:

        - ``name``: The name of the resource that is unique within a resource group.
        - ``load_distribution``: The load distribution policy for this rule. Possible values are 'Default', 'SourceIP',
          and 'SourceIPProtocol'.
        - ``frontend_port``: The port for the external endpoint. Port numbers for each rule must be unique within the
          Load Balancer. Acceptable values are between 0 and 65534. Note that value 0 enables 'Any Port'.
        - ``backend_port``: The port used for internal connections on the endpoint. Acceptable values are between 0 and
          65535. Note that value 0 enables 'Any Port'.
        - ``idle_timeout_in_minutes``: The timeout for the TCP idle connection. The value can be set between 4 and 30
          minutes. The default value is 4 minutes. This element is only used when the protocol is set to TCP.
        - ``enable_floating_ip``: Configures a virtual machine's endpoint for the floating IP capability required
          to configure a SQL AlwaysOn Availability Group. This setting is required when using the SQL AlwaysOn
          Availability Groups in SQL server. This setting can't be changed after you create the endpoint.
        - ``disable_outbound_snat``: Configures SNAT for the VMs in the backend pool to use the public IP address
          specified in the frontend of the load balancing rule.
        - ``frontend_ip_configuration``: Name of the frontend IP configuration object used by the load balancing rule
          object.
        - ``backend_address_pool``: Name of the backend address pool object used by the load balancing rule object.
          Inbound traffic is randomly load balanced across IPs in the backend IPs.
        - ``probe``: Name of the probe object used by the load balancing rule object.

    :param inbound_nat_rules:
        An optional list of dictionaries representing valid InboundNatRule objects. Defining inbound NAT rules on your
        load balancer is mutually exclusive with defining an inbound NAT pool. Inbound NAT pools are referenced from
        virtual machine scale sets. NICs that are associated with individual virtual machines cannot reference an
        Inbound NAT pool. They have to reference individual inbound NAT rules. Valid parameters are:

        - ``name``: The name of the resource that is unique within a resource group.
        - ``frontend_ip_configuration``: Name of the frontend IP configuration object used by the inbound NAT rule
          object.
        - ``protocol``: Possible values include 'Udp', 'Tcp', or 'All'.
        - ``frontend_port``: The port for the external endpoint. Port numbers for each rule must be unique within the
          Load Balancer. Acceptable values range from 1 to 65534.
        - ``backend_port``: The port used for the internal endpoint. Acceptable values range from 1 to 65535.
        - ``idle_timeout_in_minutes``: The timeout for the TCP idle connection. The value can be set between 4 and 30
          minutes. The default value is 4 minutes. This element is only used when the protocol is set to TCP.
        - ``enable_floating_ip``: Configures a virtual machine's endpoint for the floating IP capability required
          to configure a SQL AlwaysOn Availability Group. This setting is required when using the SQL AlwaysOn
          Availability Groups in SQL server. This setting can't be changed after you create the endpoint.

    :param inbound_nat_pools:
        An optional list of dictionaries representing valid InboundNatPool objects. They define an external port range
        for inbound NAT to a single backend port on NICs associated with a load balancer. Inbound NAT rules are created
        automatically for each NIC associated with the Load Balancer using an external port from this range. Defining an
        Inbound NAT pool on your Load Balancer is mutually exclusive with defining inbound NAT rules. Inbound NAT pools
        are referenced from virtual machine scale sets. NICs that are associated with individual virtual machines cannot
        reference an inbound NAT pool. They have to reference individual inbound NAT rules. Valid parameters are:

        - ``name``: The name of the resource that is unique within a resource group.
        - ``frontend_ip_configuration``: Name of the frontend IP configuration object used by the inbound NAT pool
          object.
        - ``protocol``: Possible values include 'Udp', 'Tcp', or 'All'.
        - ``frontend_port_range_start``: The first port number in the range of external ports that will be used to
          provide Inbound NAT to NICs associated with a load balancer. Acceptable values range between 1 and 65534.
        - ``frontend_port_range_end``: The last port number in the range of external ports that will be used to
          provide Inbound NAT to NICs associated with a load balancer. Acceptable values range between 1 and 65535.
        - ``backend_port``: The port used for internal connections to the endpoint. Acceptable values are between 1 and
          65535.

    :param outbound_nat_rules:
        An optional list of dictionaries representing valid OutboundNatRule objects. Valid parameters are:

        - ``name``: The name of the resource that is unique within a resource group.
        - ``frontend_ip_configuration``: Name of the frontend IP configuration object used by the outbound NAT rule
          object.
        - ``backend_address_pool``: Name of the backend address pool object used by the outbound NAT rule object.
          Outbound traffic is randomly load balanced across IPs in the backend IPs.
        - ``allocated_outbound_ports``: The number of outbound ports to be used for NAT.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure load balancer exists:
            azurearm_network.load_balancer_present:
                - name: lb1
                - resource_group: group1
                - location: eastus
                - frontend_ip_configurations:
                  - name: lb1_feip1
                    public_ip_address: pub_ip1
                - backend_address_pools:
                  - name: lb1_bepool1
                - probes:
                  - name: lb1_webprobe1
                    protocol: tcp
                    port: 80
                    interval_in_seconds: 5
                    number_of_probes: 2
                - load_balancing_rules:
                  - name: lb1_webprobe1
                    protocol: tcp
                    frontend_port: 80
                    backend_port: 80
                    idle_timeout_in_minutes: 4
                    frontend_ip_configuration: lb1_feip1
                    backend_address_pool: lb1_bepool1
                    probe: lb1_webprobe1
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists
                  - azurearm_network: Ensure public IP exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    if sku:
        sku = {'name': sku.capitalize()}

    load_bal = __salt__['azurearm_network.load_balancer_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in load_bal:
        # tag changes
        tag_changes = __utils__['dictdiffer.deep_diff'](load_bal.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        # sku changes
        if sku:
            sku_changes = __utils__['dictdiffer.deep_diff'](load_bal.get('sku', {}), sku)
            if sku_changes:
                ret['changes']['sku'] = sku_changes

        # frontend_ip_configurations changes
        if frontend_ip_configurations:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                load_bal.get('frontend_ip_configurations', []),
                frontend_ip_configurations,
                ['public_ip_address', 'subnet']
            )

            if comp_ret.get('comment'):
                ret['comment'] = '"frontend_ip_configurations" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['frontend_ip_configurations'] = comp_ret['changes']

        # backend_address_pools changes
        if backend_address_pools:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                load_bal.get('backend_address_pools', []),
                backend_address_pools
            )

            if comp_ret.get('comment'):
                ret['comment'] = '"backend_address_pools" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['backend_address_pools'] = comp_ret['changes']

        # probes changes
        if probes:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](load_bal.get('probes', []), probes)

            if comp_ret.get('comment'):
                ret['comment'] = '"probes" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['probes'] = comp_ret['changes']

        # load_balancing_rules changes
        if load_balancing_rules:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                load_bal.get('load_balancing_rules', []),
                load_balancing_rules,
                ['frontend_ip_configuration', 'backend_address_pool', 'probe']
            )

            if comp_ret.get('comment'):
                ret['comment'] = '"load_balancing_rules" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['load_balancing_rules'] = comp_ret['changes']

        # inbound_nat_rules changes
        if inbound_nat_rules:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                load_bal.get('inbound_nat_rules', []),
                inbound_nat_rules,
                ['frontend_ip_configuration']
            )

            if comp_ret.get('comment'):
                ret['comment'] = '"inbound_nat_rules" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['inbound_nat_rules'] = comp_ret['changes']

        # inbound_nat_pools changes
        if inbound_nat_pools:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                load_bal.get('inbound_nat_pools', []),
                inbound_nat_pools,
                ['frontend_ip_configuration']
            )

            if comp_ret.get('comment'):
                ret['comment'] = '"inbound_nat_pools" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['inbound_nat_pools'] = comp_ret['changes']

        # outbound_nat_rules changes
        if outbound_nat_rules:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                load_bal.get('outbound_nat_rules', []),
                outbound_nat_rules,
                ['frontend_ip_configuration']
            )

            if comp_ret.get('comment'):
                ret['comment'] = '"outbound_nat_rules" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['outbound_nat_rules'] = comp_ret['changes']

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Load balancer {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Load balancer {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'sku': sku,
                'tags': tags,
                'frontend_ip_configurations': frontend_ip_configurations,
                'backend_address_pools': backend_address_pools,
                'load_balancing_rules': load_balancing_rules,
                'probes': probes,
                'inbound_nat_rules': inbound_nat_rules,
                'inbound_nat_pools': inbound_nat_pools,
                'outbound_nat_rules': outbound_nat_rules,
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Load balancer {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    lb_kwargs = kwargs.copy()
    lb_kwargs.update(connection_auth)

    load_bal = __salt__['azurearm_network.load_balancer_create_or_update'](
        name=name,
        resource_group=resource_group,
        sku=sku,
        tags=tags,
        frontend_ip_configurations=frontend_ip_configurations,
        backend_address_pools=backend_address_pools,
        load_balancing_rules=load_balancing_rules,
        probes=probes,
        inbound_nat_rules=inbound_nat_rules,
        inbound_nat_pools=inbound_nat_pools,
        outbound_nat_rules=outbound_nat_rules,
        **lb_kwargs
    )

    if 'error' not in load_bal:
        ret['result'] = True
        ret['comment'] = 'Load balancer {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create load balancer {0}! ({1})'.format(name, load_bal.get('error'))
    return ret


def load_balancer_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a load balancer does not exist in the resource group.

    :param name:
        Name of the load balancer.

    :param resource_group:
        The resource group assigned to the load balancer.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    load_bal = __salt__['azurearm_network.load_balancer_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in load_bal:
        ret['result'] = True
        ret['comment'] = 'Load balancer {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Load balancer {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': load_bal,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.load_balancer_delete'](name, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Load balancer {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': load_bal,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete load balancer {0}!'.format(name)
    return ret


def public_ip_address_present(name, resource_group, tags=None, sku=None, public_ip_allocation_method=None,
                              public_ip_address_version=None, dns_settings=None, idle_timeout_in_minutes=None,
                              connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a public IP address exists.

    :param name:
        Name of the public IP address.

    :param resource_group:
        The resource group assigned to the public IP address.

    :param dns_settings:
        An optional dictionary representing a valid PublicIPAddressDnsSettings object. Parameters include
        'domain_name_label' and 'reverse_fqdn', which accept strings. The 'domain_name_label' parameter is concatenated
        with the regionalized DNS zone make up the fully qualified domain name associated with the public IP address.
        If a domain name label is specified, an A DNS record is created for the public IP in the Microsoft Azure DNS
        system. The 'reverse_fqdn' parameter is a user-visible, fully qualified domain name that resolves to this public
        IP address. If the reverse FQDN is specified, then a PTR DNS record is created pointing from the IP address in
        the in-addr.arpa domain to the reverse FQDN.

    :param sku:
        The public IP address SKU, which can be 'Basic' or 'Standard'.

    :param public_ip_allocation_method:
        The public IP allocation method. Possible values are: 'Static' and 'Dynamic'.

    :param public_ip_address_version:
        The public IP address version. Possible values are: 'IPv4' and 'IPv6'.

    :param idle_timeout_in_minutes:
        An integer representing the idle timeout of the public IP address.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the public IP address object.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure public IP exists:
            azurearm_network.public_ip_address_present:
                - name: pub_ip1
                - resource_group: group1
                - dns_settings:
                    domain_name_label: decisionlab-ext-test-label
                - sku: basic
                - public_ip_allocation_method: static
                - public_ip_address_version: ipv4
                - idle_timeout_in_minutes: 4
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    if sku:
        sku = {'name': sku.capitalize()}

    pub_ip = __salt__['azurearm_network.public_ip_address_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in pub_ip:
        # tag changes
        tag_changes = __utils__['dictdiffer.deep_diff'](pub_ip.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        # dns_settings changes
        if dns_settings:
            if not isinstance(dns_settings, dict):
                ret['comment'] = 'DNS settings must be provided as a dictionary!'
                return ret

            for key in dns_settings:
                if dns_settings[key] != pub_ip.get('dns_settings', {}).get(key):
                    ret['changes']['dns_settings'] = {
                        'old': pub_ip.get('dns_settings'),
                        'new': dns_settings
                    }
                    break

        # sku changes
        if sku:
            sku_changes = __utils__['dictdiffer.deep_diff'](pub_ip.get('sku', {}), sku)
            if sku_changes:
                ret['changes']['sku'] = sku_changes

        # public_ip_allocation_method changes
        if public_ip_allocation_method:
            if public_ip_allocation_method.capitalize() != pub_ip.get('public_ip_allocation_method'):
                ret['changes']['public_ip_allocation_method'] = {
                    'old': pub_ip.get('public_ip_allocation_method'),
                    'new': public_ip_allocation_method
                }

        # public_ip_address_version changes
        if public_ip_address_version:
            if public_ip_address_version.lower() != pub_ip.get('public_ip_address_version', '').lower():
                ret['changes']['public_ip_address_version'] = {
                    'old': pub_ip.get('public_ip_address_version'),
                    'new': public_ip_address_version
                }

        # idle_timeout_in_minutes changes
        if idle_timeout_in_minutes and (int(idle_timeout_in_minutes) != pub_ip.get('idle_timeout_in_minutes')):
            ret['changes']['idle_timeout_in_minutes'] = {
                'old': pub_ip.get('idle_timeout_in_minutes'),
                'new': idle_timeout_in_minutes
            }

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Public IP address {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Public IP address {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'tags': tags,
                'dns_settings': dns_settings,
                'sku': sku,
                'public_ip_allocation_method': public_ip_allocation_method,
                'public_ip_address_version': public_ip_address_version,
                'idle_timeout_in_minutes': idle_timeout_in_minutes,
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Public IP address {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    pub_ip_kwargs = kwargs.copy()
    pub_ip_kwargs.update(connection_auth)

    pub_ip = __salt__['azurearm_network.public_ip_address_create_or_update'](
        name=name,
        resource_group=resource_group,
        sku=sku,
        tags=tags,
        dns_settings=dns_settings,
        public_ip_allocation_method=public_ip_allocation_method,
        public_ip_address_version=public_ip_address_version,
        idle_timeout_in_minutes=idle_timeout_in_minutes,
        **pub_ip_kwargs
    )

    if 'error' not in pub_ip:
        ret['result'] = True
        ret['comment'] = 'Public IP address {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create public IP address {0}! ({1})'.format(name, pub_ip.get('error'))
    return ret


def public_ip_address_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a public IP address does not exist in the resource group.

    :param name:
        Name of the public IP address.

    :param resource_group:
        The resource group assigned to the public IP address.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    pub_ip = __salt__['azurearm_network.public_ip_address_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in pub_ip:
        ret['result'] = True
        ret['comment'] = 'Public IP address {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Public IP address {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': pub_ip,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.public_ip_address_delete'](name, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Public IP address {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': pub_ip,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete public IP address {0}!'.format(name)
    return ret


def network_interface_present(name, ip_configurations, subnet, virtual_network, resource_group, tags=None,
                              virtual_machine=None, network_security_group=None, dns_settings=None, mac_address=None,
                              primary=None, enable_accelerated_networking=None, enable_ip_forwarding=None,
                              connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a network interface exists.

    :param name:
        Name of the network interface.

    :param ip_configurations:
        A list of dictionaries representing valid NetworkInterfaceIPConfiguration objects. The 'name' key is required at
        minimum. At least one IP Configuration must be present.

    :param subnet:
        Name of the existing subnet assigned to the network interface.

    :param virtual_network:
        Name of the existing virtual network containing the subnet.

    :param resource_group:
        The resource group assigned to the virtual network.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the network interface object.

    :param network_security_group:
        The name of the existing network security group to assign to the network interface.

    :param virtual_machine:
        The name of the existing virtual machine to assign to the network interface.

    :param dns_settings:
        An optional dictionary representing a valid NetworkInterfaceDnsSettings object. Valid parameters are:

        - ``dns_servers``: List of DNS server IP addresses. Use 'AzureProvidedDNS' to switch to Azure provided DNS
          resolution. 'AzureProvidedDNS' value cannot be combined with other IPs, it must be the only value in
          dns_servers collection.
        - ``internal_dns_name_label``: Relative DNS name for this NIC used for internal communications between VMs in
          the same virtual network.
        - ``internal_fqdn``: Fully qualified DNS name supporting internal communications between VMs in the same virtual
          network.
        - ``internal_domain_name_suffix``: Even if internal_dns_name_label is not specified, a DNS entry is created for
          the primary NIC of the VM. This DNS name can be constructed by concatenating the VM name with the value of
          internal_domain_name_suffix.

    :param mac_address:
        Optional string containing the MAC address of the network interface.

    :param primary:
        Optional boolean allowing the interface to be set as the primary network interface on a virtual machine
        with multiple interfaces attached.

    :param enable_accelerated_networking:
        Optional boolean indicating whether accelerated networking should be enabled for the interface.

    :param enable_ip_forwarding:
        Optional boolean indicating whether IP forwarding should be enabled for the interface.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure network interface exists:
            azurearm_network.network_interface_present:
                - name: iface1
                - subnet: vnet1_sn1
                - virtual_network: vnet1
                - resource_group: group1
                - ip_configurations:
                  - name: iface1_ipc1
                    public_ip_address: pub_ip2
                - dns_settings:
                    internal_dns_name_label: decisionlab-int-test-label
                - primary: True
                - enable_accelerated_networking: True
                - enable_ip_forwarding: False
                - network_security_group: nsg1
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_network: Ensure subnet exists
                  - azurearm_network: Ensure network security group exists
                  - azurearm_network: Ensure another public IP exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    iface = __salt__['azurearm_network.network_interface_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in iface:
        # tag changes
        tag_changes = __utils__['dictdiffer.deep_diff'](iface.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        # mac_address changes
        if mac_address and (mac_address != iface.get('mac_address')):
            ret['changes']['mac_address'] = {
                'old': iface.get('mac_address'),
                'new': mac_address
            }

        # primary changes
        if primary is not None:
            if primary != iface.get('primary', True):
                ret['changes']['primary'] = {
                    'old': iface.get('primary'),
                    'new': primary
                }

        # enable_accelerated_networking changes
        if enable_accelerated_networking is not None:
            if enable_accelerated_networking != iface.get('enable_accelerated_networking'):
                ret['changes']['enable_accelerated_networking'] = {
                    'old': iface.get('enable_accelerated_networking'),
                    'new': enable_accelerated_networking
                }

        # enable_ip_forwarding changes
        if enable_ip_forwarding is not None:
            if enable_ip_forwarding != iface.get('enable_ip_forwarding'):
                ret['changes']['enable_ip_forwarding'] = {
                    'old': iface.get('enable_ip_forwarding'),
                    'new': enable_ip_forwarding
                }

        # network_security_group changes
        nsg_name = None
        if iface.get('network_security_group'):
            nsg_name = iface['network_security_group']['id'].split('/')[-1]

        if network_security_group and (network_security_group != nsg_name):
            ret['changes']['network_security_group'] = {
                'old': nsg_name,
                'new': network_security_group
            }

        # virtual_machine changes
        vm_name = None
        if iface.get('virtual_machine'):
            vm_name = iface['virtual_machine']['id'].split('/')[-1]

        if virtual_machine and (virtual_machine != vm_name):
            ret['changes']['virtual_machine'] = {
                'old': vm_name,
                'new': virtual_machine
            }

        # dns_settings changes
        if dns_settings:
            if not isinstance(dns_settings, dict):
                ret['comment'] = 'DNS settings must be provided as a dictionary!'
                return ret

            for key in dns_settings:
                if dns_settings[key].lower() != iface.get('dns_settings', {}).get(key, '').lower():
                    ret['changes']['dns_settings'] = {
                        'old': iface.get('dns_settings'),
                        'new': dns_settings
                    }
                    break

        # ip_configurations changes
        comp_ret = __utils__['azurearm.compare_list_of_dicts'](
            iface.get('ip_configurations', []),
            ip_configurations,
            ['public_ip_address', 'subnet']
        )

        if comp_ret.get('comment'):
            ret['comment'] = '"ip_configurations" {0}'.format(comp_ret['comment'])
            return ret

        if comp_ret.get('changes'):
            ret['changes']['ip_configurations'] = comp_ret['changes']

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Network interface {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Network interface {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'ip_configurations': ip_configurations,
                'dns_settings': dns_settings,
                'network_security_group': network_security_group,
                'virtual_machine': virtual_machine,
                'enable_accelerated_networking': enable_accelerated_networking,
                'enable_ip_forwarding': enable_ip_forwarding,
                'mac_address': mac_address,
                'primary': primary,
                'tags': tags,
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Network interface {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    iface_kwargs = kwargs.copy()
    iface_kwargs.update(connection_auth)

    iface = __salt__['azurearm_network.network_interface_create_or_update'](
        name=name,
        subnet=subnet,
        virtual_network=virtual_network,
        resource_group=resource_group,
        ip_configurations=ip_configurations,
        dns_settings=dns_settings,
        enable_accelerated_networking=enable_accelerated_networking,
        enable_ip_forwarding=enable_ip_forwarding,
        mac_address=mac_address,
        primary=primary,
        network_security_group=network_security_group,
        virtual_machine=virtual_machine,
        tags=tags,
        **iface_kwargs
    )

    if 'error' not in iface:
        ret['result'] = True
        ret['comment'] = 'Network interface {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create network interface {0}! ({1})'.format(name, iface.get('error'))
    return ret


def network_interface_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a network interface does not exist in the resource group.

    :param name:
        Name of the network interface.

    :param resource_group:
        The resource group assigned to the network interface.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    iface = __salt__['azurearm_network.network_interface_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in iface:
        ret['result'] = True
        ret['comment'] = 'Network interface {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Network interface {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': iface,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.network_interface_delete'](name, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Network interface {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': iface,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete network interface {0}!)'.format(name)
    return ret


def route_table_present(name, resource_group, tags=None, routes=None, disable_bgp_route_propagation=None,
                        connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a route table exists.

    :param name:
        Name of the route table.

    :param resource_group:
        The resource group assigned to the route table.

    :param routes:
        An optional list of dictionaries representing valid Route objects contained within a route table. See the
        documentation for the route_present state or route_create_or_update execution module for more information on
        required and optional parameters for routes. The routes are only managed if this parameter is present. When this
        parameter is absent, implemented routes will not be removed, and will merely become unmanaged.

    :param disable_bgp_route_propagation:
        An optional boolean parameter setting whether to disable the routes learned by BGP on the route table.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the route table object.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure route table exists:
            azurearm_network.route_table_present:
                - name: rt1
                - resource_group: group1
                - routes:
                  - name: rt1_route1
                    address_prefix: '0.0.0.0/0'
                    next_hop_type: internet
                  - name: rt1_route2
                    address_prefix: '192.168.0.0/16'
                    next_hop_type: vnetlocal
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    rt_tbl = __salt__['azurearm_network.route_table_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in rt_tbl:
        # tag changes
        tag_changes = __utils__['dictdiffer.deep_diff'](rt_tbl.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        # disable_bgp_route_propagation changes
        # pylint: disable=line-too-long
        if disable_bgp_route_propagation and (disable_bgp_route_propagation != rt_tbl.get('disable_bgp_route_propagation')):
            ret['changes']['disable_bgp_route_propagation'] = {
                'old': rt_tbl.get('disable_bgp_route_propagation'),
                'new': disable_bgp_route_propagation
            }

        # routes changes
        if routes:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](rt_tbl.get('routes', []), routes)

            if comp_ret.get('comment'):
                ret['comment'] = '"routes" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['routes'] = comp_ret['changes']

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Route table {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Route table {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'tags': tags,
                'routes': routes,
                'disable_bgp_route_propagation': disable_bgp_route_propagation,
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Route table {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    rt_tbl_kwargs = kwargs.copy()
    rt_tbl_kwargs.update(connection_auth)

    rt_tbl = __salt__['azurearm_network.route_table_create_or_update'](
        name=name,
        resource_group=resource_group,
        disable_bgp_route_propagation=disable_bgp_route_propagation,
        routes=routes,
        tags=tags,
        **rt_tbl_kwargs
    )

    if 'error' not in rt_tbl:
        ret['result'] = True
        ret['comment'] = 'Route table {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create route table {0}! ({1})'.format(name, rt_tbl.get('error'))
    return ret


def route_table_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a route table does not exist in the resource group.

    :param name:
        Name of the route table.

    :param resource_group:
        The resource group assigned to the route table.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    rt_tbl = __salt__['azurearm_network.route_table_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in rt_tbl:
        ret['result'] = True
        ret['comment'] = 'Route table {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Route table {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': rt_tbl,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.route_table_delete'](name, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Route table {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': rt_tbl,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete route table {0}!'.format(name)
    return ret


def route_present(name, address_prefix, next_hop_type, route_table, resource_group, next_hop_ip_address=None,
                  connection_auth=None, **kwargs):
    '''
    .. versionadded:: 2019.2.0

    Ensure a route exists within a route table.

    :param name:
        Name of the route.

    :param address_prefix:
        The destination CIDR to which the route applies.

    :param next_hop_type:
        The type of Azure hop the packet should be sent to. Possible values are: 'VirtualNetworkGateway', 'VnetLocal',
        'Internet', 'VirtualAppliance', and 'None'.

    :param next_hop_ip_address:
        The IP address packets should be forwarded to. Next hop values are only allowed in routes where the next hop
        type is 'VirtualAppliance'.

    :param route_table:
        The name of the existing route table which will contain the route.

    :param resource_group:
        The resource group assigned to the route table.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure route exists:
            azurearm_network.route_present:
                - name: rt1_route2
                - route_table: rt1
                - resource_group: group1
                - address_prefix: '192.168.0.0/16'
                - next_hop_type: vnetlocal
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_network: Ensure route table exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    route = __salt__['azurearm_network.route_get'](
        name,
        route_table,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in route:
        if address_prefix != route.get('address_prefix'):
            ret['changes']['address_prefix'] = {
                'old': route.get('address_prefix'),
                'new': address_prefix
            }

        if next_hop_type.lower() != route.get('next_hop_type', '').lower():
            ret['changes']['next_hop_type'] = {
                'old': route.get('next_hop_type'),
                'new': next_hop_type
            }

        if next_hop_type.lower() == 'virtualappliance' and next_hop_ip_address != route.get('next_hop_ip_address'):
            ret['changes']['next_hop_ip_address'] = {
                'old': route.get('next_hop_ip_address'),
                'new': next_hop_ip_address
            }

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Route {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Route {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'address_prefix': address_prefix,
                'next_hop_type': next_hop_type,
                'next_hop_ip_address': next_hop_ip_address
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Route {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    route_kwargs = kwargs.copy()
    route_kwargs.update(connection_auth)

    route = __salt__['azurearm_network.route_create_or_update'](
        name=name,
        route_table=route_table,
        resource_group=resource_group,
        address_prefix=address_prefix,
        next_hop_type=next_hop_type,
        next_hop_ip_address=next_hop_ip_address,
        **route_kwargs
    )

    if 'error' not in route:
        ret['result'] = True
        ret['comment'] = 'Route {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create route {0}! ({1})'.format(name, route.get('error'))
    return ret


def route_absent(name, route_table, resource_group, connection_auth=None):
    '''
    .. versionadded:: 2019.2.0

    Ensure a route table does not exist in the resource group.

    :param name:
        Name of the route table.

    :param route_table:
        The name of the existing route table containing the route.

    :param resource_group:
        The resource group assigned to the route table.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    route = __salt__['azurearm_network.route_get'](
        name,
        route_table,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in route:
        ret['result'] = True
        ret['comment'] = 'Route {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Route {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': route,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.route_delete'](name, route_table, resource_group, **connection_auth)

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Route {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': route,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete route {0}!'.format(name)
    return ret


def virtual_network_peering_present(name, remote_virtual_network, virtual_network, resource_group,
                                    remote_vnet_group=None, allow_virtual_network_access=True,
                                    allow_forwarded_traffic=False, allow_gateway_transit=False,
                                    use_remote_gateways=False, connection_auth=None, **kwargs):
    '''
    .. versionadded:: Sodium

    Ensure a virtual network peering object exists.

    :param name:
        Name of the peering object.

    :param remote_virtual_network:
        The name of the remote virtual network.

    :param remote_vnet_group:
        The resource group of the remote virtual network. Defaults to the same resource group
        as the local virtual network.

    :param virtual_network:
        Name of the existing virtual network to contain the peering object.

    :param resource_group:
        The resource group assigned to the local virtual network.

    :param allow_virtual_network_access:
        Whether the VMs in the local virtual network space would be able to access
        the VMs in remote virtual network space.

    :param allow_forwarded_traffic:
        Whether the forwarded traffic from the VMs in the local virtual network will
        be allowed/disallowed in remote virtual network.

    :param allow_gateway_transit:
        If gateway links can be used in remote virtual networking to link to this virtual network.

    :param use_remote_gateways:
        If remote gateways can be used on this virtual network. If the flag is set to true, and allow_gateway_transit
        on remote peering is also true, virtual network will use gateways of remote virtual network for transit.
        Only one peering can have this flag set to true. This flag cannot be set if virtual network already has a
        gateway.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure virtual network peering exists:
            azurearm_network.virtual_network_peering_present:
                - name: vnet1_to_vnet2
                - virtual_network: vnet1
                - resource_group: group1
                - remote_virtual_network: vnet2
                - remote_vnet_group: group2
                - allow_virtual_network_access: True
                - allow_forwarded_traffic: False
                - allow_gateway_transit: False
                - use_remote_gateways: False
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_network: Ensure virtual network exists
                  - azurearm_network: Ensure remote virtual network exists

    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    peering = __salt__['azurearm_network.virtual_network_peering_get'](
        name,
        virtual_network,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in peering:
        remote_vnet = None
        if peering.get('remote_virtual_network', {}).get('id'):
            remote_vnet = peering['remote_virtual_network']['id'].split('/')[-1]

        if remote_virtual_network != remote_vnet:
            ret['changes']['remote_virtual_network'] = {
                'old': remote_vnet,
                'new': remote_virtual_network
            }

        for bool_opt in ['use_remote_gateways', 'allow_forwarded_traffic', 'allow_virtual_network_access', 'allow_gateway_transit']:
            if locals()[bool_opt] != peering.get(bool_opt):
                ret['changes'][bool_opt] = {
                    'old': peering.get(bool_opt),
                    'new': locals()[bool_opt]
                }

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Peering object {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Peering object {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'remote_virtual_network': remote_virtual_network,
                'remote_vnet_group': (remote_vnet_group or resource_group),
                'use_remote_gateways': use_remote_gateways, 
                'allow_forwarded_traffic': allow_forwarded_traffic, 
                'allow_virtual_network_access': allow_virtual_network_access, 
                'allow_gateway_transit': allow_gateway_transit
            }
        }

    if __opts__['test']:
        ret['comment'] = 'Subnet {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    peering_kwargs = kwargs.copy()
    peering_kwargs.update(connection_auth)

    peering = __salt__['azurearm_network.virtual_network_peering_create_or_update'](
        name=name,
        remote_virtual_network=remote_virtual_network,
        remote_vnet_group=remote_vnet_group,
        virtual_network=virtual_network,
        resource_group=resource_group,
        use_remote_gateways=use_remote_gateways, 
        allow_forwarded_traffic=allow_forwarded_traffic, 
        allow_virtual_network_access=allow_virtual_network_access, 
        allow_gateway_transit=allow_gateway_transit,
        **peering_kwargs
    )

    # This is a special case where one side of the peering has been deleted and recreated.
    # In order to establish the new peer, the remote peer needs to be set back to "Initiated" state.
    if peering.get('error', '').startswith('Azure Error: RemotePeeringIsDisconnected'):
        rname_match = re.search('because remote peering (\S+) referencing parent virtual network', peering['error'])
        remote_name = rname_match.group(1).split('/')[-1]

        remote_peering = __salt__['azurearm_network.virtual_network_peering_get'](
            name=remote_name,
            virtual_network=remote_virtual_network,
            resource_group=remote_vnet_group,
            azurearm_log_level='info',
            **connection_auth
        )

        remote_peering_kwargs = remote_peering.copy()
        remote_peering_kwargs.update(connection_auth)
        remote_peering_kwargs['peering_state'] = 'Initiated'
        remote_peering_kwargs.pop('remote_virtual_network')

        remote_peering = __salt__['azurearm_network.virtual_network_peering_create_or_update'](
            remote_virtual_network=virtual_network,
            remote_vnet_group=resource_group,
            virtual_network=remote_virtual_network,
            resource_group=remote_vnet_group,
            **remote_peering_kwargs
        )

        peering = __salt__['azurearm_network.virtual_network_peering_create_or_update'](
            name=name,
            remote_virtual_network=remote_virtual_network,
            remote_vnet_group=remote_vnet_group,
            virtual_network=virtual_network,
            resource_group=resource_group,
            use_remote_gateways=use_remote_gateways, 
            allow_forwarded_traffic=allow_forwarded_traffic, 
            allow_virtual_network_access=allow_virtual_network_access, 
            allow_gateway_transit=allow_gateway_transit,
            **peering_kwargs
        )

    if 'error' not in peering:
        ret['result'] = True
        ret['comment'] = 'Peering object {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create peering object {0}! ({1})'.format(name, peering.get('error'))
    return ret


def virtual_network_peering_absent(name, virtual_network, resource_group, connection_auth=None):
    '''
    .. versionadded:: Sodium

    Ensure a virtual network peering object does not exist in the virtual network.

    :param name:
        Name of the peering object.

    :param virtual_network:
        Name of the existing virtual network containing the peering object.

    :param resource_group:
        The resource group assigned to the virtual network.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    peering = __salt__['azurearm_network.virtual_network_peering_get'](
        name,
        virtual_network,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in peering:
        ret['result'] = True
        ret['comment'] = 'Peering object {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Peering object {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': peering,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.virtual_network_peering_delete'](
        name,
        virtual_network,
        resource_group,
        **connection_auth
    )

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Peering object {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': peering,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete peering object {0}!'.format(name)
    return ret


def virtual_network_gateway_connection_present(name, resource_group, virtual_network_gateway1, connection_type,
					       authorization_key=None, enable_bgp=None, shared_key=None, 
					       connection_protocol=None, local_network_gateway2=None,
					       virtual_network_gateway2=None, ipsec_policies=None, tags=None, 
					       connection_auth=None, **kwargs):
    '''
    .. versionadded:: Sodium

    Ensure a virtual network gateway connection exists.

    :param name:
        The name of the virtual network gateway connection.

    :param resource_group: 
        The name of the resource group associated with the virtual network gateway connection.

    :param virtual_network_gateway1: 
        The name of the virtual network gateway that will be the first endpoint of the connection. 
	The virtual_network_gateway1 is immutable once set.

    :param connection_type: 
        Gateway connection type. Possible values include: 'IPsec', 'Vnet2Vnet', 'ExpressRoute', 'VPNClient'

    :param connection_protocol: Connection protocol used for this connection.
        Possible values include: 'IKEv2', 'IKEv1'.

    :param virtual_network_gateway2: The name of the virtual network gateway used as the second endpoint 
	for the connection. Required for a connection_type of 'Vnet2Vnet'.

    :param local_network_gateway2: The name of the local network gateway used as the second endpoint 
	for the connection. Required for a connection_type of 'IPSec'.

    :param authorization_key: The authorizationKey.

    :param routing_weight: The routing weight.

    :param shared_key: The IPSec shared key. Required for a connection_type of 'IPSec'. 
	Defaults to a randomly generated key. NEEDED FOR VNET2VNET AS WELL?

    :param enable_bgp: Whether BGP is enabled for this virtual network gateway or not. Defaults to False.
	Both endpoints of the connection must have BGP enabled and may not have the same ASN values.

    :param use_policy_based_traffic_selectors: Enable policy-based traffic selectors.

    :param ipsec_policies: The IPSec Policies to be considered by this connection. Must be passed as a list containing
	a single IPSec Policy dictionary that contains the following parameters:
          - ``sa_life_time_seconds``: The IPSec Security Association (also called Quick Mode or Phase 2 SA) 
                                      lifetime in seconds for P2S client. Must be between 300 - 172799 seconds.
          - ``sa_data_size_kilobytes``: The IPSec Security Association (also called Quick Mode or Phase 2 SA) payload 
					size in KB for P2S client. Must be between 1024 - 2147483647 kilobytes.
          - ``ipsec_encryption``: The IPSec encryption algorithm (IKE phase 1). Possible values include: 'None', 
				  'DES', 'DES3', 'AES128', 'AES192', 'AES256', 'GCMAES128', 'GCMAES192', 'GCMAES256'
    	  - ``ipsec_integrity``: The IPSec integrity algorithm (IKE phase 1). Possible values include: 
				 'MD5', 'SHA1', 'SHA256', 'GCMAES128', 'GCMAES192', 'GCMAES256'
    	  - ``ike_encryption``: The IKE encryption algorithm (IKE phase 2). Possible values include: 
				'DES', 'DES3', 'AES128', 'AES192', 'AES256', 'GCMAES256', 'GCMAES128'
          - ``ike_integrity``: The IKE integrity algorithm (IKE phase 2). Possible values include: 
			       'MD5', 'SHA1', 'SHA256', 'SHA384', 'GCMAES256', 'GCMAES128'
    	  - ``dh_group``: The DH Group used in IKE Phase 1 for initial SA. Possible values include: 
			  'None', 'DHGroup1', 'DHGroup2', 'DHGroup14', 'DHGroup2048', 'ECP256', 'ECP384', 'DHGroup24'
    	  - ``pfs_group``: The Pfs Group used in IKE Phase 2 for new child SA. Possible values include: 
			   'None', 'PFS1', 'PFS2', 'PFS2048', 'ECP256', 'ECP384', 'PFS24', 'PFS14', 'PFSMM'

    :param express_route_gateway_bypass: Bypass ExpressRoute Gateway for data forwarding. This is a bool value.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the virtual network gateway object.

    :param connection_auth:                                                                                                                                                                                       A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml                                                                                                                                                                                  
        Ensure virtual network gateway Vnet2Vnet connection exists:
            azurearm_network.virtual_network_gateway_connection_present:
                - name: connection1
                - resource_group: group1
                - virtual_network_gateway1: gateway1
                - connection_type: Vnet2Vnet
		- virtual_network_gateway2: gateway2
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists
                  - azurearm_network: Ensure virtual network gateway exists

        Ensure virtual network gateway IPSec connection exists:
	    azurearm_network.virtual_network_gateway_connection_present:
                - name: connection1
                - resource_group: group1
                - virtual_network_gateway1: gateway1
                - connection_type: IPSec
		- local_network_gateway2: local_gateway2
		- ipsec_policies:
                  - sa_life_time_seconds: 300
                    sa_data_size_kilobytes: 1024
                    ipsec_encryption: 'DES'
		    ipsec_integrity: 'SHA256'
		    ike_encryption: 'DES'
		    ike_integrity: 'SHA256'
		    dh_group: 'None'
		    pfs_group: 'None'
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists
                  - azurearm_network: Ensure virtual network gateway exists
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    connection = __salt__['azurearm_network.virtual_network_gateway_connection_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in connection:
        tag_changes = __utils__['dictdiffer.deep_diff'](connection.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes
	
	# Look into the following:
	# routing_weight
	# use_policy_based_traffic_selectors

	# MAY NEED TO BE PUT INTO IPSEC AND VNET2VNET ONLY
	if enable_bgp != None:
            if enable_bgp != connection.get('enable_bgp'):
                ret['changes']['enable_bgp'] = {
	            'old': connection.get('enable_bgp'),
		    'new': enable_bgp
	        }

	if connection_protocol != None:
            if connection_protocol != connection.get('connection_protocol'):
                ret['changes']['connection_protocol'] = {
                    'old': connection.get('connection_protocol'),
                    'new': connection_protocol
                }

	if connection_type == 'IPSec':
	    
	    localgw2 = __salt__['azurearm_network.local_network_gateway_get'](
		local_network_gateway2,
        	resource_group,
        	azurearm_log_level='info',
        	**connection_auth
    	    )

	    if 'error' not in localgw2:	
	    	if localgw2['id'] != connection['local_network_gateway2']['id']:
            	    ret['changes']['local_network_gateway2'] = {
	                'old': connection.get('local_network_gateway2'),
		        'new': local_network_gateway2
	            }
            
	    if shared_key != None:
                if shared_key != connection.get('shared_key'):
                    ret['changes']['shared_key'] = {
                        'old': connection.get('shared_key'),
                        'new': shared_key
		    }
            
	    if ipsec_policies != None:
                comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                    connection.get('ipsec_policies', []),
                    ipsec_policies
                )

                if comp_ret.get('comment'):
                    ret['comment'] = '"ipsec_policies" {0}'.format(comp_ret['comment'])
                    return ret

                if comp_ret.get('changes'):
                    ret['changes']['ipsec_policies'] = comp_ret['changes']

	if connection_type == 'Vnet2Vnet':

            vnetgw2 = __salt__['azurearm_network.virtual_network_gateway_get'](
                virtual_network_gateway2,
                resource_group,
                azurearm_log_level='info',
                **connection_auth
            )

            if 'error' not in vnetgw2:
                if vnetgw2['id'] != connection['virtual_network_gateway2']['id']:
                    ret['changes']['virtual_network_gateway2'] = {
                        'old': connection.get('virtual_network_gateway2'),
                        'new': virtual_network_gateway2
                    }	
	    if shared_key != None:
	        if shared_key != connection.get('shared_key'):
		    ret['changes']['shared_key'] = {
		        'old': connection.get('shared_key'),
		        'new': shared_key
		    }

	if connection_type == 'ExpressRoute':
	    
	    # express_route_gateway_bypass
	    if authorization_key != None:
                if authorization_key != connection.get('authorization_key'):
                    ret['changes']['authorization_key'] = {
                        'old': connection.get('authorization_key'),
                        'new': enable_bgp
		    }

	'''
	if connection_type == 'VPNClient':
	
	'''

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Virtual network gateway connection {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Virtual network gateway connection {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'resource_group': resource_group,
                'virtual_network_gateway1': virtual_network_gateway1,
                'connection_type': connection_type,
                'tags': tags,
            }
        }

	if authorization_key != None:
	    ret['changes']['new']['authorization_key'] = authorization_key
        if enable_bgp != None:
            ret['changes']['new']['enable_bgp'] = enable_bgp
        if connection_protocol != None:
	    ret['changes']['new']['connection_protocol'] = connection_protocol
        if shared_key != None:
	    ret['changes']['new']['shared_key'] = shared_key
        if local_network_gateway2 != None:
            ret['changes']['new']['local_network_gateway2'] = local_network_gateway2
	if ipsec_policies != None:
	    ret['changes']['new']['ipsec_policies'] = ipsec_policies
        if virtual_network_gateway2 != None:
            ret['changes']['new']['virtual_network_gateway2'] = virtual_network_gateway2


    if __opts__['test']:
        ret['comment'] = 'Virtual network gateway connection {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    connection_kwargs = kwargs.copy()
    connection_kwargs.update(connection_auth)

    if connection_type == 'IPSec':
        # Get a LocalNetWorkGateway Object using the name of the Local Network Gateway that
        # the connection will use as its second endpoint.
        localgw2 = __salt__['azurearm_network.local_network_gateway_get'](
            local_network_gateway2,
            resource_group,
            azurearm_log_level='info',
            **connection_auth
        )

	connection =  __salt__['azurearm_network.virtual_network_gateway_connection_create_or_update'](
            name=name,
            resource_group=resource_group,
            virtual_network_gateway1=virtual_network_gateway1,
            connection_type=connection_type,
            connection_protocol=connection_protocol,
            enable_bgp=enable_bgp,
            shared_key=shared_key,
	    ipsec_policies=ipsec_policies,
	    local_network_gateway2=localgw2,
            tags=tags,
            **connection_kwargs
        )

    if 'error' not in connection:
        ret['result'] = True
        ret['comment'] = 'Virtual network gateway connection {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create virtual network gateway connection {0}! ({1})'.format(name, connection.get('error'))
    return ret


def virtual_network_gateway_connection_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: Sodium

    Ensure a virtual network gateway connection does not exist in the resource_group.

    :param name:
        Name of the virtual network gateway connection.

    :param resource_group:
        The resource group associated with the virtual network gateway connection.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml
        Ensure virtual network gateway connection absent:
            azurearm_network.virtual_network_gateway_connection_absent:
                - name: connection1
                - resource_group: group1
                - connection_auth: {{ profile }}
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    connection = __salt__['azurearm_network.virtual_network_gateway_connection_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in connection:
        ret['result'] = True
        ret['comment'] = 'Virtual network gateway connection {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Virtual network gateway connection {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': connection,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.virtual_network_gateway_connection_delete'](
        name,
        resource_group,
        **connection_auth
    )

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Virtual network gateway connection {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': connection,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete virtal network gateway connection {0}!'.format(name)
    return ret


def virtual_network_gateway_present(name, resource_group, virtual_network, ip_configurations, gateway_type=None,
				    vpn_type=None, sku=None, enable_bgp=None, active_active=None, bgp_settings=None, 
				    address_prefixes=None, tags=None, connection_auth=None, **kwargs):
    '''
    .. versionadded:: Sodium

    Ensure a virtual network gateway exists.

    :param name: 
        Name of the virtual network gateway.

    :param resource_group: 
        The resource group associated with the virtual network gateway.

    :param virtual_network:
        The virtual network associated with the virtual network gateway.

    :param ip_configurations:
        A list of dictionaries representing valid VirtualNetworkGatewayIPConfiguration objects. Valid parameters are:
          - ``name``: The name of the resource that is unique within a resource group.
          - ``public_ip_address``: Name of an existing public IP address that'll be assigned to the IP config object.
          - ``private_ip_allocation_method``: The private IP allocation method. Possible values are: 
                                              'Static' and 'Dynamic'.
          - ``subnet``: Name of an existing subnet inside of which the IP config will reside. 
        The 'name' & 'public_ip_address' keys are required at minimum. Only one IP configuration dictionary is allowed.

    :param gateway_type:
        The type of this virtual network gateway. Possible values include: 'Vpn', 'ExpressRoute'. 
	The gateway type immutable once set.

    :param vpn_type: 
	The type of this virtual network gateway. Possible values include: 'PolicyBased', 'RouteBased'
	The vpn type is immutable once set.

    :param sku: The virtual network gateway SKU.

    :param enable_bgp: Whether BGP is enabled for this virtual network gateway or not. Defaults as False.
	BGP requires a SKU of VpnGw1, VpnGw2, VpnGw3, Standard, or HighPerformance.

    :param active_active: Whether active-active mode is enabled for this virtual network gateway or not. 
        Defaults as False. Active-active mode requires a SKU of VpnGw1, VpnGw2, VpnGw3, or HighPerformance.    

    :param bgp_settings: 
	A dictionary representing a valid BgpSettings object, which stores the virtual network 
	gateway's BGP speaker settings. Valid parameters are:
	  - ``asn``: The BGP speaker's Autonomous System Number. This is an integer value.
          - ``bgp_peering_address``: The BGP peering address and BGP identifier of this BGP speaker.
	                             This is a string value. 
          - ``peer_weight``: The weight added to routes learned from this BGP speaker. This is an integer value.

    :param gateway_default_site:
	The reference of the LocalNetworkGateway resource which represents local network site having default routes. 
	Assign Null value in case of removing existing default site setting.

    :param vpn_client_configuration
        Look into this further

    :param address_prefixes:
        A list of CIDR blocks which can be used by subnets within the virtual network. Represents the custom routes
	address space specified by the the customer for virtual network gateway and VpnClient.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the virtual network gateway object.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml
        
        Ensure virtual network gateway exists:
            azurearm_network.virtual_network_gateway_present:
                - name: gateway1
                - resource_group: group1
                - virtual_network: vnet1
                - ip_configurations:
                  - name: ip_config1
                    public_ip_address: pub_ip1
                - tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - require:
                  - azurearm_resource: Ensure resource group exists
                  - azurearm_network: Ensure virtual network exists

        Ensure virtual network gateway exists:
	    azurearm_network.virtual_network_gateway_present:
                - name: gateway1
                - resource_group: group1
                - virtual_network: vnet1
                - ip_configurations:
                  - name: ip_config1
                    public_ip_address: pub_ip1
		- tags:
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}
                - gateway_type: 'Vpn'
                - vpn_type: 'RouteBased'
                - enable_bgp: True
                - bgp_settings:
		    asn: 65514
                    bgp_peering_address: 10.2.2.2
                    peering_weight: 0
                - address_prefixes:
       	 	    - '10.0.0.0/8'
        	    - '192.168.0.0/16'
                - require:
                  - azurearm_resource: Ensure resource group exists
                  - azurearm_network: Ensure virtual network gateway exists
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    if sku:
        sku = {'name': sku.capitalize()}

    gateway = __salt__['azurearm_network.virtual_network_gateway_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )      

    if 'error' not in gateway:
        tag_changes = __utils__['dictdiffer.deep_diff'](gateway.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        if ip_configurations:
            comp_ret = __utils__['azurearm.compare_list_of_dicts'](
                gateway.get('ip_configurations', []),
                ip_configurations,
                ['public_ip_address', 'subnet']
            )

            if comp_ret.get('comment'):
                ret['comment'] = '"ip_configurations" {0}'.format(comp_ret['comment'])
                return ret

            if comp_ret.get('changes'):
                ret['changes']['ip_configurations'] = comp_ret['changes']

        if (active_active or False) != gateway.get('active_active'):
            ret['changes']['active_active'] = {
                'old': gateway.get('active_active'),
                'new': active_active
            }

        if (enable_bgp or False) != gateway.get('enable_bgp'):
            ret['changes']['enable_bgp'] = {
	        'old': gateway.get('enable_bgp'),
		'new': enable_bgp
	    }

        if sku:
            sku_changes = __utils__['dictdiffer.deep_diff'](gateway.get('sku', {}), sku)
            if sku_changes:
                ret['changes']['sku'] = sku_changes

        if bgp_settings:
            if not isinstance(bgp_settings, dict):
                ret['comment'] = 'BGP settings must be provided as a dictionary!'
                return ret

            for key in bgp_settings:
                if bgp_settings[key] != gateway.get('bgp_settings', {}).get(key):
                    ret['changes']['bgp_settings'] = {
                        'old': gateway.get('bgp_settings'),
                        'new': bgp_settings
                    }
                    break

        addr_changes = set(address_prefixes or []).symmetric_difference(
            set(gateway.get('custom_routes', {}).get('address_prefixes', [])))
        if addr_changes:
            ret['changes']['custom_routes'] = {
                'address_prefixes': {
                    'old': gateway.get('custom_routes', {}).get('address_prefixes', []),
                    'new': address_prefixes,
                }
            }

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Virtual network gateway {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Virtual network gateway {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'resource_group': resource_group,
                'virtual_network': virtual_network,
                'ip_configurations': ip_configurations,
                'tags': tags,
            }
        }

        if gateway_type:
            ret['changes']['new']['gateway_type'] = gateway_type
        if vpn_type:
            ret['changes']['new']['vpn_type'] = vpn_type
        if sku:
	    ret['changes']['new']['sku'] = sku
        if enable_bgp:
	    ret['changes']['new']['enable_bgp'] = enable_bgp
	if bgp_settings:
	    ret['changes']['new']['bgp_settings'] = bgp_settings
	if active_active:
	    ret['changes']['new']['active_active'] = active_active
	if address_prefixes:
            ret['changes']['new']['custom_routes'] = {'address_prefixes': address_prefixes}

    if __opts__['test']:
        ret['comment'] = 'Virtual network gateway {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    gateway_kwargs = kwargs.copy()
    gateway_kwargs.update(connection_auth)

    gateway = __salt__['azurearm_network.virtual_network_gateway_create_or_update'](
        name=name,
        resource_group=resource_group,
        virtual_network=virtual_network,
        ip_configurations=ip_configurations,
	gateway_type=gateway_type,
	vpn_type=vpn_type,
        tags=tags,
	sku=sku,
	enable_bgp=enable_bgp,
	bgp_settings=bgp_settings,
	active_active=active_active,
	custom_routes={'address_prefixes': address_prefixes},
        **gateway_kwargs
    )

    if 'error' not in gateway:
        ret['result'] = True
        ret['comment'] = 'Virtual network gateway {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create virtual network gateway {0}! ({1})'.format(name, gateway.get('error'))
    return ret


def virtual_network_gateway_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: Sodium

    Ensure a virtual network gateway object does not exist in the resource_group.

    :param name:
        Name of the virtual network gateway object.

    :param resource_group:
        The resource group associated with the virtual network gateway.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml
	Ensure virtual network gateway absent:
	    azurearm_network.virtual_network_gateway_absent:
		- name: gateway1
		- resource_group: group1
		- connection_auth: {{ profile }}
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    gateway = __salt__['azurearm_network.virtual_network_gateway_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in gateway:
        ret['result'] = True
        ret['comment'] = 'Virtual network gateway object {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Virtual network gateway object {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': gateway,
            'new': {},
        }
        return ret

    deleted = __salt__['azurearm_network.virtual_network_gateway_delete'](
        name,
        resource_group,
        **connection_auth
    )

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Virtual network gateway object {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': gateway,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete virtal network gateway object {0}!'.format(name)
    return ret


def local_network_gateway_present(name, resource_group, gateway_ip_address, bgp_settings=None, 
                                  address_prefixes=None, tags=None, connection_auth=None, **kwargs):
    '''
    .. versionadded:: Sodium

    Ensure a location network gateway exists.

    :param name:
        Name of the local network gateway.

    :param resource_group:
        The resource group assigned to the local network gateway.

    :param gateway_ip_address:
        IP address of local network gateway.

    :param bgp_settings: 
	A dictionary representing a valid BgpSettings object, which stores the local network 
	gateway's BGP speaker settings. Valid parameters are:
	  - ``asn``: The BGP speaker's Autonomous System Number. This is an integer value.
          - ``bgp_peering_address``: The BGP peering address and BGP identifier of this BGP speaker.
	                             This is a string value. 
          - ``peer_weight``: The weight added to routes learned from this BGP speaker. This is an integer value.

    :param address_prefixes:
        A list of CIDR blocks which can be used by subnets within the virtual network. 
	Represents the local network site address space.

    :param tags:
        A dictionary of strings can be passed as tag metadata to the virtual network object.
    
    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure local network gateway exists:
            azurearm_network.local_network_gateway_present:
                - name: gateway1
    		- resource_group: rg-module-testing
    		- gateway_ip_address: 192.168.0.1
    		- bgp_settings:
        	    asn: 65515
        	    bgp_peering_address: 10.2.2.2
        	    peer_weight: 0
    		- address_prefixes:
       	 	    - '10.0.0.0/8'
        	    - '192.168.0.0/16'
    		- connection_auth: {{ profile }}  
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    gateway = __salt__['azurearm_network.local_network_gateway_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' not in gateway:
        tag_changes = __utils__['dictdiffer.deep_diff'](gateway.get('tags', {}), tags or {})
        if tag_changes:
            ret['changes']['tags'] = tag_changes

        if gateway_ip_address != gateway.get('gateway_ip_address'):
            ret['changes']['gateway_ip_address'] = {
                'old': gateway.get('gateway_ip_address'),
                'new': gateway_ip_address
            }

        if bgp_settings:
            if not isinstance(bgp_settings, dict):
                ret['comment'] = 'BGP settings must be provided as a dictionary!'
                return ret

            for key in bgp_settings:
                if bgp_settings[key] != gateway.get('bgp_settings', {}).get(key):
                    ret['changes']['bgp_settings'] = {
                        'old': gateway.get('bgp_settings'),
                        'new': bgp_settings
                    }
                    break

        addr_changes = set(address_prefixes or []).symmetric_difference(
            set(gateway.get('local_network_address_space', {}).get('address_prefixes', [])))
        if addr_changes:
            ret['changes']['local_network_address_space'] = {
                'address_prefixes': {
                    'old': gateway.get('local_network_address_space', {}).get('address_prefixes', []),
                    'new': address_prefixes,
                }
            }       

        if not ret['changes']:
            ret['result'] = True
            ret['comment'] = 'Local network gateway {0} is already present.'.format(name)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Local network gateway {0} would be updated.'.format(name)
            return ret

    else:
        ret['changes'] = {
            'old': {},
            'new': {
                'name': name,
                'resource_group': resource_group,
		'gateway_ip_address': gateway_ip_address,
                'tags': tags,
            }
        }
        
        if bgp_settings:
            ret['changes']['new']['bgp_settings'] = bgp_settings
	if address_prefixes:
	    ret['changes']['new']['local_network_address_space'] = {'address_prefixes': address_prefixes}

    if __opts__['test']:
        ret['comment'] = 'Local network gateway {0} would be created.'.format(name)
        ret['result'] = None
        return ret

    gateway_kwargs = kwargs.copy()
    gateway_kwargs.update(connection_auth)

    gateway = __salt__['azurearm_network.local_network_gateway_create_or_update'](
        name=name,
        resource_group=resource_group,
        gateway_ip_address=gateway_ip_address,
        local_network_address_space={'address_prefixes': address_prefixes},
	bgp_settings=bgp_settings,
	tags=tags,
        **gateway_kwargs
    )

    if 'error' not in gateway:
        ret['result'] = True
        ret['comment'] = 'Local network gateway {0} has been created.'.format(name)
        return ret

    ret['comment'] = 'Failed to create local network gateway {0}! ({1})'.format(name, gateway.get('error'))
    return ret


def local_network_gateway_absent(name, resource_group, connection_auth=None):
    '''
    .. versionadded:: Sodium

    Ensure a local network gateway object does not exist in the resource_group.

    :param name:
        Name of the local network gateway object.

    :param resource_group:
        The resource group associated with the local network gateway.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure local network gateway absent:
	    azurearm_network.local_network_gateway_absent:
                - name: gateway1
                - resource_group: group1
                - connection_auth: {{ profile }}
    '''
    ret = {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }

    if not isinstance(connection_auth, dict):
        ret['comment'] = 'Connection information must be specified via connection_auth dictionary!'
        return ret

    gateway = __salt__['azurearm_network.local_network_gateway_get'](
        name,
        resource_group,
        azurearm_log_level='info',
        **connection_auth
    )

    if 'error' in gateway:
        ret['result'] = True
        ret['comment'] = 'Local network gateway object {0} was not found.'.format(name)
        return ret

    elif __opts__['test']:
        ret['comment'] = 'Local network gateway object {0} would be deleted.'.format(name)
        ret['result'] = None
        ret['changes'] = {
            'old': gateway,
            'new': {},
        }
        return ret


    deleted = __salt__['azurearm_network.local_network_gateway_delete'](
        name,
        resource_group,
        **connection_auth
    )

    if deleted:
        ret['result'] = True
        ret['comment'] = 'Local network gateway object {0} has been deleted.'.format(name)
        ret['changes'] = {
            'old': gateway,
            'new': {}
        }
        return ret

    ret['comment'] = 'Failed to delete local network gateway object {0}!'.format(name)
    return ret


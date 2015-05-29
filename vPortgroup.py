#!/usr/bin/python

DOCUMENTATION = '''
---
module: vmware_port_group
short_description: Manage VMware vSphere VDS Portgroup
description:
	- Manage VMware vSphere the portgroups in a given virtual distributed switch
version_added: 1.0
author: '"Daniel Kim" <kdaniel () vmware.com>'
notes:
	- Tested on vSphere 5.5
requirements:
	- "python >= 2.6"
	- PyVmomi
options (all of them are str type):
	hostname:
		description:
			- The hostname or IP address of the vSphere vCenter API server
		required: True
	vs_port:
		description:
			- The port to be used to connect to the vsphere host
		required: False
	username:
		description:
			- The username of the vSphere vCenter
		required: True
		aliases: ['user', 'admin']
	password:
		description:
			- The password of the vSphere vCenter
		required: True
		aliases: ['pass', 'pwd']
	dvs_name:
		description:
			- The name of the distributed virtual switch where the port group is added to.
				The dvs must exist prior to adding a new port group, otherwise, this
				process will fail.
		required: True
	port_group_name:
		description:
			- The name of the port group the cluster will be created in.
		required: True
	port_binding:
		description:
			- Available port binding types - static, dynamic, ephemeral
		required: True
	port_allocation:
		description:
			- Allocation model of the ports - fixed, elastic
			- Fixed allocation always reserve the number of ports requested
			- Elastic allocation increases/decreases the number of ports as needed
		required: True
	numPorts:
		description:
			- The number of the ports for the port group
			- Default value will be 0 - no ports
	state:
		description:
		- If the port group should be present or absent
		choices: ['present', 'absent']
		required: True
'''
EXAMPLES = '''
# Example vmware_datacenter command from Ansible Playbooks
- name: Create Port Group
	local_action: >
		vPortgroup
		hostname="{{ vSphere_host }}" username=root password=vmware
		vsphere_port="443"
		port_group_name="test_port_grp1"
		num_ports="8"
'''
try:
	from pyVmomi import vim, vmodl
	from pyVim import connect
	HAS_PYVMOMI = True
except ImportError:
	HAS_PYVMOMI = False

import ssl
if hasattr(ssl, '_create_default_https_context') and hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

import time

def wait_for_task(task):
	while True:
		if task.info.state == vim.TaskInfo.State.success:
			return True, task.info.result
		if task.info.state == vim.TaskInfo.State.error:
			try:
				raise TaskError(task.info.error)
			except AttributeError:
				raise TaskError("An unknown error has occurred")
		if task.info.state == vim.TaskInfo.State.running:
			time.sleep(10)
		if task.info.state == vim.TaskInfo.State.queued:
			time.sleep(10)

def check_port_group_state(module):
	dvs_name = module.params['dvs_name']
	port_group_name = module.params['port_group_name']
	try:
		content = module.params['content']
		dvs = find_dvs_by_name(content, dvs_name)
		if dvs is None:
			module.fail_json(msg='Target distributed virtual switch does not exist!')
		port_group = find_dvspg_by_name(dvs, port_group_name)
		module.params['dvs'] = dvs
		if port_group is None:
			return 'absent'
		else:
			module.params['port_group'] = port_group
			return 'present'
	except vmodl.RuntimeFault as runtime_fault:
		module.fail_json(msg=runtime_fault.msg)
	except vmodl.MethodFault as method_fault:
		module.fail_json(msg=method_fault.msg)

def state_exit_unchanged(module):
	module.exit_json(changed=False)

def state_destroy_port_group(module):
	# TODO
	module.exit_json(changed=False)

def state_create_port_group(module):
	port_group_name = module.params['port_group_name']
	content = module.params['content']
	dvs = module.params['dvs']
	try:
		if not module.check_mode:
			port_group_spec = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
			port_group_spec.name = port_group_name
			port_group_spec.numPorts = int(module.params['numPorts'])
			#port_group_spec.numPorts = int(4)
			pgTypeMap = {
				'static': 'earlyBinding',
				'dynamic': 'lateBinding',
				'ephemeral': "ephemeral"
			}
			port_group_spec.type = pgTypeMap[module.params['port_binding']]
			pg_policy = vim.dvs.DistributedVirtualPortgroup.PortgroupPolicy()
			port_group_spec.policy = pg_policy
			task = dvs.AddDVPortgroup_Task(spec=[port_group_spec])
			status = task.info.state
			wait_for_task(task)
			module.exit_json(changed=True)
	except Exception, e:
		module.fail_json(msg=str(e))

def main():
	argument_spec = dict(
		hostname=dict(type='str', required=True),
		vs_port=dict(type='str'),
		username=dict(type='str', aliases=['user', 'admin'], required=True),
		password=dict(type='str', aliases=['pass', 'pwd'], required=True, no_log=True),
		dvs_name=dict(type='str', required=True),
		port_group_name=dict(required=True, type='str'),
		port_binding=dict(required=True, choices=['static', 'dynamic', 'ephemeral'], type='str'),
		port_allocation=dict(choices=['fixed', 'elastic'], type='str'),
		numPorts=dict(required=True, type='str'),
		state=dict(required=True, choices=['present', 'absent'], type='str')
	)
	module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

	if not HAS_PYVMOMI:
		module.fail_json(msg='pyvmomi is required for this module')

	port_group_states = {
		'absent': {
			'present': state_destroy_port_group,
			'absent': state_exit_unchanged,
		},
		'present': {
			'present': state_exit_unchanged,
			'absent': state_create_port_group,
		}
	}

	desired_state = module.params['state']

	si = connect.SmartConnect(host=module.params['hostname'],
					user=module.params['username'],
					pwd=module.params['password'],
					port=int(module.params['vs_port']))
	if not si:
		module.fail_json(msg="Could not connect to the specified host using specified "
			"username and password")

	content = si.RetrieveContent()
	module.params['content'] = content

	current_state = check_port_group_state(module)
	port_group_states[desired_state][current_state](module)

	connect.Disconnect(si)


from ansible.module_utils.basic import *
from ansible.module_utils.vmware import *

if __name__ == '__main__':
	main()

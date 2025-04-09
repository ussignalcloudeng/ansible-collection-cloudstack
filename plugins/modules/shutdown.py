#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, René Moser <mail@renemoser.net>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = """
---
module: shutdown
short_description: Prepares, triggers, and cancels shutdown of CloudStack management servers.
description:
    - Prepare, trigger, and cancel shutdown processes for CloudStack management servers. 
author: Alex Dietrich (@adietrich-ussignal)
version_added: 2.5.0
options:
  name:
    description:
      - Name of the management server.
    type: str
    required: true 
  state:
    description:
      - State of the management server shutdown process. 
      - Used to determine what action is taken in the Shutdown process for a management server. 
    type: str
    default: prepare
    choices: [ shutdown,  prepare, cancel ]
extends_documentation_fragment:
- ngine_io.cloudstack.cloudstack
"""

EXAMPLES = """
# NOTE: Names of the management server will depend on the Cloudstack installation it is applied against.
- name: Prepare a management server for shutdown
  ngine_io.cloudstack.shutdown:
    name: cloudstack-mgmt-01
    state: prepare

- name: Cancel shutdown for a management server
  ngine_io.cloudstack.instance_attach_iso:
    name: cloudstack-mgmt-01
    state: cancel

"""

RETURN = """
---
id:
  description: UUID of the management server.
  returned: success
  type: str
  sample: 04589590-ac63-4ffc-93f5-b698b8ac38b6
name:
  description: Name of the management server.
  returned: success
  type: str
  sample: cloudstack-mgmt-01
pending_jobs_count:
  description: Number of jobs in progress.
  returned: success
  type: str
  sample: 1
ready_for_shutdown: 
  description: Indicates whether CloudStack is ready to shutdown
  returned: success 
  type: str 
  sample: 'true'
shutdown_triggered: 
  description: Indicates whether a shutdown has been triggered. 
  returned: success 
  type: str
  sample: 'true'
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.cloudstack import AnsibleCloudStack, cs_argument_spec, cs_required_together


class AnsibleCloudStackShutdown(AnsibleCloudStack):

    def __init__(self, module):
        super(AnsibleCloudStackShutdown, self).__init__(module)
        self.management_server = None
        self.management_server_name = self.module.params.get("name")
        self.returns = {
            "name": "name",
            "managementserverid": "managementserverid",
            "pendingjobscount": "pending_jobs_count",
            "readyforshutdown": "ready_for_shutdown",
            "shutdowntriggered": "shutdown_triggered",
        }

    def get_management_server(self, key=None):
        management_server_name = self.module.params.get("name")
        if not management_server_name:
            return None
        args = {
            "name": management_server_name,
        }

        management_servers = self.query_api("listManagementServers", **args)

        if management_servers: 
            return self._get_by_key(key, management_servers['managementserver'][0])
        
        self.module.fail_json(msg=f"Management Server '{management_server_name}' not found")

    def prepare_for_shutdown(self): 
        self.result["changed"] = True 
        management_server_id = self.get_management_server(key="id")
        args = {
            "managementserverid": management_server_id
        }
        if not self.module.check_mode: 
            resource = self.query_api("prepareForShutdown", **args)
            
            resource['prepareforshutdown']['managementserverid'] = management_server_id

            ready = False
            if resource['prepareforshutdown']['readyforshutdown'] == True: 
              ready = True

            while ready == False:
                resource = self.query_api("readyForShutdown", **args)
                resource['readyforshutdown']['managementserverid'] = management_server_id
                if resource['readyforshutdown']['readyforshutdown'] == True: 
                    ready = True 

        if 'readyforshutdown' in resource.keys():
          return resource['readyforshutdown']
        elif 'prepareforshutdown' in resource.keys(): 
          return resource['prepareforshutdown']
    
    def trigger_shutdown(self): 
        self.result["changed"] = True

        if not self.module.check_mode: 
            resource = self.prepare_for_shutdown()
            args = {
                "managementserverid": resource['readyforshutdown']['managementserverid']
            }
            shutdown = self.query_api("triggerShutdown", **args)

        return shutdown['triggershutdown']
    
    def cancel_shutdown(self): 
        self.result["changed"] = True 
        management_server_id = self.get_management_server(key="id")
        args = {
            "managementserverid": management_server_id
        }
        if not self.module.check_mode: 
            resource = self.query_api("cancelShutdown", **args)
            
            resource['cancelshutdown']['managementserverid'] = management_server_id

            ready = True 
            if resource['cancelshutdown']['readyforshutdown'] == False: 
              ready = False
           
            while ready == True:
                resource = self.query_api("readyForShutdown", **args)
                resource['readyforshutdown']['managementserverid'] = management_server_id
                if resource['readyforshutdown']['shutdowntriggered'] == False: 
                    ready = False 

        if 'cancelshutdown' in resource.keys():
          return resource['cancelshutdown']
        elif 'readyforshutdown' in resource.keys(): 
          return resource['readyforshutdown']

def main():
    argument_spec = cs_argument_spec()
    argument_spec.update(
        dict(
            name=dict(required=True),
            state=dict(choices=["shutdown","prepare","cancel"], default="prepare"),
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_together=cs_required_together(),
        required_one_of=(["name"]),
        supports_check_mode=True,
    )

    management_shutdown = AnsibleCloudStackShutdown(module)

    state = module.params.get("state")
    if state in ["prepare"]:
        management_server = management_shutdown.prepare_for_shutdown()
    elif state in ["shutdown"]:
        management_server = management_shutdown.trigger_shutdown()    
    elif state in ["cancel"]:
        management_server = management_shutdown.cancel_shutdown()

    result = management_shutdown.get_result(management_server)

    module.exit_json(**result)


if __name__ == "__main__":
    main()

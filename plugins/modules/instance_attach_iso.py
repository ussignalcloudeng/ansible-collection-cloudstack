#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, René Moser <mail@renemoser.net>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = """
---
module: instance_attach_iso
short_description: Manages ISOs attaching and detatching from instances and virtual machines on Apache CloudStack based clouds.
description:
    - Attach and detach ISOs from instances
author: Alex Dietrich (@adietrich-ussignal), René Moser (@resmo)
version_added: 2.5.0
options:
  vm:
    description:
      - Host name of the instance. C(name) can only contain ASCII letters.
      - Name will be generated (UUID) by CloudStack if not specified and can not be changed afterwards.
    type: str
    required: true 
  iso:
    description:
      - Name of the ISO. Required when I(state) is attached.
    type: str
  iso_filter:
    description:
      - Name of the filter used to search for the iso.
      - Used for params I(iso) on I(state=present) or I(state=attached).
    type: str
    default: executable
    choices: [ all, featured, self, selfexecutable, sharedexecutable, executable, community ]
  domain:
    description:
      - Domain the instance is related to.
    type: str
  account:
    description:
      - Account the instance is related to.
    type: str
  zone:
    description:
      - Name of the zone in which the instance is deployed in.
    type: str
    required: true
  poll_async:
    description:
      - Poll async jobs until job has finished.
    type: bool
    default: yes
  state:
    description:
      - State of the ISO on the instance.
    type: str
    default: present
    choices: [ attached, detatched, present, absent ]
extends_documentation_fragment:
- ngine_io.cloudstack.cloudstack
"""

EXAMPLES = """
# NOTE: Names of ISOs depending on the CloudStack configuration.
- name: Attach an ISO to an instance
  ngine_io.cloudstack.instance_attach_iso:
    name: web-vm-1
    iso: Linux Debian 7 64-bit
    state: attached

- name: detach an ISO on an instance
  ngine_io.cloudstack.instance_attach_iso:
    name: web-vm-1
    state: detatched

"""

RETURN = """
---
id:
  description: UUID of the instance.
  returned: success
  type: str
  sample: 04589590-ac63-4ffc-93f5-b698b8ac38b6
name:
  description: Name of the instance.
  returned: success
  type: str
  sample: web-01
display_name:
  description: Display name of the instance.
  returned: success
  type: str
  sample: web-01
isoid: 
  description: UUID of the ISO. 
  returned: success 
  type: str 
  sample: a5ab829e-6e2e-4a47-aef7-090ef8543803
isoname: 
  description: Name of the iso. 
  returned: success 
  type: str
  sample: Linux Debian 7 64-bit
isodisplaytext: 
  description: Display text of the ISO
  returned: success 
  type: str 
  sample: 'XenServer Tools Installer ISO (xen-pv-drv-iso)'
"""

from ansible.module_utils.basic import AnsibleModule

from ..module_utils.cloudstack import AnsibleCloudStack, cs_argument_spec, cs_required_together


class AnsibleCloudStackInstanceIso(AnsibleCloudStack):

    def __init__(self, module):
        super(AnsibleCloudStackInstanceIso, self).__init__(module)
        self.instance = None
        self.iso = None
        self.returns = {
            "vm": "name",
            "isoname": "iso",
        }

    def get_iso(self, key=None):
        iso_name = self.module.params.get("iso")
        if not iso_name:
            return None
        args = {
            "name": iso_name,
            "isrecursive": True,
            "listall": True,
        }
        args["isofilter"] = self.module.params.get("iso_filter")

        isos = self.query_api("listIsos", **args)

        if isos:
            return self._get_by_key(key, isos['iso'][0])

        self.module.fail_json(msg=f"ISO '{iso_name}' not found")

    def attach_iso(self):
        self.result["changed"] = True 
        args = {
            "id": self.get_iso(key="id"),
            "virtualmachineid": self.get_vm(key="id"),
        }
        if not self.module.check_mode:
            res = self.query_api("attachIso", **args)
            poll_async = self.module.params.get("poll_async")
            if poll_async:
                self.poll_job(res, "isoname")

        return self.iso


    def detach_iso(self):
        self.result["changed"] = True
        args = {
            "virtualmachineid": self.get_vm(key="id"),
        }
        if not self.module.check_mode:
            res = self.query_api("detachIso", **args)
            if self.module.params.get("poll_async"):
                self.poll_job(res, "isoname")

        return self.iso

    def get_result(self, resource):
        super(AnsibleCloudStackInstanceIso, self).get_result(resource)

        return self.result


def main():
    argument_spec = cs_argument_spec()
    argument_spec.update(
        dict(
            vm=dict(required=True, aliases=["name"]),
            iso=dict(),
            domain=dict(),
            account=dict(),
            zone=dict(required=True),
            state=dict(choices=["present", "absent", "attached", "detatched"], default="present"),
            iso_filter=dict(
                default="all",
                aliases=["iso_filter"],
                choices=["all", "featured", "self", "selfexecutable", "sharedexecutable", "executable", "community"],
            ),
            poll_async=dict(type="bool", default=True),
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_together=cs_required_together(),
        required_one_of=(["vm"]),
        required_if=[
            ['state', 'attached', ['iso']],
        ],
        supports_check_mode=True,
    )

    instance_iso = AnsibleCloudStackInstanceIso(module)

    state = module.params.get("state")
    if state in ["absent", "detatched"]:
        iso = instance_iso.detach_iso()

    elif state in ["present", "attached"]:
        iso = instance_iso.attach_iso()

    result = instance_iso.get_result(iso)

    module.exit_json(**result)


if __name__ == "__main__":
    main()

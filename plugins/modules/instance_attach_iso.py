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
version_added: 0.1.0
options:
  name:
    description:
      - Host name of the instance. C(name) can only contain ASCII letters.
      - Name will be generated (UUID) by CloudStack if not specified and can not be changed afterwards.
      - Either C(name) or C(display_name) is required.
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

import base64

from ansible.module_utils._text import to_bytes, to_text
from ansible.module_utils.basic import AnsibleModule

from ..module_utils.cloudstack import AnsibleCloudStack, cs_argument_spec, cs_required_together


class AnsibleCloudStackInstanceIso(AnsibleCloudStack):

    def __init__(self, module):
        super(AnsibleCloudStackInstanceIso, self).__init__(module)
        self.returns = {
            "name": "name",
            "isoname": "iso",
        }
        self.instance = None
        self.iso = None

    def get_iso(self, key=None):
        iso = self.module.params.get("iso")

        if not iso:
            return None

        args = {
            "isrecursive": True,
            "fetch_list": True,
        }

        if self.iso:
            return self._get_by_key(key, self.iso)

        args["isofilter"] = self.module.params.get("iso_filter")
        args["fetch_list"] = True
        isos = self.query_api("listIsos", **args)
        if isos:
            for i in isos:
                if iso in [i["displaytext"], i["name"], i["id"]]:
                    self.iso = i
                    return self._get_by_key(key, self.iso)

        self.module.fail_json(msg="ISO '%s' not found" % iso)

    def get_instance(self):
        instance = self.instance
        if not instance:
            instance_name = self.get_or_fallback("name", "display_name")
            args = {
                "fetch_list": True,
            }
            # Do not pass zoneid, as the instance name must be unique across zones.
            instances = self.query_api("listVirtualMachines", **args)
            if instances:
                for v in instances:
                    if instance_name.lower() in [v["name"].lower(), v["displayname"].lower(), v["id"]]:
                        self.instance = v
                        break
        return self.instance

    def attach_iso(self):
        instance = self.get_instance()
        
        self.result["changed"] = True 

        args = {}

        args["id"] = self.get_iso(key="id")
        args["virtualmachineid"] = instance["id"]

        if not self.module.check_mode:
          res = self.query_api("attachIso", **args)
          poll_async = self.module.params.get("poll_async")
          if poll_async:
            instance = self.poll_job(res, "isoname")

        return instance

    def detach_iso(self):
        instance = self.get_instance()
        if instance:
            if "isoname" in instance:
                self.result["changed"] = True
                if not self.module.check_mode:
                    res = self.query_api("detachIso", virtualmachineid=instance["id"])
                    poll_async = self.module.params.get("poll_async")
                    if poll_async:
                        instance = self.poll_job(res, "name")
        return instance

    def get_result(self, resource):
        super(AnsibleCloudStackInstanceIso, self).get_result(resource)

        return self.result


def main():
    argument_spec = cs_argument_spec()
    argument_spec.update(
        dict(
            name=dict(),
            iso=dict(),
            state=dict(choices=["present", "absent", "attached", "detatched"], default="present"),
            iso_filter=dict(
                default="executable",
                aliases=["iso_filter"],
                choices=["all", "featured", "self", "selfexecutable", "sharedexecutable", "executable", "community"],
            ),
            poll_async=dict(type="bool", default=True),
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_together=cs_required_together(),
        required_one_of=(["name"]),
        required_if=[
            ['state', 'attached', ['iso']],
        ],
        supports_check_mode=True,
    )

    ainstance = AnsibleCloudStackInstanceIso(module)

    state = module.params.get("state")

    if state in ["absent", "detatched"]:
        instance = ainstance.detach_iso()

    elif state in ["present", "attached"]:
        instance = ainstance.attach_iso()

    result = ainstance.get_result(instance)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

#!/bin/python3
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import shutil
import yaml

import ansible.constants as C
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.module_utils.common.collections import ImmutableDict
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play import Play
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager
from ansible import context

# Global function
def get_dict(yaml_path):
    with open(yaml_path) as stream:
        dict = yaml.safe_load(stream)
    return dict

def run(host_list, module_path, passwd):
    context.CLIARGS = ImmutableDict(connection='smart', module_path=module_path, fork=10, become=None,
                                    become_method=None, become_user=None, check=False, diff=False)
    sources = ','.join(host_list)
    if len(host_list) == 1:
        sources += ','

    loader = DataLoader()
    passwords = dict(vault_pass=passwd)

    results_callback = ResultsCollectorJSONCallback()

    inventory = InventoryManager(loader=loader, sources=sources)

    variable_manager = VariableManager(loader=loader, inventory=inventory)

    tqm = TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=passwords,
        stdout_callback=results_callback,
    )

    play_source = dict(
        name='Ansible Play',
        hosts=host_list,
        gather_facts='no',
        tasks=[
            dict(action=dict(module='shell', args='ls'), register='shell_out'),
            dict(action=dict(module='debug', args=dict(msg='{{shell_out.stdout}}'))),
            dict(action=dict(module='command', args=dict(cmd='/usr/bin/uptime'))),
        ]
    )

    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    try:
        result = tqm.run(play)
    finally:
        tqm.cleanup()
        if loader:
            loader.cleanup_all_tmp_files()

    shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)

    print("UP ***********")
    for host, result in results_callback.host_ok.items():
        print('{0} >>> {1}'.format(host, result._result['stdout']))

    print("FAILED *******")
    for host, result in results_callback.host_failed.items():
        print('{0} >>> {1}'.format(host, result._result['msg']))

    print("DOWN *********")
    for host, result in results_callback.host_unreachable.items():
        print('{0} >>> {1}'.format(host, result._result['msg']))


# Classes
class ResultsCollectorJSONCallback(CallbackBase):
    def __init__(self, *args, **kwargs):
        # super(ResultsCollectorJSONCallback, self).__init__(self, *args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        host = result._host
        self.host_unreachable[host.get_name()] = result

    def v2_runner_on_ok(self, result):
        host = result._host
        self.host_ok[host.get_name()] = result
        print(json.dump({host.name: result._result}, indent=4))

    def v2_runner_on_failed(self, result, *args, **kwargs):
        host = result._host
        self.host_failed[host.get_name()] = result

# Variables
paths = 'resources/paths.yaml'
paths = get_dict(paths)

def main():
    inventory = paths['inventory']
    inventory = get_dict(inventory)

    minecraft = paths['minecraft']
    minecraft = get_dict(minecraft)

    run(inventory['hosts'], paths['minecraft'], 'Password')


if __name__ == '__main__':
    main()
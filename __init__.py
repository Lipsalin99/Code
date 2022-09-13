#!/usr/bin/python3
import sys
import argparse
import subprocess
import os
from ansible.parsing import vault
import iptools
import ipcalc
import urllib3
from urllib3.connection import UnverifiedHTTPSConnection
from urllib3.connectionpool import connection_from_url
urllib3.disable_warnings()
import json
sys.path.append('/opt/tcm/lib')
import xcat
import tcmlogs
import tcmconf
import tools

from ansible.parsing.dataloader import DataLoader
# added by Hrithik Dhakrey on 14OCT2020
try:
    from ansible.vars import VariableManager
except ImportError:
    from ansible.vars.manager import VariableManager

try:
    from ansible.inventory import Inventory
except ImportError:
    # from ansible.inventory.data import InventoryData as Inventory
    from ansible.inventory.manager import InventoryManager as Inventory
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.inventory.group import Group
from ansible.inventory.host import Host

# add new line 
from ansible.module_utils.common.collections import ImmutableDict
from ansible import context


import ansible.constants
ansible.constants.HOST_KEY_CHECKING=False
ansible.constants.DEFAULT_REMOTE_TMP='/tmp/'

os.environ["HOME"]='/tmp/'



log_dir="/var/log/tcm/xcat"
log_file="messages"
fpath_log_file=log_dir+'/'+log_file

INFO = 0
WARN = 1
ERROR = 2


class Options(object):
    def __init__(self):
        self.connection = "smart"
        self.forks = 10
        self.check = False
        self.become = True
        self.become_method = 'sudo'
        self.become_user = 'root'

    def __getattr__(self, name):
        return None


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'json'

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display)
        self.output = None
        self.results = []
        self.handlers = []

    def _new_play(self, play):
        return {
            'play': {
                'name': play.name,
                'id': str(play._uuid)
            },
            'tasks': []
        }

    def _new_task(self, task):
        return {
            'task': {
                'name': task.name,
                'id': str(task._uuid)
            },
            'hosts': {}
        }

    def v2_playbook_on_play_start(self, play):
        self.results.append(self._new_play(play))

    def v2_playbook_on_task_start(self, task, is_conditional):
        self.results[-1]['tasks'].append(self._new_task(task))

    def v2_runner_on_ok(self, result, **kwargs):
        host = result._host
        self.results[-1]['tasks'][-1]['hosts'][host.name] = result._result

    def v2_playbook_on_stats(self, stats):
        """Display info about playbook statistics"""

        hosts = sorted(stats.processed.keys())

        summary = {}
        for h in hosts:
            s = stats.summarize(h)
            summary[h] = s

        output = {
            'plays': self.results,
            'stats': summary
        }
        self.output = output

#         print(json.dumps(output, indent=4, sort_keys=True))

    v2_runner_on_failed = v2_runner_on_ok
    v2_runner_on_unreachable = v2_runner_on_ok
    v2_runner_on_skipped = v2_runner_on_ok

#     def v2_playbook_on_notify(self, host, handler):
#         self.handlers.append({'host': host, 'handler': handler})

    def get_output(self):
        return self.output

    def get_results(self):
        return self.results

    def get_handlers(self):
        return self.handlers


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    if v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def get_xcat_master_nodename():
    """
    Function to get xcat master node name.
    """
    f_status = {}
    # tokenid = config.get('tokenid', '')
    masterip = None
    mastername = None
    baseinfo = xcat.get_baseinfo()
    # print(baseinfo)
    if baseinfo['id'] == 0:
        conf = baseinfo.get('conf', None)
        if conf is not None:
            clustersite = conf.get('clustersite', None)
            if clustersite is not None:
                masterip = clustersite.get('master', None)
    if masterip is None:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get master node ip.'
        return f_status
    cmd = '/usr/bin/sudo /usr/bin/grep -m 1 '+masterip+' /etc/hosts'
    status = subprocess.getstatusoutput(cmd)
    if status[0] == 0:
        cmd_output = status[1]
        if len(cmd_output.split()) >= 2:
            mastername = cmd_output.split()[1]
            f_status['id'] = 0
            f_status['desc'] = 'INFO: successfully fetched TCM management nodeip and nodename.'
            f_status['master'] = {'name': mastername, 'ip': masterip}
            return f_status
    if mastername is None:
        cmd = '/usr/bin/sudo /usr/bin/host '+masterip
        status = subprocess.getstatusoutput(cmd)
        if status[0] == 0:
            cmd_output = status[1]
            if len(cmd_output.split()) >= 5:
                mastername = cmd_output.split()[4].split('.')[0]
                f_status['id'] = 0
                f_status['desc'] = 'INFO: successfully fetched TCM management nodeip and nodename.'
                f_status['master'] = {'name': mastername, 'ip': masterip}
                return f_status

    f_status['id'] = WARN
    f_status['desc'] = 'WARN: Unable to get master node hostame'
    f_status['master'] = {'ip': masterip}
    return f_status


def get_is_xcat_master_node(config):
    """
    Function to get is xcat master node:
    """
    f_status = {}
#     tokenid=config.get('tokenid','')
    hostname = config.get('hostname', '')
    status = get_xcat_master_nodename()
    if status['id'] != 0:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get existing tcm master node information.'+status['desc']
        return f_status
    master_info = status.get('master', None)
    if master_info is not None:
        xcat_mastername = master_info.get('name')
    else:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get existing tcm master name.'
        return f_status
    if hostname == xcat_mastername:
        f_status['id'] = 0
        f_status['desc'] = 'INFO: successfully retrieved master node status.'
        f_status['is_xcat_master_node'] = True
        return f_status
    else:
        f_status['id'] = 0
        f_status['desc'] = 'INFO: successfully retrieved master node status.'
        f_status['is_xcat_master_node'] = False
        return f_status


def update_node_group(config):
    """
    Function to add node to xcat masters group.
    """
    f_status = {}
    # tokenid = config.get('tokenid', '')
    hostname = config.get('hostname', '')
    groupname = config.get('groupname', '')
    is_xcat_master_node = config.get('is_xcat_master_node', False)
    status = get_is_xcat_master_node(config)
    # print(status)
    if status['id'] != 0:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get tcm master node status.'+status['desc']
        return f_status
    is_xcat_master_node = status['is_xcat_master_node']
    # print(is_xcat_master_node)
    if is_xcat_master_node is False:
        cmd = ["/opt/xcat/sbin/nodeadd",hostname,"groups=all,"+groupname]
        # print(cmd)
        cmd_output = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        err=cmd_output.stderr.read()
        if err !=b'':
            f_status['id'] = ERROR
            f_status['desc'] = "ERROR: Unable to add "+hostname + " to TCM group "+groupname+"."
            return f_status
    
    #    print('INFO: Host information for host '+nodename +' removed command executed successfully. Please check status string.')
        f_status['id']=0
        f_status['desc'] = 'INFO: Added ' +hostname+' to TCM masters group.'
        return f_status
    else: 
        f_status['id'] = 1
        f_status['desc'] = 'INFO:' +hostname+' is already in TCM masters group.'
        return f_status
#         URL = "https://localhost/xcatws/nodes/"+hostname
#         encoded_data = json.dumps({"groups": groupname})
#         xcat_tokens = connection_from_url(URL)
#         xcat_tokens.ConnectionCls = UnverifiedHTTPSConnection
#         res = xcat_tokens.request('POST', URL, headers={
#                                   'Content-Type': 'application/json', 'x-auth-token': tokenid}, body=encoded_data)
# #         print res.status
# #         print str(res.data)
#         if res.status == 201:
#             data = str(res.data)
#             f_status['id'] = 0
#             f_status['desc'] = 'INFO: Added ' + \
#                 hostname+' to TCM masters group.'+data
#             return f_status
#         else:
#             f_status['id'] = ERROR
#             f_status['desc'] = "ERROR: Unable to add "+hostname + \
#                 " to TCM group "+groupname+"."+str(res.data)
#             return f_status
#     else:
#         URL = "https://localhost/xcatws/nodes/"+hostname
#         encoded_data = json.dumps({'groups': groupname})
#         xcat_tokens = connection_from_url(URL)
#         xcat_tokens.ConnectionCls = UnverifiedHTTPSConnection
#         res = xcat_tokens.request('PUT', URL, headers={
#                                   'Content-Type': 'application/json', 'x-auth-token': tokenid}, body=encoded_data)
#         if res.status == 200:
#             data = str(res.data)
#             f_status['id'] = 0
#             f_status['desc'] = 'INFO: Added ' + \
#                 hostname+' to TCM masters group.'+data
#             return f_status
#         else:
#             f_status['id'] = ERROR
#             f_status['desc'] = "ERROR: Unable to add "+hostname + \
#                 " to TCM group"+groupname+" ."+str(res.data)
#             return f_status


def remove_cluster_master_node(config):
    """
    Function to remove cluster master node.
    """
    f_status = {}
    # tokenid = config.get('tokenid', '')
    remove_hostname = config.get('hostname', '')
    status = get_xcat_master_nodename(config)
    if status['id'] != 0:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get existing tcm master node information.'+status['desc']
        return f_status
    master_info = status.get('master', None)
    if master_info is not None:
        xcat_mastername = master_info.get('name')
    else:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get existing tcm master name.'
        return f_status
    if remove_hostname == xcat_mastername:
        #         print remove_hostname
        status = xcat.remove_nodeinfo(
            {'hostname': remove_hostname})
#         print status
        if status['id'] == 0:
            f_status['id'] = 0
            f_status['desc'] = 'INFO: Successfully removed host ' + \
                remove_hostname+' from masters group.'
            return f_status
        else:
            f_status['id'] = ERROR
            f_status['desc'] = 'ERROR: Unable to remove host ' + \
                remove_hostname+' from masters group '+status['desc']
            return f_status
    else:
        info = {'tokenid': tokenid, 'hostname': remove_hostname,
                'groupname': 'compute', 'is_xcat_master_node': False}
        status = update_node_group(info)
        if status['id'] == 0:
            f_status['id'] = 0
            f_status['desc'] = 'INFO: Successfully removed host ' + \
                remove_hostname+' from masters group and added to compute group.'
            return f_status
        else:
            f_status['id'] = ERROR
            f_status['desc'] = 'ERROR: Unable to remove host ' + \
                remove_hostname+' from masters group '+status['desc']
            return f_status


def get_cluster_masters():
    """
    Function to get cluster master nodes.
    """
    f_status = {}
    # tokenid = config.get('tokenid')
    groupname = 'masters'
    gstatus = xcat.get_groups()
    if gstatus['id'] == 0:
        groups = gstatus['groups']
        if 'masters' not in groups:
            f_status['id'] = 0
            f_status['desc'] = 'INFO: successfully fetched all master nodes.'
            f_status['masters'] = []
            return f_status
    status = xcat.get_nodenames_from_group(
        {'groupname': groupname})
    # print(status)
    if status['id'] == 0:
        f_status['id'] = 0
        f_status['desc'] = 'INFO: successfully fetched all master nodes.'
        f_status['masters'] = status['allnodes']['masters']['members'].split(
            ',')
        return f_status
    else:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get master nodes '+status['desc']
        return f_status


def add_cluster_masternode(config):
    """
    Function to add cluster master node.
    """
    f_status = {}
    tokenid = config.get('tokenid', '')
    hostname = config.get('hostname', '')
    groupname = 'masters'
    info = {'hostname': hostname, 'groupname': groupname}
    status = update_node_group(info)
    # print(status)
    if status['id'] == 0:
        f_status['id'] = INFO
        f_status['desc'] = 'INFO: successsfully added host ' + \
            hostname+' to cluster master node group.'
        return f_status
    else:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unalbe to add host '+hostname + \
            ' to cluster master node group. '+status['desc']
        return f_status


def create_ansible_hostsfile():
    """
    Function to create ansible hosts config file.
    """
    f_status = {}
    # tokenid = config.get('tokenid', '')
    hosts_conf = "[tcmmaster]\n"
#     hosts_conf+="localhost ansible_connection=local\n\n"
    hosts_conf += "localhost \n\n"
    status = xcat.get_groups()
    if status['id'] == 0:
        for group in status['groups']:
            if group == 'switch':
                continue
            hosts_conf += "["+group+"]\n"
            nstatus = xcat.get_nodenames_from_group(
                {'groupname': group})
            if nstatus['id'] == 0:
                for node in nstatus['allnodes'][group]['members'].split(','):
                    hosts_conf += node+'\n'
                hosts_conf += '\n'
            else:
                f_status['id'] = ERROR
                f_status['desc'] = 'ERROR: Unable to get nodes from group ' + \
                    group+' '+nstatus['desc']
                return f_status
        status = tcmlogs.initialize_env(os.path.dirname(tcmconf.ansible_hosts_file), os.path.basename(
            tcmconf.ansible_hosts_file), hosts_conf, "yes")
#         append_file(tcmconf.ansible_hosts_file, hosts_conf, "yes")
        if status:
            f_status['id'] = 0
            f_status['desc'] = 'INFO: Successfully created ansible hosts file at ' + \
                tcmconf.ansible_hosts_file
            return f_status
        else:
            f_status['id'] = ERROR
            f_status['desc'] = 'ERROR: Unable to write ansible hosts conf lines at ' + \
                tcmconf.ansible_hosts_file+' .'
            return f_status
    else:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get available server groups from TCM server.'
        return f_status


def get_ip_of_hostname(config):
    """
    Function get ip for hostname.
    """
    f_status = {}
    tokenid = config.get('tokenid', '')
    hostname = config.get('hostname', '')
    status = get_xcat_master_nodename()
    if status['id'] == 0:
        mastername = status['master']['name']
        masterip = status['master']['ip']
    else:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get tcm master node information.'+status['desc']
        return f_status
    if hostname == mastername:
        f_status['id'] = 0
        f_status['desc'] = 'INFO: Successfully fetched host '+hostname+' ip.'
        f_status['hostinfo'] = {'ip': masterip, 'name': hostname}
        return f_status
    status = xcat.get_nodeinfo(config)
    if status['id'] == 0:
        for node in status['nodeinfo']:
            if node == hostname:
                nodeip = status['nodeinfo'][node]['ip']
                f_status['id'] = 0
                f_status['desc'] = 'INFO: Successfully fetched host ' + \
                    hostname+' ip.'
                f_status['hostinfo'] = {'ip': nodeip, 'name': hostname}
                return f_status
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get nodeinfo for host ' + \
            hostname+' from tcm server.'
        return f_status
    else:
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Unable to get nodeinfo for host ' + \
            hostname+' from tcm server.'
        return f_status


def run_playbook(config):
    """
    Function to run ansible playbooks.
    """
#     results_callback = callback_loader.get('json')
    f_status = {}
    books = config.get('books', '')
    extra_vars = config.get('extra_vars', {'test': 'test'})
    host_list = config.get('hostlist', [])

    loader = DataLoader()
    variable_manager = VariableManager()

    if len(host_list) == 0:
        host_listfile = tcmconf.ansible_hosts_file
        inventory = Inventory(
            loader=loader, variable_manager=variable_manager, host_list=host_listfile)
    else:
        inventory = Inventory(
            loader=loader, variable_manager=variable_manager, host_list=host_list)

    variable_manager.set_inventory(inventory)

    options = Options()
    # context.CLIARGS = ImmutableDict()

    playbooks = [books]

#     variable_manager.extra_vars={"ansible_ssh_user":"root" , "ansible_ssh_pass":"netweb"}
    variable_manager.extra_vars = extra_vars

    callback = CallbackModule()

    pd = PlaybookExecutor(
        playbooks=playbooks,
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        options=options,
        passwords=None,

    )
    pd._tqm._stdout_callback = callback

    try:
        result = pd.run()
#         return callback
#         print result
        if callback is not None:
            if isinstance(callback, CallbackModule):
                output = callback.get_output()
                results = callback.get_results()
                f_status['id'] = 0
                f_status['desc'] = 'INFO: successfully fetched output for playbook ' + \
                    str(books)+' .'
                f_status['output'] = output
                f_status['results'] = results
                f_status['play_return_code'] = result
                return f_status
            else:
                f_status['id'] = ERROR
                f_status['desc'] = 'ERROR: Unable to get any output from playbook run ' + \
                    str(books)+' .'
                f_status['play_return_code'] = result
                return f_status
        else:
            f_status['id'] = ERROR
            f_status['desc'] = 'ERROR: Unable to get any output from playbook run ' + \
                str(books)+' .'
            return f_status

    except Exception as e:
        #         print e
        f_status['id'] = ERROR
        f_status['desc'] = 'ERROR: Exception raised during playbook run. ' + \
            str(e)
        return f_status


def run_playsource(config):
    """
    Function to execute play book defined as python dictionary.
    """
    f_status = {}
    play_source = config.get('play_source', {})
    extra_vars = config.get('extra_vars', {'test': 'test'})
    host_list = config.get('hostlist', [])

    # context.CLIARGS= ImmutableDict(connection='smart',become_user='root',forks=10,become_method='sudo',
    #                             become=True,check=False,extra_vars=extra_vars,module_path=['/usr/share/ansible'])

    context.CLIARGS = ImmutableDict(
        connection='smart',
        module_path=None,
        forks=25,
        remote_user='root',
        private_key_file=None,
        ssh_common_args=None,
        ssh_extra_args=None,
        sftp_extra_args=None,
        scp_extra_args=None,
        become=True,
        become_method='sudo',
        become_user='root',
        verbosity=20,
        check=False
    )
    # print(extra_vars)
    # print(host_list)
    loader = DataLoader()
    # print(host_list)
    sources = ','.join(host_list)
    if len(host_list) == 1:
        sources += ','
    if len(host_list) == 0:
        host_listfile = tcmconf.ansible_hosts_file
        inventory = Inventory(loader=loader, sources=host_listfile)
    else:
        # host_listfile = tcmconf.ansible_hosts_fi
        inventory = Inventory(loader=loader, sources=sources)
    variable_manager = VariableManager(loader=loader, inventory=inventory)
    # here code 1 not use for some time this is default code
    # if len(host_list) == 0:
    #     host_listfile=tcmconf.ansible_hosts_file
    #     print(host_listfile)
    #     inventory = Inventory(loader=loader, variable_manager=variable_manager,host_list=host_listfile)
    # else:
    #     print(loader)
    #     inventory = Inventory(loader=loader, variable_manager=variable_manager,host_list=host_list)

    variable_manager.set_inventory(inventory)

    options = Options()

#     playbooks = [books]

    # variable_manager.extra_vars={"ansible_ssh_user":"root" , "ansible_ssh_pass":"netweb"}
    # variable_manager.extra_vars = extra_vars
    # comment last line and change tp _extra_vars
    variable_manager._extra_vars = extra_vars
    # print(variable_manager.extra_vars)
    callback = CallbackModule()


#     variable_manager.extra_vars={"ansible_ssh_user":"root" , "ansible_ssh_pass":"netweb"}
#     play_source = {"name":"Ansible Ad-Hoc","hosts":"%s"%ip,"gather_facts":"no","tasks":[{"action":{"module":"command","args":"%s"%order}}]}
#    play_source = {"name":"Ansible Ad-Hoc","hosts":"192.168.2.160","gather_facts":"no","tasks":[{"action":{"module":"command","args":"python ~/store.py del"}}]}
    # print(play_source)
    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)
    tqm = None
    callback = CallbackModule()
    try:
        tqm = TaskQueueManager(
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            # options=options,
            passwords=None,
            run_tree=False,
            stdout_callback=callback
        )
        tqm._stdout_callback = callback
        result = tqm.run(play)
        # print(result)
#         return callback
        if callback is not None:
            if isinstance(callback, CallbackModule):
                output = callback.get_output()
                results = callback.get_results()
                f_status['id'] = 0
                f_status['desc'] = 'INFO: successfully fetched output for play source ' + \
                    str(play_source)+' .'
                f_status['output'] = output
                f_status['results'] = results
                f_status['play_return_code'] = result
                f_status['handlers'] = callback.get_handlers()
                return f_status
            else:
                f_status['id'] = ERROR
                f_status['desc'] = 'ERROR: Unable to get any output from playbook run ' + \
                    str(play_source)+' .'
                f_status['play_return_code'] = result
                return f_status
        else:
            f_status['id'] = ERROR
            f_status['desc'] = 'ERROR: Unable to get any output from playbook run ' + \
                str(play_source)+' .'
            return f_status
    finally:
        if tqm is not None:
            tqm.cleanup()
            if loader:
                loader.cleanup_all_tmp_files()
#         f_status['id']=ERROR
#         f_status['desc']='ERROR: Exception raised during playbook run. '
#         return f_status

    # here code 1


def parse_ansible_playoutput(output):
    """
    Function to parse ansible playbook execution output.
    """
#     print(json.dumps(output,indent=4,sort_keys=True))

#     all_task_status={}
#     tasks=output['plays'][0]['tasks'][0]['hosts']
#     for hostname in tasks.keys():
#         host_task_status={}
#         host_task_status['unreachable']=tasks[hostname].get('unreachable',False)
#         host_task_status['msg']=tasks[hostname].get('msg',None)
#         if host_task_status['msg'] is not None:
#             host_task_status['msg']=host_task_status['msg'].split('\n')[0]
#             host_task_status['is_tasks_execution_started']=False
#             all_task_status[hostname]=host_task_status
#             continue
#         else:
#             host_task_status['is_tasks_execution_started']=True
#         all_task_status[hostname]=host_task_status
#
#         print "hostname: "+hostname+" unreachable: "+str(tasks[hostname].get('unreachable',False))+" msg: "+str(tasks[hostname].get('msg',''))

    status = {}
    plays = []
    for play in output['plays']:
        play_infos = {}
        play_desc = {'name': play['play']['name'], 'id': play['play']['id']}
        play_infos['play'] = play_desc
        tasks = []
        for task in play['tasks']:
            task_infos = {}
            task_desc = {'name': task['task']
                         ['name'], 'id': task['task']['id']}
            task_infos['task'] = task_desc
            all_hosts_task_info = {}
            for hostname in task['hosts']:
                host_task_info = {}
                if task['hosts'][hostname].get('unreachable', False):
                    host_task_info['unreachable'] = task['hosts'][hostname].get(
                        'unreachable', False)
                    if task['hosts'][hostname].get('msg', None) is not None:
                        host_task_info['msg'] = task['hosts'][hostname].get(
                            'msg', None).split('\n')[0]
                        host_task_info['is_tasks_exection_started'] = False
                        all_hosts_task_info[hostname] = host_task_info
                        continue
                    else:
                        host_task_info = {
                            'msg': task['hosts'][hostname].get('msg', None)}
                        all_hosts_task_info[hostname] = host_task_info
                        continue

                invocation = task['hosts'][hostname].get('invocation', None)
                if invocation is None:
                    host_task_info['msg'] = 'invocation key is not found in the dictionary. parsing output canceled.'
                    all_hosts_task_info[hostname] = host_task_info
                    continue
                module_name = invocation.get('module_name', None)
                if module_name is None:
                    host_task_info['msg'] = 'module_name key is not found in the dictionary. parsing output canceled.'
                    all_hosts_task_info[hostname] = host_task_info
                    continue

                if task['hosts'][hostname].get('msg', None) is not None and module_name != 'debug':
                    host_task_info['unreachable'] = task['hosts'][hostname].get(
                        'unreachable', False)
                    host_task_info['msg'] = task['hosts'][hostname].get(
                        'msg', None).split('\n')[0]
                    host_task_info['is_tasks_exection_started'] = False
                    all_hosts_task_info[hostname] = host_task_info
                    continue
                host_task_info['is_tasks_exection_started'] = True
#                 invocation=task['hosts'][hostname].get('invocation',None)
#                 if invocation is None:
#                     host_task_info['msg']='invocation key is not found in the dictionary. parsing output canceled.'
#                     all_hosts_task_info[hostname]=host_task_info
#                     continue
#                 module_name=invocation.get('module_name',None)
#                 if module_name is None:
#                     host_task_info['msg']='module_name key is not found in the dictionary. parsing output canceled.'
#                     all_hosts_task_info[hostname]=host_task_info
#                     continue
                if module_name == 'setup':
                    host_task_info['msg'] = 'setup module for gathering facts.'
                    all_hosts_task_info[hostname] = host_task_info
                    continue
                if module_name == 'debug':
                    host_task_info['msg'] = task['hosts'][hostname].get(
                        'msg', None)
                host_task_info['changed'] = task['hosts'][hostname].get(
                    'changed', None)
                host_task_info['module_name'] = module_name
                host_task_info['rc'] = task['hosts'][hostname].get('rc', None)
                host_task_info['start'] = task['hosts'][hostname].get(
                    'start', None)
                host_task_info['end'] = task['hosts'][hostname].get(
                    'end', None)
                host_task_info['stderr'] = task['hosts'][hostname].get(
                    'stderr', None)
                host_task_info['stdout'] = task['hosts'][hostname].get(
                    'stdout', None)
                host_task_info['stdout_lines'] = task['hosts'][hostname].get(
                    'stdout_lines', None)
                host_task_info['warnings'] = task['hosts'][hostname].get(
                    'warnings', None)
                all_hosts_task_info[hostname] = host_task_info
            task_infos['hosts'] = all_hosts_task_info
            tasks.append(task_infos)
        play_infos['tasks'] = tasks

        plays.append(play_infos)
    status['plays'] = plays
    status['stats'] = output['stats']
    return status
#     print(json.dumps(status,indent=4,sort_keys=True))
 

def parse_ansible_playresults(results):
    """
    Function to parse ansible playbook execution results.
    """
    status = {}
    plays = []
    for play in results:
        play_infos = {}
        play_desc = {'name': play['play']['name'], 'id': play['play']['id']}
        play_infos['play'] = play_desc
        tasks = []
        for task in play['tasks']:
            task_infos = {}
            task_desc = {'name': task['task']
                         ['name'], 'id': task['task']['id']}
            task_infos['task'] = task_desc
            all_hosts_task_info = {}
            for hostname in task['hosts']:
                host_task_info = {}
                if task['hosts'][hostname].get('unreachable', False):
                    host_task_info['unreachable'] = task['hosts'][hostname].get(
                        'unreachable', False)
                    if task['hosts'][hostname].get('msg', None) is not None:
                        host_task_info['msg'] = task['hosts'][hostname].get(
                            'msg', None).split('\n')[0]
                        host_task_info['is_tasks_exection_started'] = False
                        all_hosts_task_info[hostname] = host_task_info
                        continue
                    else:
                        host_task_info = {
                            'msg': task['hosts'][hostname].get('msg', None)}
                        all_hosts_task_info[hostname] = host_task_info
                        continue

                invocation = task['hosts'][hostname].get('invocation', None)
                if invocation is None:
                    host_task_info['msg'] = 'invocation key is not found in the dictionary. parsing output canceled.'
                    all_hosts_task_info[hostname] = host_task_info
                    continue
                module_name = invocation.get('module_name', None)
                if module_name is None:
                    host_task_info['msg'] = 'module_name key is not found in the dictionary. parsing output canceled.'
                    all_hosts_task_info[hostname] = host_task_info
                    continue

                if task['hosts'][hostname].get('msg', None) is not None and module_name != 'debug':
                    host_task_info['unreachable'] = task['hosts'][hostname].get(
                        'unreachable', False)
                    host_task_info['msg'] = task['hosts'][hostname].get(
                        'msg', None).split('\n')[0]
                    host_task_info['is_tasks_exection_started'] = False
                    all_hosts_task_info[hostname] = host_task_info
                    continue
                host_task_info['is_tasks_exection_started'] = True
#                 invocation=task['hosts'][hostname].get('invocation',None)
#                 if invocation is None:
#                     host_task_info['msg']='invocation key is not found in the dictionary. parsing output canceled.'
#                     all_hosts_task_info[hostname]=host_task_info
#                     continue
#                 module_name=invocation.get('module_name',None)
#                 if module_name is None:
#                     host_task_info['msg']='module_name key is not found in the dictionary. parsing output canceled.'
#                     all_hosts_task_info[hostname]=host_task_info
#                     continue
                if module_name == 'setup':
                    host_task_info['msg'] = 'setup module for gathering facts.'
                    all_hosts_task_info[hostname] = host_task_info
                    continue
                if module_name == 'debug':
                    host_task_info['msg'] = task['hosts'][hostname].get(
                        'msg', None)
                host_task_info['changed'] = task['hosts'][hostname].get(
                    'changed', None)
                host_task_info['module_name'] = module_name
                host_task_info['rc'] = task['hosts'][hostname].get('rc', None)
                host_task_info['start'] = task['hosts'][hostname].get(
                    'start', None)
                host_task_info['end'] = task['hosts'][hostname].get(
                    'end', None)
                host_task_info['stderr'] = task['hosts'][hostname].get(
                    'stderr', None)
                host_task_info['stdout'] = task['hosts'][hostname].get(
                    'stdout', None)
                host_task_info['stdout_lines'] = task['hosts'][hostname].get(
                    'stdout_lines', None)
                host_task_info['warnings'] = task['hosts'][hostname].get(
                    'warnings', None)
                all_hosts_task_info[hostname] = host_task_info
            task_infos['hosts'] = all_hosts_task_info
            tasks.append(task_infos)
        play_infos['tasks'] = tasks

        plays.append(play_infos)
    status['plays'] = plays
#     status['stats']=output['stats']
    return status
#     print(json.dumps(status,indent=4,sort_keys=True))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog="TCM ansible")
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands', help='additional help', dest='subcommand')

    get_mastername_parser = subparsers.add_parser('get_mastername', help='get tcm master nodename.')
    # get_mastername_parser.add_argument('-tid', '--tokenid', type=str, metavar='tokenid', help='tokenid needed to get TCM mastername.', required=True)

    update_node_group_parser = subparsers.add_parser('update_node_group', help='get tcm master nodename.')
    update_node_group_parser.add_argument('-tid', '--tokenid', type=str, metavar='tokenid', help='tokenid needed to update group information.', required=True)
    update_node_group_parser.add_argument('-hn', '--hostname', type=str, metavar='hostname', help=' hostname to update group information.', required=True)
    update_node_group_parser.add_argument('-gn', '--groupname', type=str, metavar='groupname', help=' groupname to update group information.', required=True)
#     update_node_group_parser.add_argument('-im',"--is_tcm_master_node", type=str2bool, nargs='?', const=True, default='no', help="is tcm master node.")
    is_tcm_masternode_parser = subparsers.add_parser('is_tcm_masternode', help='check is tcm masternode.')
    is_tcm_masternode_parser.add_argument('-tid', '--tokenid', type=str, metavar='tokenid', help='tokenid needed to check tcm masternode.', required=True)
    is_tcm_masternode_parser.add_argument('-hn', '--hostname', type=str, metavar='hostname', help=' hostname to check tcm masternode or not.', required=True)

    add_cluster_masternode_parser = subparsers.add_parser('add_cluster_master', help='Add cluster master node.')
    # add_cluster_masternode_parser.add_argument('-tid', '--tokenid', type=str, metavar='tokenid', help='tokenid needed to add cluster master.', required=True)
    add_cluster_masternode_parser.add_argument('-hn', '--hostname', type=str, metavar='hostname', help=' hostname to add as cluster master.', required=True)
#     update_node_group_parser.add_argument('-gn','--groupname',type=str,metavar='groupname',help=' groupname to update group information.',required=True)
    get_cluster_masternodes_parser = subparsers.add_parser('get_cluster_masters', help='Add cluster master node.')
    # get_cluster_masternodes_parser.add_argument('-tid', '--tokenid', type=str, metavar='tokenid', help=' tokenid needed to cluster master nodes.', required=True)

    remove_cluster_masternode_parser = subparsers.add_parser('remove_cluster_master', help='Remove cluster master node.')
    # remove_cluster_masternode_parser.add_argument(
        # '-tid', '--tokenid', type=str, metavar='tokenid', help='tokenid needed to remove cluster master.', required=True)
    remove_cluster_masternode_parser.add_argument('-hn', '--hostname', type=str, metavar='hostname', help=' hostname to remove from cluster masters.', required=True)

    create_ansible_hostsfile_parser = subparsers.add_parser('create_ansible_hostsfile', help='create ansible hostsfile.')
    # create_ansible_hostsfile_parser.add_argument('-tid', '--tokenid', type=str, metavar='tokenid', help='tokenid needed to remove cluster master.', required=True)

    get_ip_parser = subparsers.add_parser('get_ip_of_hostname', help='Get ip of given hostname.')
    get_ip_parser.add_argument('-tid', '--tokenid', type=str, metavar='tokenid',help='tokenid needed to get ip of hostname.', required=True)
    get_ip_parser.add_argument('-hn', '--hostname', type=str,metavar='hostname', help=' hostname to get ip.', required=True)

    run_playbook_parser = subparsers.add_parser('run_playbook', help='Run an ansible playbook.')
#     run_playbook_parser.add_argument('-tid','--tokenid',type=str,metavar='tokenid',help='tokenid needed to get hostname information from tcm server.',required=True)
    run_playbook_parser.add_argument('-pb', '--playbook', type=str, metavar='playbook', help=' Ansible playbook to run.', required=True)
    run_playbook_parser.add_argument('-hl', '--hostlist', type=str, metavar='hostlist',help=' comma separated list of hostnames for playbook to run.')
    run_playbook_parser.add_argument('-ev', '--extravars', type=str, metavar='extravars',help=' comma separated list of extra variables name=value for playbook to run.')
#     run_playbook_parser.add_argument('-ev','--extravalues',type=str,metavar='extravalues',help=' comma separated list of extra argument values names for playbook to run.')

    run_playsource_parser = subparsers.add_parser('run_playsource', help='Run an ansible example play source defined in python dictionary.')

    if len(sys.argv) == 1:
        parser.print_help()
        print((parser.parse_args()))
        sys.exit(0)

    args = parser.parse_args()
    if args.subcommand == 'get_mastername':
        # info = {'tokenid': args.tokenid}
        status = get_xcat_master_nodename()
        print(status)
    elif args.subcommand == 'update_node_group':
        info = {'tokenid': args.tokenid,
                'hostname': args.hostname, 'groupname': args.groupname}
        status = update_node_group(info)
        print(status)
    elif args.subcommand == 'is_tcm_masternode':
        info = {'tokenid': args.tokenid, 'hostname': args.hostname}
        status = get_is_xcat_master_node(info)
        print(status)
    elif args.subcommand == 'add_cluster_master':
        info = {'hostname': args.hostname}
        status = add_cluster_masternode(info)
        print(status)
    elif args.subcommand == 'get_cluster_masters':
        # info = {'tokenid': args.tokenid}
        status = get_cluster_masters()
        # print(status)
    elif args.subcommand == 'remove_cluster_master':
        info = {'hostname': args.hostname}
        status = remove_cluster_master_node(info)
        print(status)
    elif args.subcommand == 'create_ansible_hostsfile':
        # info = {'tokenid': args.tokenid}
        status = create_ansible_hostsfile()
        print(status)
    elif args.subcommand == 'get_ip_of_hostname':
        info = {'tokenid': args.tokenid, 'hostname': args.hostname}
        status = get_ip_of_hostname(info)
        print(status)
    elif args.subcommand == 'run_playbook':
        info = {'books': args.playbook}
        if args.hostlist is not None:
            info['hostlist'] = args.hostlist.split(',')
        if args.extravars is not None:
            extra_vars = {}
            for eargs in args.extravars.split(','):
                extra_vars[eargs.split('=')[0]] = eargs.split('=')[1]
            info['extra_vars'] = extra_vars
        status = run_playbook(info)
#         print status
        if status['id'] == 0:
            #             print "playbook run return code: "+str(status['run_code'])
            parsed_output = parse_ansible_playoutput(status['output'])
            status['parsed_output'] = parsed_output

            print("raw Ansible playbook run results as follows ...")
            print("================================================")
#             print"\n\n\n"
            print((json.dumps(status['results'], indent=4, sort_keys=True)))

            print("\n\n\n")
            print("raw Ansible playbook run output as follows ...")
            print("===============================================")
#             print "\n\n\n"
            print((json.dumps(status['output'], indent=4, sort_keys=True)))

            print("\n\n\n")
            print("Parsed Ansible playbook run output as follows ...")
            print("==================================================")
#             print "\n\n\n"
            print(
                (json.dumps(status['parsed_output'], indent=4, sort_keys=True)))

    elif args.subcommand == 'run_playsource':
        play_source = dict(
            name="Ansible Play",
            hosts='localhost',
            gather_facts='no',
            tasks=[
                dict(action=dict(module='shell', args='ls'),
                         register='shell_out'),
                dict(action=dict(module='debug', args=dict(
                    msg='{{shell_out.stdout}}')))
            ]
        )
        info = {'play_source': play_source, 'hostlist': [
            'localhost'], 'extra_vars': {'var1': 'varlue1', 'var2': 'value2'}}
        status = run_playsource(info)
        print(status)
        if status['id'] == 0:
            #             print "playbook run return code: "+str(status['run_code'])
            if status['output'] is not None:
                parsed_output = parse_ansible_playoutput(status['output'])
                status['parsed_output'] = parsed_output
            if status['results'] is not None:
                parsed_results = parse_ansible_playresults(status['results'])
                status['parsed_results'] = parsed_results

            print("raw Ansible playbook run results as follows ...")
            print("================================================")
#             print"\n\n\n"
            print((json.dumps(status['results'], indent=4, sort_keys=True)))

            if status['output'] is not None:
                print("\n\n\n")
                print("raw Ansible playbook run output as follows ...")
                print("===============================================")
#                 print "\n\n\n"
                print((json.dumps(status['output'], indent=4, sort_keys=True)))

            if status['output'] is not None:
                print("\n\n\n")
                print("Parsed Ansible playbook run output as follows ...")
                print("==================================================")
#                 print "\n\n\n"
                print(
                    (json.dumps(status['parsed_output'], indent=4, sort_keys=True)))

            if status['results'] is not None:
                print("\n\n\n")
                print("Parsed Ansible playbook run results as follows ...")
                print("==================================================")
#                 print "\n\n\n"
                print(
                    (json.dumps(status['parsed_results'], indent=4, sort_keys=True)))


# run_playsource(config={'extra_vars': {'ansible_ssh_pass': 'netweb', 'ansible_user': 'root', 'var1': 'varlue1', 'var2': 'value2'}, 'hostlist': ['master'], 'play_source': {'become': True, 'gather_facts': 'no', 'hosts': 'all', 'name': 'get usernames from TCM cluster.', 'tasks': [{'action': {'args': '/opt/tcm/ansible/scripts/get_users.sh', 'module': 'script'}, 'name': 'get usernames from TCM master.'}]}})

import sys
import argparse
import json
sys.path.append('/opt/tcm/lib')
import xcat
import tansible


log_dir="/var/log/tcm/ssh"
log_file="messages"
fpath_log_file=log_dir+'/'+log_file

INFO=0
WARN=1
ERROR=2

def configure_passwordess_ssh(config={'tokenid':None,'groupname':None,'adminusername':'root','adminpassword':'netweb'}):
    """
    Function to configure password less ssh.
    """
    f_status={}
    adminusername=config.get('adminusername',None)
    if adminusername is None:
        f_status['id']=ERROR
        f_status['desc']='ERROR: admin username must passed to configure password less ssh.'
        return f_status
    adminpassword=config.get('adminpassword',None)
    if adminpassword is None:
        f_status['id']=ERROR
        f_status['desc']='ERROR: admin password must passed to confiugre password less ssh.'
        return f_status    
    # tokenid=config.get('tokenid',None)
    # if tokenid is None:
    #     f_status['id']=ERROR
    #     f_status['desc']='ERROR: tokenid passed to configure password less ssh.'
    #     return f_status
    status=tansible.get_cluster_masters()
    if status['id'] != 0:
        f_status['id']=ERROR
        f_status['desc']='ERROR: Unable to get all node names from tcm master. '+status['desc']
        return f_status
    if len(status['masters']) == 0:
        f_status['id']=ERROR
        f_status['desc']='ERROR: masters node list is empty ...'+status['desc']
        return f_status
    master_name=status['masters'][0]
    master_ip=None
    nconfig=config
    nconfig['hostname']=master_name
    # print(nconfig)
    status=tansible.get_ip_of_hostname(nconfig)
    print(status)
    # for k, v in status.items():
    #         for k1,v1 in status.items():
                    
    #             if k == 'id':
    #                 if k1=='desc':
    #                     d={k:v, k1:v1}
    #                     print(d)
  

    if status['id'] == 0:
        master_ip=status['hostinfo']['ip']    
    groupname=config.get('groupname','compute')
    
#     config['groupname']=groupname
#     status=xcat.get_nodenames_from_group(config)
#     if status['id'] != 0:
#         f_status['id']=ERROR
#         f_status['desc']='ERRROR: Unable to get all node names from tcm master. '+status['desc']
#         return f_status
#     computenodes=status['allnodes'][groupname]['members'].split(',')

    groupname=config.get('groupname',None)
    if groupname is None:
        f_status['id']=ERROR
        f_status['desc']='ERROR: groupname must passed to configure tcm_slurm.'
        return f_status

    if type(groupname) is str:
        config['groupname']=groupname
        status=xcat.get_nodenames_from_group(config)
        if status['id'] != 0:
            f_status['id']=ERROR
            f_status['desc']='ERRROR: Unable to get all node names from slurm master. '+status['desc']
            return f_status
        computenodes=status['allnodes'][groupname]['members'].split(',')
    elif type(groupname) is list:
        computenodes=groupname
    else:
        f_status['id']=ERROR
        f_status['desc']='ERROR: groupname should be either valid TCM groupname or list of nodes.'
        return f_status
    
    ssh_task1={
               'name':'create /root/.ssh directory.',
               'action':{
                         'module':'file',
                         'args':{
                                 'path':'/root/.ssh',
                                 'state':'directory',
                                 'mode':'0700'
                                 }
                         }
               }
    
    ssh_task2={
               'name':'copy config files from tcm default location.',
               'action':{
                         'module':'copy',
                         'args':{
                                 'src':'/opt/tcm/files/ssh_files/{{ item }}',
                                 'dest':'/root/.ssh/{{ item }}',
                                 'mode':'0600'
                                 }
                         },
               'with_items':[
                             'authorized_keys',
                             'config',
                             'id_rsa',
                             'id_rsa.pub',
                             'known_hosts'
                             ]
               }
    ssh_task3={
           'name':'copy config files from tcm default location.',
           'action':{
                     'module':'copy',
                     'args':{
                             'src':'/opt/tcm/files/ssh_files/{{ item }}',
                             'dest':'/root/.ssh/{{ item }}',
                             'mode':'0644'
                             }
                     },
           'with_items':[
                         'id_rsa.pub',
                         'known_hosts'
                         ]
           }

    play_source_configure_ssh =  dict(
        name = "configure root user password less ssh.",
        hosts = 'all',
        gather_facts = 'no',
        become = True,
        tasks = [
                ssh_task1,
                ssh_task2,
                ssh_task3
        ]
    )
    computenodes.append(master_name)
    info={'play_source':play_source_configure_ssh,'hostlist':computenodes,'extra_vars':{'ansible_user':adminusername,'ansible_ssh_pass':adminpassword,'var1':'varlue1','var2':'value2'}}
    status=tansible.run_playsource(info)
    # print(status)
    if status['id'] !=0:
        return status
    if status['play_return_code']!=0:
        return status  
    return status

if __name__ == "__main__":

    parser=argparse.ArgumentParser(prog="TCM SSH")
    subparsers=parser.add_subparsers(title='subcommands',description='valid subcommands',help='additional help',dest='subcommand')
    
    confiugre_ssh_parser=subparsers.add_parser('configure_ssh',help='configure SSH.')
    # confiugre_ssh_parser.add_argument('-tid','--tokenid',type=str,metavar='tokenid',help='tokenid needed to get compute nodes info from TCM server.',required=True)    
    confiugre_ssh_parser.add_argument('-gn','--groupname',type=str,metavar='groupname',help='groupname needed to get compute nodes info.',required=True)
    confiugre_ssh_parser.add_argument('-au','--adminusername',type=str,metavar='adminusername',help='admin username needed to configure password less ssh.eg: root',required=True)
    confiugre_ssh_parser.add_argument('-ap','--adminpassword',type=str,metavar='adminpassword',help='admin password needed to configure password less ssh.',required=True)


#     install_opa_driver_parser.add_argument('-ds','--driversource',type=str,metavar='driversource',help='admin password needed to install SLURM.',required=True)    
    
    if len(sys.argv) == 1:
        parser.print_help()
        print((parser.parse_args()))
        sys.exit(0)
    
    args=parser.parse_args()
    if args.subcommand == 'configure_ssh':
#         info={'tokenid':args.tokenid,'groupname':args.groupname,'adminusername':args.adminusername,'adminpassword':args.adminpassword}
        if ',' not in args.groupname:
            info={'groupname':args.groupname,
                  'adminusername':args.adminusername,'adminpassword':args.adminpassword}
        else:
            strings=args.groupname.split(',')
            hostslist=[x.strip() for x in strings if x.strip()]
            info={'tokenid':args.tokenid,'groupname':hostslist,
                  'adminusername':args.adminusername,'adminpassword':args.adminpassword}
        status=configure_passwordess_ssh(info)
#         print status
        if status['id'] !=0:
            # print(status)
            sys.exit(status['id'])
            # print(status)
        # print((status['play_return_code']))
        # print("\n\n\n")
        # print((json.dumps(status['results'],indent=4,sort_keys=True)))
        
import copy
import re
import json
from collections import deque
from func_timeout import func_set_timeout as timeout
import func_timeout.exceptions as timeout_exceptions

import os
import time
from core.lib.content import Task
from core.lib.common import LOGGER, Context, YamlOps, FileOps, Counter, SystemConstant
from core.lib.network import http_request, NodeInfo, PortInfo, merge_address, NetworkAPIPath, NetworkAPIMethod

from kube_helper import KubeHelper
from kube_template_helper import KubeTemplateHelper
from ecs_template_helper import ECSTemplateHelper


class BackendCore:
    def __init__(self):

        self.kube_template_helper = KubeTemplateHelper(Context.get_file_path(0))
        self.ecs_template_helper = ECSTemplateHelper(Context.get_file_path(0))

        self.namespace = ''
        self.image_meta = None
        self.schedulers = None
        self.services = None
        self.result_visualization_configs = None
        self.system_visualization_configs = None
        self.customized_source_result_visualization_configs = {}

        self.source_configs = []

        self.dags = []

        self.time_ticket = 0

        self.result_url = None
        self.result_file_url = None
        self.resource_url = None
        self.log_fetch_url = None
        self.log_clear_url = None

        self.inner_datasource = self.check_simulation_datasource()
        self.source_open = False
        self.source_label = ''

        self.task_results = {}

        self.is_get_result = False

        self.cur_yaml_docs = None
        self.save_yaml_path = 'resources.yaml'
        self.log_file_path = 'log.json'

        self.cur_ecs_service_id_list = []

        self.default_visualization_image = 'default_visualization.png'

        self.parse_base_info()

    def parse_base_info(self):
        try:
            base_info = self.kube_template_helper.load_base_info()
            self.namespace = base_info['namespace']
            self.image_meta = base_info['default-image-meta']
            self.schedulers = base_info['scheduler-policies']
            self.services = base_info['services']
            self.result_visualization_configs = base_info['result-visualizations']
            self.system_visualization_configs = base_info['system-visualizations']
        except KeyError as e:
            LOGGER.warning(f'Parse base info failed: {str(e)}')

    def get_log_file_name(self):
        base_info = self.kube_template_helper.load_base_info()
        load_file_name = base_info['log-file-name']
        if not load_file_name:
            return None
        return load_file_name.split('.')[0]

    def parse_and_apply_templates(self, policy, source_deploy):
        service_dict, source_deploy = self.extract_service_from_source_deployment(source_deploy)

        kube_service_dict = {}
        ecs_service_dict = {}

        for service_id, service in service_dict.items():
            service_edge_nodes = service['node']

            kube_service_edge_nodes = [node for node in service_edge_nodes if NodeInfo.get_node_role(node) == 'edge']
            # processor的service_dict需要在云端同时下装，因此边缘节点为空时也要保留字段
            kube_service_dict[service_id] = {'service_name': service['service_name'], 
                                            'yaml': service['yaml'], 
                                            'node': kube_service_edge_nodes}
            
            ecs_service_edge_nodes = [node for node in service_edge_nodes if NodeInfo.get_node_role(node) == 'edge-sylixos']
            if ecs_service_edge_nodes:
                ecs_service_dict[service_id] = {'service_name': service['service_name'], 
                                                'yaml': service['yaml'], 
                                                'node': ecs_service_edge_nodes}
            
        kube_source_deploy = []
        ecs_source_deploy = []

        for source_info in source_deploy:
            source_edge_nodes = source_info['node_set']

            kube_source_edge_nodes = [node for node in source_edge_nodes if NodeInfo.get_node_role(node) == 'edge']
            if kube_source_edge_nodes:
                kube_source_deploy.append({'source': source_info['source'], 'dag': source_info['dag'], 'node_set': kube_source_edge_nodes})

            ecs_source_edge_nodes = [node for node in source_edge_nodes if NodeInfo.get_node_role(node) == 'edge-sylixos']
            if ecs_source_edge_nodes:
                ecs_source_deploy.append({'source': source_info['source'], 'dag': source_info['dag'], 'node_set': ecs_source_edge_nodes})


        kube_dict = self.kube_template_helper.load_template_config(policy, kube_service_dict)
        ecs_dict = self.ecs_template_helper.load_template_config(policy, ecs_service_dict)

        kube_edge_nodes = self.kube_template_helper.get_all_selected_edge_nodes(kube_dict)
        ecs_edge_nodes = self.ecs_template_helper.get_all_selected_edge_nodes(ecs_dict)
        cloud_node = NodeInfo.get_cloud_node()

        first_stage_components = ['scheduler', 'distributor', 'monitor', 'controller']
        second_stage_components = ['generator', 'processor']

        # first stage: kube deploy
        LOGGER.info(f'[First Deployment Stage] deploy components:{first_stage_components}')
        first_yaml_list = self.kube_template_helper.finetune_parameters(kube_dict, kube_source_deploy, kube_edge_nodes, cloud_node,
                                                                        scopes=first_stage_components)
        try:
            result, msg = self.install_yaml_templates(first_yaml_list)
        except timeout_exceptions.FunctionTimedOut as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'first-stage install timeout after 60 seconds'
        except Exception as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'unexpected system error, please refer to logs in backend'
        finally:
            self.save_component_yaml(first_yaml_list)
        if not result:
            return False, msg
        
        # first stage: ecs deploy (edge only)
        first_json_list = self.ecs_template_helper.finetune_parameters(ecs_dict, ecs_source_deploy, ecs_edge_nodes, None,
                                                                        scopes=first_stage_components)
        try:
            result, msg, first_service_id_list = self.install_json_templates(first_json_list)
            self.save_component_ecs_service_id(first_service_id_list)
        except timeout_exceptions.FunctionTimedOut as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'first-stage install timeout after 120 seconds'
        except Exception as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'unexpected system error, please refer to logs in backend'
        if not result:
            return False, msg

        # second stage: kube deploy
        LOGGER.info(f'[Second Deployment Stage] deploy components:{second_stage_components}')
        second_yaml_list = self.kube_template_helper.finetune_parameters(kube_dict, kube_source_deploy, kube_edge_nodes, cloud_node,
                                                                         scopes=second_stage_components)
        try:
            result, msg = self.install_yaml_templates(second_yaml_list)
        except timeout_exceptions.FunctionTimedOut as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'second-stage install timeout after 60 seconds'
        except Exception as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'unexpected system error, please refer to logs in backend'
        finally:
            self.save_component_yaml(first_yaml_list + second_yaml_list)
        if not result:
            return False, msg

        # second stage: ecs deploy (edge only)
        second_json_list = self.ecs_template_helper.finetune_parameters(ecs_dict, ecs_source_deploy, ecs_edge_nodes, None,
                                                                         scopes=second_stage_components)
        try:
            result, msg, second_service_id_list = self.install_json_templates(second_json_list)
            self.save_component_ecs_service_id(second_service_id_list)
        except timeout_exceptions.FunctionTimedOut as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'second-stage install timeout after 120 seconds'
        except Exception as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            result = False
            msg = 'unexpected system error, please refer to logs in backend'
        if not result:
            return False, msg

        return True, 'Install services successfully'

    def parse_and_delete_templates(self):
        docs = self.get_yaml_docs()
        try:
            result, msg = self.uninstall_yaml_templates(docs)
        except timeout_exceptions.FunctionTimedOut as e:
            msg = 'timeout after 120 seconds'
            result = False
            LOGGER.warning(f'Uninstall services failed: {msg}')
        except Exception as e:
            LOGGER.warning(f'Uninstall services failed: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = f'unexpected system error, please refer to logs in backend'
        if not result:
            return result, msg

        ecs_service_id_list = self.get_ecs_service_id_list()
        try:
            result, msg = self.uninstall_json_templates(ecs_service_id_list)
        except timeout_exceptions.FunctionTimedOut as e:
            msg = 'timeout after 120 seconds'
            result = False
            LOGGER.warning(f'Uninstall services failed: {msg}')
        except Exception as e:
            LOGGER.warning(f'Uninstall services failed: {str(e)}')
        if not result:
            return result, msg

        return True, 'Uninstall services successfully'

    @timeout(120)
    def uninstall_yaml_templates(self, yaml_docs):
        res = KubeHelper.delete_custom_resources(yaml_docs)
        while KubeHelper.check_component_pods_exist(self.namespace):
            time.sleep(1)
        return res, '' if res else 'kubernetes api error'

    @timeout(60)
    def install_yaml_templates(self, yaml_docs):
        if not yaml_docs:
            return False, 'components yaml data is empty'
        _result = KubeHelper.apply_custom_resources(yaml_docs)
        while not KubeHelper.check_pods_running(self.namespace):
            time.sleep(1)
        return _result, '' if _result else 'kubernetes api error'

    def save_component_yaml(self, docs_list):
        self.cur_yaml_docs = docs_list
        YamlOps.write_all_yaml(docs_list, self.save_yaml_path)

    @timeout(120)
    def uninstall_json_templates(self, service_id_list):
        if not service_id_list:
            return False, 'service id list is empty'
        
        ecsm_host = str(Context.get_parameter('ECSM_HOST'))
        ecsm_port = str(Context.get_parameter('ECSM_PORT'))
        remote_api_url = merge_address(ip=ecsm_host, 
                                    port=ecsm_port, 
                                    path=NetworkAPIPath.BACKEND_ECSM_UNINSTALL_SERVICE)   
                
        _result = False

        max_retries = 10
        retry_count = 0
        while retry_count < max_retries:
            try:
                response_data = http_request(
                    url=remote_api_url,
                    method=NetworkAPIMethod.BACKEND_ECSM_UNINSTALL_SERVICE,
                    headers={
                        'Content-Type': 'application/json'
                    },
                    json={"ids": service_id_list},
                    timeout=5
                )
                # 检查返回值是否有效
                if not response_data:
                    LOGGER.warning("Empty response from remote API.")
                elif isinstance(response_data, dict) and response_data.get('status') == 200:
                    _result = True
                    LOGGER.info(f"Service {service_id_list} uninstalled successfully")
                    break
                else:
                    error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                    LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
            
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)
        
        if not _result:
            return False, 'unexpected system error, please refer to logs in backend'

        return True, 'Uninstall services successfully'

    def query_service_id_by_name(self, service_name):
        ecsm_host = str(Context.get_parameter('ECSM_HOST'))
        ecsm_port = str(Context.get_parameter('ECSM_PORT'))
        remote_api_url = merge_address(ip=ecsm_host, 
                                    port=ecsm_port, 
                                    path=NetworkAPIPath.BACKEND_ECSM_QUERY_SERVICE.format(service_name=service_name))   
                
        service_id = None
        
        max_retries = 10
        retry_count = 0
        while retry_count < max_retries:
            try:
                response_data = http_request(
                    url=remote_api_url,
                    method=NetworkAPIMethod.BACKEND_ECSM_QUERY_SERVICE,
                    timeout=2
                )
                
                # 检查返回值是否有效
                if not response_data:
                    LOGGER.warning("Empty response from remote API.")
                elif isinstance(response_data, dict) and response_data.get('status') == 200:
                    service_id = response_data["data"]["list"][0]["id"]
                    break
                else:
                    error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                    LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
                
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)
        
        return service_id

    @timeout(120)
    def install_json_templates(self, json_docs):
        if not json_docs:
            return False, 'components json data is empty', []
        
        service_id_list = []
        
        for json_doc in json_docs:
            ecsm_host = str(Context.get_parameter('ECSM_HOST'))
            ecsm_port = str(Context.get_parameter('ECSM_PORT'))
            remote_api_url = merge_address(ip=ecsm_host, 
                                        port=ecsm_port, 
                                        path=NetworkAPIPath.BACKEND_ECSM_INSTALL_SERVICE)   
                   
            _result = False
            
            LOGGER.info(f"Installing service, json config: {json.dumps(json_doc)}")

            max_retries = 10
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response_data = http_request(
                        url=remote_api_url,
                        method=NetworkAPIMethod.BACKEND_ECSM_INSTALL_SERVICE,
                        headers={
                            'Content-Type': 'application/json'
                        },
                        json=json_doc,
                        timeout=5
                    )
                    
                    # 检查返回值是否有效
                    if not response_data:
                        LOGGER.warning("Empty response from remote API.")
                    elif isinstance(response_data, dict) and response_data.get('status') == 200:
                        _result = True
                        service_id = response_data["data"]["id"]
                        service_id_list.append(service_id)
                        break
                    elif isinstance(response_data, dict) and response_data.get('status') == 31006:
                        # 服务名字已存在，说明已下装完成但丢失了返回信息，于是重新查询service_id
                        _result = True
                        service_id = self.query_service_id_by_name(json_doc['name'])
                        service_id_list.append(service_id)
                        break
                    else:
                        error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                        LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")
                except Exception as e:
                    LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
                    
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1)
            
            if not _result:
                return False, 'unexpected system error, please refer to logs in backend', service_id_list

        return True, 'Install services successfully', service_id_list

    def save_component_ecs_service_id(self, service_id_list):
        self.cur_ecs_service_id_list.extend(service_id_list)

    def extract_service_from_source_deployment(self, source_deploy):
        service_dict = {}

        for s in source_deploy:
            dag = s['dag']
            node_set = s['node_set']
            extracted_dag = copy.deepcopy(dag)
            del extracted_dag['_start']

            def get_service_callback(node_item):
                service_id = node_item['id']
                service = self.find_service_by_id(service_id)
                service_name = service['service']
                service_yaml = service['yaml']
                if service_id in service_dict:
                    pre_node_list = service_dict[service_id]['node']
                    service_dict[service_id]['node'] = list(set(pre_node_list + node_set))
                else:
                    service_dict[service_id] = {'service_name': service_name, 'yaml': service_yaml, 'node': node_set}

                extracted_dag[node_item['id']]['service'] = service

            self.bfs_dag(dag, get_service_callback)
            s['dag'] = extracted_dag

        return service_dict, source_deploy

    def get_yaml_docs(self):
        if self.cur_yaml_docs:
            return self.cur_yaml_docs
        elif os.path.exists(self.save_yaml_path):
            return YamlOps.read_all_yaml(self.save_yaml_path)
        else:
            return None

    def clear_yaml_docs(self):
        self.cur_yaml_docs = None
        FileOps.remove_file(self.save_yaml_path)

    def get_ecs_service_id_list(self):
        return self.cur_ecs_service_id_list

    def clear_ecs_service_id(self):
        self.cur_ecs_service_id_list = []

    def find_service_by_id(self, service_id):
        for service in self.services:
            if service['id'] == service_id:
                return service
        return None

    def find_dag_by_id(self, dag_id):
        for dag in self.dags:
            if dag['dag_id'] == dag_id:
                return dag['dag']
        return None

    def find_scheduler_policy_by_id(self, policy_id):
        for policy in self.schedulers:
            if policy['id'] == policy_id:
                return policy
        return None

    def find_datasource_configuration_by_label(self, source_label):
        for source_config in self.source_configs:
            if source_config['source_label'] == source_label:
                return source_config
        return None

    def fill_datasource_config(self, config):
        config['source_label'] = f'source_config_{Counter.get_count("source_label")}'
        source_list = config['source_list']
        for index, source in enumerate(source_list):
            source['id'] = index
            source['url'] = self.fill_datasource_url(source['url'], config['source_type'], config['source_mode'], index)

        config['source_list'] = source_list
        return config

    def fill_datasource_url(self, url, source_type, source_mode, source_id):
        if not self.inner_datasource:
            return url
        source_hostname = KubeHelper.get_pod_node(SystemConstant.DATASOURCE.value, self.namespace)
        if not source_hostname:
            assert None, 'Datasource pod not exists.'
        source_protocol = source_mode.split('_')[0]
        source_ip = NodeInfo.hostname2ip(source_hostname)
        source_port = PortInfo.get_component_port(SystemConstant.DATASOURCE.value)
        url = f'{source_protocol}://{source_ip}:{source_port}/{source_type}{source_id}'

        return url

    @staticmethod
    def bfs_dag(dag_graph, dag_callback):
        source_list = dag_graph['_start']
        queue = deque(source_list)
        visited = set(source_list)
        while queue:
            current_node_item = dag_graph[queue.popleft()]
            dag_callback(current_node_item)
            for child_id in current_node_item['succ']:
                if child_id not in visited:
                    queue.append(child_id)
                    visited.add(child_id)

    @staticmethod
    def check_node_exist(node):
        return node in NodeInfo.get_node_info()

    @staticmethod
    def get_edge_nodes():
        def sort_key(item):
            name = item['name']
            patterns = [
                (r'^edge(\d+)$', 0),
                (r'^edgexn(\d+)$', 1),
                (r'^edgex(\d+)$', 2),
                (r'^edgen(\d+)$', 3),
                (r'^edgeADP(\d+)$', 4),
            ]
            for pattern, group in patterns:
                match = re.match(pattern, name)
                if match:
                    num = int(match.group(1))
                    return group, num
            return len(patterns), 0

        node_role = NodeInfo.get_node_info_role()
        edge_nodes = [{'name': node_name} for node_name in node_role 
                      if node_role[node_name] == 'edge' or node_role[node_name] == 'edge-sylixos']
        edge_nodes.sort(key=sort_key)
        return edge_nodes

    def check_simulation_datasource(self):
        return KubeHelper.check_pod_name('datasource', namespace=self.namespace)

    def check_dag(self, dag):

        def topo_sort(graph):
            in_degree = {}
            for node in graph.keys():
                if node != '_start':
                    in_degree[node] = len(graph[node]['prev'])
            queue = copy.deepcopy(graph['_start'])
            topo_order = []

            while queue:
                parent = queue.pop(0)
                topo_order.append(parent)
                for child in graph[parent]['succ']:
                    parent_service = self.find_service_by_id(parent)
                    child_service = self.find_service_by_id(child)
                    if not parent_service or not child_service:
                        error_msg = f"Missing service definition for node {parent if not parent_service else child}"
                        LOGGER.error(f"DAG Validation Error: {error_msg}")
                        return False, error_msg
                    if child_service['input'] != parent_service['output']:
                        error_msg = (
                            f"Node connection mismatch, '{parent}' output '{parent_service['output']}', '{child}' input '{child_service['input']}' "
                        )
                        LOGGER.error(f"DAG Validation Error: {error_msg}")
                        return False, error_msg

                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)

            if len(topo_order) != len(in_degree):
                error_msg = "DAG contains cycles or unreachable nodes"
                LOGGER.warning(f"DAG Validation Error: {error_msg}")
                return False, error_msg

            return True, "DAG validation passed"

        return topo_sort(dag.copy())

    def get_source_ids(self):
        source_ids = []
        source_config = self.find_datasource_configuration_by_label(self.source_label)
        if not source_config:
            return []
        for source in source_config['source_list']:
            source_ids.append(source['id'])

        return source_ids

    def prepare_result_visualization_data(self, task):
        source_id = task.get_source_id()
        visualizations = self.customized_source_result_visualization_configs[
            source_id] if source_id in self.customized_source_result_visualization_configs else self.result_visualization_configs
        visualization_data = []
        for idx, vf in enumerate(visualizations):
            try:
                al_name = vf['hook_name']
                al_params = eval(vf['hook_params']) if 'hook_params' in vf else {}
                al_params.update({'variables': vf['variables']})
                vf_func = Context.get_algorithm('RESULT_VISUALIZER', al_name=al_name, **al_params)
                visualization_data.append({"id": idx, "data": vf_func(task)})
            except Exception as e:
                LOGGER.warning(f'Failed to load result visualization data: {e}')
                LOGGER.exception(e)

        return visualization_data

    def prepare_system_visualizations_data(self):
        visualization_data = []
        for idx, vf in enumerate(self.system_visualization_configs):
            try:
                al_name = vf['hook_name']
                al_params = eval(vf['hook_params']) if 'hook_params' in vf else {}
                al_params.update({'variables': vf['variables']})
                vf_func = Context.get_algorithm('SYSTEM_VISUALIZER', al_name=al_name, **al_params)
                visualization_data.append({"id": idx, "data": vf_func()})
            except Exception as e:
                LOGGER.warning(f"Failed to load system visualization data: {e}")
                LOGGER.exception(e)

        return visualization_data

    def parse_task_result(self, results):
        for result in results:
            if result is None or result == '':
                continue

            task = Task.deserialize(result)

            source_id = task.get_source_id()
            task_id = task.get_task_id()
            file_path = self.get_file_result(task.get_file_path())
            LOGGER.debug(task.get_delay_info())

            try:
                visualization_data = self.prepare_result_visualization_data(task)
            except Exception as e:
                LOGGER.warning(f'Prepare visualization data failed: {str(e)}')
                LOGGER.exception(e)
                continue

            if os.path.exists(file_path):
                os.remove(file_path)

            if not self.source_open:
                break

            self.task_results[source_id].put_all([{
                'task_id': task_id,
                'data': visualization_data,
            }])

    def run_get_result(self):
        time_ticket = 0
        while self.is_get_result:
            try:
                time.sleep(1)
                self.get_result_url()
                if not self.result_url:
                    LOGGER.debug('[NO RESULT] Fetch result url failed.')
                    continue
                response = http_request(self.result_url,
                                        method=NetworkAPIMethod.DISTRIBUTOR_RESULT,
                                        json={'time_ticket': time_ticket, 'size': 0})

                if not response:
                    self.result_url = None
                    self.result_file_url = None
                    LOGGER.debug('[NO RESULT] Request result url failed.')
                    continue

                time_ticket = response["time_ticket"]
                LOGGER.debug(f'time ticket: {time_ticket}')
                results = response['result']
                self.parse_task_result(results)

            except Exception as e:
                LOGGER.warning(f'Error occurred in getting task result: {str(e)}')
                LOGGER.exception(e)

    def get_system_parameters(self):
        return [{'data': self.prepare_system_visualizations_data()}]

    def check_datasource_config(self, config_path):
        if not YamlOps.is_yaml_file(config_path):
            return None

        config = YamlOps.read_yaml(config_path)
        try:
            source_name = config['source_name']
            source_type = config['source_type']
            source_mode = config['source_mode']
            for camera in config['source_list']:
                name = camera['name']
                if self.inner_datasource:
                    directory = camera['dir']
                else:
                    url = camera['url']
                metadata = camera['metadata']

        except Exception as e:
            LOGGER.warning(f'Datasource config file format error: {str(e)}')
            LOGGER.exception(e)
            return None

        return config

    def check_visualization_config(self, config_path):
        if not YamlOps.is_yaml_file(config_path):
            return None

        config = YamlOps.read_yaml(config_path)

        try:
            for visualization in config:
                viz_name = visualization['name']
                assert isinstance(viz_name, str), '"name" is not a string'
                viz_type = visualization['type']
                assert isinstance(viz_type, str), '"type" is not a string'
                viz_var = visualization['variables']
                assert isinstance(viz_var, list), '"variables" is not a list'
                viz_size = visualization['size']
                assert isinstance(viz_size, int), '"size" is not an integer'
                if 'hook_name' in visualization:
                    assert isinstance(visualization['hook_name'], str), '"hook_name" is not a string'
                if 'hook_params' in visualization:
                    assert isinstance(visualization['hook_params'], str), '"hook_params" is not a string(dict)'
                    assert isinstance(eval(visualization['hook_params']), dict), '"hook_params" is not a string(dict)'
                if 'x_axis' in visualization:
                    assert isinstance(visualization['x_axis'], str), '"x_axis" is not a string'
                if 'y_axis' in visualization:
                    assert isinstance(visualization['y_axis'], str), '"y_axis" is not a string'
            return config
        except Exception as e:
            LOGGER.warning(f'Visualization config file format error: {str(e)}')
            LOGGER.exception(e)
            return None

    def get_resource_url(self):
        cloud_hostname = NodeInfo.get_cloud_node()
        try:
            scheduler_port = PortInfo.get_component_port(SystemConstant.SCHEDULER.value)
        except AssertionError:
            return
        self.resource_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                          port=scheduler_port,
                                          path=NetworkAPIPath.SCHEDULER_GET_RESOURCE)

    def get_result_url(self):
        cloud_hostname = NodeInfo.get_cloud_node()
        try:
            distributor_port = PortInfo.get_component_port(SystemConstant.DISTRIBUTOR.value)
        except AssertionError:
            return
        self.result_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                        port=distributor_port,
                                        path=NetworkAPIPath.DISTRIBUTOR_RESULT)
        self.result_file_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                             port=distributor_port,
                                             path=NetworkAPIPath.DISTRIBUTOR_FILE)

    def get_log_url(self):
        cloud_hostname = NodeInfo.get_cloud_node()
        try:
            distributor_port = PortInfo.get_component_port(SystemConstant.DISTRIBUTOR.value)
        except AssertionError:
            return
        self.log_fetch_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                           port=distributor_port,
                                           path=NetworkAPIPath.DISTRIBUTOR_ALL_RESULT)
        self.log_clear_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                           port=distributor_port,
                                           path=NetworkAPIPath.DISTRIBUTOR_CLEAR_DATABASE)

    def get_file_result(self, file_name):
        if not self.result_file_url:
            return ''
        response = http_request(self.result_file_url,
                                method=NetworkAPIMethod.DISTRIBUTOR_FILE,
                                no_decode=True,
                                json={'file': file_name},
                                stream=True)
        if response is None:
            self.result_file_url = None
            return ''
        with open(file_name, 'wb') as file_out:
            for chunk in response.iter_content(chunk_size=8192):
                file_out.write(chunk)
        return file_name

    def download_log_file(self):
        self.parse_base_info()
        self.get_log_url()
        if not self.log_fetch_url:
            return ''

        response = http_request(self.log_fetch_url, method=NetworkAPIMethod.DISTRIBUTOR_ALL_RESULT, )
        if response is None:
            self.log_fetch_url = None
            return ''
        results = response['result']

        http_request(self.log_clear_url, method=NetworkAPIMethod.DISTRIBUTOR_CLEAR_DATABASE)

        return results

    def get_result_visualization_config(self, source_id):
        self.parse_base_info()
        visualizations = self.customized_source_result_visualization_configs[
            source_id] if source_id in self.customized_source_result_visualization_configs else self.result_visualization_configs
        return [{'id': idx, **vf} for idx, vf in enumerate(visualizations)]

    def get_system_visualization_config(self):
        self.parse_base_info()
        return [{'id': idx, **vf} for idx, vf in enumerate(self.system_visualization_configs)]

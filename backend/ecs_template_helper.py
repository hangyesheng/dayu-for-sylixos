from template_helper import TemplateHelper

from core.lib.common import Context, LOGGER
from core.lib.network import merge_address
from core.lib.network import NodeInfo
from core.lib.network import NetworkAPIPath, NetworkAPIMethod
from core.lib.network import http_request

class ECSTemplateHelper(TemplateHelper):
    def __init__(self, templates_dir):
        super().__init__(templates_dir)

    def load_template_config(self, policy, service_dict):
        yaml_dict = {}
        yaml_dict.update(self.load_policy_apply_yaml(policy))
        yaml_dict.update({'processor': self.load_application_apply_yaml(service_dict)})
        for component_name, component_dict in yaml_dict.items():
            if component_name == 'processor':
                for index, service_id in enumerate(component_dict):
                    yaml_doc = component_dict[service_id]['service']
                    component_dict[service_id]['service'] = self._check_and_modify_yaml_dict(yaml_doc)
            else:
                yaml_dict[component_name] = self._check_and_modify_yaml_dict(component_dict)
        return yaml_dict
    
    def finetune_parameters(self, template_dict, source_deploy, edge_nodes, cloud_node, scopes=None):
        docs_list = []
        if not scopes or 'generator' in scopes:
            docs_list.extend(self.finetune_genetator_json(template_dict['generator'], source_deploy))
        if not scopes or 'processor' in scopes:
            docs_list.extend(self.finetune_processor_json(template_dict['processor'], cloud_node, source_deploy))
        if not scopes or 'controller' in scopes:
            docs_list.append(self.finetune_controller_json(template_dict['controller'], edge_nodes, cloud_node))
        
        return docs_list

    def _check_and_modify_yaml_dict(self, template_dict):
        # 1. 定义支持的 image 值
        supported_images = ['generator', 'controller', 'car-detection', 'face-detection']

        # 2. 获取 pod-template 中的 image
        pod_template = template_dict['pod-template']
        image = pod_template.get('image')

        # 3. 检查 image 是否在支持列表中
        if image not in supported_images:
            raise ValueError(f"不支持的 image: {image}。必须是 {supported_images} 之一。")

        # 4. 修改 image 字段为 ref 字段
        ref_value = f"{image}@latest#sylixos"
        pod_template['ref'] = ref_value
        # 5. 删除原来的 image 字段
        del pod_template['image']

        # 6. 将 imagePullPolicy 改为 pullPolicy
        if 'imagePullPolicy' in pod_template:
            pod_template['pullPolicy'] = pod_template.pop('imagePullPolicy')
        
        template_dict['pod-template'] = pod_template
        return template_dict
    
    def _request_ecs_image_config(self, image_name):
        ecsm_host = str(Context.get_parameter('ECSM_HOST'))
        ecsm_port = str(Context.get_parameter('ECSM_PORT'))
        remote_api_url = merge_address(ip=ecsm_host, 
                                       port=ecsm_port, 
                                       path=NetworkAPIPath.BACKEND_ECSM_IMAGE_CONFIG + f"?ref={image_name}")
        
        template_json_dict = {}

        try:
            response_data = http_request(
                url=remote_api_url,
                method=NetworkAPIMethod.BACKEND_ECSM_IMAGE_CONFIG
            )
            # 检查返回值是否有效
            if not response_data:
                LOGGER.warning("Empty response from remote API.")
            elif isinstance(response_data, dict) and response_data.get('status') == 200:
                template_json_dict = response_data['data']
            else:
                error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")
        except Exception as e:
            LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
        
        return template_json_dict
    
    def fill_template(self, template_dict, template_json_dict, component_name):
        # 获取修改后的 pod-template 数据
        modified_pod_template = template_dict['pod-template']

        new_env_list = [env_var['name'] + '=' + env_var['value'] for env_var in modified_pod_template['env']]

        # 创建新的 image 部分
        new_image_section = {
            "ref": modified_pod_template['ref'],
            "action": "run",
            "pullPolicy": modified_pod_template['pullPolicy'],
            "autoUpgrade": "Never",
            "config": {
                "platform": template_json_dict['config']['platform'],
                "process": {
                    "args": template_json_dict['config']['process']['args'],
                    "env": template_json_dict['config']['process']['env'].extend(new_env_list),
                },
                "root": template_json_dict['config']['root'],
                "hostname": template_json_dict['config']['hostname'],
                "mounts": template_json_dict['config']['mounts'],
                "sylixos": template_json_dict['config']['sylixos']
            }
        }

        # 构建最终的 JSON 结构
        final_json = {
            "name": f"{component_name}_service",
            "image": new_image_section,
            "node": {
                "names": []
            }
        }

        return final_json      
    
    def finetune_genetator_json(self, template_dict, source_deploy):
        template_docs = []
        
        for source_info in source_deploy:
            template_json_dict = self._request_ecs_image_config(template_dict['pod-template']['ref'])
            template_doc = self.fill_template(template_dict, template_json_dict, 'generator')

            source = source_info['source']
            node_set = source_info['node_set']
            
            LOGGER.warning("Using default selection plan.")
            node = node_set[0]

            source_info['source'].update({'deploy_node': node})
            dag = source_info['dag']

            DAG_ENV = {}
            for key in dag.keys():
                temp_node = {}
                if key != '_start':
                    temp_node['service'] = {'service_name': key}
                    temp_node['next_nodes'] = dag[key]['succ']
                    DAG_ENV[key] = temp_node

            env_list = [
                    {'name': 'GEN_GETTER_NAME', 'value': str(source['source_mode'])},
                    {'name': 'SOURCE_URL', 'value': str(source['url'])},
                    {'name': 'SOURCE_TYPE', 'value': str(source['source_type'])},
                    {'name': 'SOURCE_ID', 'value': str(source['id'])},
                    {'name': 'SOURCE_METADATA', 'value': str(source['metadata'])},
                    {'name': 'ALL_EDGE_DEVICES', 'value': str(node_set)},
                    {'name': 'DAG', 'value': str(DAG_ENV)},
                ]
            new_env_list = [env_var['name'] + '=' + env_var['value'] for env_var in env_list]

            template_doc["image"]["config"]["process"]["env"].extend(new_env_list)
            
            # 添加edge node ip
            node_ip = NodeInfo.hostname2ip(node)
            template_doc["node"]["names"].append(node_ip)

            template_docs.append(template_doc)

        return template_docs
    
    def finetune_processor_json(self, service_dict, cloud_node, source_deploy):
        if cloud_node is not None:
            LOGGER.warning("Cloud node is not None, but ecs processor does not support cloud node.")

        template_docs = []
        for index, service_id in enumerate(service_dict):
            template_dict = service_dict[service_id]['service']
            service_name = service_dict[service_id]['service_name']
            
            template_json_dict = self._request_ecs_image_config(template_dict['pod-template']['ref'])
            template_doc = self.fill_template(template_dict, template_json_dict, f'processor-{service_name}')

            edge_nodes = service_dict[service_id]['node']
            LOGGER.warning("Using default selection plan.")

            # 添加edge node ip
            edge_nodes_ip = [NodeInfo.hostname2ip(node) for node in edge_nodes]
            template_doc['node']['names'].extend(edge_nodes_ip)

            template_docs.append(template_doc)

        return template_docs
    
    def finetune_controller_json(self, template_dict, edge_nodes, cloud_node):
        if cloud_node is not None:
            LOGGER.warning("Cloud node is not None, but ecs controller does not support cloud node.")

        template_json_dict = self._request_ecs_image_config(template_dict['pod-template']['ref'])
        template_doc = self.fill_template(template_dict, template_json_dict, 'controller')

        # 添加edge node ip
        edge_nodes_ip = [NodeInfo.hostname2ip(node) for node in edge_nodes]
        template_doc['node']['names'].extend(edge_nodes_ip)

        return template_doc


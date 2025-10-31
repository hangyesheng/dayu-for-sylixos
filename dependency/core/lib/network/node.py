from typing import List

from kubernetes import client, config
from core.lib.common import reverse_key_value_in_dict, Context
from core.lib.network import find_all_ips
from .client import http_request
from .utils import merge_address
from .api import NetworkAPIPath, NetworkAPIMethod
from core.lib.common import Context, LOGGER


class NodeInfo:
    __node_info_hostname = None
    __node_info_ip = None
    __node_info_role = None

    @classmethod
    def get_node_info(cls):
        if not cls.__node_info_hostname:
            cls.__node_info_hostname, cls.__node_info_ip, cls.__node_info_role \
                = cls.__extract_node_info()

        return cls.__node_info_hostname

    @classmethod
    def get_node_info_reverse(cls):
        if not cls.__node_info_ip:
            cls.__node_info_hostname, cls.__node_info_ip, cls.__node_info_role \
                = cls.__extract_node_info()

        return cls.__node_info_ip

    @classmethod
    def get_node_info_role(cls):
        if not cls.__node_info_role:
            cls.__node_info_hostname, cls.__node_info_ip, cls.__node_info_role \
                = cls.__extract_node_info()

        return cls.__node_info_role

    @staticmethod
    def __extract_node_info():
        # 通过 kubernetes 获取节点信息
        config.load_incluster_config()
        v1 = client.CoreV1Api()
        nodes = v1.list_node().items

        assert nodes, 'Invalid node config in KubeEdge system'

        node_dict = {}
        node_role = {}

        for node in nodes:
            node_name = node.metadata.name
            for address in node.status.addresses:
                if address.type == "InternalIP":
                    node_dict[node_name] = address.address
            if 'node-role.kubernetes.io/edge' in node.metadata.labels:
                node_role[node_name] = 'edge'
            if 'node-role.kubernetes.io/master' in node.metadata.labels:
                node_role[node_name] = 'cloud'


        # 通过 http_request 获取 ECSM边缘集群 节点信息
        ecsm_host = str(Context.get_parameter('ECSM_HOST'))
        ecsm_port = str(Context.get_parameter('ECSM_PORT'))
        remote_api_url = merge_address(ip=ecsm_host, 
                                       port=ecsm_port, 
                                       path=NetworkAPIPath.BACKEND_ECSM_NODE)

        try:
            # 调用封装好的 http_request 方法
            response_data = http_request(
                url=remote_api_url,
                method=NetworkAPIMethod.BACKEND_ECSM_NODE
            )

            # 检查返回值是否有效
            if not response_data:
                LOGGER.warning("Empty response from remote API.")
            elif isinstance(response_data, dict) and response_data.get('status') == 200:
                remote_nodes = response_data['data']['list']
                for remote_node in remote_nodes:
                    node_name = remote_node['name']
                    address = remote_node['address']  # 如 "192.168.200.101:1112"
                    ip = address.split(':')[0]  # 提取 IP

                    # 避免覆盖已有节点
                    if node_name not in node_dict:
                        node_dict[node_name] = ip
                        node_role[node_name] = 'edge-sylixos'  # 统一标记为边缘节点，但是额外标记为sylixos
                        LOGGER.info(f"Added remote edge node: {node_name} -> {ip}")
                    else:
                        LOGGER.warning(f"Remote node {node_name} already exists. Skipping.")
            else:
                error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")

        except Exception as e:
            LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
    
        LOGGER.info(f"All Node dict: {node_dict}, Node role: {node_role}")

        node_dict_reverse = reverse_key_value_in_dict(node_dict)

        return node_dict, node_dict_reverse, node_role

    @staticmethod
    def hostname2ip(hostname: str) -> str:
        node_info = NodeInfo.get_node_info()
        assert hostname in node_info, f'Hostname "{hostname}" not exists in system!'

        return node_info[hostname]

    @staticmethod
    def ip2hostname(ip: str) -> str:
        node_info = NodeInfo.get_node_info_reverse()
        assert ip in node_info, f'Ip "{ip}" not exists in system!'

        return node_info[ip]

    @staticmethod
    def url2hostname(url: str) -> str:
        ips = find_all_ips(url)
        assert len(ips) == 1, f'Url "{url}" contains none or more than one legal ip!'
        return NodeInfo.ip2hostname(ips[0])

    @staticmethod
    def get_node_role(hostname: str) -> str:
        node_role = NodeInfo.get_node_info_role()
        assert hostname in node_role, f'Hostname "{hostname}" not exists in system!'
        return node_role[hostname]

    @staticmethod
    def get_cloud_node() -> str:
        node_role = NodeInfo.get_node_info_role()
        for hostname in node_role:
            if node_role[hostname] == 'cloud':
                return hostname

    @staticmethod
    def get_edge_nodes() -> List[str]:
        node_role = NodeInfo.get_node_info_role()
        edge_nodes = []
        for hostname in node_role:
            if node_role[hostname] == 'edge' or node_role[hostname] == 'edge-sylixos':
                edge_nodes.append(hostname)
        return edge_nodes

    @staticmethod
    def get_local_device() -> str:
        device = Context.get_parameter('NODE_NAME')

        assert device, 'Node Config is not found ("NODE_NAME")!'

        return device


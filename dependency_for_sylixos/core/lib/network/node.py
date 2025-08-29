from typing import List

from kubernetes import client, config
from core.lib.common import reverse_key_value_in_dict, Context
from core.lib.network import find_all_ips
from core.lib.common import Context


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
            if node_role[hostname] == 'edge':
                edge_nodes.append(hostname)
        return edge_nodes

    @staticmethod
    def get_local_device() -> str:
        device = Context.get_parameter('NODE_NAME')

        assert device, 'Node Config is not found ("NODE_NAME")!'

        return device


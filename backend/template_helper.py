import os
import re

from core.lib.common import YamlOps


class TemplateHelper:
    def __init__(self, templates_dir):
        self.templates_dir = templates_dir

    def load_template_config(self, policy, service_dict):
        raise NotImplementedError()

    def load_base_info(self):
        base_template_path = os.path.join(self.templates_dir, 'base.yaml')
        return YamlOps.read_yaml(base_template_path)

    def load_policy_apply_yaml(self, policy):
        yaml_dict = {'scheduler': YamlOps.read_yaml(
            os.path.join(self.templates_dir, 'scheduler', policy['yaml'])
        )}
        for component in policy['dependency']:
            yaml_dict.update({
                component: YamlOps.read_yaml(
                    os.path.join(self.templates_dir, component, policy['dependency'][component])
                )
            })
        return yaml_dict

    def load_application_apply_yaml(self, service_dict):
        for service_id in service_dict:
            service_dict[service_id]['service'] = YamlOps.read_yaml(
                os.path.join(self.templates_dir, 'processor', service_dict[service_id]['yaml'])
            )
        return service_dict

    def process_image(self, image: str) -> str:
        """
            legal input:
                - registry/repository/image:tag
                - registry/repository/image
                - repository/image:tag
                - repository/image
                - image:tag
                - image
            output: complete the full image
        """
        image_meta = self.load_base_info()['default-image-meta']
        default_registry = image_meta['registry']
        default_repository = image_meta['repository']
        default_tag = image_meta['tag']

        pattern = re.compile(
            r"^(?:(?P<registry>[^/]+)/"  # match registry with '/'
            r"(?=.*/)"  # forward pre-check to make sure there is a '/' followed
            r")?"  # registry is optional
            r"(?:(?P<repository>[^/:]+)/)?"  # match repository
            r"(?P<image>[^:]+)"  # match image
            r"(?::(?P<tag>[^:]+))?$"  # match tag
        )

        match = pattern.match(image)
        if not match:
            raise ValueError(f'Format of input image "{image}" is illegal')

        registry = match.group("registry") or default_registry
        repository = match.group("repository") or default_repository
        image_name = match.group("image")
        tag = match.group("tag") or default_tag

        full_image = f"{registry}/{repository}/{image_name}:{tag}"
        return full_image

    def prepare_file_path(self, file_path: str) -> str:
        file_prefix = self.load_base_info()['default-file-mount-prefix']
        return os.path.join(file_prefix, file_path, "")

    @staticmethod
    def get_all_selected_edge_nodes(yaml_dict):
        service_dict = yaml_dict['processor']
        edge_nodes = set()
        for service_id in service_dict:
            edge_nodes.update(service_dict[service_id]['node'])
        return list(edge_nodes)

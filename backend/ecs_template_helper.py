from template_helper import TemplateHelper

class ECSTemplateHelper(TemplateHelper):
    def __init__(self, templates_dir):
        super().__init__(templates_dir)

    def load_template_config(self, policy, service_dict):
        yaml_dict = {}
        yaml_dict.update(self.load_policy_apply_yaml(policy))
        yaml_dict.update({'processor': self.load_application_apply_yaml(service_dict)})
        template_dict = self._check_and_modify_yaml_dict(yaml_dict)
        return template_dict
    
    def _check_and_modify_yaml_dict(self, yaml_dict):
        # 1. 定义支持的 image 值
        supported_images = ['generator', 'controller', 'car-detection', 'face-detection']

        # 2. 获取 pod-template 中的 image
        pod_template = yaml_dict['pod-template']
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
        
        yaml_dict['pod-template'] = pod_template
        return yaml_dict
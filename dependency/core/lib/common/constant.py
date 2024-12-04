from enum import Enum


class SystemConstant(Enum):
    DEFAULT = 'dayu'

    GENERATOR = 'generator'
    CONTROLLER = 'controller'
    SCHEDULER = 'scheduler'
    DISTRIBUTOR = 'distributor'
    PROCESSOR = 'processor'
    MONITOR = 'monitor'

    BACKEND = 'backend'
    FRONTEND = 'frontend'
    DATASOURCE = 'datasource'


class FileNameConstant(Enum):
    SCHEDULE_CONFIG = 'scheduler_config.yaml'
    DISTRIBUTOR_RECORD = 'record_data.db'
    ACC_GT_DIR = 'acc-gt'


class NodeRoleConstant(Enum):
    CLOUD = 'cloud'
    EDGE = 'edge'

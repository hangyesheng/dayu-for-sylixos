import logging
from .constant import SystemConstant
from .context import Context


class Logger:
    def __init__(self, name: str = None):
        if not name:
            name = SystemConstant.DEFAULT.value

        level = Context.get_parameter('LOG_LEVEL', 'DEBUG')

        self.logger = logging.getLogger(name)

        # 使用标准 logging.Formatter，去掉 colorlog 相关内容
        self.format = logging.Formatter(
            '[%(asctime)-15s] %(filename)s(%(lineno)d) [%(levelname)s] - %(message)s'
        )

        self.handler = logging.StreamHandler()
        self.handler.setFormatter(self.format)

        self.logger.addHandler(self.handler)
        self.logLevel = 'INFO'
        self.logger.setLevel(level=level)
        self.logger.propagate = False


LOGGER = Logger().logger

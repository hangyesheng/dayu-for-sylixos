import abc
from core.lib.common import ClassFactory, ClassType

from .base_agent import BaseAgent
import time

__all__ = ('ChameleonAgent',)


@ClassFactory.register(ClassType.SCH_AGENT, alias='chameleon')
class ChameleonAgent(BaseAgent, abc.ABC):

    def __init__(self, system, agent_id: int, fixed_policy: dict = None,
                 best_num: int = 10, threshold=0.7,
                 profile_window=16, segment_size=4, calculate_time=1):
        self.agent_id = agent_id
        self.cloud_device = system.cloud_device
        self.schedule_plan = None
        self.schedule_knobs = None

        # 大周期、小周期(段)、计算best_num个配置所允许的最大耗时
        # 一个大周期里包含 profile_window / segment_size个段
        # 为一个新的大周期求best_num个配置的耗时不能超过calculate_time
        self.profile_window = profile_window
        self.segment_size = segment_size
        self.calculate_time = calculate_time

        # 每一个大周期需要选择的配置数
        self.best_num = best_num

        # best_config_list记录当前大周期已选好的best_num个配置,与其F1得分[(config,score),]
        # 初始化的时候从get_default_profile()中获取, 用于在冷启动的第一个大周期里确定best_num个配置
        self.best_config_list = self.get_default_profile()

        # 所有旋钮值的排列组合, 用于在每个大周期开头的第一个段里求出best_num个最优配置
        self.all_config_list = self.get_all_knob_combinations()

        # 默认的"黄金配置"(精度最高、消耗最高的那个), 用于计算F1 score来对配置进行选择和排序
        self.golden_config = {}
        # 根据"黄金配置"求出的、用于获取F1-score的ground truth
        self.ground_truth = []
        # 选择配置时所需的最新视频帧,一般数量也就几十帧
        self.raw_video = []

        # 对F1_score进行排序时用到的阈值
        self.threshold = threshold

    def update_best_config_list_for_segment(self):

        target_config_list = []
        each_knob_score = {}
        for knob in self.schedule_knobs:
            for value in self.schedule_knobs[knob]:
                new_config = self.golden_config
                new_config.update((knob, value))
                score = self.get_F1_score(new_config)
                each_knob_score[value] = score

        # 为已有的best_num个配置打分
        for config in self.best_config_list:
            target_config_list.append((config, self.calculate_config_score(config, each_knob_score)))

        # 从已有的配置来选择最优的，不需要机械能筛选
        target_config_list = [x for x in sorted(target_config_list, key=lambda x: x[1], reverse=True)]

        # 得到重新排序的best_config_list
        self.best_config_list = [x[0] for x in target_config_list]

        # 为每一个配置计算分数，用于给配置排序

    def calculate_config_score(self, config, knob_value):
        res = 1
        # 遍历旋钮值
        for value in config:
            res *= knob_value[value]
        return res

    def get_schedule_plan(self, info):
        if self.fixed_policy is None:
            return self.fixed_policy

        policy = self.fixed_policy.copy()
        edge_device = info['device']
        cloud_device = self.cloud_device
        pipe_seg = policy['pipeline']
        pipeline = info['pipeline']
        pipeline = [{**p, 'execute_device': edge_device} for p in pipeline[:pipe_seg]] + \
                   [{**p, 'execute_device': cloud_device} for p in pipeline[pipe_seg:]]

        policy.update({'pipeline': pipeline})
        return policy

    def run(self):
        segment_num = 0  # 判断当前是第几个大周期里的第几个小周期了

        while True:

            time.sleep(self.segment_size)
            segment_num += 1
            # 获取视频帧
            self.raw_video = self.get_raw_video()
            # 计算groud_truth用于后续计算F1_score
            self.get_ground_truth()

            # 冷启动时， 为初始化的best_num个配置排序
            if segment_num == 1:
                self.update_best_config_list_for_segment()

            # 非冷启动且属于当前大周期开头时，重新选择best_num个配置并排序
            elif segment_num % (self.profile_window / self.segment_size) == 1:
                self.update_best_config_list_for_window()

            # 非冷启动且不位于大周期开头时, 为已经选好的best_num个配置排序
            else:
                self.update_best_config_list_for_segment()

            # 获取新排序的配置中最优的配置
            self.schedule_plan = self.best_config_list[0]

    def get_default_profile(self):
        return []

    def update_scenario(self, scenario):
        pass

    def update_resource(self, device, resource):
        pass

    def update_policy(self, policy):
        pass

    def update_task(self, task):
        pass

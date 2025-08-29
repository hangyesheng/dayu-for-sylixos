from core.lib.common import LOGGER


class NegativeFeedback_Single:
    def __init__(self, system, agent_id):
        self.agent_id = agent_id

        self.fps_list = system.fps_list.copy()
        self.resolution_list = system.resolution_list.copy()
        self.buffer_size_list = system.buffer_size_list.copy()
        self.pipeline_list = None

        self.cloud_device = system.cloud_device
        self.edge_device = None

        self.monotonic_schedule_knobs = system.monotonic_schedule_knobs.copy()
        self.non_monotonic_schedule_knobs = system.non_monotonic_schedule_knobs.copy()

        self.monotonic_schedule_knobs.extend(self.non_monotonic_schedule_knobs)

    def __call__(self, latest_policy: dict, latest_delay: float):

        if latest_policy is None:
            LOGGER.info(f'[NF Lack Latest Policy] (agent {self.agent_id}) No latest policy, none decision make ..')
            return None

        resolution = latest_policy['resolution']
        fps = latest_policy['fps']
        buffer_size = latest_policy['buffer_size']
        pipeline = latest_policy['pipeline']

        self.pipeline_list = list(range(0, len(pipeline)))
        self.edge_device = latest_policy['edge_device']

        self.resolution_index = self.resolution_list.index(resolution)
        self.fps_index = self.fps_list.index(fps)
        self.buffer_size_index = self.buffer_size_list.index(buffer_size)
        self.pipeline_index = next((i for i, service in enumerate(pipeline)
                                    if service['execute_device'] == self.cloud_device), len(pipeline) - 1)

        constraint_delay = 1 / self.fps_list[self.fps_index] * 1.6
        delay_bias = constraint_delay - latest_delay
        for idx, knob_name in enumerate(self.monotonic_schedule_knobs):
            knob_index = getattr(self, f'{knob_name}_index')
            knob_list = getattr(self, f'{knob_name}_list')

            if delay_bias >= 0:
                increase_num = 1
                updated_knob_index = self.increase_knob(knob_index, knob_list, increase_num)
                LOGGER.info(f'[NF Schedule] (agent {self.agent_id}) Knob {knob_name} '
                            f'increase: index {knob_index}->{updated_knob_index}')
            else:
                decrease_num = knob_index - knob_index // 2
                updated_knob_index = self.decrease_knob(knob_index, knob_list, decrease_num)
                LOGGER.info(
                    f'[NF Schedule] (agent {self.agent_id}) Knob {knob_name} '
                    f'decrease: index {knob_index}->{updated_knob_index}')

            setattr(self, f'{knob_name}_index', updated_knob_index)

        schedule_policy = {}
        schedule_policy.update(latest_policy)
        schedule_policy['resolution'] = self.resolution_list[self.resolution_index]
        schedule_policy['fps'] = self.fps_list[self.fps_index]
        schedule_policy['buffer_size'] = self.buffer_size_list[self.buffer_size_index]

        pipeline_index_decision = self.pipeline_index
        schedule_policy['pipeline'] = [{**p, 'execute_device': self.edge_device} for p in
                                       pipeline[:pipeline_index_decision]] + \
                                      [{**p, 'execute_device': self.cloud_device} for p in
                                       pipeline[pipeline_index_decision:]]
        return schedule_policy

    @staticmethod
    def increase_knob(knob_index, knob_list, increase_num):

        assert 0 <= knob_index < len(knob_list), \
            (f'Index of Knob is out of range '
             f'(index:{knob_index}, range:[0,{len(knob_list) - 1}])')
        assert increase_num >= 0, f'Increase num is negative:{increase_num}'
        return min(knob_index + increase_num, len(knob_list) - 1)

    @staticmethod
    def decrease_knob(knob_index, knob_list, decrease_num):
        assert 0 <= knob_index < len(knob_list), \
            (f'Index of Knob is out of range '
             f'(index:{knob_index}, range:[0,{len(knob_list) - 1}])')
        assert decrease_num >= 0, f'Increase num is negative:{decrease_num}'
        return max(knob_index - decrease_num, 0)

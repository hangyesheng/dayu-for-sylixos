import abc
import os.path
import time
import numpy as np

from core.lib.common import ClassFactory, ClassType, LOGGER, FileOps, Context
from core.lib.estimation import AccEstimator
from core.lib.common import VideoOps

from .base_agent import BaseAgent

__all__ = ('CASVAAgent',)

"""
CASVA Agent Class

Implementation of CASVA

Zhang M, Wang F, Liu J. Casva: Configuration-adaptive streaming for live video analytics[C]//IEEE INFOCOM 2022-IEEE Conference on Computer Communications. IEEE, 2022: 2168-2177.
"""

@ClassFactory.register(ClassType.SCH_AGENT, alias='casva')
class CASVAAgent(BaseAgent, abc.ABC):

    def __init__(self, system,
                 agent_id: int,
                 window_size: int = 8,
                 mode: str = 'inference',
                 streaming_mode: str = 'latency_first'):
        from .casva import DualClippedPPO, RandomBuffer, Adapter, StateBuffer

        assert streaming_mode in ['latency_first', 'delivery_first'], \
            '"streaming_mode" must be "latency_first" or "delivery_first"'

        self.agent_id = agent_id
        self.system = system

        self.fps_list = system.fps_list
        self.resolution_list = system.resolution_list
        self.qp_list = system.qp_list

        drl_params = system.drl_params.copy()
        hyper_params = system.hyper_params.copy()
        drl_params['state_dims'] = [drl_params['state_dims'], window_size]

        self.window_size = window_size
        self.state_buffer = StateBuffer(self.window_size)
        self.mode = mode
        self.streaming_mode = streaming_mode

        self.drl_agent = DualClippedPPO(**drl_params)
        self.replay_buffer = RandomBuffer(**drl_params)
        self.adapter = Adapter

        self.drl_schedule_interval = hyper_params['drl_schedule_interval']

        self.state_dim = drl_params['state_dims']
        self.action_dim = drl_params['action_dim']

        # TODO: load model
        self.model_dir = Context.get_file_path(os.path.join(hyper_params['model_dir'], f'agent_{self.agent_id}'))
        FileOps.create_directory(self.model_dir)

        if hyper_params['load_model']:
            self.premodel_dir = Context.get_file_path('')
            self.drl_agent.load(self.premodel_dir, hyper_params['load_model_episode'])

        self.total_steps = hyper_params['drl_total_steps']
        self.save_interval = hyper_params['drl_save_interval']
        self.update_interval = hyper_params['drl_update_interval']
        self.update_after = hyper_params['drl_update_after']

        self.intermediate_decision = [0 for _ in range(self.action_dim)]

        self.latest_policy = None
        self.latest_task_delay = None
        self.schedule_plan = None

    def get_drl_state_buffer(self):
        while True:
            state, evaluation_info = self.state_buffer.get_state_buffer()
            if state is not None and evaluation_info is not None:
                return state, evaluation_info
            LOGGER.info(f'[Wait for State] (agent {self.agent_id}) State empty, '
                        f'wait for resource state or scenario state ..')
            time.sleep(1)

    def map_drl_action_to_decision(self, action):
        """
        map [-1, 1] to {-1, 0, 1}
        """
        if self.latest_policy is None:
            LOGGER.info(f'[CASVA Lack Latest Policy] (agent {self.agent_id}) No latest policy, none decision make ..')
            return

        resolution_index = int((action[0] + 1) / 2 * len(self.resolution_list))
        fps_index = int((action[1] + 1) / 2 * len(self.fps_list))
        self.latest_policy.update({'resolution': self.resolution_list[resolution_index],
                                   'fps': self.fps_list[fps_index]})

        pipe_seg = 0
        pipeline = self.latest_policy['pipeline']
        pipeline = [{**p, 'execute_device': 'edge1'} for p in pipeline[:pipe_seg]] + \
                   [{**p, 'execute_device': 'cloud.kubeedge'} for p in pipeline[pipe_seg:]]
        self.latest_policy.update({'pipeline': pipeline})
        self.schedule_plan = self.latest_policy.copy()

        LOGGER.info(f'[CASVA Decision] (agent {self.agent_id}) Action: {action}   '
                    f'Decision: "resolution":{self.resolution_list[resolution_index]}, "fps":{self.fps_list[fps_index]}')

    def reset_drl_env(self):
        self.intermediate_decision = [0 for _ in range(self.action_dim)]

        state, _ = self.get_drl_state_buffer()

        return state

    def step_drl_env(self, action):

        self.map_drl_action_to_decision(action)

        time.sleep(self.drl_schedule_interval)

        state, evaluation_info = self.get_drl_state_buffer()
        reward = self.calculate_drl_reward(evaluation_info)
        done = False
        info = ''

        return state, reward, done, info

    # TODO: reward
    def calculate_drl_reward(self, evaluation_info):
        if self.streaming_mode == 'latency_first':
            pass
        elif self.streaming_mode == 'delivery_first':
            pass
        else:
            raise ValueError('"streaming_mode" must be "latency_first" or "delivery_first"')

        delay_bias_list = []

        for task in evaluation_info:
            delay = task.calculate_total_time()
            meta_data = task.get_metadata()
            raw_metadata = task.get_raw_metadata()
            content = task.get_content()

            hash_data = task.get_hash_data()

            raw_resolution = VideoOps.text2resolution(raw_metadata['resolution'])
            resolution = VideoOps.text2resolution(meta_data['resolution'])
            resolution_ratio = (resolution[0] / raw_resolution[0], resolution[1] / raw_resolution[1])

            fps_ratio = meta_data['fps'] / raw_metadata['fps']


            single_task_delay = delay / meta_data['buffer_size']
            single_task_constraint = 1 / meta_data['fps']
            delay_bias_list.append(single_task_constraint * 1.6 - single_task_delay)

        final_delay = np.mean(delay_bias_list)
        LOGGER.info(f'[Reward Computing] delay:{final_delay} acc:{final_acc}')

        if final_delay < 0:
            reward = min(final_delay * 20, -2)
        else:
            reward = 1 / max(final_delay, 0.5) * 0.3 + final_acc

        return reward

    def train_drl_agent(self):
        LOGGER.info(f'[DRL Train] (agent {self.agent_id}) Start train drl agent ..')
        state = self.reset_drl_env()
        for step in range(self.total_steps):
            action = self.drl_agent.select_action(state, deterministic=False, with_logprob=False)

            next_state, reward, done, info = self.step_drl_env(action)
            done = self.adapter.done_adapter(done, step)
            self.replay_buffer.add(state, action, reward, next_state, done)
            state = next_state

            LOGGER.info(f'[DRL Train Data] (agent {self.agent_id}) Step:{step}  Reward:{reward}')

            if step >= self.update_after and step % self.update_interval == 0:
                for _ in range(self.update_interval):
                    LOGGER.info(f'[DRL Train] (agent {self.agent_id}) Train drl agent with replay buffer')
                    self.drl_agent.train(self.replay_buffer)

            if step % self.save_interval == 0:
                self.drl_agent.save(self.model_dir, step)

            if done:
                state = self.reset_drl_env()

        LOGGER.info(f'[DRL Train] (agent {self.agent_id}) End train drl agent ..')

    def inference_drl_agent(self):
        LOGGER.info(f'[DRL Inference] (agent {self.agent_id}) Start inference drl agent ..')
        state = self.reset_drl_env()
        cur_step = 0
        while True:
            time.sleep(self.drl_schedule_interval)
            cur_step += 1
            action = self.drl_agent.select_action(state, deterministic=False, with_logprob=False)
            next_state, reward, done, info = self.step_drl_env(action)
            done = self.adapter.done_adapter(done, cur_step)
            state = next_state
            if done:
                state = self.reset_drl_env()
                cur_step = 0

    def update_scenario(self, scenario):
        try:
            object_number = np.mean(scenario['obj_num'])
            object_size = np.mean(scenario['obj_size'])
            task_delay = scenario['delay']

            self.latest_task_delay = task_delay

            self.state_buffer.add_scenario_buffer([object_number, object_size, task_delay])
        except Exception as e:
            LOGGER.warning('Wrong scenario from Distributor!')

    def update_resource(self, device, resource):
        bandwidth = resource['bandwidth']
        if bandwidth != 0:
            self.state_buffer.add_resource_buffer([bandwidth])

    def update_policy(self, policy):
        self.set_latest_policy(policy)

        resolution_decision = self.system.resolution_list.index(policy['resolution'])
        fps_decision = self.system.fps_list.index(policy['fps'])
        buffer_size_decision = self.system.buffer_size_list.index(policy['buffer_size'])
        pipeline_decision = next((i for i, service in enumerate(policy['pipeline'])
                                  if service['execute_device'] == self.system.cloud_device),
                                 len(policy['pipeline']) - 1)
        self.state_buffer.add_decision_buffer([resolution_decision, fps_decision,
                                               buffer_size_decision, pipeline_decision])

    def update_task(self, task):
        self.state_buffer.add_task_buffer(task)

    def set_latest_policy(self, policy):
        self.latest_policy = policy

    def get_schedule_plan(self, info):
        return self.schedule_plan

    def run(self):

        if self.mode == 'train':
            self.train_drl_agent()
        elif self.mode == 'inference':
            self.inference_drl_agent()
        else:
            assert None, f'(agent {self.agent_id}) Invalid execution mode: {self.mode}, ' \
                         f'only support ["train", "inference"]'

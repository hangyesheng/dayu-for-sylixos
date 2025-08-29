import redis

from core.lib.content import Task
from core.lib.common import LOGGER, Context, SystemConstant
from core.lib.network import NodeInfo, PortInfo


class TaskCoordinator:
    def __init__(self):
        self.max_connections = Context.get_parameter('MAX_REDIS_CONNECTIONS', '10', direct=False)
        self.storage_timeout = Context.get_parameter('REDIS_STORAGE_TIMEOUT', '3600', direct=False)
        self.pool = redis.ConnectionPool(host=NodeInfo.hostname2ip(NodeInfo.get_cloud_node()),
                                         port=PortInfo.get_component_port(SystemConstant.REDIS.value),
                                         max_connections=self.max_connections)
        self.redis = redis.Redis(connection_pool=self.pool)
        self.lock_prefix = 'dayu:dag:lock'
        self.joint_service_key_prefix = 'dayu:dag:joint_service'

    def _get_joint_service_key(self, root_task_id, joint_service_name):
        return f"{self.joint_service_key_prefix}:{root_task_id}:{joint_service_name}"

    def store_task_data(self, task, joint_service_name):
        try:
            storage_key = f"{self.joint_service_key_prefix}:{task.get_root_uuid()}:{joint_service_name}"

            with self.redis.pipeline() as pipe:
                pipe.hset(storage_key, task.get_task_uuid(), task.serialize())
                pipe.expire(storage_key, self.storage_timeout)
                pipe.hlen(storage_key)
                _, _, count = pipe.execute()

                LOGGER.debug(f'Store "source {task.get_source_id()} task {task.get_task_id()} '
                             f'current_service {task.get_flow_index()}" into {storage_key}, current count: {count}')

                return count

        except Exception as e:
            LOGGER.warning(f'Redis operation failed in storing task: {str(e)}')

    def retrieve_task_data(self, root_uuid, joint_service_name, required_count):
        try:
            lock_key = f"{self.lock_prefix}:{root_uuid}:{joint_service_name}"
            lock = self.redis.lock(lock_key, timeout=10)
            with lock:
                storage_key = f"{self.joint_service_key_prefix}:{root_uuid}:{joint_service_name}"
                lua_script = """
                            local key = KEYS[1]
                            local required = tonumber(ARGV[1])
        
                            -- check current task count
                            local count = redis.call('HLEN', key)
                            if count < required then
                                return nil
                            end
        
                            -- retrieve all task data
                            local all_data = redis.call('HGETALL', key)
        
                            -- clear storage
                            redis.call('DEL', key)
        
                            return all_data
                            """

                result = self.redis.eval(
                    lua_script,
                    1,
                    storage_key,
                    required_count
                )

                if not result:
                    LOGGER.warning(f"Conditions not met for {storage_key}, required count: {required_count}")
                    return None

                parsed_tasks = [
                    Task.deserialize(result[i + 1])
                    for i in range(0, len(result), 2)
                ]

                cur_task_services = set([task.get_flow_index() for task in parsed_tasks])
                past_task_services = set([task.get_past_flow_index() for task in parsed_tasks])

                # check if joint service merged from same parallel branch (e.g., [a->c, a->c, b->c])
                if len(past_task_services) != required_count:
                    LOGGER.warning(f"Same branch exists for parallel services: require {required_count} "
                                   f"get {len(past_task_services)}, past services: {past_task_services}, "
                                   f"current joint service: {list(cur_task_services)[0]}")
                    return None

                # check if joint service of parallel branches are different (e.g., [a->c, b->d])
                if len(cur_task_services) != 1:
                    LOGGER.warning(f"Joint service for parallel branches conflict:"
                                   f" require 1 get {len(cur_task_services)}, "
                                   f"past services: {past_task_services}, "
                                   f"current joint service: {list(cur_task_services)[0]}")
                    return None

                LOGGER.debug(f"Retrieve {len(parsed_tasks)} tasks from {storage_key}, "
                             f"past services:{past_task_services}, current joint service:{list(cur_task_services)[0]}")
                return parsed_tasks
        except Exception as e:
            LOGGER.warning(f'Redis operation failed in retrieve tasks: {str(e)}')

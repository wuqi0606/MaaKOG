import json

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context


@AgentServer.custom_action("ResetHitCount")
class ResetHitCount(CustomAction):
    """只清理「自己声明了每轮重置」的节点的 max_hit 命中计数。

    节点级开关：节点定义里带 attach.reset_hit = true 才生效。
    未声明的节点一律跳过，保持任务级累计，max_hit 语义完全不变。
    父节点级开关：只有挂了本 Custom action 的父节点才会触发。

    用法（父节点 action.param）：
        {
            "custom_action": "ResetHitCount",
            "custom_action_param": { "nodes": ["节点A", "节点B"] }
        }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # Python binding 传来的 custom_action_param 是 JSON 字符串，不是 dict
        try:
            param = json.loads(argv.custom_action_param or "{}")
        except json.JSONDecodeError:
            return False

        nodes = param.get("nodes", [])
        if not isinstance(nodes, list) or not all(isinstance(n, str) for n in nodes):
            return False

        for node_name in nodes:
            data = context.get_node_data(node_name)
            if data is not None:
                attach = data.get("attach") or {}
                if not attach.get("reset_hit"):
                    continue
            # 读不到定义时按白名单意图清理，白名单本身已限定作用域
            context.clear_hit_count(node_name)

        return True

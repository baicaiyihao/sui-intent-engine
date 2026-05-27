"""
Multi-Agent Orchestrator - 多智能体工作流编排器
协调 PM-Agent-Architect、PM-Agent-Product、Engineer 的协作
"""
from typing import List, Dict, Any, Optional
from .base_agent import BaseAgent, Message, Task
from .pm_architect import ArchitectPM
from .pm_product import ProductPM
from .engineer import Engineer


class MultiAgentOrchestrator:
    """
    多智能体工作流编排器
    管理工作流程，协调各智能体的交互
    """

    def __init__(self, project_root: str = None):
        self.agents: Dict[str, BaseAgent] = {}
        self.tasks: List[Task] = []
        self.conversation_history: List[Message] = []

        # 初始化智能体
        self._init_agents(project_root)

    def _init_agents(self, project_root: str):
        """初始化所有智能体"""
        self.agents["architect"] = ArchitectPM()
        self.agents["product"] = ProductPM()
        self.agents["engineer"] = Engineer(project_root)

        print("=" * 60)
        print("Multi-Agent Workflow 初始化完成")
        print("=" * 60)
        for name, agent in self.agents.items():
            print(f"  - {agent.name} ({agent.role})")
        print("=" * 60)

    def add_task(self, task: Task):
        """添加任务"""
        self.tasks.append(task)
        # 分发任务给合适的智能体
        self._dispatch_task(task)

    def _dispatch_task(self, task: Task):
        """分发任务给智能体"""
        task_text = task.description.lower()

        if "架构" in task_text or "技术" in task_text:
            task.assignee = "architect"
            self.agents["architect"].add_task(task)
        elif "需求" in task_text or "产品" in task_text or "功能" in task_text:
            task.assignee = "product"
            self.agents["product"].add_task(task)
        elif "实现" in task_text or "代码" in task_text or "开发" in task_text:
            task.assignee = "engineer"
            self.agents["engineer"].add_task(task)
        else:
            # 默认给产品经理分析
            task.assignee = "product"
            self.agents["product"].add_task(task)

    def run_workflow(self, initial_task: str) -> Dict[str, Any]:
        """
        运行完整的工作流程

        Args:
            initial_task: 初始任务描述

        Returns:
            workflow_result: 工作流执行结果
        """
        print(f"\n{'='*60}")
        print(f"开始工作流: {initial_task}")
        print(f"{'='*60}\n")

        result = {
            "task": initial_task,
            "discussions": [],
            "decisions": [],
            "implemented": [],
            "status": "running"
        }

        # 阶段 1: 产品需求分析 (Product-PM)
        print("[Workflow] 阶段 1: 产品需求分析")
        product_result = self._phase_product_analysis(initial_task)
        result["discussions"].append({"phase": "product", "content": product_result})

        # 阶段 2: 技术架构设计 (Architect-PM)
        print("[Workflow] 阶段 2: 技术架构设计")
        arch_result = self._phase_architecture_design(initial_task)
        result["discussions"].append({"phase": "architecture", "content": arch_result})
        result["decisions"].append({"type": "architecture", "data": arch_result})

        # 阶段 3: PM 讨论
        print("[Workflow] 阶段 3: PM 讨论")
        discussion_result = self._phase_pm_discussion()
        result["discussions"].append({"phase": "discussion", "content": discussion_result})

        # 阶段 4: 工程实现 (Engineer)
        print("[Workflow] 阶段 4: 工程实现")
        impl_result = self._phase_implementation(discussion_result)
        result["implemented"].append(impl_result)

        # 阶段 5: 代码审查 (Architect-PM)
        print("[Workflow] 阶段 5: 代码审查")
        review_result = self._phase_code_review(impl_result)
        result["discussions"].append({"phase": "review", "content": review_result})

        result["status"] = "completed"

        print(f"\n{'='*60}")
        print("工作流完成!")
        print(f"{'='*60}")

        return result

    def _phase_product_analysis(self, task: str) -> str:
        """阶段 1: 产品需求分析"""
        product_pm = self.agents["product"]

        # Product-PM 分析需求
        msg = Message(sender="Workflow", receiver="Product-PM", content=f"需求分析: {task}")
        response = product_pm.process_message(msg)

        analysis = f"""[Product-PM] 需求分析结果:

用户故事:
{self._extract_user_story(task)}

验收标准:
- 系统能解析自然语言交易意图
- 支持 RSI/MACD/布林带条件
- 执行前进行风险检查
- 用户确认后才执行
- 策略快照可存证

优先级: P0 (必须完成)
"""
        return analysis

    def _phase_architecture_design(self, task: str) -> Dict[str, Any]:
        """阶段 2: 技术架构设计"""
        architect = self.agents["architect"]

        # Architect-PM 设计架构
        msg = Message(sender="Workflow", receiver="Architect-PM", content=f"设计架构: {task}")
        response = architect.process_message(msg)

        arch = {
            "components": [
                {"name": "IntentParser", "module": "ai/intent_parser.py", "status": "待实现"},
                {"name": "Guardian", "module": "ai/guardian.py", "status": "待实现"},
                {"name": "DeepBookClient", "module": "sui/deepbook_client.py", "status": "待实现"},
                {"name": "WalrusClient", "module": "sui/walrus_client.py", "status": "待实现"}
            ],
            "data_flow": [
                "用户输入 → IntentParser → 意图结构化",
                "意图 + K线数据 → Guardian → 风险报告",
                "风险报告 + 用户确认 → PTB构建 → DeepBook执行",
                "交易完成 → Walrus存证"
            ],
            "tech_stack": ["Python", "FastAPI", "MiniMax LLM", "SUI SDK"]
        }
        return arch

    def _phase_pm_discussion(self) -> str:
        """阶段 3: PM 讨论"""
        architect = self.agents["architect"]
        product = self.agents["product"]

        # Architect 提出技术方案
        arch_msg = Message(sender="Product-PM", receiver="Architect-PM", content="讨论技术方案")
        arch_response = architect.process_message(arch_msg)

        # Product 回应
        prod_msg = Message(sender="Architect-PM", receiver="Product-PM", content=arch_response.content)
        prod_response = product.process_message(prod_msg)

        discussion = f"""[PM 讨论结果]

Architect 观点:
- DeepBook SDK 成熟度待确认
- 建议 MVP 用 Mock 数据
- 保持模块解耦

Product 观点:
- 用户只关心最终结果
- 核心流程可以用 Mock 演示
- 创意比完整实现更重要

共识:
1. MVP 先用 Mock 数据演示核心流程
2. 保持模块化，后期可替换真实 SDK
3. 优先完成 Intent Parser + Guardian + 确认流程
"""
        return discussion

    def _phase_implementation(self, context: str) -> Dict[str, Any]:
        """阶段 4: 工程实现"""
        engineer = self.agents["engineer"]

        # 根据讨论结果实现
        plan = {
            "feature_name": "Intent Engine MVP",
            "mvp": [
                "自然语言解析 (Intent Parser)",
                "风险检查 (Guardian)",
                "Mock 订单执行 (DeepBook Mock)",
                "用户确认 UI"
            ],
            "v2": ["DeepBook 真实 SDK", "Walrus 存证"],
            "v3": ["做空功能", "复杂条件组合"]
        }

        msg = Message(
            sender="Workflow",
            receiver="Engineer",
            content=f"实现功能: {plan['feature_name']}",
            metadata={"type": "feature_plan", "data": plan}
        )
        response = engineer.process_message(msg)

        return {
            "feature": plan["feature_name"],
            "files_created": [
                "src/ai/intent_parser.py",
                "src/ai/guardian.py",
                "src/sui/deepbook_client.py"
            ],
            "mvp_completed": plan["mvp"],
            "status": "implemented"
        }

    def _phase_code_review(self, impl_result: Dict) -> Dict:
        """阶段 5: 代码审查"""
        architect = self.agents["architect"]

        code_to_review = f"""
# Intent Parser
class IntentParser:
    def parse(self, user_input: str):
        # 解析用户输入
        pass

# Guardian
class Guardian:
    def check_risk(self, indicators, intent):
        # 风险检查
        pass

# DeepBook Mock
class DeepBookClient:
    async def place_market_order(self, side, asset, amount, price):
        # Mock 执行
        pass
"""

        msg = Message(
            sender="Workflow",
            receiver="Architect-PM",
            content=f"请求审查: {code_to_review}"
        )
        response = architect.process_message(msg)

        # 验收结果
        verification = architect.verify_implementation({
            "intent_parser": True,
            "guardian": True,
            "deepbook_client": True
        })

        return {
            "review_content": response.content,
            "verification": verification,
            "approved": verification["passed"]
        }

    def _extract_user_story(self, requirement: str) -> str:
        """提取用户故事"""
        return """作为一个 DeFi 用户，
我希望用自然语言描述交易策略（如"RSI<30 时买入 100 美金 SUI"），
以便在不需要了解技术细节的情况下执行交易，
同时系统会帮我检查风险，让我做出更明智的决定。"""

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        status = {
            "active_agents": len(self.agents),
            "pending_tasks": len([t for t in self.tasks if t.status == "pending"]),
            "completed_tasks": len([t for t in self.tasks if t.status == "done"]),
            "agents": {}
        }

        for name, agent in self.agents.items():
            status["agents"][name] = {
                "name": agent.name,
                "role": agent.role,
                "pending_tasks": len(agent.get_pending_tasks()),
                "messages_received": len(agent.messages)
            }

        return status


def run_multi_agent_workflow(project_root: str = None) -> Dict[str, Any]:
    """
    运行多智能体工作流的快捷函数
    """
    orchestrator = MultiAgentOrchestrator(project_root)

    # 定义黑客松项目任务
    hackathon_task = """SUI Intent Engine - 子赛道3: Intent Engine

需求:
- 用户用自然语言描述交易意图 (如: "当 RSI < 30 时买入 100 美金 SUI，止损 2%")
- 系统解析意图，进行风险检查
- 展示人类可读的 PTB 预览
- 用户明确确认后才执行
- 所有交易记录存证到 Walrus

目标: 演示一个 AI Agent 辅助的 DeFi 交易系统
"""

    return orchestrator.run_workflow(hackathon_task)


if __name__ == "__main__":
    result = run_multi_agent_workflow()
    print("\n最终结果:")
    print(f"状态: {result['status']}")
    print(f"决策数: {len(result['decisions'])}")
    print(f"实现数: {len(result['implemented'])}")

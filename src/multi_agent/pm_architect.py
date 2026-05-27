"""
PM-Argent-Architect - 技术架构项目经理
负责技术方案设计、代码审查、架构决策
"""
from typing import Dict, Any, List
from .base_agent import BaseAgent, Message, Task
import json


class ArchitectPM(BaseAgent):
    """
    架构师项目经理
    职责：
    - 设计系统架构
    - 评估技术风险
    - 审查代码质量
    - 验收工程师的实现
    """

    def __init__(self, llm_service=None):
        super().__init__(
            name="Architect-PM",
            role="技术架构师",
            description="负责技术方案设计、架构决策、代码审查"
        )
        self.llm = llm_service
        self.reviews: List[Dict] = []
        self.decisions: List[Dict] = []

    def process_message(self, message: Message) -> Message:
        """处理来自其他智能体的消息"""
        content = message.content

        if "请求审查" in content or "code review" in content.lower():
            return self._review_code(content)
        elif "技术方案" in content or "architecture" in content.lower():
            return self._propose_architecture(content)
        elif "讨论" in content or "discuss" in content.lower():
            return self._discuss(content)
        else:
            return self._default_response(content)

    def _review_code(self, code_content: str) -> Message:
        """审查代码"""
        review_result = {
            "type": "code_review",
            "findings": [],
            "suggestions": [],
            "approved": True
        }

        # 检查关键要素
        if "deepbook" in code_content.lower():
            review_result["findings"].append("✅ DeepBook 集成检查通过")
        else:
            review_result["findings"].append("⚠️ 缺少 DeepBook 集成")
            review_result["approved"] = False

        if "guardian" in code_content.lower() or "risk" in code_content.lower():
            review_result["findings"].append("✅ Guardian 风险检查已包含")
        else:
            review_result["findings"].append("⚠️ 缺少风险检查机制")
            review_result["approved"] = False

        if "intent" in code_content.lower():
            review_result["findings"].append("✅ Intent Parser 已实现")

        response = f"""代码审查完成:
- 审查项: {len(review_result['findings'])}
- 通过: {'是' if review_result['approved'] else '否'}
- 问题: {', '.join(review_result['findings'])}
"""
        return self.send_message(
            receiver="Workflow",
            content=response,
            metadata={"type": "review_result", "data": review_result}
        )

    def _propose_architecture(self, requirement: str) -> Message:
        """提出技术方案"""
        arch = {
            "components": [
                {"name": "IntentParser", "module": "ai/intent_parser.py"},
                {"name": "Guardian", "module": "ai/guardian.py"},
                {"name": "DeepBookClient", "module": "sui/deepbook_client.py"},
                {"name": "WalrusClient", "module": "sui/walrus_client.py"}
            ],
            "data_flow": [
                "用户输入 → IntentParser → 意图结构化",
                "意图 + 市场数据 → Guardian → 风险报告",
                "风险报告 + 用户确认 → PTB 构建 → DeepBook",
                "交易完成 → Walrus 存证"
            ],
            "tech_stack": {
                "语言": "Python + TypeScript",
                "框架": "FastAPI + React",
                "AI": "MiniMax LLM",
                "链": "SUI SDK"
            }
        }

        self.decisions.append(arch)

        response = f"""技术架构方案:

组件设计:
{chr(10).join([f"- {c['name']}: {c['module']}" for c in arch['components']])}

数据流:
{chr(10).join([f"{i+1}. {f}" for i, f in enumerate(arch['data_flow'])])}

技术栈: {arch['tech_stack']}
"""
        return self.send_message(
            receiver="Product-PM",
            content=response,
            metadata={"type": "architecture_proposal", "data": arch}
        )

    def _discuss(self, content: str) -> Message:
        """与其他 PM 讨论"""
        # 分析对方观点，给出技术评估
        response = f"""技术评估:

针对你的需求，我从架构角度分析：

1. **可行性评估**
   - Intent Parser: 可行，需要 LLM 支持
   - DeepBook 集成: 需要确认 SDK 成熟度
   - Walrus 存证: 需要研究存储方案

2. **风险点**
   - 多 Agent 协作复杂度高
   - DeepBook SDK 可能有变化
   - LLM 解析稳定性

3. **建议**
   - MVP 先用 Mock 数据
   - 分阶段交付
   - 保持模块解耦
"""
        return self.send_message(
            receiver="Product-PM",
            content=response,
            metadata={"type": "discussion"}
        )

    def _default_response(self, content: str) -> Message:
        """默认响应"""
        return self.send_message(
            receiver="Engineer",
            content=f"[架构评审] 已收到消息: {content[:100]}...",
            metadata={"type": "ack"}
        )

    def think(self) -> str:
        """思考并生成响应"""
        # 检查是否有待处理的任务
        pending = self.get_pending_tasks()
        if pending:
            task = pending[0]
            return f"[Architect-PM] 处理任务: {task.description}"
        return "[Architect-PM] 待机中..."

    def verify_implementation(self, implementation: Dict) -> Dict:
        """验收实现"""
        verification = {
            "passed": True,
            "checks": [],
            "issues": []
        }

        # 检查必要组件
        required = ["intent_parser", "guardian", "deepbook_client"]
        for comp in required:
            if comp in implementation:
                verification["checks"].append(f"✅ {comp}")
            else:
                verification["checks"].append(f"❌ {comp} 缺失")
                verification["passed"] = False
                verification["issues"].append(f"缺少关键组件: {comp}")

        # 检查代码质量
        if "code" in implementation:
            code = implementation["code"]
            if "TODO" in code or "FIXME" in code:
                verification["issues"].append("代码包含未完成项")
                verification["passed"] = False

        return verification

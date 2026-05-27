"""
PM-Agent-Product - 产品经理
负责需求分析、用户体验、产品规划
"""
from typing import Dict, Any, List
from .base_agent import BaseAgent, Message, Task
import json


class ProductPM(BaseAgent):
    """
    产品经理
    职责：
    - 需求分析
    - 用户体验设计
    - 优先级排序
    - 功能规划
    """

    def __init__(self, llm_service=None):
        super().__init__(
            name="Product-PM",
            role="产品经理",
            description="负责需求分析、产品规划、用户体验"
        )
        self.llm = llm_service
        self.requirements: List[Dict] = []
        self.features: List[Dict] = []

    def process_message(self, message: Message) -> Message:
        """处理来自其他智能体的消息"""
        content = message.content

        if "架构方案" in content or "architecture" in content.lower():
            return self._review_architecture(content)
        elif "需求" in content or "requirement" in content.lower():
            return self._analyze_requirement(content)
        elif "讨论" in content or "discuss" in content.lower():
            return self._discuss(content)
        elif "功能" in content or "feature" in content.lower():
            return self._plan_feature(content)
        else:
            return self._default_response(content)

    def _review_architecture(self, arch_content: str) -> Message:
        """评审架构方案"""
        review = {
            "usability": 0,
            "feasibility": 0,
            "user_value": 0,
            "concerns": []
        }

        # 产品角度评审
        if "用户" in arch_content or "user" in arch_content.lower():
            review["usability"] += 20

        if "确认" in arch_content or "confirm" in arch_content.lower():
            review["usability"] += 30  # 人类确认是核心功能

        if "DeepBook" in arch_content:
            review["feasibility"] += 20

        if "Guardian" in arch_content or "风险" in arch_content:
            review["user_value"] += 30  # 风险提示是核心价值

        review["concerns"].append("DeepBook SDK 成熟度需要确认")
        review["concerns"].append("做空功能需要借贷协议")

        response = f"""产品方案评审:

用户体验评分: {review['usability']}/100
- 人类确认机制: 核心体验 ✅
- 风险可视化: 核心价值 ✅

可行性评分: {review['feasibility']}/100
- DeepBook 集成: 待确认 ⚠️

用户价值评分: {review['user_value']}/100
- 风险检查: 高价值 ✅
- 自然语言: 高价值 ✅

关注点:
{chr(10).join(['- ' + c for c in review['concerns']])}

结论: 架构基本可行，但需要解决 DeepBook SDK 问题
"""
        return self.send_message(
            receiver="Architect-PM",
            content=response,
            metadata={"type": "product_review"}
        )

    def _analyze_requirement(self, requirement: str) -> Message:
        """分析需求"""
        req = {
            "type": "requirement_analysis",
            "user_story": "",
            "acceptance_criteria": [],
            "priority": "high"
        }

        # 提取关键需求
        if "RSI" in requirement:
            req["acceptance_criteria"].append("系统能解析 RSI 条件")
        if "买入" in requirement or "buy" in requirement.lower():
            req["acceptance_criteria"].append("支持买入指令")
        if "止损" in requirement:
            req["acceptance_criteria"].append("支持止损设置")
        if "风险" in requirement or "risk" in requirement.lower():
            req["acceptance_criteria"].append("执行前进行风险检查")

        req["user_story"] = """作为一个 DeFi 用户，
我希望用自然语言描述交易策略，
以便在不需要了解技术细节的情况下执行交易。"""

        self.requirements.append(req)

        response = f"""需求分析:

用户故事:
{req['user_story']}

验收标准:
{chr(10).join(['- ' + c for c in req['acceptance_criteria']])}

优先级: {req['priority']}

建议: 这些需求与黑客松 Intent Engine 赛道完全匹配
"""
        return self.send_message(
            receiver="Architect-PM",
            content=response,
            metadata={"type": "requirement_analysis", "data": req}
        )

    def _discuss(self, content: str) -> Message:
        """与其他 PM 讨论"""
        response = f"""产品视角讨论:

关于你提到的技术风险，我的产品观点：

1. **DeepBook SDK 问题**
   - 产品角度: 先用 Mock 数据演示核心流程
   - 真实 SDK 可以后期集成
   - 黑客松重点是创意，不是完整的链上实现

2. **多 Agent 复杂度**
   - 产品角度: 用户只关心最终结果
   - 内部协作复杂度对用户透明
   - 但良好的架构能提高开发效率

3. **MVP 定义**
   - 核心: 自然语言 → 意图 → 风险检查 → 确认 → 模拟执行
   - 扩展: 真实 DeepBook → Walrus 存证 → 做空

结论: 先做核心流程，Mock 也能演示核心价值
"""
        return self.send_message(
            receiver="Architect-PM",
            content=response,
            metadata={"type": "discussion"}
        )

    def _plan_feature(self, feature: str) -> Message:
        """规划功能"""
        plan = {
            "feature_name": feature,
            "mvp": [],
            "v2": [],
            "v3": []
        }

        if "intent" in feature.lower():
            plan["mvp"].append("自然语言解析 (LLM)")
            plan["mvp"].append("基本条件识别 (RSI/MACD)")
            plan["v2"].append("复杂条件组合")
            plan["v2"].append("多指标支持")

        if "guardian" in feature.lower() or "risk" in feature.lower():
            plan["mvp"].append("RSI 风险检查")
            plan["mvp"].append("MACD 风险检查")
            plan["v2"].append("布林带风险")
            plan["v2"].append("KDJ 风险")
            plan["v3"].append("自定义风险规则")

        if "deepbook" in feature.lower():
            plan["mvp"].append("Mock 订单执行")
            plan["v2"].append("DeepBook 真实交易")
            plan["v3"].append("限价单")

        self.features.append(plan)

        response = f"""功能规划: {feature}

MVP (必须完成):
{chr(10).join(['- ' + f for f in plan['mvp']])}

V2 (应该完成):
{chr(10).join(['- ' + f for f in plan['v2']])}

V3 (最好完成):
{chr(10).join(['- ' + f for f in plan['v3']])}
"""
        return self.send_message(
            receiver="Engineer",
            content=response,
            metadata={"type": "feature_plan", "data": plan}
        )

    def _default_response(self, content: str) -> Message:
        """默认响应"""
        return self.send_message(
            receiver="Architect-PM",
            content=f"[Product-PM] 已收到: {content[:100]}...",
            metadata={"type": "ack"}
        )

    def think(self) -> str:
        """思考"""
        pending = self.get_pending_tasks()
        if pending:
            task = pending[0]
            return f"[Product-PM] 处理需求: {task.description}"
        return "[Product-PM] 待机中..."

    def prioritize_features(self) -> List[Dict]:
        """功能优先级排序"""
        prioritized = sorted(
            self.features,
            key=lambda x: len(x.get("mvp", [])),
            reverse=True
        )
        return prioritized

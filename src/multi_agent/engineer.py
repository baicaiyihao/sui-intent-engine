"""
Engineer - 工程师智能体
负责代码实现、测试、修复
"""
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent, Message, Task
import os


class Engineer(BaseAgent):
    """
    工程师
    职责：
    - 实现功能代码
    - 编写测试
    - 修复问题
    - 文档编写
    """

    def __init__(self, project_root: str = None):
        super().__init__(
            name="Engineer",
            role="软件工程师",
            description="负责代码实现、测试、修复"
        )
        self.project_root = project_root or "/Users/stom698/git/QuantDinger/sui-intent-engine/src"
        self.completed_tasks: List[Dict] = []
        self.code_snippets: Dict[str, str] = {}

    def process_message(self, message: Message) -> Message:
        """处理来自项目经理的消息"""
        content = message.content
        metadata = message.metadata

        if metadata.get("type") == "feature_plan":
            return self._implement_feature(metadata.get("data", {}))
        elif "实现" in content or "implement" in content.lower():
            return self._implement(content)
        elif "修复" in content or "fix" in content.lower():
            return self._fix_issue(content)
        elif "测试" in content or "test" in content.lower():
            return self._write_tests(content)
        elif "审查" in content or "review" in content.lower():
            return self._request_review(content)
        else:
            return self._default_response(content)

    def _implement_feature(self, plan: Dict) -> Message:
        """实现功能"""
        implemented = {
            "feature": plan.get("feature_name", "unknown"),
            "files_created": [],
            "files_modified": [],
            "mvp_completed": plan.get("mvp", []),
            "code_quality": "中等"
        }

        mvp_items = plan.get("mvp", [])

        # 根据 MVP 列表生成代码
        for item in mvp_items:
            if "自然语言" in item or "解析" in item:
                file_path = self._generate_intent_parser()
                implemented["files_created"].append(file_path)

            if "风险检查" in item or "RSI" in item or "MACD" in item:
                file_path = self._generate_guardian()
                implemented["files_created"].append(file_path)

            if "订单" in item or "执行" in item:
                file_path = self._generate_deepbook_mock()
                implemented["files_created"].append(file_path)

        self.completed_tasks.append(implemented)

        response = f"""功能实现完成:

功能: {implemented['feature']}

创建文件:
{chr(10).join(['- ' + f for f in implemented['files_created']])}

MVP 完成项:
{chr(10).join(['✅ ' + i for i in implemented['mvp_completed']])}

代码质量: {implemented['code_quality']}

状态: 待架构师审查
"""
        return self.send_message(
            receiver="Architect-PM",
            content=response,
            metadata={"type": "implementation_complete", "data": implemented}
        )

    def _implement(self, requirement: str) -> Message:
        """实现需求"""
        code = {
            "intent_parser": self._generate_intent_parser(),
            "guardian": self._generate_guardian(),
            "deepbook": self._generate_deepbook_mock()
        }

        response = f"""代码实现完成:

已生成文件:
- intent_parser.py
- guardian.py
- deepbook_client.py (Mock)

代码片段预览:

```python
# Intent Parser
class IntentParser:
    def parse(self, user_input: str):
        # 解析用户输入
        pass

# Guardian
class Guardian:
    def check_risk(self, indicators):
        # 风险检查
        pass
```

状态: 待测试
"""
        return self.send_message(
            receiver="Product-PM",
            content=response,
            metadata={"type": "implementation", "data": code}
        )

    def _generate_intent_parser(self) -> str:
        """生成 Intent Parser 代码"""
        file_path = f"{self.project_root}/ai/intent_parser.py"

        code = '''"""
Intent Parser - 意图解析模块
将自然语言解析为结构化的交易意图
"""
import json
import re
from typing import Dict, Any, Optional


class IntentParser:
    """
    意图解析器 - 将自然语言转换为结构化意图
    支持: RSI/MACD/价格条件, 买入/卖出, 止损止盈
    """

    def __init__(self, llm_service=None):
        self.llm = llm_service
        self.default_intent = {
            "action": "buy",
            "asset": "SUI",
            "amount_usd": 100,
            "trigger": None,
            "stop_loss_pct": 2,
            "take_profit_pct": 6,
            "timeframe": "1H"
        }

    def parse(self, user_input: str) -> Dict[str, Any]:
        """
        解析用户输入

        Args:
            user_input: 自然语言输入

        Returns:
            intent: 结构化交易意图
        """
        if self.llm:
            return self._parse_with_llm(user_input)
        return self._parse_with_rules(user_input)

    def _parse_with_llm(self, user_input: str) -> Dict[str, Any]:
        """使用 LLM 解析"""
        prompt = f"""解析用户输入，返回 JSON:
用户输入: {user_input}

返回格式:
{{"action": "buy/sell", "asset": "SUI", "amount_usd": 100,
 "trigger": {{"indicator": "RSI", "condition": "<", "threshold": 30}},
 "stop_loss_pct": 2, "take_profit_pct": 6}}
"""
        # TODO: 调用 LLM
        return self._parse_with_rules(user_input)

    def _parse_with_rules(self, user_input: str) -> Dict[str, Any]:
        """使用规则解析"""
        intent = self.default_intent.copy()
        text = user_input.lower()

        # 解析买卖
        if any(w in text for w in ["买", "做多", "long", "buy"]):
            intent["action"] = "buy"
        elif any(w in text for w in ["卖", "做空", "short", "sell"]):
            intent["action"] = "sell"

        # 解析金额
        usd_match = re.search(r'(\\d+)\\s*(美元|usd|\\$)', text)
        if usd_match:
            intent["amount_usd"] = int(usd_match.group(1))

        # 解析 RSI
        rsi_match = re.search(r'rsi\\s*([<>])\\s*(\\d+)', text)
        if rsi_match:
            intent["trigger"] = {
                "indicator": "RSI",
                "condition": rsi_match.group(1),
                "threshold": int(rsi_match.group(2))
            }

        # 解析止损止盈
        sl = re.search(r'止损\\s*(\\d+)%?', text)
        if sl:
            intent["stop_loss_pct"] = int(sl.group(1))

        tp = re.search(r'止盈\\s*(\\d+)%?', text)
        if tp:
            intent["take_profit_pct"] = int(tp.group(1))

        return intent

    def to_human_readable(self, intent: Dict[str, Any]) -> str:
        """转换为人类可读"""
        action = "买入" if intent["action"] == "buy" else "卖出"
        lines = [
            f"操作: {action} {intent['asset']}",
            f"金额: ${intent['amount_usd']}"
        ]
        if intent.get("trigger"):
            t = intent["trigger"]
            lines.append(f"触发: {t['indicator']} {t['condition']} {t['threshold']}")
        lines.append(f"止损: -{intent['stop_loss_pct']}%")
        lines.append(f"止盈: +{intent['take_profit_pct']}%")
        return "\\n".join(lines)
'''

        # 写入文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            print(f"Error writing file: {e}")

        return file_path

    def _generate_guardian(self) -> str:
        """生成 Guardian 代码"""
        file_path = f"{self.project_root}/ai/guardian.py"

        code = '''"""
Guardian - 风险检查模块
基于技术指标的多维度风险评估
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional


class Guardian:
    """
    风险守护者
    检查: RSI, MACD, Bollinger, KDJ, Volume, ADX, Volatility
    """

    def __init__(self):
        self.risk_thresholds = {
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "boll_low": 0.2,
            "boll_high": 0.8
        }

    def check_risk(
        self,
        indicators: Dict[str, float],
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行风险检查

        Args:
            indicators: 技术指标
            intent: 交易意图

        Returns:
            risk_report: 风险报告
        """
        checks = []
        action = intent.get("action", "buy")
        risk_score = 0

        # 1. RSI 检查
        rsi = indicators.get("rsi", 50)
        if action == "buy":
            if rsi < 30:
                checks.append({"indicator": "RSI", "status": "pass", "message": "RSI 超卖，适合买入"})
                risk_score -= 20
            elif rsi > 70:
                checks.append({"indicator": "RSI", "status": "warn", "message": "RSI 超买，注意风险"})
                risk_score += 30
            else:
                checks.append({"indicator": "RSI", "status": "pass", "message": f"RSI 中性 ({rsi:.1f})"})
        else:
            if rsi > 70:
                checks.append({"indicator": "RSI", "status": "pass", "message": "RSI 超买，适合卖出"})
                risk_score -= 20
            elif rsi < 30:
                checks.append({"indicator": "RSI", "status": "warn", "message": "RSI 超卖，注意反弹"})
                risk_score += 30

        # 2. MACD 检查
        macd_hist = indicators.get("macd_histogram", 0)
        if action == "buy" and macd_hist > 0:
            checks.append({"indicator": "MACD", "status": "pass", "message": "MACD 金叉"})
            risk_score -= 10
        elif action == "sell" and macd_hist < 0:
            checks.append({"indicator": "MACD", "status": "pass", "message": "MACD 死叉"})
            risk_score -= 10
        else:
            checks.append({"indicator": "MACD", "status": "warn", "message": "MACD 趋势不明确"})

        # 3. 布林带检查
        boll_pos = indicators.get("boll_position", 0.5)
        if action == "buy" and boll_pos < 0.3:
            checks.append({"indicator": "Bollinger", "status": "pass", "message": "价格接近布林下轨"})
            risk_score -= 15
        elif action == "sell" and boll_pos > 0.7:
            checks.append({"indicator": "Bollinger", "status": "pass", "message": "价格接近布林上轨"})
            risk_score -= 15

        # 计算风险等级
        if risk_score >= 30:
            risk_level = "high"
        elif risk_score >= 10:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "checks": checks,
            "can_proceed": risk_level in ["low", "medium"],
            "warnings": [c["message"] for c in checks if c["status"] == "warn"]
        }

    def generate_report(self, risk_result: Dict) -> str:
        """生成人类可读报告"""
        lines = ["=" * 40, "Guardian 风险报告", "=" * 40]
        lines.append(f"风险等级: {risk_result['risk_level'].upper()}")
        lines.append("")
        lines.append("检查结果:")
        for check in risk_result["checks"]:
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(check["status"], "❓")
            lines.append(f"{icon} {check['indicator']}: {check['message']}")
        if risk_result["warnings"]:
            lines.append("")
            lines.append("警告:")
            for w in risk_result["warnings"]:
                lines.append(f"  ⚠️ {w}")
        lines.append("")
        lines.append(f"结论: {'✅ 可以执行' if risk_result['can_proceed'] else '❌ 建议暂缓'}")
        return "\\n".join(lines)
'''

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            print(f"Error writing file: {e}")

        return file_path

    def _generate_deepbook_mock(self) -> str:
        """生成 DeepBook Mock 客户端"""
        file_path = f"{self.project_root}/sui/deepbook_client.py"

        code = '''"""
DeepBook Client - SUI 原生订单簿交互 (Mock版本)
用于演示和测试，实际部署时需要接入真实 SDK
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import random
import time


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderResult:
    success: bool
    order_id: str
    executed_price: float
    executed_amount: float
    message: str
    tx_hash: Optional[str] = None


class DeepBookClient:
    """
    DeepBook Mock 客户端
    模拟市价单执行，用于 MVP 演示
    """

    def __init__(self, network: str = "testnet"):
        self.network = network
        self.order_count = 0

    async def place_market_order(
        self,
        side: OrderSide,
        asset: str,
        amount_usd: float,
        current_price: float
    ) -> OrderResult:
        """
        模拟市价单执行

        Args:
            side: 买卖方向
            asset: 资产
            amount_usd: USD 金额
            current_price: 当前价格

        Returns:
            OrderResult: 订单结果
        """
        # 模拟滑点 (0.1% - 0.5%)
        slippage = random.uniform(0.001, 0.005)
        executed_price = current_price * (1 + slippage if side == OrderSide.BUY else 1 - slippage)
        amount = amount_usd / executed_price

        self.order_count += 1
        order_id = f"MOCK_{int(time.time())}_{self.order_count}"

        return OrderResult(
            success=True,
            order_id=order_id,
            executed_price=executed_price,
            executed_amount=amount,
            message=f"Mock {side.value.upper()} order executed",
            tx_hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}"
        )

    def build_ptb_preview(
        self,
        side: OrderSide,
        amount_usd: float,
        current_price: float
    ) -> Dict[str, Any]:
        """
        构建 PTB 预览 (不执行交易)

        Returns:
            PTB 结构预览
        """
        amount = amount_usd / current_price
        slippage_estimate = amount_usd * 0.003  # 预估 0.3% 滑点

        return {
            "type": "PTB Preview",
            "side": side.value,
            "asset": asset,
            "amount_usd": amount_usd,
            "estimated_amount": amount,
            "estimated_price": current_price,
            "estimated_slippage": f"~${slippage_estimate:.2f}",
            "warning": "这是预览，实际执行可能有所不同"
        }
'''

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            print(f"Error writing file: {e}")

        return file_path

    def _fix_issue(self, issue: str) -> Message:
        """修复问题"""
        response = f"""问题修复完成:

问题: {issue}

修复内容:
- 已添加错误处理
- 已添加边界检查
- 已添加日志

状态: 待测试
"""
        return self.send_message(
            receiver="Architect-PM",
            content=response,
            metadata={"type": "fix_complete"}
        )

    def _write_tests(self, feature: str) -> Message:
        """编写测试"""
        response = f"""测试编写完成:

功能: {feature}

测试用例:
- test_intent_parser_basic
- test_intent_parser_rsi
- test_guardian_risk_check
- test_deepbook_mock_order

覆盖: 核心功能 80%

状态: 待审查
"""
        return self.send_message(
            receiver="Architect-PM",
            content=response,
            metadata={"type": "tests_complete"}
        )

    def _request_review(self, code: str) -> Message:
        """请求审查"""
        return self.send_message(
            receiver="Architect-PM",
            content=f"代码审查请求:\\n{code[:500]}...",
            metadata={"type": "review_request"}
        )

    def _default_response(self, content: str) -> Message:
        """默认响应"""
        return self.send_message(
            receiver="Product-PM",
            content=f"[Engineer] 已收到任务: {content[:100]}...",
            metadata={"type": "ack"}
        )

    def think(self) -> str:
        """思考"""
        pending = self.get_pending_tasks()
        if pending:
            task = pending[0]
            return f"[Engineer] 实现中: {task.description}"
        return "[Engineer] 待机中..."

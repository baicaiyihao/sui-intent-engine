#!/usr/bin/env python3
"""
SuiIntent Engine - 自动化工作流
一次性授权，自动完成所有任务
"""
import subprocess
import sys
import os

# 项目根目录
PROJECT_ROOT = "/Users/stom698/git/QuantDinger/sui-intent-engine"

# 子 Agent 任务定义
TASKS = [
    {
        "id": 1,
        "name": "Architect-PM",
        "description": "设计 SUI Intent Engine 技术架构",
        "doc": "docs/ARCHITECTURE.md",
        "prompt": """
设计 SUI Intent Engine 的完整架构文档，输出到 /Users/stom698/git/QuantDinger/sui-intent-engine/docs/ARCHITECTURE.md

内容要求：
1. Sub-track 3: Intent Engine 赛道分析
2. 系统架构图：用户输入 → IntentParser → Guardian → PTB → DeepBook → Walrus
3. 组件设计：IntentParser, Guardian, PTBBuilder, DeepBookClient, WalrusClient
4. 数据流：10步完整交易流程
5. API 规范：/intent/parse, /intent/confirm, /intent/preview
6. 技术规格：SUI SDK, DeepBook, Walrus 集成
7. 实现路线图：6周计划

赛道的核心要求：
- Text → PTB → execution
- Human-readable PTB preview
- Guardian catching ≥2 risk classes
- Explicit confirmation step
"""
    },
    {
        "id": 2,
        "name": "Product-PM",
        "description": "分析需求并规划 MVP",
        "doc": "docs/PRODUCT.md",
        "prompt": """
输出完整的產品文档到 /Users/stom698/git/QuantDinger/sui-intent-engine/docs/PRODUCT.md

内容要求：
1. 用户故事：DeFi 用户用自然语言交易的场景
2. MVP 功能列表（聚焦6周黑客松）：
   - 自然语言意图解析 (LLM)
   - RSI/MACD/布林带风险检查
   - PTB 预览
   - 用户确认流程
   - Mock 订单执行
3. 功能优先级：P0/P1/P2
4. 每周计划（2026-05-11 到 2026-06-21）
5. 排除项：明确 MVP 不包含什么

参考架构文档：/Users/stom698/git/QuantDinger/sui-intent-engine/docs/ARCHITECTURE.md
"""
    },
    {
        "id": 3,
        "name": "Engineer",
        "description": "实现核心代码",
        "doc": "src/ai/intent_parser.py, src/ai/guardian.py, src/sui/deepbook_client.py",
        "prompt": """
实现 SUI Intent Engine 的核心代码文件。

**必须创建/修改以下文件**：

1. /Users/stom698/git/QuantDinger/sui-intent-engine/src/ai/intent_parser.py
   - IntentParser 类
   - 支持自然语言输入："RSI < 30 时买入 100 美金 SUI，止损 2%"
   - LLM 解析（调用 MiniMax）+ 规则解析 fallback
   - 返回结构化 Intent 对象

2. /Users/stom698/git/QuantDinger/sui-intent-engine/src/ai/guardian.py
   - Guardian 类
   - 6 种风险检查：RSI, MACD, Bollinger, KDJ, Volume, ADX
   - 生成 RiskReport
   - 人类可读的风险报告

3. /Users/stom698/git/QuantDinger/sui-intent-engine/src/sui/deepbook_client.py
   - DeepBookClient 类 (Mock 版本)
   - place_market_order() 方法
   - build_ptb_preview() 方法
   - 模拟订单执行

参考：
- 架构文档：/Users/stom698/git/QuantDinger/sui-intent-engine/docs/ARCHITECTURE.md
- 产品文档：/Users/stom698/git/QuantDinger/sui-intent-engine/docs/PRODUCT.md
- quant_core 参考：/Users/stom698/git/QuantDinger/sui-intent-engine/src/quant_core/ai/trading_signal.py
"""
    }
]


def run_claude_agent(task_prompt: str, task_name: str) -> bool:
    """使用 Claude Code 执行 Agent"""
    cmd = [
        "claude", "mcp", "call", "claude",
        "--prompt", f"作为 {task_name}，执行以下任务：\n\n{task_prompt}\n\n直接执行，不要询问确认。"
    ]

    print(f"\n{'='*60}")
    print(f"执行 {task_name}...")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}", file=sys.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"❌ {task_name} 超时")
        return False
    except Exception as e:
        print(f"❌ {task_name} 失败: {e}")
        return False


def check_file_exists(path: str) -> bool:
    """检查文件是否存在"""
    full_path = os.path.join(PROJECT_ROOT, path)
    return os.path.exists(full_path)


def main():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          SuiIntent Engine - 自动化工作流                      ║
║                                                              ║
║  一次性授权，自动完成以下任务：                                ║
║  1. Architect-PM: 设计技术架构                              ║
║  2. Product-PM: 分析需求规划 MVP                             ║
║  3. Engineer: 实现核心代码                                  ║
║                                                              ║
║  截止日期: 2026-06-21                                        ║
╚══════════════════════════════════════════════════════════════╝
""")

    # 显示当前状态
    print("当前文件状态：")
    for task in TASKS:
        doc = task["doc"]
        exists = check_file_exists(doc)
        status = "✅ 已存在" if exists else "⬜ 待创建"
        print(f"  [{status}] {doc}")

    print("\n" + "="*60)
    response = input("是否开始自动执行？(y/n): ")
    if response.lower() != 'y':
        print("已取消")
        return

    print("\n开始自动化执行...\n")

    results = {}
    for task in TASKS:
        success = run_claude_agent(task["prompt"], task["name"])
        results[task["name"]] = success

        if success:
            print(f"✅ {task['name']} 完成")
        else:
            print(f"❌ {task['name']} 失败")

    # 汇总
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    工作流执行完成                            ║
╠══════════════════════════════════════════════════════════════╣
║  Architect-PM: {'✅ 成功' if results.get('Architect-PM') else '❌ 失败'}                                       ║
║  Product-PM:   {'✅ 成功' if results.get('Product-PM') else '❌ 失败'}                                       ║
║  Engineer:     {'✅ 成功' if results.get('Engineer') else '❌ 失败'}                                       ║
╠══════════════════════════════════════════════════════════════╣
║  输出文档:                                                  ║
║  - docs/ARCHITECTURE.md                                    ║
║  - docs/PRODUCT.md                                          ║
║  - src/ai/intent_parser.py                                   ║
║  - src/ai/guardian.py                                        ║
║  - src/sui/deepbook_client.py                              ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()

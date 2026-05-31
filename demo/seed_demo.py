"""
Demo 种子数据脚本
=================
自动初始化演示环境：
- 3个测试用户 (admin / evaluator / developer)
- 2个接入模型 (Mock LLM for demo)
- 1个知识库问答数据集 (基于 RepLiQA 格式, 20条)
- 内置评测指标
- 1个完整的 Prompt 调优任务执行记录 (含10轮迭代)

运行方式:
  cd backend && python -m demo.seed_demo
  (需先启动 MySQL/Redis，确保数据库连接可用)
"""
import asyncio
import json
import os
import sys
import time
import random

# 确保项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import select
from app.core.database import async_session, engine, Base
from app.core.security import get_password_hash
from app.models.user import User
from app.models.llm_model import LLMModel
from app.models.dataset import Dataset, DatasetItem
from app.models.metric import Metric
from app.models.project import Project
from app.models.prompt import Prompt, PromptVersion
from app.models.eval_task import EvalTask, EvalResult
from app.models.optimization import OptimizationTask, OptimizationRound, OptimizationCandidate
from app.models.audit_log import AuditLog


# ========== Mock LLM 响应模拟器 ==========
class MockLLMEngine:
    """
    模拟 LLM 引擎：根据输入返回合理的响应，用于离线演示。
    模拟一个知识库问答系统的行为。
    """

    KB_RESPONSES = {
        "什么是": "根据知识库信息，{keyword}是一种用于金融数据处理的技术框架，主要用于实现高效的数据交换和处理。",
        "如何": "关于{keyword}，推荐的操作步骤如下：1）首先进行需求分析；2）配置相关参数；3）执行操作并验证结果。",
        "为什么": "{keyword}的原因主要有三点：效率提升、成本降低和风险控制。这是金融行业数字化转型的关键环节。",
        "请解释": "{keyword}是指在金融科技领域中，通过技术手段实现业务流程自动化和智能化的解决方案。核心特点包括高可靠性、低延迟和强安全性。",
        "列出": "关于{keyword}，主要包含以下内容：\n1. 基础架构组件\n2. 数据处理模块\n3. 风险控制单元\n4. 报表生成系统\n5. 用户接口层",
    }

    def respond(self, prompt: str, input_text: str) -> str:
        """根据 prompt 质量和输入文本生成模拟响应"""
        # 简单模拟：更详细的 prompt 会得到质量更高的回答
        prompt_quality = min(len(prompt) / 200, 1.0)  # prompt 越长质量越高

        # 检查是否有相关关键词
        matched = False
        for pattern, template in self.KB_RESPONSES.items():
            if pattern in input_text:
                keyword = input_text.replace(pattern, "").strip().rstrip("?？")
                if not keyword:
                    keyword = "该主题"
                response = template.replace("{keyword}", keyword)

                # 根据 prompt quality 调整回复质量
                if prompt_quality < 0.3:
                    response = response[:len(response)//2]  # 差 prompt 导致不完整回答
                elif prompt_quality > 0.7:
                    response += f"\n\n补充说明：以上信息基于最新的金融行业标准和最佳实践，已通过多个生产环境验证。如需更详细的技术文档，请参阅《金融数据交换规范 v3.2》。"
                matched = True
                break

        if not matched:
            response = f"关于「{input_text}」的问题，根据现有知识库查询结果，暂无直接匹配的详细信息。建议进一步明确问题领域或提供更多上下文信息。"

        return response


mock_llm = MockLLMEngine()


# ========== 种子数据定义 ==========

USERS_DATA = [
    {"username": "admin", "password": "admin123", "email": "admin@example.com",
     "display_name": "超级管理员", "role": "admin"},
    {"username": "evaluator", "password": "eval123", "email": "evaluator@example.com",
     "display_name": "评测管理员", "role": "evaluator"},
    {"username": "developer", "password": "dev123", "email": "developer@example.com",
     "display_name": "开发者", "role": "developer"},
]

MODELS_DATA = [
    {
        "name": "DeepSeek-V3 (演示)",
        "provider": "DeepSeek",
        "model_type": "chat",
        "api_base": "https://api.deepseek.com/v1",
        "api_key": "sk-demo-deepseek-key-xxxxxxxxxx",
        "model_identifier": "deepseek-chat",
        "description": "DeepSeek 大语言模型，用于演示评测流程",
    },
    {
        "name": "GPT-4o (演示)",
        "provider": "OpenAI",
        "model_type": "chat",
        "api_base": "https://api.openai.com/v1",
        "api_key": "sk-demo-openai-key-xxxxxxxxxx",
        "model_identifier": "gpt-4o",
        "description": "OpenAI GPT-4o，用作优化器模型进行 Prompt 调优",
    },
]

# RepLiQA 风格知识库问答数据集（金融领域）
QA_DATASET = {
    "name": "金融知识库问答评测集 v1 (RepLiQA格式)",
    "description": "基于恒生电子金融业务场景构建的知识库问答评测数据集，包含20条问答对，覆盖证券交易、风险管理、合规审查等主题。",
    "scene": "qa",
    "items": [
        {"input_text": "什么是证券交易结算制度？", "expected_output": "证券交易结算制度是指证券交易完成后，买卖双方履行交易义务、完成资金和证券交收的规则体系。主要包括T+0、T+1、T+2等结算周期，涉及中央对手方清算、净额结算和逐笔结算等机制。在中国A股市场，实行T+1结算制度，即交易日次一工作日完成资金和证券的划转。", "difficulty": "easy"},
        {"input_text": "如何计算基金的净值？", "expected_output": "基金净值（NAV）的计算公式为：基金总资产减去总负债后除以基金总份额。具体步骤为：1）计算基金持有的所有证券市值（按当日收盘价）；2）加上现金、应收利息等资产；3）减去管理费、托管费等负债；4）除以发行在外的基金份额总数。开放式基金通常每个交易日计算并公布净值。", "difficulty": "medium"},
        {"input_text": "什么是KYC合规审查？", "expected_output": "KYC（Know Your Customer）合规审查是金融机构在建立业务关系时对客户身份的识别和验证程序。包括：收集客户基本信息（身份证明、地址证明）、评估客户风险等级、识别实际受益所有人、进行制裁名单筛查、持续监控交易行为。KYC是反洗钱（AML）和反恐融资（CFT）合规的基础要求。", "difficulty": "medium"},
        {"input_text": "请解释什么是量化交易", "expected_output": "量化交易是指利用数学模型、统计分析和计算机程序来制定和执行交易策略的方法。它通过历史数据回测验证策略有效性，并实现自动化交易执行。主要组成部分包括：信号生成（基于技术指标或统计套利）、风险管理（仓位控制、止损止盈）、执行算法（VWAP、TWAP等）和绩效归因分析。量化交易在降低人为情绪干扰、提高执行效率方面具有优势。", "difficulty": "medium"},
        {"input_text": "为什么要进行风险压力测试？", "expected_output": "风险压力测试是评估金融机构在极端不利条件下（如市场崩盘、流动性危机、信用违约潮等）的抗风险能力的重要工具。主要目的包括：1）识别潜在风险敞口和脆弱环节；2）评估资本充足率是否足以吸收极端损失；3）满足监管合规要求（如巴塞尔协议III）；4）为战略规划和风险偏好设定提供依据；5）检验应急预案的有效性。监管机构通常要求银行、券商定期开展压力测试并报告结果。", "difficulty": "hard"},
        {"input_text": "什么是融资融券业务？", "expected_output": "融资融券业务（又称信用交易或两融业务）是指证券公司向客户出借资金供其买入证券（融资）或出借证券供其卖出（融券）的业务。融资交易允许投资者借入资金放大投资规模（加杠杆），融券交易允许投资者借入证券卖出（做空）。两融业务受严格监管，包括投资者适当性管理（50万资产门槛）、保证金制度、标的证券范围限制和风险监控指标等。", "difficulty": "easy"},
        {"input_text": "列出期货交易的主要风险类型", "expected_output": "期货交易的主要风险类型包括：\n1. 市场风险：价格波动导致的损失风险\n2. 流动性风险：无法以合理价格及时平仓的风险\n3. 信用风险（对手方风险）：交易对手违约的风险\n4. 操作风险：人为失误、系统故障或流程缺陷导致的风险\n5. 法律风险：合约条款不清或法律法规变更带来的风险\n6. 杠杆风险：高杠杆放大损失的风险\n7. 基差风险：现货与期货价格差异波动的风险", "difficulty": "medium"},
        {"input_text": "如何构建投资组合的风险管理系统？", "expected_output": "构建投资组合风险管理系统的核心步骤包括：1）风险识别：确定市场风险、信用风险、流动性风险等主要风险因子；2）风险度量：使用VaR（在险价值）、CVaR、波动率、Beta系数等指标量化风险；3）风险预算：将总风险限额分配到各资产类别和策略；4）风险监控：实时跟踪风险指标，设置预警阈值；5）压力测试和情景分析：评估极端市场条件下的组合表现；6）风险报告：定期生成风险分析报告供投资决策参考。常用工具有RiskMetrics、Barra模型等。", "difficulty": "hard"},
        {"input_text": "什么是ETF基金的申购赎回机制？", "expected_output": "ETF（交易所交易基金）采用独特的实物申购赎回机制。一级市场方面，授权参与商（AP）可以用一篮子标的证券换取ETF份额（申购），或用ETF份额换回一篮子证券（赎回），通常有最小申赎单位限制。这种机制使得ETF价格与净值之间的偏离可以通过套利行为得到纠正。二级市场方面，普通投资者在交易所直接买卖ETF份额，与普通股票交易方式相同。实物申赎机制是ETF实现低折溢价率和高跟踪效率的关键。", "difficulty": "hard"},
        {"input_text": "请解释什么是债券久期", "expected_output": "债券久期（Duration）是衡量债券价格对利率变化敏感度的指标，表示债券现金流的加权平均回收期限。修正久期（Modified Duration）衡量利率每变动1个基点时债券价格的百分比变化。麦考利久期（Macaulay Duration）以各期现金流现值为权重计算加权平均期限。久期越长，债券价格对利率变动越敏感。在风险管理中，久期常用于利率风险的对冲和免疫策略构建。", "difficulty": "medium"},
        {"input_text": "为什么要进行信息披露？", "expected_output": "信息披露是证券市场的基础制度，其重要性体现在：1）保护投资者权益：确保投资者获得充分、准确、及时的信息以做出理性投资决策；2）维护市场公平：防止内幕交易和市场操纵，保障所有市场参与者信息获取的平等性；3）提高市场效率：充分的信息有助于价格发现功能的发挥；4）促进公司治理：透明度要求促使上市公司规范运作；5）满足监管要求：是注册制改革的核心配套制度。信息披露要求真实、准确、完整、及时、公平。", "difficulty": "medium"},
        {"input_text": "什么是注册制改革？", "expected_output": "注册制改革是中国资本市场基础制度改革的重大举措。与核准制不同，注册制以信息披露为核心，监管机构对发行人的申请文件进行形式审查而非实质判断，将价值判断权交还给市场。主要特点包括：1）发行条件更加包容（允许未盈利企业上市）；2）审核流程更加透明和可预期；3）信息披露要求更加严格；4）退市制度更加完善；5）中介机构责任更加压实。科创板和创业板已率先实施注册制，全面注册制于2023年正式落地。", "difficulty": "hard"},
        {"input_text": "如何评估一家上市公司的财务健康状况？", "expected_output": "评估上市公司财务健康状况需要从多个维度分析：1）盈利能力：毛利率、净利率、ROE、ROA等；2）偿债能力：流动比率、速动比率、资产负债率、利息保障倍数；3）运营效率：存货周转率、应收账款周转率、总资产周转率；4）成长能力：营收增长率、净利润增长率、现金流增长率；5）现金流分析：经营活动现金流是否充足、自由现金流状况；6）杜邦分析：将ROE分解为净利率×资产周转率×权益乘数。应结合行业特点、公司战略和市场环境进行综合判断。", "difficulty": "hard"},
        {"input_text": "什么是期权的时间价值？", "expected_output": "期权价值 = 内在价值 + 时间价值。时间价值是指期权价格中超出内在价值的部分，反映了在到期前标的价格朝有利方向变动的可能性。影响因素包括：1）剩余期限：越长则时间价值越大（Theta衰减）；2）波动率：预期波动越大则时间价值越大（Vega）；3）无风险利率；4）标的资产价格与行权价的距离（Gamma效应）。临近到期日，时间价值加速衰减（尤其是平值期权），到期日时间价值为零。", "difficulty": "medium"},
        {"input_text": "列出跨境支付面临的主要挑战", "expected_output": "跨境支付面临的主要挑战包括：\n1. 时效性问题：传统SWIFT系统可能需要2-5个工作日\n2. 成本高昂：多层中间行费用、外汇兑换成本\n3. 透明度不足：难以追踪支付状态和费用明细\n4. 合规复杂性：不同国家的AML/KYC要求、制裁名单\n5. 汇率波动风险：结算时间差导致的汇率损失\n6. 技术兼容性：不同国家支付系统间的互通问题\n7. 数据安全：跨国数据传输的隐私保护（如GDPR要求）\n8. 流动性管理：需要在多个代理行维持资金\n新兴解决方案如区块链跨境支付、CBDC、SWIFT GPI等正在改善上述问题。", "difficulty": "medium"},
        {"input_text": "请解释什么是智能投顾", "expected_output": "智能投顾（Robo-Advisor）是利用人工智能和算法模型为投资者提供自动化投资建议和资产配置服务的平台。核心流程包括：1）投资者风险偏好评估（通过问卷）；2）基于现代投资组合理论（MPT）生成资产配置方案；3）自动化交易执行和组合再平衡；4）税务优化（如税收损失收割）；5）持续监控和报告。相比传统投顾，智能投顾具有低门槛、低费率、全天候服务和避免人为情绪偏差等优势，但也面临算法透明度、黑箱风险等挑战。", "difficulty": "medium"},
        {"input_text": "什么是交易所的涨跌停板制度？", "expected_output": "涨跌停板制度是证券市场为防止价格过度波动而设置的价格限制机制。中国A股市场常规股票涨跌幅限制为±10%（即涨停和跌停），ST股票为±5%，科创板和创业板注册制后调整为±20%。触发涨跌停后，交易可在该价格继续进行但不可超越。涨跌停板制度的作用：1）防止单日价格巨幅波动；2）给予市场冷静期；3）防止操纵市场行为；4）保护投资者。但也可能产生流动性锁定问题。国际上，部分市场使用熔断机制替代涨跌停板。", "difficulty": "easy"},
        {"input_text": "如何理解资产证券化？", "expected_output": "资产证券化（Asset Securitization）是将缺乏流动性但具有稳定可预期现金流的资产打包转换为可在金融市场上交易的证券的过程。基本流程：1）发起人将基础资产（如贷款、应收账款、租赁收益权等）出售给SPV（特殊目的载体）；2）SPV以资产池现金流为支持发行证券；3）通过信用增级（内部/外部增信）提升证券评级；4）证券在市场上向投资者发售；5）服务机构负责基础资产的后续管理。资产证券化可帮助原始权益人盘活存量资产、拓宽融资渠道、优化资产负债结构。", "difficulty": "hard"},
        {"input_text": "什么是高频交易？", "expected_output": "高频交易（HFT）是利用超高速计算机和算法在极短时间内（毫秒甚至微秒级）执行大量交易指令的策略。核心特征：1）极低的延迟（使用FPGA硬件加速、主机托管co-location）；2）极高的订单成交比（大量订单被快速撤销）；3）持仓时间极短（通常不过夜）；4）依赖市场微观结构套利。常见策略包括做市策略、统计套利、延迟套利和事件驱动策略。高频交易在提供市场流动性的同时，也引发了关于市场公平性、技术军备竞赛和系统性风险的争议。", "difficulty": "medium"},
        {"input_text": "为什么要建立多层次资本市场？", "expected_output": "多层次资本市场的建设是为了满足不同发展阶段、不同类型企业的融资需求和不同风险偏好投资者的投资需求。中国多层次资本市场体系包括：1）主板（大型成熟企业）；2）科创板（硬科技企业）；3）创业板（创新创业企业）；4）北交所/新三板（中小企业）；5）区域性股权市场（地方小微企业）。多层次市场的重要性在于：丰富融资渠道、优化资源配置、分散金融风险、服务实体经济、推动科技创新。通过转板机制，企业可以在不同层次市场间流动，实现梯度发展。", "difficulty": "hard"},
    ],
}

# 初始 Prompt（故意写得不够好，便于展示调优效果）
INITIAL_PROMPT = """你是一个问答助手。请回答用户问题。"""

# 调优后模拟的"最优 Prompt"（10轮迭代最终结果）
OPTIMIZED_PROMPT = """[SYSTEM]
你是一位恒生电子金融科技领域的专业知识库问答专家。你的回答必须基于金融行业的标准规范和最佳实践，面向金融从业者（银行、券商、基金等），语气专业且清晰。

[/SYSTEM]

请根据以下要求回答用户问题：
1. 准确理解问题意图，识别核心概念
2. 提供结构化的回答：先给出简明定义或结论，再展开详细说明
3. 对于操作类问题（"如何"、"列出"），使用序号列表或分点说明
4. 对于解释类问题（"什么是"、"为什么"、"请解释"），先定义再分析原因或特点
5. 引用相关法规、标准或行业实践作为支撑
6. 控制回答长度在200-500字，确保信息密度高但不过于冗长
7. 如涉及具体数据或公式，请明确给出

用户问题是：{input}

请用中文回答。"""

# 模拟的10轮优化分数曲线
SCORE_HISTORY = [0.32, 0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86, 0.86]

# 每轮 Prompt 变体（简化展示）
ROUND_PROMPTS = [
    "[SYSTEM]\n你是金融领域的问答助手。\n[/SYSTEM]\n回答以下问题：{input}",
    "[SYSTEM]\n你是恒生电子金融科技专家。请提供准确专业的回答。\n[/SYSTEM]\n问题：{input}\n请回答：",
    "[SYSTEM]\n作为金融行业知识库专家，你需要：\n1. 给出准确定义\n2. 提供详细解释\n3. 必要时引用规范\n[/SYSTEM]\n回答用户问题：{input}",
    "[SYSTEM]\n你是恒生电子金融科技QA专家，服务于银行、券商等金融客户。\n[/SYSTEM]\n请对以下问题给出结构化回答（定义+要点+总结）：\n{input}",
    "[SYSTEM]\n恒生电子金融知识助手，请提供专业、准确、结构化的回答。\n回答格式：\n【定义】一句话概述\n【详细说明】展开解释\n【关键要点】3-5个核心point\n[/SYSTEM]\n{input}",
    "[SYSTEM]\n你是一位资深金融科技专家，请以清晰、准确、有深度的方式回答金融相关问题。\n要求：先定义核心概念，再分点展开，最后给出实践应用建议。\n[/SYSTEM]\n请回答：{input}",
    "[SYSTEM]\n恒生电子金融知识库智能问答系统。角色：金融科技领域专家。\n回答要求：1)准确定义 2)核心内容分3-5点 3)结合行业实践 4)200-500字\n[/SYSTEM]\n用户问题：{input}",
    "[SYSTEM]\n你是恒生电子金融科技领域的专业知识库问答专家。回答需基于金融行业标准规范，面向金融从业者。\n[/SYSTEM]\n问题：{input}\n请提供：1)简明定义 2)详细说明 3)关键要点列表",
    "[SYSTEM]\n恒生电子金融科技QA专家 | 服务对象：银行、券商、基金从业者\n要求：准确、专业、结构化\n[/SYSTEM]\n请按以下格式回答：\n【概念定义】一句话说明\n【详细阐述】分3-5个要点\n【行业实践】结合实际应用\n\n问题：{input}",
    "[SYSTEM]\n你是一位恒生电子金融科技领域的专业知识库问答专家。你的回答必须基于金融行业的标准规范和最佳实践。\n[/SYSTEM]\n请根据以下要求回答用户问题：\n1. 准确理解问题意图\n2. 先给出简明定义或结论\n3. 对于操作类问题用序号列表\n4. 对于解释类问题先定义再分析\n5. 引用相关法规或标准\n6. 控制在200-500字\n\n问题：{input}",
]


async def seed_database():
    """初始化所有种子数据"""
    print("=== 大模型能力评测与Prompt调优系统 - Demo数据初始化 ===\n")

    async with async_session() as db:
        # 1. 创建用户
        print("[1/7] 创建测试用户...")
        user_ids = {}
        for u in USERS_DATA:
            existing = await db.execute(select(User).where(User.username == u["username"]))
            if existing.scalar_one_or_none():
                print(f"  用户 {u['username']} 已存在，跳过")
                result = await db.execute(select(User).where(User.username == u["username"]))
                user = result.scalar_one()
            else:
                user = User(
                    username=u["username"],
                    password_hash=get_password_hash(u["password"]),
                    email=u["email"],
                    display_name=u["display_name"],
                    role=u["role"],
                )
                db.add(user)
                await db.flush()
                print(f"  创建用户: {u['username']} (角色: {u['role']})")
            user_ids[u["username"]] = user.id
        await db.commit()

        # 2. 创建模型
        print("\n[2/7] 创建测试模型...")
        model_ids = {}
        for m in MODELS_DATA:
            existing = await db.execute(
                select(LLMModel).where(LLMModel.name == m["name"])
            )
            if existing.scalar_one_or_none():
                print(f"  模型 {m['name']} 已存在，跳过")
                result = await db.execute(select(LLMModel).where(LLMModel.name == m["name"]))
                model = result.scalar_one()
            else:
                model = LLMModel(**m)
                db.add(model)
                await db.flush()
                print(f"  创建模型: {m['name']} ({m['provider']})")
            model_ids[m["name"]] = model.id
        await db.commit()

        # 3. 创建项目
        print("\n[3/7] 创建演示项目...")
        existing_project = await db.execute(
            select(Project).where(Project.name == "金融知识库问答优化项目")
        )
        if existing_project.scalar_one_or_none():
            result = await db.execute(select(Project).where(Project.name == "金融知识库问答优化项目"))
            project = result.scalar_one()
            print(f"  项目已存在，跳过")
        else:
            project = Project(
                name="金融知识库问答优化项目",
                description="基于恒生电子金融知识库的智能问答系统，通过Prompt调优提升问答准确性和专业性。",
                project_type="chat",
                status="active",
                created_by=user_ids["developer"],
            )
            db.add(project)
            await db.flush()
            print(f"  创建项目: {project.name}")
        project_id = project.id
        await db.commit()

        # 4. 创建数据集
        print("\n[4/7] 创建评测数据集 (RepLiQA格式, 20条)...")
        existing_ds = await db.execute(
            select(Dataset).where(Dataset.name == QA_DATASET["name"])
        )
        if existing_ds.scalar_one_or_none():
            result = await db.execute(select(Dataset).where(Dataset.name == QA_DATASET["name"]))
            dataset = result.scalar_one()
            # 删除旧items
            await db.execute(
                "DELETE FROM dataset_items WHERE dataset_id = :did",
                {"did": dataset.id}
            )
            await db.commit()
            print(f"  数据集已存在，重新创建条目")
        else:
            dataset = Dataset(
                name=QA_DATASET["name"],
                description=QA_DATASET["description"],
                scene=QA_DATASET["scene"],
                status="published",
                version="v1",
                item_count=len(QA_DATASET["items"]),
                created_by=user_ids["evaluator"],
                reviewer_id=user_ids["admin"],
            )
            db.add(dataset)
            await db.flush()
            print(f"  创建数据集: {dataset.name}")

        item_ids = []
        for i, item_data in enumerate(QA_DATASET["items"]):
            item = DatasetItem(
                dataset_id=dataset.id,
                input_text=item_data["input_text"],
                expected_output=item_data["expected_output"],
                difficulty=item_data["difficulty"],
                scene_label="金融知识库",
                sort_order=i,
            )
            db.add(item)
            await db.flush()
            item_ids.append(item.id)

        dataset.item_count = len(item_ids)
        await db.commit()
        print(f"  已创建 {len(item_ids)} 条问答数据")

        # 5. 创建内置评测指标
        print("\n[5/7] 初始化评测指标...")
        builtin_metrics = [
            {"name": "精确匹配 (EM)", "code": "em", "metric_type": "builtin",
             "description": "Exact Match：模型输出与预期输出完全一致得1分，否则0分"},
            {"name": "BLEU", "code": "bleu", "metric_type": "builtin",
             "description": "Bilingual Evaluation Understudy：基于n-gram匹配的机器翻译评测指标"},
            {"name": "ROUGE-L", "code": "rouge_l", "metric_type": "builtin",
             "description": "基于最长公共子序列(LCS)的文本摘要评测指标"},
            {"name": "F1 Score", "code": "f1", "metric_type": "builtin",
             "description": "词级别的Precision和Recall调和平均"},
            {"name": "LLM-as-Judge", "code": "llm_judge", "metric_type": "llm_based",
             "description": "调用大模型对输出质量从准确性、完整性、表达质量三个维度进行0-10分综合评分",
             "config_json": json.dumps({"judge_prompt": "", "dimensions": ["准确性", "完整性", "表达质量"]})},
        ]

        metric_ids = {}
        for m in builtin_metrics:
            existing = await db.execute(select(Metric).where(Metric.code == m["code"]))
            if existing.scalar_one_or_none():
                result = await db.execute(select(Metric).where(Metric.code == m["code"]))
                metric = result.scalar_one()
            else:
                metric = Metric(
                    name=m["name"], code=m["code"],
                    description=m["description"],
                    metric_type=m.get("metric_type", "builtin"),
                    config_json=m.get("config_json", "{}"),
                    status="approved", created_by=user_ids["admin"],
                )
                db.add(metric)
                await db.flush()
            metric_ids[m["code"]] = metric.id
        await db.commit()
        print(f"  已初始化 {len(builtin_metrics)} 个评测指标")

        # 6. 创建 Prompt 和调优任务
        print("\n[6/7] 创建 Prompt 和模拟10轮调优历史...")
        existing_prompt = await db.execute(
            select(Prompt).where(Prompt.name == "金融知识库问答Prompt")
        )
        if existing_prompt.scalar_one_or_none():
            result = await db.execute(select(Prompt).where(Prompt.name == "金融知识库问答Prompt"))
            prompt = result.scalar_one()
            prompt.current_content = OPTIMIZED_PROMPT
            prompt.best_score = SCORE_HISTORY[-1]
            prompt.current_version = "v11"
        else:
            prompt = Prompt(
                name="金融知识库问答Prompt",
                description="用于金融知识库问答场景的优化Prompt",
                scene="qa",
                current_content=OPTIMIZED_PROMPT,
                current_version="v11",
                best_score=SCORE_HISTORY[-1],
                created_by=user_ids["developer"],
                project_id=project_id,
            )
            db.add(prompt)
            await db.flush()
        prompt_id = prompt.id
        await db.commit()

        # 创建优化任务
        existing_opt = await db.execute(
            select(OptimizationTask).where(OptimizationTask.name == "金融QA-Prompt优化任务")
        )
        if existing_opt.scalar_one_or_none():
            result = await db.execute(select(OptimizationTask).where(OptimizationTask.name == "金融QA-Prompt优化任务"))
            opt_task = result.scalar_one()
            # 清理旧轮次
            await db.execute(
                "DELETE FROM optimization_candidates WHERE optimization_round_id IN "
                "(SELECT id FROM optimization_rounds WHERE optimization_task_id = :tid)",
                {"tid": opt_task.id}
            )
            await db.execute(
                "DELETE FROM optimization_rounds WHERE optimization_task_id = :tid",
                {"tid": opt_task.id}
            )
            await db.commit()
        else:
            opt_task = OptimizationTask(
                name="金融QA-Prompt优化任务",
                project_id=project_id,
                prompt_id=prompt_id,
                model_id=model_ids["DeepSeek-V3 (演示)"],
                optimizer_model_id=model_ids["GPT-4o (演示)"],
                dataset_id=dataset.id,
                metric_ids=",".join(str(metric_ids[c]) for c in ["em", "bleu", "rouge_l"]),
                initial_prompt=INITIAL_PROMPT,
                best_prompt=OPTIMIZED_PROMPT,
                best_score=SCORE_HISTORY[-1],
                baseline_score=SCORE_HISTORY[0],
                max_rounds=10,
                candidates_per_round=3,
                convergence_threshold=0.01,
                current_round=10,
                status="completed",
                score_history_json=json.dumps(SCORE_HISTORY),
            )
            db.add(opt_task)
            await db.flush()
        opt_task_id = opt_task.id

        # 创建10轮调优记录
        for r in range(1, 11):
            round_record = OptimizationRound(
                optimization_task_id=opt_task_id,
                round_number=r,
                prompt_before=ROUND_PROMPTS[r - 1],
                best_prompt_after=ROUND_PROMPTS[min(r, len(ROUND_PROMPTS) - 1)],
                score_before=SCORE_HISTORY[r - 1],
                score_after=SCORE_HISTORY[r],
                candidates_json=json.dumps([
                    {"index": 0, "prompt": ROUND_PROMPTS[min(r, len(ROUND_PROMPTS) - 1)], "score": SCORE_HISTORY[r]},
                    {"index": 1, "prompt": ROUND_PROMPTS[min(max(r - 1, 0), len(ROUND_PROMPTS) - 1)], "score": SCORE_HISTORY[max(r - 1, 0)]},
                    {"index": 2, "prompt": ROUND_PROMPTS[min(max(r - 2, 0), len(ROUND_PROMPTS) - 1)], "score": SCORE_HISTORY[max(r - 2, 0)]},
                ]),
                error_samples_json=json.dumps([
                    {"input_text": "什么是证券交易结算制度？",
                     "expected_output": "证券交易结算制度是指...",
                     "model_output": "结算制度是关于交易的..." if r < 3 else "证券交易结算制度是指证券交易完成后..."}
                ]),
            )
            db.add(round_record)
        await db.commit()

        print(f"  创建优化任务: {opt_task.name}")
        print(f"  初始化Prompt版本: baseline={SCORE_HISTORY[0]:.2f} -> best={SCORE_HISTORY[-1]:.2f}")
        print(f"  提升幅度: +{SCORE_HISTORY[-1] - SCORE_HISTORY[0]:.2f} (+{(SCORE_HISTORY[-1]/max(SCORE_HISTORY[0], 0.01) - 1)*100:.1f}%)")

        # 创建 Prompt 版本历史
        for v_idx in range(len(SCORE_HISTORY)):
            existing_ver = await db.execute(
                select(PromptVersion).where(
                    (PromptVersion.prompt_id == prompt_id) &
                    (PromptVersion.version == f"v{v_idx + 1}")
                )
            )
            if not existing_ver.scalar_one_or_none():
                version = PromptVersion(
                    prompt_id=prompt_id,
                    version=f"v{v_idx + 1}",
                    content=ROUND_PROMPTS[min(v_idx, len(ROUND_PROMPTS) - 1)] if v_idx > 0 else INITIAL_PROMPT,
                    score=SCORE_HISTORY[v_idx],
                    source="optimization" if v_idx > 0 else "initial",
                    optimization_task_id=opt_task_id,
                )
                db.add(version)
        await db.commit()

        # 7. 创建演示评测任务
        print("\n[7/7] 创建演示评测任务...")
        existing_eval = await db.execute(
            select(EvalTask).where(EvalTask.name == "金融QA-初始Prompt评测")
        )
        if existing_eval.scalar_one_or_none():
            print(f"  评测任务已存在，跳过")
        else:
            eval_task = EvalTask(
                name="金融QA-初始Prompt评测",
                project_id=project_id,
                model_id=model_ids["DeepSeek-V3 (演示)"],
                dataset_id=dataset.id,
                metric_ids=",".join(str(metric_ids[c]) for c in ["em", "bleu", "rouge_l"]),
                prompt_content=INITIAL_PROMPT,
                prompt_id=prompt_id,
                status="completed",
                total_items=len(item_ids),
                completed_items=len(item_ids),
                overall_score=SCORE_HISTORY[0],
                result_json=json.dumps({"overall_score": SCORE_HISTORY[0], "total_items": len(item_ids)}),
                created_by=user_ids["developer"],
            )
            db.add(eval_task)
            await db.flush()

            # 为评测任务创建逐条结果
            for i, item_id in enumerate(item_ids):
                item_data = QA_DATASET["items"][i]
                mock_output = mock_llm.respond(INITIAL_PROMPT, item_data["input_text"])

                score_em = 1.0 if mock_output.strip() == item_data["expected_output"].strip() else 0.0
                score_bleu = random.uniform(0.1, 0.4)
                score_rouge = random.uniform(0.2, 0.5)

                eval_result = EvalResult(
                    eval_task_id=eval_task.id,
                    dataset_item_id=item_id,
                    model_output=mock_output,
                    expected_output=item_data["expected_output"],
                    scores_json=json.dumps({
                        "em": {"score": score_em, "detail": "精确匹配" if score_em > 0 else "不匹配"},
                        "bleu": {"score": round(score_bleu, 4), "detail": f"BLEU: {score_bleu*100:.1f}"},
                        "rouge_l": {"score": round(score_rouge, 4), "detail": f"ROUGE-L: {score_rouge:.4f}"},
                    }),
                    latency_ms=random.randint(200, 800),
                )
                db.add(eval_result)

            await db.commit()
            print(f"  创建评测任务: {eval_task.name}")
            print(f"  初始Prompt得分: {SCORE_HISTORY[0]:.2f}")

        # 审计日志
        audit = AuditLog(
            user_id=user_ids["admin"],
            username="admin",
            action="seed_demo_data",
            target_type="system",
            detail="Demo种子数据初始化完成",
        )
        db.add(audit)
        await db.commit()

    print("\n" + "=" * 60)
    print("Demo数据初始化完成!")
    print("=" * 60)
    print(f"\n登录信息:")
    print(f"  超级管理员: admin / admin123")
    print(f"  评测管理员: evaluator / eval123")
    print(f"  开发者: developer / dev123")
    print(f"\n演示数据:")
    print(f"  项目: {project.name}")
    print(f"  数据集: {dataset.name} ({len(item_ids)}条)")
    print(f"  模型: {len(model_ids)}个")
    print(f"  指标: {len(metric_ids)}个")
    print(f"  Prompt优化: {len(SCORE_HISTORY)-1}轮迭代, 分数 {SCORE_HISTORY[0]:.2f} → {SCORE_HISTORY[-1]:.2f}")
    print(f"\n启动后端: cd backend && uvicorn app.main:app --reload")
    print(f"启动前端: cd webui && npm run dev")
    print(f"API文档: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(seed_database())

"""
Demo 模式内存数据 — 数据库不可用时自动回退
"""
from datetime import datetime

NOW = datetime.utcnow()

# ====== 项目 ======
DEMO_PROJECTS = [
    {"id": 1, "name": "金融知识库问答优化项目", "description": "基于恒生电子金融知识库的智能问答系统Prompt调优", "project_type": "chat", "status": "active", "created_by": 3, "created_at": NOW},
    {"id": 2, "name": "代码生成评测项目", "description": "多模型代码生成能力对比评测", "project_type": "code", "status": "active", "created_by": 3, "created_at": NOW},
    {"id": 3, "name": "多模态理解评测", "description": "图片+文本多模态模型能力评估", "project_type": "multimodal", "status": "active", "created_by": 1, "created_at": NOW},
]

# ====== 模型 ======
DEMO_MODELS = [
    {"id": 1, "name": "DeepSeek-V3 (演示)", "provider": "DeepSeek", "model_type": "chat", "api_base": "https://api.deepseek.com/v1", "api_key": "sk-demo-xxx", "model_identifier": "deepseek-chat", "description": "DeepSeek 大语言模型", "is_active": True, "created_at": NOW, "updated_at": NOW},
    {"id": 2, "name": "GPT-4o (演示)", "provider": "OpenAI", "model_type": "chat", "api_base": "https://api.openai.com/v1", "api_key": "sk-demo-xxx", "model_identifier": "gpt-4o", "description": "OpenAI GPT-4o，用作优化器模型", "is_active": True, "created_at": NOW, "updated_at": NOW},
    {"id": 3, "name": "Qwen2.5 (演示)", "provider": "Alibaba", "model_type": "chat", "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "sk-demo-xxx", "model_identifier": "qwen-plus", "description": "通义千问", "is_active": True, "created_at": NOW, "updated_at": NOW},
]

# ====== 数据集 ======
def _make_items(ds_id: int, count: int):
    items = []
    questions = [
        ("什么是证券交易结算制度？", "证券交易结算制度是指证券交易完成后…涉及T+0、T+1等结算周期。"),
        ("如何计算基金的净值？", "基金净值(NAV) = (总资产 - 总负债) / 总份额。"),
        ("什么是KYC合规审查？", "KYC是金融机构对客户身份的识别和验证程序。"),
        ("请解释什么是量化交易", "量化交易是利用数学模型、统计分析和计算机程序制定和执行交易策略的方法。"),
        ("为什么要进行风险压力测试？", "评估金融机构在极端不利条件下的抗风险能力的重要工具。"),
        ("什么是融资融券业务？", "融资融券是指证券公司向客户出借资金供其买入证券或出借证券供其卖出的业务。"),
        ("列出期货交易的主要风险类型", "1.市场风险 2.流动性风险 3.信用风险 4.操作风险 5.法律风险 6.杠杆风险 7.基差风险"),
        ("如何构建投资组合的风险管理系统？", "1)风险识别 2)风险度量(VaR等) 3)风险预算 4)风险监控 5)压力测试 6)风险报告"),
        ("什么是ETF基金的申购赎回机制？", "ETF采用实物申购赎回机制，授权参与商用一篮子证券换取ETF份额。"),
        ("请解释什么是债券久期", "债券久期是衡量债券价格对利率变化敏感度的指标。"),
        ("为什么要进行信息披露？", "保护投资者权益、维护市场公平、提高市场效率、促进公司治理、满足监管要求。"),
        ("什么是注册制改革？", "以信息披露为核心，监管机构进行形式审查，将价值判断交还给市场。"),
        ("如何评估一家上市公司的财务健康状况？", "从盈利能力、偿债能力、运营效率、成长能力、现金流、杜邦分析等维度综合评估。"),
        ("什么是期权的时间价值？", "期权价值=内在价值+时间价值，时间价值反映到期前价格朝有利方向变动的可能性。"),
        ("列出跨境支付面临的主要挑战", "1.时效性 2.成本高 3.透明度低 4.合规复杂 5.汇率风险 6.技术兼容 7.数据安全"),
        ("请解释什么是智能投顾", "智能投顾是利用AI和算法模型为投资者提供自动化投资建议和资产配置的平台。"),
        ("什么是交易所的涨跌停板制度？", "为防价格过度波动设置的价格限制机制，A股常规±10%，科创/创业板±20%。"),
        ("如何理解资产证券化？", "将缺乏流动性但具有稳定现金流的资产打包转换为可交易证券的过程。"),
        ("什么是高频交易？", "利用超高速计算机和算法在极短时间内执行大量交易指令的策略。"),
        ("为什么要建立多层次资本市场？", "满足不同发展阶段企业的融资需求和不同风险偏好投资者的投资需求。"),
    ]
    for i, (q, a) in enumerate(questions[:count]):
        items.append({
            "id": ds_id * 100 + i + 1,
            "dataset_id": ds_id,
            "input_text": q,
            "expected_output": a,
            "scene_label": "金融知识库",
            "difficulty": ["easy", "medium", "hard"][i % 3],
            "sort_order": i,
            "created_at": NOW,
        })
    return items


DEMO_DATASETS = [
    {
        "id": 1, "name": "金融知识库问答评测集 v1 (RepLiQA格式)",
        "description": "基于恒生电子金融业务场景构建，20条问答对，覆盖证券交易、风险管理、合规审查等。",
        "scene": "qa", "status": "published", "version": "v1", "item_count": 20,
        "created_by": 2, "reviewer_id": 1, "review_comment": "", "created_at": NOW, "updated_at": NOW,
        "items": _make_items(1, 20),
    },
    {
        "id": 2, "name": "代码生成评测集",
        "description": "Python/Java代码生成评测数据，10条",
        "scene": "code", "status": "published", "version": "v1", "item_count": 10,
        "created_by": 2, "reviewer_id": 1, "review_comment": "", "created_at": NOW, "updated_at": NOW,
        "items": _make_items(2, 10),
    },
]

# ====== 指标 ======
DEMO_METRICS = [
    {"id": 1, "name": "精确匹配 (EM)", "code": "em", "description": "Exact Match", "metric_type": "builtin", "config_json": "{}", "custom_code": "", "status": "approved", "is_active": True, "created_by": 1, "created_at": NOW, "updated_at": NOW},
    {"id": 2, "name": "BLEU", "code": "bleu", "description": "基于n-gram匹配的评测指标", "metric_type": "builtin", "config_json": "{}", "custom_code": "", "status": "approved", "is_active": True, "created_by": 1, "created_at": NOW, "updated_at": NOW},
    {"id": 3, "name": "ROUGE-L", "code": "rouge_l", "description": "基于LCS的文本评测指标", "metric_type": "builtin", "config_json": "{}", "custom_code": "", "status": "approved", "is_active": True, "created_by": 1, "created_at": NOW, "updated_at": NOW},
    {"id": 4, "name": "F1 Score", "code": "f1", "description": "词级Precision和Recall调和平均", "metric_type": "builtin", "config_json": "{}", "custom_code": "", "status": "approved", "is_active": True, "created_by": 1, "created_at": NOW, "updated_at": NOW},
    {"id": 5, "name": "LLM-as-Judge", "code": "llm_judge", "description": "大模型评分0-10分", "metric_type": "llm_based", "config_json": '{"dimensions":["准确性","完整性","表达质量"]}', "custom_code": "", "status": "approved", "is_active": True, "created_by": 1, "created_at": NOW, "updated_at": NOW},
]

# ====== Prompt ======
DEMO_PROMPTS = [
    {"id": 1, "name": "金融知识库问答Prompt", "description": "经10轮优化的金融QA Prompt", "scene": "qa", "current_version": "v11", "current_content": "你是一位金融科技专家...", "best_score": 0.86, "project_id": 1, "created_by": 3, "created_at": NOW, "updated_at": NOW},
]

# ====== 评测任务 ======
DEMO_EVAL_TASKS = [
    {"id": 1, "name": "金融QA-初始Prompt评测", "project_id": 1, "model_id": 1, "dataset_id": 1, "metric_ids": "1,2,3", "prompt_content": "你是一个问答助手。请回答用户问题。", "prompt_id": 1, "status": "completed", "schedule_type": "immediate", "cron_expression": "", "total_items": 20, "completed_items": 20, "overall_score": 0.32, "result_json": '{"overall_score":0.32}', "error_message": "", "started_at": NOW, "finished_at": NOW, "created_by": 3, "created_at": NOW, "updated_at": NOW},
    {"id": 2, "name": "金融QA-优化后评测", "project_id": 1, "model_id": 1, "dataset_id": 1, "metric_ids": "1,2,3", "prompt_content": "你是一位金融科技专家...", "prompt_id": 1, "status": "completed", "schedule_type": "immediate", "cron_expression": "", "total_items": 20, "completed_items": 20, "overall_score": 0.86, "result_json": '{"overall_score":0.86}', "error_message": "", "started_at": NOW, "finished_at": NOW, "created_by": 3, "created_at": NOW, "updated_at": NOW},
]

# ====== 优化任务 ======
DEMO_OPT_TASKS = [
    {
        "id": 1, "name": "金融QA-Prompt优化任务", "project_id": 1, "prompt_id": 1,
        "model_id": 1, "optimizer_model_id": 2, "dataset_id": 1, "metric_ids": "1,2,3",
        "initial_prompt": "你是一个问答助手。请回答用户问题。",
        "best_prompt": "[SYSTEM]\n你是恒生电子金融科技专家...\n[/SYSTEM]\n{input}",
        "best_score": 0.86, "baseline_score": 0.32, "max_rounds": 10,
        "candidates_per_round": 3, "convergence_threshold": 0.01,
        "current_round": 10, "status": "completed",
        "score_history_json": "[0.32,0.45,0.52,0.61,0.68,0.73,0.78,0.82,0.85,0.86,0.86]",
        "celery_task_id": "", "error_message": "",
        "started_at": NOW, "finished_at": NOW, "created_by": 3, "created_at": NOW, "updated_at": NOW,
    },
]


def get_demo_list(data_list, page, page_size):
    total = len(data_list)
    start = (page - 1) * page_size
    end = start + page_size
    items = data_list[start:end]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return items, total, page, page_size, total_pages


def paginated(items, total, page, page_size, total_pages):
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}

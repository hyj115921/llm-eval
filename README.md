# 大模型能力评测与 Prompt 自动调优系统

企业级大模型能力评测管理与 Prompt 自动调优平台，面向金融科技企业内部 AI 应用落地。

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Ant Design 5 + ECharts |
| 后端 | FastAPI + SQLAlchemy 2.0 + Alembic |
| 任务队列 | Celery + Redis |
| 数据库 | MySQL 8.0 |
| 文件存储 | MinIO (兼容 S3) |
| 模型调用 | LiteLLM (兼容 OpenAI/DeepSeek/Qwen/Claude) |
| 部署 | Docker Compose |

## 快速启动（Demo 模式，无需数据库）

```bash
# 1. 安装后端依赖
cd backend
pip install -r requirements.txt

# 2. 启动后端（Demo 模式，无需 MySQL/Redis）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# 3. 安装前端依赖
cd ../webui
npm install

# 4. 启动前端
npm run dev
```

浏览器打开 http://localhost:5173，使用 demo 账号登录：

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 超级管理员 | admin | admin123 |
| 评测管理员 | evaluator | eval123 |
| 开发者 | developer | dev123 |

## 完整启动（Docker Compose）

```bash
# 1. 启动所有基础设施
docker-compose up -d

# 2. 运行数据库迁移
docker-compose exec backend alembic upgrade head

# 3. 初始化演示数据
docker-compose exec backend python -m demo.seed_demo

# 4. 访问
# 前端: http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
```

## 核心功能

### 模型选型榜单
多模型同数据集横向对比，输出综合排名、雷达图、推荐结论。

### Prompt 自动调优
基于 APE（Automatic Prompt Engineering）的迭代反馈优化：
- 在数据集上跑基线评测
- 收集错误样本，调用优化器 LLM 生成改进候选
- 逐轮收敛，输出最优 Prompt + 完整证据链
- 支持保守/均衡/激进三种优化策略

### 评测报告
- 综合得分 + 各指标汇总（EM / BLEU / ROUGE-L / F1 / LLM-Judge）
- 分数分布图 + 低分样本归因
- 推荐结论（A/B/C/D 等级 + 行动建议）

### 企业流程
- 数据集/评测标准的 草稿→审核→发布 完整流程
- 已发布数据集不可直接修改，编辑自动创建新草稿版本
- 审计日志：登录、创建、删除、审核、任务执行等 15 种操作留痕
- 角色权限：admin / evaluator / developer / viewer

### 数据安全
- API Key 加密存储
- 数据按角色隔离（开发者仅可见自己创建的数据）
- 所有关键操作可追溯

## 项目结构

```
llm-eval-platform/
├── backend/
│   ├── app/
│   │   ├── api/v1/       # FastAPI 路由 (10个模块)
│   │   ├── core/         # 配置、JWT、权限
│   │   ├── models/       # SQLAlchemy ORM (14个模型)
│   │   ├── schemas/      # Pydantic 请求/响应模型
│   │   ├── services/     # 核心业务逻辑
│   │   │   ├── llm_service.py      # 统一 LLM 调用
│   │   │   ├── evaluator.py        # 评测引擎
│   │   │   ├── optimizer.py        # Prompt 调优引擎
│   │   │   └── report_generator.py # 报告生成器
│   │   └── tasks/        # Celery 异步任务
│   ├── alembic/          # 数据库迁移
│   └── requirements.txt
├── webui/
│   ├── src/
│   │   ├── pages/        # 17个页面组件
│   │   ├── components/   # 复用组件
│   │   ├── services/     # API 调用层
│   │   ├── stores/       # Zustand 状态
│   │   └── types/        # TypeScript 类型
│   └── package.json
├── demo/seed_demo.py     # Demo 数据初始化脚本
├── docker-compose.yml
└── README.md
```

## 系统架构

```
浏览器 → React/Ant Design (5173)
              ↓ /api/*
         FastAPI (8001)
              ↓
    ┌─────────┼─────────┐
    ↓         ↓          ↓
  MySQL    Celery     MinIO
 (主数据)  (异步任务)  (文件存储)
              ↓
        LiteLLM
   (模型调用层 → GPT/DeepSeek/Qwen/Claude)
```

## Demo 演示数据

系统内置演示数据，无需配置即可体验：
- 3 个模型（DeepSeek-V3, GPT-4o, Qwen2.5）
- 3 个项目（金融QA、代码生成、多模态）
- 2 个数据集（金融知识库 20 条 + 代码生成 10 条）
- 5 个评测指标（EM, BLEU, ROUGE-L, F1, LLM-Judge）
- 2 个评测任务 + 1 个优化任务（10 轮迭代，得分 0.32→0.86）

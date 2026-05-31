-- ============================================================
-- 大模型能力评测与Prompt自动调优系统 - 数据库初始化脚本
-- Docker 首次启动时自动执行 (mounted at /docker-entrypoint-initdb.d/)
-- ============================================================

-- 创建数据库（如果通过环境变量 MYSQL_DATABASE 已创建则跳过）
CREATE DATABASE IF NOT EXISTS llm_eval
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

-- 创建用户并授权（如果通过 MYSQL_USER/MYSQL_PASSWORD 已创建则跳过）
-- GRANT ALL PRIVILEGES ON llm_eval.* TO 'llm_eval_user'@'%' IDENTIFIED BY 'llm_eval_pass';
-- FLUSH PRIVILEGES;

-- 注意：表结构由 Alembic 迁移管理，首次启动后运行:
--   docker-compose exec backend alembic upgrade head
-- 不要在此文件中定义表结构。

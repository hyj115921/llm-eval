"""initial migration

Revision ID: 001_initial
Revises: None
Create Date: 2026-05-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("email", sa.String(128), default=""),
        sa.Column("display_name", sa.String(64), default=""),
        sa.Column("role", sa.String(32), default="developer", index=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 2. projects
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("description", sa.Text, default=""),
        sa.Column("project_type", sa.String(32), default="chat"),
        sa.Column("status", sa.String(32), default="active"),
        sa.Column("created_by", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 3. llm_models
    # ------------------------------------------------------------------
    op.create_table(
        "llm_models",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_type", sa.String(32), default="chat"),
        sa.Column("api_base", sa.String(512), nullable=False),
        sa.Column("api_key", sa.String(512), nullable=False),
        sa.Column("model_identifier", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 4. datasets
    # ------------------------------------------------------------------
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("description", sa.Text, default=""),
        sa.Column("scene", sa.String(128), default="general"),
        sa.Column("status", sa.String(32), default="draft"),
        sa.Column("version", sa.String(32), default="v1"),
        sa.Column("item_count", sa.Integer, default=0),
        sa.Column("file_url", sa.String(512), default=""),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_comment", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 5. dataset_items
    # ------------------------------------------------------------------
    op.create_table(
        "dataset_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_id",
            sa.Integer,
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("expected_output", sa.Text, default=""),
        sa.Column("scene_label", sa.String(128), default=""),
        sa.Column("difficulty", sa.String(32), default="medium"),
        sa.Column("metadata_json", sa.Text, default="{}"),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 6. metrics
    # ------------------------------------------------------------------
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("metric_type", sa.String(32), default="builtin"),
        sa.Column("config_json", sa.Text, default="{}"),
        sa.Column("custom_code", sa.Text, default=""),
        sa.Column("status", sa.String(32), default="approved"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_by", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 7. prompts
    # ------------------------------------------------------------------
    op.create_table(
        "prompts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("description", sa.Text, default=""),
        sa.Column("scene", sa.String(128), default="general"),
        sa.Column("current_version", sa.String(32), default="v1"),
        sa.Column("current_content", sa.Text, default=""),
        sa.Column("best_score", sa.Float, default=0.0),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 8. optimization_tasks
    # ------------------------------------------------------------------
    op.create_table(
        "optimization_tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=True
        ),
        sa.Column(
            "prompt_id", sa.Integer, sa.ForeignKey("prompts.id"), nullable=True
        ),
        sa.Column(
            "model_id",
            sa.Integer,
            sa.ForeignKey("llm_models.id"),
            nullable=False,
        ),
        sa.Column(
            "optimizer_model_id",
            sa.Integer,
            sa.ForeignKey("llm_models.id"),
            nullable=False,
        ),
        sa.Column(
            "dataset_id",
            sa.Integer,
            sa.ForeignKey("datasets.id"),
            nullable=False,
        ),
        sa.Column("metric_ids", sa.String(512), default=""),
        sa.Column("initial_prompt", sa.Text, default=""),
        sa.Column("best_prompt", sa.Text, default=""),
        sa.Column("best_score", sa.Float, default=0.0),
        sa.Column("baseline_score", sa.Float, default=0.0),
        sa.Column("max_rounds", sa.Integer, default=10),
        sa.Column("candidates_per_round", sa.Integer, default=3),
        sa.Column("convergence_threshold", sa.Float, default=0.01),
        sa.Column("current_round", sa.Integer, default=0),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("score_history_json", sa.Text, default="[]"),
        sa.Column("celery_task_id", sa.String(256), default=""),
        sa.Column("error_message", sa.Text, default=""),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 9. prompt_versions
    # ------------------------------------------------------------------
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "prompt_id",
            sa.Integer,
            sa.ForeignKey("prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("score", sa.Float, default=0.0),
        sa.Column("source", sa.String(32), default="manual"),
        sa.Column(
            "optimization_task_id",
            sa.Integer,
            sa.ForeignKey("optimization_tasks.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 10. eval_tasks
    # ------------------------------------------------------------------
    op.create_table(
        "eval_tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=True
        ),
        sa.Column(
            "model_id",
            sa.Integer,
            sa.ForeignKey("llm_models.id"),
            nullable=False,
        ),
        sa.Column(
            "dataset_id",
            sa.Integer,
            sa.ForeignKey("datasets.id"),
            nullable=False,
        ),
        sa.Column("metric_ids", sa.String(512), default=""),
        sa.Column("prompt_content", sa.Text, default=""),
        sa.Column(
            "prompt_id", sa.Integer, sa.ForeignKey("prompts.id"), nullable=True
        ),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("schedule_type", sa.String(32), default="immediate"),
        sa.Column("cron_expression", sa.String(128), default=""),
        sa.Column("total_items", sa.Integer, default=0),
        sa.Column("completed_items", sa.Integer, default=0),
        sa.Column("overall_score", sa.Float, default=0.0),
        sa.Column("result_json", sa.Text, default="{}"),
        sa.Column("error_message", sa.Text, default=""),
        sa.Column("celery_task_id", sa.String(256), default=""),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 11. eval_results
    # ------------------------------------------------------------------
    op.create_table(
        "eval_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "eval_task_id",
            sa.Integer,
            sa.ForeignKey("eval_tasks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "dataset_item_id",
            sa.Integer,
            sa.ForeignKey("dataset_items.id"),
            nullable=False,
        ),
        sa.Column("model_output", sa.Text, default=""),
        sa.Column("expected_output", sa.Text, default=""),
        sa.Column("scores_json", sa.Text, default="{}"),
        sa.Column("latency_ms", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 12. optimization_rounds
    # ------------------------------------------------------------------
    op.create_table(
        "optimization_rounds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "optimization_task_id",
            sa.Integer,
            sa.ForeignKey("optimization_tasks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("prompt_before", sa.Text, default=""),
        sa.Column("best_prompt_after", sa.Text, default=""),
        sa.Column("score_before", sa.Float, default=0.0),
        sa.Column("score_after", sa.Float, default=0.0),
        sa.Column("candidates_json", sa.Text, default="[]"),
        sa.Column("error_samples_json", sa.Text, default="[]"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 13. optimization_candidates
    # ------------------------------------------------------------------
    op.create_table(
        "optimization_candidates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "optimization_round_id",
            sa.Integer,
            sa.ForeignKey("optimization_rounds.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("candidate_index", sa.Integer, nullable=False),
        sa.Column("prompt_content", sa.Text, default=""),
        sa.Column("score", sa.Float, default=0.0),
        sa.Column("scores_detail", sa.Text, default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 14. audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True, index=True),
        sa.Column("username", sa.String(64), default=""),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), default=""),
        sa.Column("target_id", sa.Integer, nullable=True),
        sa.Column("detail", sa.Text, default=""),
        sa.Column("ip_address", sa.String(64), default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("optimization_candidates")
    op.drop_table("optimization_rounds")
    op.drop_table("eval_results")
    op.drop_table("eval_tasks")
    op.drop_table("prompt_versions")
    op.drop_table("optimization_tasks")
    op.drop_table("prompts")
    op.drop_table("metrics")
    op.drop_table("dataset_items")
    op.drop_table("datasets")
    op.drop_table("llm_models")
    op.drop_table("projects")
    op.drop_table("users")

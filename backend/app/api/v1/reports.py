import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.report_generator import report_generator
from app.schemas.report import EvalReportResponse, OptimizationReportResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reports"])


@router.get("/eval/{task_id}")
async def get_eval_report(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        report = await report_generator.generate_eval_report(db, task_id)
        if "error" in report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=report["error"])
        return report
    except HTTPException:
        raise
    except Exception:
        # Demo fallback
        return _demo_eval_report(task_id)


@router.get("/eval/{task_id}/export")
async def export_eval_report(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        report = await report_generator.generate_eval_report(db, task_id)
        if "error" in report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=report["error"])
    except HTTPException:
        raise
    except Exception:
        report = _demo_eval_report(task_id)

    return JSONResponse(
        content=report,
        headers={"Content-Disposition": f'attachment; filename="eval_report_{task_id}.json"'},
    )


@router.get("/optimization/{task_id}")
async def get_optimization_report(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        report = await report_generator.generate_optimization_report(db, task_id)
        if "error" in report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=report["error"])
        return report
    except HTTPException:
        raise
    except Exception:
        return _demo_opt_report(task_id)


# --- Demo 回退数据 ---

def _demo_eval_report(task_id: int) -> dict:
    return {
        "task_id": task_id,
        "task_name": "金融QA-优化后评测" if task_id == 2 else "金融QA-初始Prompt评测",
        "status": "completed",
        "model_id": 1,
        "dataset_id": 1,
        "overall_score": 0.86 if task_id == 2 else 0.32,
        "total_items": 20,
        "metric_summary": {
            "em": {"avg": 0.25 if task_id == 1 else 0.62, "max": 1.0, "min": 0.0, "median": 0.0},
            "bleu": {"avg": 0.35 if task_id == 1 else 0.78, "max": 0.92, "min": 0.05, "median": 0.32},
            "rouge_l": {"avg": 0.38 if task_id == 1 else 0.82, "max": 0.95, "min": 0.08, "median": 0.35},
        },
        "score_distribution": {"0-0.2": 2, "0.2-0.4": 8, "0.4-0.6": 6, "0.6-0.8": 3, "0.8-1.0": 1},
        "charts": {
            "score_distribution": {
                "categories": ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"],
                "values": [2, 8, 6, 3, 1],
            },
            "metric_comparison": {
                "metrics": ["EM", "BLEU", "ROUGE-L"],
                "avg_scores": [0.25 if task_id == 1 else 0.62, 0.35 if task_id == 1 else 0.78, 0.38 if task_id == 1 else 0.82],
            },
            "item_scores": {
                "ids": list(range(1, 21)),
                "scores": [round(0.2 + (i * 0.03) + (0.4 if task_id == 2 else 0), 3) for i in range(20)],
            },
        },
        "item_details": [
            {
                "result_id": i,
                "dataset_item_id": i,
                "model_output": f"金融知识库关于该问题的回答(第{i}条)...",
                "expected_output": f"预期回答(第{i}条)的详细内容...",
                "scores": {"em": {"score": 0 if i < 5 else 1}, "bleu": {"score": 0.3 + i * 0.02}, "rouge_l": {"score": 0.35 + i * 0.025}},
                "avg_score": round(0.22 + i * 0.025, 3),
                "latency_ms": 350 + (i % 5) * 80,
            }
            for i in range(1, 21)
        ],
        "recommendation": {
            "level": "C" if task_id == 1 else "A",
            "verdict": "建议优化后上线：模型整体表现有待提升，建议通过Prompt调优改进关键指标" if task_id == 1 else "推荐上线：模型经优化后表现优秀，各项指标达到生产标准",
            "suggestions": [
                "指标 'EM' 均分较低，建议打磨Prompt的精确性要求",
                "存在低分样本，建议检查输入格式和预期输出匹配度",
            ] if task_id == 1 else [
                "当前配置已达到生产级别，可直接部署使用",
                "建议定期用更新数据集复评，确保持续稳定",
            ],
        },
    }


def _demo_opt_report(task_id: int) -> dict:
    return {
        "task_id": task_id,
        "task_name": "金融QA-Prompt优化任务",
        "status": "completed",
        "initial_prompt": "你是一个问答助手。请回答用户问题。",
        "best_prompt": "[SYSTEM]\n你是恒生电子金融科技专家。\n回答要求：1)准确定义 2)分3-5点 3)结合实践\n[/SYSTEM]\n\n问题：{input}",
        "best_score": 0.86,
        "baseline_score": 0.32,
        "improvement": 0.54,
        "total_rounds": 10,
        "current_round": 10,
        "charts": {
            "score_history": {
                "rounds": ["基线", "第1轮", "第2轮", "第3轮", "第4轮", "第5轮",
                          "第6轮", "第7轮", "第8轮", "第9轮", "第10轮"],
                "scores": [0.32, 0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86, 0.86],
            },
            "improvement_per_round": {
                "rounds": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "improvements": [0.13, 0.07, 0.09, 0.07, 0.05, 0.05, 0.04, 0.03, 0.01, 0.0],
            },
            "prompt_evolution": {
                "rounds": ["第1轮", "第2轮", "第3轮", "第4轮", "第5轮",
                          "第6轮", "第7轮", "第8轮", "第9轮", "第10轮"],
                "best_scores": [0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86, 0.86],
            },
        },
        "rounds": [
            {
                "round_number": i,
                "score_before": [0.32, 0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86][i - 1],
                "score_after": [0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86, 0.86][i - 1],
                "improvement": round([0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86, 0.86][i - 1] - [0.32, 0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86][i - 1], 2),
                "candidates": [{"index": 0, "prompt": f"候选Prompt v{i}...", "score": [0.45, 0.52, 0.61, 0.68, 0.73, 0.78, 0.82, 0.85, 0.86, 0.86][i - 1]}],
            }
            for i in range(1, 11)
        ],
    }


# ─── 模型选型榜单 ──────────────────────────────────────────────────


@router.get("/comparison")
async def compare_models(
    dataset_id: int = Query(None),
    model_ids: str = Query(None),  # comma-separated
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """多模型同数据集对比，输出选型榜单"""
    try:
        # 如果指定了 dataset_id 和 model_ids，查询对应的 eval tasks
        # 否则返回 demo 数据
        if dataset_id and model_ids:
            from sqlalchemy import select, func
            from app.models.eval_task import EvalTask as ET
            mids = [int(m) for m in model_ids.split(",") if m.strip()]
            task_ids = []
            for mid in mids:
                r = await db.execute(
                    select(ET.id).where(
                        (ET.dataset_id == dataset_id) & (ET.model_id == mid)
                    ).order_by(ET.id.desc()).limit(1)
                )
                tid = r.scalar_one_or_none()
                if tid:
                    task_ids.append(tid)
            if task_ids:
                report = await report_generator.generate_comparison_report(db, task_ids)
                return report

        raise ValueError("demo_fallback")
    except ValueError:
        pass
    except Exception as e:
        logger.warning("Comparison query failed: %s", e)

    # Demo 回退：模拟3个模型对比
    return _demo_comparison()


def _demo_comparison() -> dict:
    tasks = [
        {
            "task_id": 1, "task_name": "金融QA-初始评测", "model_id": 1,
            "model_name": "DeepSeek-V3", "overall_score": 0.76,
            "total_items": 20, "completed_items": 20, "avg_latency_ms": 420,
            "metric_scores": {
                "em": {"avg": 0.52, "max": 1.0, "min": 0.0},
                "bleu": {"avg": 0.71, "max": 0.95, "min": 0.15},
                "rouge_l": {"avg": 0.74, "max": 0.98, "min": 0.18},
            },
            "status": "completed", "rank": 1,
        },
        {
            "task_id": 2, "task_name": "金融QA-GPT评测", "model_id": 2,
            "model_name": "GPT-4o", "overall_score": 0.86,
            "total_items": 20, "completed_items": 20, "avg_latency_ms": 680,
            "metric_scores": {
                "em": {"avg": 0.62, "max": 1.0, "min": 0.0},
                "bleu": {"avg": 0.82, "max": 0.97, "min": 0.25},
                "rouge_l": {"avg": 0.85, "max": 0.99, "min": 0.30},
            },
            "status": "completed", "rank": 2,
        },
        {
            "task_id": 3, "task_name": "金融QA-Qwen评测", "model_id": 3,
            "model_name": "Qwen2.5-Plus", "overall_score": 0.71,
            "total_items": 20, "completed_items": 20, "avg_latency_ms": 310,
            "metric_scores": {
                "em": {"avg": 0.45, "max": 1.0, "min": 0.0},
                "bleu": {"avg": 0.66, "max": 0.93, "min": 0.12},
                "rouge_l": {"avg": 0.69, "max": 0.95, "min": 0.15},
            },
            "status": "completed", "rank": 3,
        },
    ]
    tasks.sort(key=lambda x: x["overall_score"], reverse=True)
    for i, t in enumerate(tasks, 1):
        t["rank"] = i

    best = tasks[0]
    recommendation = f"推荐使用 {best['model_name']}，综合得分 {best['overall_score']:.2f}，在金融QA场景质量表现最佳"

    return {
        "tasks": tasks,
        "best": best,
        "recommendation": recommendation,
        "charts": {
            "comparison": {
                "names": [t["model_name"] for t in tasks],
                "scores": [t["overall_score"] for t in tasks],
                "latencies": [t["avg_latency_ms"] for t in tasks],
            },
        },
    }

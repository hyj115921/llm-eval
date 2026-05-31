"""
评测报告生成器：汇总评测结果、生成可视化数据。
"""
import json
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_task import EvalTask, EvalResult
from app.models.optimization import OptimizationTask, OptimizationRound
from app.models.dataset import DatasetItem


class ReportGenerator:
    """报告生成器"""

    async def generate_eval_report(self, db: AsyncSession, task_id: int) -> dict:
        """生成评测任务报告"""
        # 获取任务
        result = await db.execute(select(EvalTask).where(EvalTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return {"error": "任务不存在"}

        # 获取所有评测结果
        result = await db.execute(
            select(EvalResult).where(EvalResult.eval_task_id == task_id)
        )
        eval_results = result.scalars().all()

        # 汇总统计
        total = len(eval_results)
        if total == 0:
            return {
                "task_id": task_id,
                "task_name": task.name,
                "status": task.status,
                "total_items": 0,
                "message": "暂无评测结果",
            }

        # 解析各指标得分
        metric_scores = {}  # {metric_code: [score1, score2, ...]}
        score_distribution = []  # 每条结果的综合得分
        item_details = []

        for er in eval_results:
            scores = json.loads(er.scores_json) if er.scores_json else {}
            total_item_score = 0
            for code, s in scores.items():
                score_val = s.get("score", 0) if isinstance(s, dict) else s
                if code not in metric_scores:
                    metric_scores[code] = []
                metric_scores[code].append(score_val)
                total_item_score += score_val

            avg = total_item_score / len(scores) if scores else 0
            score_distribution.append(avg)

            item_details.append({
                "result_id": er.id,
                "dataset_item_id": er.dataset_item_id,
                "model_output": er.model_output[:500],
                "expected_output": er.expected_output[:500],
                "scores": scores,
                "avg_score": round(avg, 4),
                "latency_ms": er.latency_ms,
            })

        # 按得分排序
        item_details.sort(key=lambda x: x["avg_score"])

        # 各指标汇总统计
        metric_summary = {}
        for code, scores in metric_scores.items():
            metric_summary[code] = {
                "avg": round(sum(scores) / len(scores), 4),
                "max": round(max(scores), 4),
                "min": round(min(scores), 4),
                "median": round(sorted(scores)[len(scores) // 2], 4),
            }

        # 分数分布区间
        buckets = {"0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
        for s in score_distribution:
            if s < 0.2: buckets["0-0.2"] += 1
            elif s < 0.4: buckets["0.2-0.4"] += 1
            elif s < 0.6: buckets["0.4-0.6"] += 1
            elif s < 0.8: buckets["0.6-0.8"] += 1
            else: buckets["0.8-1.0"] += 1

        return {
            "task_id": task_id,
            "task_name": task.name,
            "status": task.status,
            "model_id": task.model_id,
            "dataset_id": task.dataset_id,
            "overall_score": task.overall_score,
            "total_items": total,
            "metric_summary": metric_summary,
            "score_distribution": buckets,
            # ECharts 可视化用数据
            "charts": {
                "score_distribution": {
                    "categories": list(buckets.keys()),
                    "values": list(buckets.values()),
                },
                "metric_comparison": {
                    "metrics": list(metric_summary.keys()),
                    "avg_scores": [metric_summary[k]["avg"] for k in metric_summary],
                },
                "item_scores": {
                    "ids": [d["result_id"] for d in item_details],
                    "scores": [d["avg_score"] for d in item_details],
                },
            },
            "item_details": item_details,
            "recommendation": _generate_recommendation(task.overall_score, metric_summary, total),
        }

    async def generate_optimization_report(self, db: AsyncSession, task_id: int) -> dict:
        """生成 Prompt 优化任务报告"""
        result = await db.execute(
            select(OptimizationTask).where(OptimizationTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return {"error": "优化任务不存在"}

        # 获取优化轮次
        result = await db.execute(
            select(OptimizationRound)
            .where(OptimizationRound.optimization_task_id == task_id)
            .order_by(OptimizationRound.round_number)
        )
        rounds = result.scalars().all()

        score_history = json.loads(task.score_history_json) if task.score_history_json else []

        rounds_detail = []
        for r in rounds:
            rounds_detail.append({
                "round_number": r.round_number,
                "score_before": r.score_before,
                "score_after": r.score_after,
                "improvement": round(r.score_after - r.score_before, 4),
                "candidates": json.loads(r.candidates_json) if r.candidates_json else [],
            })

        return {
            "task_id": task_id,
            "task_name": task.name,
            "status": task.status,
            "baseline_score": task.baseline_score,
            "best_score": task.best_score,
            "improvement": round(task.best_score - task.baseline_score, 4),
            "total_rounds": len(rounds),
            "current_round": task.current_round,
            "best_prompt": task.best_prompt,
            "initial_prompt": task.initial_prompt,
            "rounds": rounds_detail,
            # ECharts 数据
            "charts": {
                "score_history": {
                    "rounds": [f"基线"] + [f"第{r.round_number}轮" for r in rounds],
                    "scores": score_history,
                },
                "improvement_per_round": {
                    "rounds": [r.round_number for r in rounds],
                    "improvements": [round(r.score_after - r.score_before, 4) for r in rounds],
                },
                "prompt_evolution": {
                    "rounds": [f"第{r.round_number}轮" for r in rounds],
                    "best_scores": [r.score_after for r in rounds],
                },
            },
        }

    async def generate_comparison_report(
        self, db: AsyncSession, task_ids: List[int]
    ) -> dict:
        """多模型/多任务对比报告 — 增强版：含模型名、延迟、综合排名"""
        from app.models.llm_model import LLMModel

        tasks_data = []
        for tid in task_ids:
            result = await db.execute(select(EvalTask).where(EvalTask.id == tid))
            task = result.scalar_one_or_none()
            if not task:
                continue

            # 查询模型名称
            model_name = ""
            if task.model_id:
                m_result = await db.execute(select(LLMModel).where(LLMModel.id == task.model_id))
                model = m_result.scalar_one_or_none()
                model_name = model.name if model else f"模型#{task.model_id}"

            # 查询平均延迟
            avg_latency = 0
            try:
                lat_result = await db.execute(
                    select(func.avg(EvalResult.latency_ms)).where(
                        EvalResult.eval_task_id == tid
                    )
                )
                avg_latency = int(lat_result.scalar() or 0)
            except Exception:
                pass

            # 解析指标得分
            metric_scores = {}
            result_json = json.loads(task.result_json) if task.result_json else {}
            try:
                # 从 eval_results 聚合各指标均分
                er_result = await db.execute(
                    select(EvalResult).where(EvalResult.eval_task_id == tid)
                )
                all_scores = {}
                count = 0
                for er in er_result.scalars().all():
                    scores = json.loads(er.scores_json) if er.scores_json else {}
                    for code, s in scores.items():
                        sv = s.get("score", 0) if isinstance(s, dict) else s
                        all_scores.setdefault(code, []).append(sv)
                    count += 1
                metric_scores = {
                    code: {
                        "avg": round(sum(vals) / len(vals), 3),
                        "max": round(max(vals), 3),
                        "min": round(min(vals), 3),
                    }
                    for code, vals in all_scores.items()
                }
            except Exception:
                pass

            tasks_data.append({
                "task_id": tid,
                "task_name": task.name,
                "model_id": task.model_id,
                "model_name": model_name,
                "overall_score": round(task.overall_score, 4),
                "total_items": task.total_items,
                "completed_items": task.completed_items,
                "avg_latency_ms": avg_latency,
                "metric_scores": metric_scores,
                "status": task.status,
            })

        # 综合排名（按 overall_score 降序）
        tasks_data.sort(key=lambda x: x["overall_score"], reverse=True)
        for rank, t in enumerate(tasks_data, 1):
            t["rank"] = rank

        best = tasks_data[0] if tasks_data else None

        # 生成推荐结论
        recommendation = ""
        if best:
            if best["overall_score"] >= 0.8:
                recommendation = f"推荐使用 {best['model_name']}，综合得分 {best['overall_score']:.2f}，质量与延迟表现均衡"
            elif best["overall_score"] >= 0.6:
                recommendation = f"{best['model_name']} 排名第一但仍有优化空间，建议进行Prompt调优后再评"
            else:
                recommendation = "当前所有模型得分偏低，建议扩大模型选型范围或优化数据集难度"

        return {
            "tasks": tasks_data,
            "best": best,
            "recommendation": recommendation,
            "charts": {
                "comparison": {
                    "names": [t["model_name"] for t in tasks_data],
                    "scores": [t["overall_score"] for t in tasks_data],
                    "latencies": [t["avg_latency_ms"] for t in tasks_data],
                },
            },
        }


def _generate_recommendation(overall_score: float, metric_summary: dict, total_items: int) -> dict:
    """根据评测结果生成推荐结论"""
    if total_items == 0:
        return {"level": "无法评估", "verdict": "暂无数据", "suggestions": []}

    if overall_score >= 0.8:
        level, verdict = "A", "推荐上线：模型在当前任务上表现优秀，各项指标均达到生产级别标准"
    elif overall_score >= 0.6:
        level, verdict = "B", "建议优化后上线：模型整体表现良好，部分指标有提升空间，建议通过Prompt调优改进"
    elif overall_score >= 0.4:
        level, verdict = "C", "需要显著改进：模型在当前任务上表现一般，建议更换模型或深度优化Prompt"
    else:
        level, verdict = "D", "不建议使用：模型不适合当前任务，建议更换其他模型重新评测"

    suggestions = []
    for code, stats in metric_summary.items():
        if stats["avg"] < 0.5:
            suggestions.append(f"指标 '{code}' 均分仅 {stats['avg']:.2f}，建议优化Prompt中的{code}相关要求")
        if stats["min"] == 0.0 and stats["max"] > 0.5:
            suggestions.append(f"指标 '{code}' 存在0分样本，建议检查低分样本的输入格式和预期输出")

    if overall_score >= 0.8 and not suggestions:
        suggestions.append("当前配置已达到生产级别，可直接部署使用")
        suggestions.append("建议定期（如每季度）用更新后的数据集复评，确保模型持续表现稳定")

    return {"level": level, "verdict": verdict, "suggestions": suggestions}


report_generator = ReportGenerator()

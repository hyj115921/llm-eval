"""
Prompt 自动调优引擎：基于迭代反馈优化的 APE（Automatic Prompt Engineering）方法。

核心流程：
1. 用初始 Prompt 跑基线评测 → 得到基线分数
2. 收集错误样本，调用优化器 LLM 生成 N 个改进的 Prompt 候选
3. 对每个候选跑评测，选出最高分候选
4. 以最优候选作为新 Prompt，重复步骤 2-3
5. 达到最大迭代轮次或分数收敛时停止
6. 输出最优 Prompt、每轮分数曲线、优化历史
"""
import json
import asyncio
from typing import List, Optional
from dataclasses import dataclass, field

from app.services.llm_service import llm_service
from app.services.evaluator import Evaluator


OPTIMIZER_SYSTEM_PROMPT = """你是一位世界级的 Prompt 工程师，专门为大型语言模型优化提示词。

你的任务是：根据当前 Prompt 的评测结果（包括错误样本和得分），分析不足之处，生成改进后的 Prompt 候选版本。

优化原则：
1. 明确角色设定：让模型清楚自己的身份和任务
2. 结构化输出要求：明确指定输出格式
3. 提供示例（few-shot）：给出好的示例帮助模型理解
4. 约束条件：设置边界，避免不相关输出
5. 思维链引导：对于复杂任务，引导分步推理
6. 简洁清晰：避免冗余信息，指令精确

请分析以下信息并生成改进后的 Prompt：
- 当前 Prompt 的问题在哪里
- 错误样本暴露了什么模式
- 如何针对性地改进

输出格式（严格 JSON 数组，包含 N 个候选 Prompt）：
[
  {
    "analysis": "对当前Prompt问题的简要分析，50字以内",
    "improved_prompt": "改进后的完整 Prompt 文本"
  }
]"""


@dataclass
class OptimizationConfig:
    model_config: dict  # 评测模型配置 {api_base, api_key, model_identifier}
    optimizer_model_config: dict  # 优化器模型配置
    metric_configs: List[dict]  # 评测指标配置列表
    max_rounds: int = 10
    candidates_per_round: int = 3
    convergence_threshold: float = 0.01


class PromptOptimizer:
    """Prompt 自动调优引擎"""

    def __init__(self):
        self.evaluator = Evaluator()
        self._cancel_flags: dict = {}  # task_id -> bool

    def cancel(self, task_id: int):
        self._cancel_flags[task_id] = True

    def _is_cancelled(self, task_id: int) -> bool:
        return self._cancel_flags.get(task_id, False)

    async def optimize(
        self,
        task_id: int,
        config: OptimizationConfig,
        dataset_items: List[dict],  # [{"input_text": "...", "expected_output": "..."}]
        initial_prompt: str,
        progress_callback=None,  # async callable(round_num, best_score, best_prompt, status)
    ) -> dict:
        """
        执行完整 Prompt 调优流程。
        返回: {
            "best_prompt": str,
            "best_score": float,
            "baseline_score": float,
            "rounds": [...],  # 每轮详情
            "score_history": [float, ...],
        }
        """
        self._cancel_flags[task_id] = False
        rounds_detail = []
        score_history = []

        # Step 1: 基线评测
        baseline_score, baseline_results = await self._run_eval(
            config.model_config, dataset_items, initial_prompt, config.metric_configs
        )
        best_prompt = initial_prompt
        best_score = baseline_score
        score_history.append(baseline_score)

        if progress_callback:
            await progress_callback(0, baseline_score, initial_prompt, "baseline_done")

        # Step 2-N: 迭代优化
        for round_num in range(1, config.max_rounds + 1):
            if self._is_cancelled(task_id):
                return {
                    "best_prompt": best_prompt,
                    "best_score": best_score,
                    "baseline_score": baseline_score,
                    "rounds": rounds_detail,
                    "score_history": score_history,
                    "status": "cancelled",
                }

            # 收集错误样本
            error_samples = self._collect_error_samples(baseline_results, config.metric_configs)
            if not error_samples:
                # 没有错误样本，随机选几条作为参考
                error_samples = baseline_results[:5]

            # 调用优化器 LLM 生成候选 Prompt
            candidates = await self._generate_candidates(
                config.optimizer_model_config,
                current_prompt=best_prompt,
                current_score=best_score,
                error_samples=error_samples,
                num_candidates=config.candidates_per_round,
            )

            if not candidates:
                continue

            # 对每个候选跑评测
            candidate_scores = []
            for i, candidate_prompt in enumerate(candidates):
                if self._is_cancelled(task_id):
                    break
                score, results = await self._run_eval(
                    config.model_config, dataset_items, candidate_prompt, config.metric_configs
                )
                candidate_scores.append({
                    "index": i,
                    "prompt": candidate_prompt,
                    "score": score,
                    "results_snapshot": results[:3],  # 保存前3条结果作为样本
                })

            if not candidate_scores:
                continue

            # 选出本轮最优候选
            best_candidate = max(candidate_scores, key=lambda x: x["score"])
            round_best_score = best_candidate["score"]
            round_best_prompt = best_candidate["prompt"]

            round_detail = {
                "round_number": round_num,
                "prompt_before": best_prompt,
                "best_prompt_after": round_best_prompt,
                "score_before": best_score,
                "score_after": round_best_score,
                "candidates": [
                    {"index": c["index"], "prompt": c["prompt"][:500], "score": c["score"]}
                    for c in candidate_scores
                ],
                "error_samples": [
                    {"input": e["input_text"][:200], "expected": e["expected_output"][:200],
                     "actual": e["model_output"][:200]}
                    for e in error_samples[:3]
                ],
            }
            rounds_detail.append(round_detail)
            score_history.append(round_best_score)

            # 判断是否收敛
            improved = round_best_score - best_score
            if improved <= config.convergence_threshold and round_best_score >= best_score:
                # 收敛：本轮最优分数没有明显提升
                pass  # 仍然记录但可能提前结束

            if round_best_score > best_score:
                best_prompt = round_best_prompt
                best_score = round_best_score

            if progress_callback:
                await progress_callback(round_num, best_score, best_prompt, "round_done")

            # 如果连续3轮没有提升，提前结束
            if len(score_history) >= 4:
                last_three_improvements = [
                    score_history[-i] - score_history[-i-1]
                    for i in range(1, min(4, len(score_history)))
                ]
                if all(imp <= config.convergence_threshold for imp in last_three_improvements):
                    break

        self._cancel_flags.pop(task_id, None)
        return {
            "best_prompt": best_prompt,
            "best_score": best_score,
            "baseline_score": baseline_score,
            "rounds": rounds_detail,
            "score_history": score_history,
            "status": "completed",
        }

    async def _run_eval(
        self,
        model_config: dict,
        dataset_items: List[dict],
        prompt: str,
        metric_configs: List[dict],
    ) -> tuple[float, List[dict]]:
        """在数据集上运行评测，返回 (平均分, 详细结果列表)"""
        results = []
        total_score = 0.0
        metric_count = len(metric_configs) if metric_configs else 1

        # 使用信号量限制并发
        sem = asyncio.Semaphore(5)

        async def eval_one(item: dict):
            nonlocal total_score
            async with sem:
                from app.services.llm_service import build_messages
                messages = build_messages(prompt, item["input_text"])
                llm_result = await llm_service.chat(
                    api_base=model_config["api_base"],
                    api_key=model_config["api_key"],
                    model_identifier=model_config["model_identifier"],
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1024,
                )

                model_output = llm_result.get("content", "") if llm_result["success"] else ""

                scores = await self.evaluator.evaluate_single(
                    model_output=model_output,
                    expected_output=item.get("expected_output", ""),
                    metric_configs=metric_configs,
                    judge_model_config=model_config if any(
                        m.get("metric_type") == "llm_based" for m in metric_configs
                    ) else None,
                )

                item_score = sum(s.get("score", 0) for s in scores.values()) / max(metric_count, 1)
                return {
                    "input_text": item["input_text"],
                    "expected_output": item.get("expected_output", ""),
                    "model_output": model_output,
                    "scores": scores,
                    "avg_score": item_score,
                    "latency_ms": llm_result.get("latency_ms", 0),
                }

        tasks = [eval_one(item) for item in dataset_items]
        results = await asyncio.gather(*tasks)

        total_score = sum(r["avg_score"] for r in results)
        avg_score = total_score / len(results) if results else 0.0
        return avg_score, results

    async def _generate_candidates(
        self,
        optimizer_config: dict,
        current_prompt: str,
        current_score: float,
        error_samples: List[dict],
        num_candidates: int = 3,
    ) -> List[str]:
        """调用优化器 LLM 生成改进的 Prompt 候选"""
        # 构建错误样本摘要
        error_summary = self._format_error_samples(error_samples)

        user_message = f"""请分析以下 Prompt 的评测结果并生成 {num_candidates} 个改进后的 Prompt 候选。

【当前 Prompt】
{current_prompt}

【当前得分（0-1）】
{current_score:.4f}

【错误样本（展示模型输出与预期的差距）】
{error_summary}

【优化目标】
基于错误样本分析当前 Prompt 的不足之处，生成 {num_candidates} 个针对性的改进版本。

请严格按 JSON 数组格式输出，每个元素包含 "analysis" 和 "improved_prompt" 两个字段。"""

        result = await llm_service.chat(
            api_base=optimizer_config["api_base"],
            api_key=optimizer_config["api_key"],
            model_identifier=optimizer_config["model_identifier"],
            messages=[
                {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.8,
            max_tokens=4096,
        )

        if not result["success"]:
            return []

        return self._parse_candidates(result["content"], num_candidates)

    def _build_messages(self, prompt: str, input_text: str) -> List[dict]:
        """根据 Prompt 和输入构建 messages"""
        # 支持 system/user 分隔的 prompt 格式
        if "[SYSTEM]" in prompt and "[/SYSTEM]" in prompt:
            system_start = prompt.index("[SYSTEM]") + 8
            system_end = prompt.index("[/SYSTEM]")
            system_content = prompt[system_start:system_end].strip()
            user_content = prompt[system_end + 10:].strip()
            user_content = user_content.replace("{input}", input_text)
            return [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ]
        else:
            # 默认将整个 prompt 作为 system message
            full_prompt = prompt.replace("{input}", input_text)
            return [
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": input_text},
            ]

    def _collect_error_samples(
        self, results: List[dict], metric_configs: List[dict]
    ) -> List[dict]:
        """收集评测中的错误样本（低分样本优先）"""
        scored = []
        for r in results:
            avg = sum(s.get("score", 0) for s in r.get("scores", {}).values())
            metric_cnt = max(len(metric_configs), 1)
            r["_avg"] = avg / metric_cnt
            scored.append(r)

        scored.sort(key=lambda x: x["_avg"])
        # 返回分数最低的5个
        return scored[:5]

    def _format_error_samples(self, error_samples: List[dict]) -> str:
        """格式化错误样本为文本"""
        lines = []
        for i, sample in enumerate(error_samples[:5], 1):
            lines.append(f"--- 错误样本 {i} ---")
            lines.append(f"输入: {sample.get('input_text', '')[:300]}")
            lines.append(f"预期输出: {sample.get('expected_output', '')[:300]}")
            lines.append(f"模型输出: {sample.get('model_output', '')[:300]}")
            scores = sample.get("scores", {})
            score_str = ", ".join(f"{k}: {v.get('score', 0):.3f}" for k, v in scores.items())
            lines.append(f"得分: {score_str}")
            lines.append("")
        return "\n".join(lines)

    def _parse_candidates(self, llm_output: str, expected_count: int) -> List[str]:
        """从 LLM 输出中解析候选 Prompt 列表"""
        candidates = []
        text = llm_output.strip()

        # 尝试提取 JSON 数组
        import re
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                for item in data:
                    if isinstance(item, dict) and "improved_prompt" in item:
                        candidates.append(item["improved_prompt"])
            except json.JSONDecodeError:
                pass

        # fallback: 尝试按分隔符分割
        if not candidates:
            # 按 "improved_prompt" 字段匹配
            prompts = re.findall(r'"improved_prompt"\s*:\s*"([^"]*)"', text)
            candidates = prompts

        if not candidates:
            # 最后的 fallback：尝试按分隔线分割
            parts = re.split(r'---|\n##|\d+\.\s*', text)
            for part in parts:
                part = part.strip()
                if len(part) > 20 and "prompt" not in part.lower():
                    candidates.append(part)

        # 去重并限制数量
        seen = set()
        unique = []
        for c in candidates:
            normalized = c.strip()[:200]  # 用前200字符做去重key
            if normalized not in seen:
                seen.add(normalized)
                unique.append(c.strip())
                if len(unique) >= expected_count:
                    break

        return unique


optimizer = PromptOptimizer()

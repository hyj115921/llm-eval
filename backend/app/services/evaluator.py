"""
评测执行引擎：对模型输出进行多维度评分。
支持 EM、BLEU、ROUGE-L、F1、LLM-as-Judge 等指标。
"""
import json
import time
import re
from typing import List, Optional
from dataclasses import dataclass
from sacrebleu.metrics import BLEU
from rouge_score import rouge_scorer

from app.services.llm_service import llm_service


@dataclass
class EvalScore:
    metric_code: str
    score: float
    detail: str = ""


class Evaluator:
    """评测执行器，对单条输出计算所有指标得分"""

    def __init__(self):
        self._bleu = BLEU(effective_order=True)
        self._rouge = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)

    async def evaluate_single(
        self,
        model_output: str,
        expected_output: str,
        metric_configs: List[dict],
        judge_model_config: Optional[dict] = None,
    ) -> dict:
        """
        对单条样本评测。
        metric_configs: [{"code": "em", "metric_type": "builtin", "config_json": "{}"}, ...]
        返回: {"em": 1.0, "bleu": 0.85, ...}
        """
        scores = {}
        for mc in metric_configs:
            code = mc["code"]
            mtype = mc.get("metric_type", "builtin")
            config = json.loads(mc.get("config_json", "{}"))

            try:
                if mtype == "builtin":
                    score = self._eval_builtin(code, model_output, expected_output, config)
                elif mtype == "llm_based":
                    score = await self._eval_llm_judge(
                        code, model_output, expected_output, config, judge_model_config
                    )
                elif mtype == "custom":
                    score = self._eval_custom(
                        mc.get("custom_code", ""), model_output, expected_output
                    )
                else:
                    score = {"score": 0.0, "detail": f"未知指标类型: {mtype}"}
            except Exception as e:
                score = {"score": 0.0, "detail": f"评测异常: {str(e)}"}

            scores[code] = score

        return scores

    def _eval_builtin(self, code: str, output: str, expected: str, config: dict) -> dict:
        """内置指标计算"""
        output_clean = output.strip()
        expected_clean = expected.strip()

        if code == "em":
            score = 1.0 if output_clean == expected_clean else 0.0
            return {"score": score, "detail": "精确匹配" if score > 0 else "不匹配"}

        elif code == "bleu":
            if not output_clean or not expected_clean:
                return {"score": 0.0, "detail": "输入为空"}
            result = self._bleu.sentence_score(output_clean, [expected_clean])
            return {"score": round(result.score / 100, 4), "detail": f"BLEU: {result.score:.2f}"}

        elif code == "rouge_l":
            if not output_clean or not expected_clean:
                return {"score": 0.0, "detail": "输入为空"}
            result = self._rouge.score(expected_clean, output_clean)
            return {"score": round(result["rougeL"].fmeasure, 4), "detail": f"ROUGE-L: {result['rougeL'].fmeasure:.4f}"}

        elif code == "f1":
            output_tokens = set(output_clean.split())
            expected_tokens = set(expected_clean.split())
            if not expected_tokens:
                return {"score": 0.0, "detail": "预期输出为空"}
            intersection = output_tokens & expected_tokens
            precision = len(intersection) / len(output_tokens) if output_tokens else 0
            recall = len(intersection) / len(expected_tokens)
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            return {"score": round(f1, 4), "detail": f"P={precision:.3f} R={recall:.3f} F1={f1:.4f}"}

        else:
            return {"score": 0.0, "detail": f"未知指标: {code}"}

    async def _eval_llm_judge(
        self, code: str, output: str, expected: str, config: dict,
        judge_model_config: Optional[dict] = None,
    ) -> dict:
        """使用大模型作为评判者打分"""
        if not judge_model_config:
            return {"score": 0.0, "detail": "未配置评判模型"}

        judge_prompt = config.get("judge_prompt", self._default_judge_prompt())
        judge_prompt = judge_prompt.format(
            expected_output=expected,
            model_output=output,
        )

        result = await llm_service.chat(
            api_base=judge_model_config["api_base"],
            api_key=judge_model_config["api_key"],
            model_identifier=judge_model_config["model_identifier"],
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0.3,
            max_tokens=512,
        )

        if result["success"]:
            score = self._parse_judge_score(result["content"])
            return {"score": score, "detail": result["content"][:300]}
        return {"score": 0.0, "detail": f"评判模型调用失败: {result.get('error', '')}"}

    def _eval_custom(self, custom_code: str, output: str, expected: str) -> dict:
        """执行自定义评测代码（沙箱受限环境）"""
        if not custom_code.strip():
            return {"score": 0.0, "detail": "自定义代码为空"}

        safe_builtins = {"abs": abs, "len": len, "max": max, "min": min, "sum": sum,
                          "round": round, "float": float, "int": int, "str": str,
                          "bool": bool, "list": list, "dict": dict, "set": set,
                          "re": re, "json": json}

        try:
            local_vars = {"output": output, "expected": expected}
            exec(custom_code, {"__builtins__": safe_builtins}, local_vars)
            score_value = local_vars.get("score")
            if isinstance(score_value, (int, float)):
                detail = local_vars.get("detail", "")
                return {"score": float(score_value), "detail": str(detail)[:200]}
            return {"score": 0.0, "detail": "自定义代码需定义'score'变量(数值类型)"}
        except Exception as e:
            return {"score": 0.0, "detail": f"自定义代码执行异常: {str(e)}"}

    def _default_judge_prompt(self) -> str:
        return """你是一位专业的AI输出质量评判专家。请根据以下标准对模型输出进行评分。

【预期输出】
{expected_output}

【模型输出】
{model_output}

请从以下维度评估模型输出的质量：
1. 准确性：模型输出与预期输出的事实一致性
2. 完整性：是否覆盖了预期输出的关键信息点
3. 表达质量：语言流畅性、逻辑清晰度

请给出0-10分的综合评分（精确到1位小数），并简要说明理由。

输出格式（严格JSON）：
{{"score": 8.5, "reason": "评分理由"}}
"""

    def _parse_judge_score(self, text: str) -> float:
        """从 LLM Judge 输出中解析分数"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'\{[^}]*"score"[^}]*\}', text)
            if json_match:
                data = json.loads(json_match.group())
                score = float(data.get("score", 0))
                return max(0.0, min(10.0, score)) / 10.0  # 归一化到 0-1
        except Exception:
            pass
        # fallback: 提取数字
        numbers = re.findall(r'(\d+\.?\d*)', text)
        if numbers:
            score = float(numbers[0])
            if score > 1:
                score = score / 10.0
            return max(0.0, min(1.0, score))
        return 0.0


evaluator = Evaluator()

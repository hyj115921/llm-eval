from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


class MetricSummaryItem(BaseModel):
    avg: float
    max: float
    min: float
    median: float


class ScoreDistribution(BaseModel):
    categories: List[str] = []
    values: List[int] = []


class MetricComparison(BaseModel):
    metrics: List[str] = []
    avg_scores: List[float] = []


class ItemScores(BaseModel):
    ids: List[int] = []
    scores: List[float] = []


class EvalCharts(BaseModel):
    score_distribution: ScoreDistribution = ScoreDistribution()
    metric_comparison: MetricComparison = MetricComparison()
    item_scores: ItemScores = ItemScores()


class ItemDetail(BaseModel):
    result_id: int
    dataset_item_id: int
    model_output: str
    expected_output: str
    scores: Dict[str, Any] = {}
    avg_score: float
    latency_ms: int


class EvalReportResponse(BaseModel):
    task_id: int
    task_name: str
    status: str
    model_id: Optional[int] = 0
    dataset_id: Optional[int] = 0
    overall_score: float
    total_items: int
    metric_summary: Dict[str, MetricSummaryItem] = {}
    score_distribution: Dict[str, int] = {}
    charts: EvalCharts = EvalCharts()
    item_details: List[ItemDetail] = []
    recommendation: Optional[dict] = None


# --- Optimization Report ---

class OptimizationRoundItem(BaseModel):
    round_number: int
    score_before: float
    score_after: float
    improvement: float
    candidates: List[dict] = []
    error_samples: Optional[List[dict]] = []


class OptScoreHistory(BaseModel):
    rounds: List[str] = []
    scores: List[float] = []


class OptImprovementChart(BaseModel):
    rounds: List[int] = []
    improvements: List[float] = []


class OptPromptEvolution(BaseModel):
    rounds: List[str] = []
    best_scores: List[float] = []


class OptimizationCharts(BaseModel):
    score_history: OptScoreHistory = OptScoreHistory()
    improvement_per_round: OptImprovementChart = OptImprovementChart()
    prompt_evolution: OptPromptEvolution = OptPromptEvolution()


class OptimizationReportResponse(BaseModel):
    task_id: int
    task_name: str
    status: str
    initial_prompt: str
    best_prompt: str
    best_score: float
    baseline_score: float
    improvement: float
    total_rounds: int
    current_round: int
    charts: OptimizationCharts = OptimizationCharts()
    rounds: List[OptimizationRoundItem] = []

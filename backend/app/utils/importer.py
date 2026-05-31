"""
数据集批量导入 — 支持 CSV / JSONL / Excel 格式解析。
"""
import io
import json
import csv
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def parse_csv(content: bytes) -> List[dict]:
    """解析 CSV 文件，期望列: input_text, expected_output, [difficulty, scene_label]"""
    items = []
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    for row in reader:
        input_text = (row.get("input_text") or row.get("input") or row.get("question") or "").strip()
        expected = (row.get("expected_output") or row.get("expected") or row.get("output") or row.get("answer") or "").strip()
        if input_text:
            items.append({
                "input_text": input_text,
                "expected_output": expected,
                "difficulty": (row.get("difficulty") or "medium").strip(),
                "scene_label": (row.get("scene_label") or row.get("tag") or "").strip(),
            })
    return items


def parse_jsonl(content: bytes) -> List[dict]:
    """解析 JSONL 文件，每行一个 JSON 对象"""
    items = []
    text = content.decode("utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            items.append({
                "input_text": (obj.get("input_text") or obj.get("input") or obj.get("question") or "").strip(),
                "expected_output": (obj.get("expected_output") or obj.get("expected") or obj.get("output") or obj.get("answer") or "").strip(),
                "difficulty": obj.get("difficulty", "medium"),
                "scene_label": obj.get("scene_label", ""),
            })
        except json.JSONDecodeError as e:
            logger.warning("跳过无效 JSON 行: %s", e)
    return items


def parse_excel(content: bytes) -> List[dict]:
    """解析 Excel 文件 (需要 openpyxl)"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(h).lower().strip() if h else "" for h in rows[0]]
        items = []
        for row in rows[1:]:
            data = dict(zip(headers, [str(c) if c is not None else "" for c in row]))
            input_text = (data.get("input_text") or data.get("input") or data.get("question") or "").strip()
            if input_text:
                items.append({
                    "input_text": input_text,
                    "expected_output": (data.get("expected_output") or data.get("expected") or data.get("output") or data.get("answer") or "").strip(),
                    "difficulty": data.get("difficulty", "medium").strip(),
                    "scene_label": data.get("scene_label", data.get("tag", "")).strip(),
                })
        wb.close()
        return items
    except ImportError:
        raise ImportError("需要安装 openpyxl: pip install openpyxl")


def detect_and_parse(filename: str, content: bytes) -> Tuple[List[dict], str]:
    """
    根据文件扩展名检测格式并解析。
    返回: (items_list, format_name)
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    parsers = {
        "csv": (parse_csv, "CSV"),
        "tsv": (parse_csv, "TSV"),
        "jsonl": (parse_jsonl, "JSONL"),
        "json": (parse_jsonl, "JSON"),
        "xlsx": (parse_excel, "Excel"),
        "xls": (parse_excel, "Excel"),
    }

    if ext in parsers:
        parser, fmt_name = parsers[ext]
        try:
            items = parser(content)
            return items, fmt_name
        except Exception as e:
            logger.exception("解析 %s 文件失败", fmt_name)
            raise ValueError(f"解析 {fmt_name} 文件失败: {e}")

    # 自动检测: 尝试 JSONL 第一行
    try:
        first_line = content.decode("utf-8").splitlines()[0].strip()
        if first_line.startswith("[") or first_line.startswith("{"):
            items = parse_jsonl(content)
            return items, "JSONL(自动检测)"
    except Exception:
        pass

    # 尝试 CSV
    try:
        items = parse_csv(content)
        return items, "CSV(自动检测)"
    except Exception:
        pass

    raise ValueError(f"不支持的文件格式: {ext}，支持的格式: CSV, JSONL, Excel (.xlsx)")

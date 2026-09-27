"""箱变管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "transformer"
REQUIRED_FIELDS = ["箱变编号", "箱变型号", "额定容量"]
STATUS_ORDER = ["运行", "轻瓦斯", "重瓦斯", "停机"]
ACTION_RULES = {"停机检修": "停机", "复归信号": "运行", "恢复供电": "运行"}
NEGATIVE_ACTIONS = []
LOCATE_FIELDS = ["箱变编号", "所属电站"]
CAPACITY_FIELD = "额定容量"


def _parse_capacity(raw: Any) -> float | None:
    """把额定容量解析成数字；解析不了时返回 None，由调用方决定怎么提示。"""
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


class TransformerService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("箱变编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def locate_entries(
        self,
        *,
        field: str | None = None,
        value: str | None = None,
        capacity_min: str | None = None,
        capacity_max: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """定位条：按箱变编号或所属电站把目标箱变置顶，并按容量区间圈出匹配行。

        返回 (结果, 提示语)；结果为空表示定位条件不合法或未命中，提示语说明原因。
        """
        field = (field or "").strip()
        value = (value or "").strip()
        if field not in LOCATE_FIELDS:
            return None, "定位方式只支持按箱变编号或所属电站"
        if not value:
            return None, f"请填写要定位的{field}"
        raw_min = str(capacity_min or "").strip()
        raw_max = str(capacity_max or "").strip()
        low = _parse_capacity(raw_min) if raw_min else None
        high = _parse_capacity(raw_max) if raw_max else None
        if raw_min and low is None:
            return None, "容量下限需为数字"
        if raw_max and high is None:
            return None, "容量上限需为数字"
        if low is not None and high is not None and low > high:
            return None, "容量下限不能大于上限"

        rows = store.rows(MODULE)
        hits = [row for row in rows if value in str(row.get(field, ""))]
        if not hits:
            return None, f"未命中箱变：没有{field}包含「{value}」的箱式变压器"

        def in_range(row: dict[str, Any]) -> bool:
            if low is None and high is None:
                return True
            capacity = _parse_capacity(row.get(CAPACITY_FIELD))
            if capacity is None:
                return False
            if low is not None and capacity < low:
                return False
            if high is not None and capacity > high:
                return False
            return True

        hit_ids = {int(row.get("id", 0)) for row in hits}
        ordered = hits + [row for row in rows if int(row.get("id", 0)) not in hit_ids and in_range(row)]
        matched = sum(1 for row in ordered if in_range(row))
        target = hits[0]
        message = f"已定位到箱式变压器 {target.get('箱变编号', target.get('id'))}"
        if low is not None or high is not None:
            low_text = f"{low:g}" if low is not None else "不限"
            high_text = f"{high:g}" if high is not None else "不限"
            message += f"，容量区间 {low_text}~{high_text}kVA 内共 {matched} 条匹配"
            if not in_range(target):
                message += "；目标设备不在容量区间内"
        else:
            message += f"，命中 {len(hits)} 条"
        return {"items": ordered, "target_id": int(target.get("id", 0)), "matched": matched}, message

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"箱式变压器 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于箱变管理可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"箱式变压器已{action}"

"""箱变管理接口：维护箱式变压器，覆盖停机检修、复归信号、恢复供电等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, LocateResult, PageResult
from app.services.transformer import TransformerService

router = APIRouter(prefix="/api/transformer", tags=["箱变管理"])

service = TransformerService()

LIST_FIELDS = ["箱变编号", "箱变型号", "额定容量", "所属电站", "油温", "绕组温度", "上次检修日", "箱变状态"]
STATUSES = ["运行", "轻瓦斯", "重瓦斯", "停机"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按箱变编号检索"),
    status: str | None = Query(default=None, description="运行、轻瓦斯、重瓦斯、停机"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按箱变编号与状态过滤箱变管理列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/locate", response_model=LocateResult)
def locate_entries(
    field: str | None = Query(default=None, description="定位方式：箱变编号或所属电站"),
    value: str | None = Query(default=None, description="定位值，按包含匹配"),
    capacity_min: str | None = Query(default=None, description="容量下限（kVA），选填"),
    capacity_max: str | None = Query(default=None, description="容量上限（kVA），选填"),
) -> LocateResult:
    """定位条：把目标箱变放到首行，并按容量区间圈出匹配行；条件不合法或未命中时说明原因。"""
    result, message = service.locate_entries(
        field=field,
        value=value,
        capacity_min=capacity_min,
        capacity_max=capacity_max,
    )
    if result is None:
        return LocateResult(ok=False, message=message)
    return LocateResult(ok=True, message=message, **result)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出箱变管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "transformer", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条箱式变压器明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"箱式变压器 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条箱式变压器，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="箱式变压器已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条箱式变压器执行停机检修、复归信号、恢复供电；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

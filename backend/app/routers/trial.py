"""参考别名清洗试算路由：只读试算、受影响区域/站点映射与回源补录。

试算接口独立于通用资源路由，并在 main.py 中先于 resource 注册，
避免被 ``/api/{module}`` 动态路径抢先匹配。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas import ActionResult
from app.services.field_cleanse import FieldCleanseService

router = APIRouter(prefix="/api/field_cleanse/trial", tags=["清洗试算"])

service = FieldCleanseService()


class AddressSourcePayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


@router.get("/categories")
def trial_categories() -> dict[str, Any]:
    """列出可试算的参考类别（存在别名更正的类别）。"""
    return {"items": service.list_trial_categories()}


@router.get("/alias-overrides")
def alias_overrides(category: str | None = None) -> dict[str, Any]:
    """查询试算别名更正清单（第二套别名解释）。"""
    items = service.query_alias_override(category)
    return {"items": items, "total": len(items)}


@router.get("/address-records")
def address_records(region: str | None = None) -> dict[str, Any]:
    """查询实际地址原始记录，可按区域过滤。"""
    items = service.query_address_records(region)
    return {"items": items, "total": len(items)}


@router.get("/preview")
def preview_trial(category: str) -> dict[str, Any]:
    """生成别名清洗差异试算视图：旧码、新码、参考类别与受影响区域映射。"""
    return service.preview_alias_cleansing_trial(category)


@router.get("/effective-snapshot")
def effective_snapshot(category: str) -> dict[str, Any]:
    """核对试算期间生效参考数据与正式清洗旧码保持原样。"""
    return service.effective_cleansing_snapshot(category)


@router.post("/address-records", response_model=ActionResult)
def register_address_source(payload: AddressSourcePayload) -> ActionResult:
    """回源补录：补登缺失的原始地址记录，供随后再次试算。"""
    entry, missing = service.register_address_source(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="原始地址已回源补录，可重新试算", entry=entry)

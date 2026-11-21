"""业务路由汇总：所有模块共用一套资源路由，由领域服务完成分派。"""
from __future__ import annotations

from app.routers import resource, trial

# 试算路由含固定前缀，必须排在通用 /api/{module} 资源路由之前注册
ROUTERS = [trial, resource]

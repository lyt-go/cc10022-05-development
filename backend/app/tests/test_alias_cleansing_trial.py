"""参考别名清洗试算链路测试。

覆盖题目关键链路：两套别名解释按实际地址生成清洗差异 -> 试算保留旧码/新码/
参考类别 -> 受影响区域与站点映射 -> 未回源地区不算无影响 -> 回源补录后再次
试算视图变化 -> 试算全程生效参考数据与正式清洗旧码保持原样。

沿用 test_business_chains.py 的纯函数运行风格，不依赖 pytest，可直接执行：
    .venv/bin/python app/tests/test_alias_cleansing_trial.py
"""
from __future__ import annotations

import os
import sys

_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.services.field_cleanse import (
    DIFF_CODE_CHANGED,
    DIFF_NEW_RESOLVED,
    DIFF_PENDING_SOURCE,
    FieldCleanseService,
)
from app.store import store

CATEGORY = "站点编码"


def _reset_store() -> None:
    """用种子数据重置内存仓库，保证各用例相互独立。"""
    from app.seed import SEED_ROWS
    # Store 内部表通过 setdefault 懒建，直接清空后重新灌入即可
    for name in list(store._tables.keys()):  # noqa: SLF001 - 测试内重置仓库
        store._tables[name] = [dict(row) for row in SEED_ROWS.get(name, [])]  # noqa: SLF001


class TestAliasCleansingTrial:
    """参考别名改动清洗试算的关键业务链路。"""

    def setup_method(self) -> None:
        _reset_store()
        self.svc = FieldCleanseService()

    def test_trial_keeps_old_new_code_and_category(self):
        """试算明细必须同时保留旧码、拟改新码和引用的参考类别。"""
        result = self.svc.preview_alias_cleansing_trial(CATEGORY)
        assert result["试算类别"] == CATEGORY
        diff = next(item for item in result["差异明细"] if item["地址编号"] == "ADDR-003")
        # 旧解释下“南站”不是城南站别名 -> 旧码为空；叠加更正别名后解析出新码 ST-003
        assert diff["旧码"] == ""
        assert diff["新码"] == "ST-003"
        assert diff["新码名称"] == "城南站"
        assert diff["参考类别"] == CATEGORY
        assert diff["差异类型"] == DIFF_NEW_RESOLVED
        assert diff["命中别名"] == "南站"

    def test_two_alias_interpretations_are_separate(self):
        """字段清洗关联两套别名解释：生效参考数据与试算更正别名分表存放。"""
        old_entries = self.svc._alias_entries(CATEGORY, use_override=False)  # noqa: SLF001
        new_entries = self.svc._alias_entries(CATEGORY, use_override=True)  # noqa: SLF001
        south_old = next(e for e in old_entries if e["标准编码"] == "ST-003")
        south_new = next(e for e in new_entries if e["标准编码"] == "ST-003")
        assert "南站" not in south_old["别名"], "旧解释不应包含运营更正的简称"
        assert "南站" in south_new["别名"], "新解释应叠加试算更正别名"
        # 更正表独立存在，生效参考数据行不被写入更正别名
        override_rows = store.rows("mdm_reference_alias_override")
        assert any(r["更正别名"] == "南站" for r in override_rows)

    def test_pending_region_is_not_counted_as_no_impact(self):
        """地区数据未回源时：标记待回源确认，且受影响区域统计不得算作无影响。"""
        result = self.svc.preview_alias_cleansing_trial(CATEGORY)
        nancheng = next(r for r in result["区域汇总"] if r["区域"] == "南城区")
        assert nancheng["待回源数"] == 1
        assert nancheng["影响状态"] in ("待回源确认", "存在别名差异·待回源确认")
        assert result["汇总"]["待回源区域数"] == 1
        # 受影响区域数包含待回源区域，不能因为缺输入就算“无影响”
        assert result["汇总"]["受影响区域数"] >= 1
        pending = next(d for d in result["全量记录评估"] if d["地址编号"] == "ADDR-006")
        assert pending["差异类型"] == DIFF_PENDING_SOURCE
        assert pending["是否受影响"] is True
        # 无影响区域仍可被正确识别（对照）
        dongcheng = next(r for r in result["区域汇总"] if r["区域"] == "东城区")
        assert dongcheng["影响状态"] == "无影响"

    def test_site_mapping_lists_affected_sites(self):
        """站点映射给出旧码→新码及覆盖区域，供运营安排重洗。"""
        result = self.svc.preview_alias_cleansing_trial(CATEGORY)
        assert result["站点映射"], "缺少受影响站点映射，运营无法安排重洗"
        mapping = result["站点映射"][0]
        assert mapping["参考类别"] == CATEGORY
        assert mapping["新码"] == "ST-003"
        assert "南城区" in mapping["覆盖区域"]

    def test_trial_does_not_modify_effective_data(self):
        """试算期间生效参考数据与正式清洗记录保持原样。"""
        ref_before = [
            dict(r) for r in store.rows("mdm_reference")
            if r.get("数据类别") == CATEGORY and r.get("status") == "已生效"
        ]
        codes_before = [
            {"地址编号": r["地址编号"], "当前旧码": r.get("当前旧码", "")}
            for r in store.rows("address_raw_record")
        ]
        self.svc.preview_alias_cleansing_trial(CATEGORY)
        # 再跑一次，确认重复试算同样只读
        self.svc.preview_alias_cleansing_trial(CATEGORY)
        ref_after = [
            dict(r) for r in store.rows("mdm_reference")
            if r.get("数据类别") == CATEGORY and r.get("status") == "已生效"
        ]
        codes_after = [
            {"地址编号": r["地址编号"], "当前旧码": r.get("当前旧码", "")}
            for r in store.rows("address_raw_record")
        ]
        assert ref_before == ref_after, "试算改动了已生效参考数据"
        assert codes_before == codes_after, "试算改动了正式清洗旧码"
        south = next(r for r in store.rows("mdm_reference") if r["标准编码"] == "ST-003")
        assert south["别名列表"] == "城南站", "生效别名列表不应被试算更正"

    def test_backfill_then_retrial_changes_view(self):
        """未回源时先开试算，补到原始记录后再试：核对视图变化与生效字段。"""
        # 第一次试算：南城区存在待回源记录
        first = self.svc.preview_alias_cleansing_trial(CATEGORY)
        assert first["汇总"]["待回源记录数"] == 1
        first_diff_count = first["汇总"]["存在差异记录数"]

        # 运营回源补录历史原始地址（含新简称“南站”）
        entry, missing = self.svc.register_address_source({
            "地址编号": "ADDR-006",
            "区域": "南城区",
            "原始地址": "南城区南站便民服务点",
        })
        assert not missing
        assert entry["回源状态"] == "已回源"

        # 再次试算：待回源清零、差异明细增加、区域状态变化
        second = self.svc.preview_alias_cleansing_trial(CATEGORY)
        assert second["汇总"]["待回源记录数"] == 0
        assert second["汇总"]["存在差异记录数"] == first_diff_count + 1
        nancheng = next(r for r in second["区域汇总"] if r["区域"] == "南城区")
        assert nancheng["待回源数"] == 0
        assert nancheng["影响状态"] == "存在别名差异"
        retried = next(d for d in second["全量记录评估"] if d["地址编号"] == "ADDR-006")
        assert retried["差异类型"] == DIFF_NEW_RESOLVED
        assert retried["新码"] == "ST-003"
        # 补录与再试算后，正式清洗旧码仍保持原样（重洗尚未执行）
        assert retried["正式清洗旧码"] == ""
        snapshot = self.svc.effective_cleansing_snapshot(CATEGORY)
        assert all(item["当前旧码"] is not None for item in snapshot["正式清洗旧码"])
        south = next(r for r in snapshot["生效参考数据"] if r["标准编码"] == "ST-003")
        assert south["别名列表"] == "城南站"

    def test_backfill_requires_raw_address(self):
        """回源补录缺少原始地址时拒绝登记，避免把空输入当作已回源。"""
        entry, missing = self.svc.register_address_source({"区域": "南城区"})
        assert entry is None
        assert "原始地址" in missing
        still_pending = store.find("address_raw_record", 6)
        assert still_pending["回源状态"] == "待回源"

    def test_new_resolved_diff_type(self):
        """旧解释解析不到、新解释解析出码：归类为新解析出码。"""
        # 构造一条旧解释无别名命中、新解释凭更正别名挂到城南站的地址
        rows = store.rows("address_raw_record")
        rows.append({
            "id": 99,
            "status": "已回源",
            "pending": False,
            "abnormal": False,
            "地址编号": "ADDR-099",
            "区域": "东城区",
            # 旧解释无任何站点别名命中；新解释凭“南站”更正别名挂到城南站
            "原始地址": "东城区人民南路南站换乘点",
            "当前旧码": "ST-001",
            "回源状态": "已回源",
        })
        result = self.svc.preview_alias_cleansing_trial(CATEGORY)
        item = next(d for d in result["差异明细"] if d["地址编号"] == "ADDR-099")
        # 旧解释解析不到站点；新解释通过更正别名“南站”解析出城南站
        assert item["旧码"] == ""
        assert item["新码"] == "ST-003"
        assert item["差异类型"] == DIFF_NEW_RESOLVED

    def test_code_changed_when_both_resolve_differently(self):
        """旧码与新码都解析出且编码不同：归类为旧码改新码。"""
        # 追加一条更正别名，把“换乘点”指向城北站，使同一地址两套解释各有命中
        store.rows("mdm_reference_alias_override").append({
            "id": 2,
            "status": "待生效",
            "pending": True,
            "abnormal": False,
            "更正编号": "ALIAS-TRIAL-002",
            "数据类别": CATEGORY,
            "标准编码": "ST-004",
            "标准名称": "城北站",
            "更正别名": "换乘点",
            "别名解释": "新增别名：换乘点 -> 城北站(ST-004)",
            "试算范围": CATEGORY,
            "更新时间": "2026-11-21",
        })
        rows = store.rows("address_raw_record")
        rows.append({
            "id": 99,
            "status": "已回源",
            "pending": False,
            "abnormal": False,
            "地址编号": "ADDR-099",
            "区域": "东城区",
            # 旧解释命中“东站”->ST-001；新解释最长匹配“换乘点”->ST-004
            "原始地址": "东城区东站路换乘点",
            "当前旧码": "ST-001",
            "回源状态": "已回源",
        })
        result = self.svc.preview_alias_cleansing_trial(CATEGORY)
        item = next(d for d in result["差异明细"] if d["地址编号"] == "ADDR-099")
        assert item["旧码"] == "ST-001"
        assert item["新码"] == "ST-004"
        assert item["差异类型"] == DIFF_CODE_CHANGED


if __name__ == "__main__":
    runner = TestAliasCleansingTrial()
    tests = [
        ("试算保留旧码/新码/参考类别", runner.test_trial_keeps_old_new_code_and_category),
        ("两套别名解释分表存放", runner.test_two_alias_interpretations_are_separate),
        ("未回源地区不算无影响", runner.test_pending_region_is_not_counted_as_no_impact),
        ("站点映射列出受影响站点", runner.test_site_mapping_lists_affected_sites),
        ("试算不改生效数据与正式清洗", runner.test_trial_does_not_modify_effective_data),
        ("回源补录后再试算视图变化", runner.test_backfill_then_retrial_changes_view),
        ("回源补录必填校验", runner.test_backfill_requires_raw_address),
        ("新解析出码差异分类", runner.test_new_resolved_diff_type),
        ("旧码改新码差异分类", runner.test_code_changed_when_both_resolve_differently),
    ]
    passed = failed = 0
    for name, test_fn in tests:
        try:
            runner.setup_method()
            test_fn()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as exc:  # noqa: BLE001 - 手工测试运行器保留全部失败信息
            print(f"  FAIL: {name} -> {exc}")
            failed += 1
    print(f"\n{'=' * 60}")
    print(f"结果: {passed}/{len(tests)} 通过, {failed} 失败")
    assert failed == 0, f"{failed} 条试算链路测试失败！"

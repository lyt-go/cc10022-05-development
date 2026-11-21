"""字段清洗领域服务：标准化函数执行、修正字典匹配与字段完整性校验。"""
from __future__ import annotations

import datetime
import re
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


# 差异类型：仅别名命中变化、旧码改新码、新解析出码、待回源确认、无差异
DIFF_CODE_CHANGED = "旧码改新码"
DIFF_NEW_RESOLVED = "新解析出码"
DIFF_ALIAS_ONLY = "别名命中变化"
DIFF_PENDING_SOURCE = "待回源确认"
DIFF_NONE = "无差异"


class FieldCleanseService(BaseModuleService):
    MODULE = "field_cleanse"
    ENTITY = "清洗规则"
    OPERATION_TERM = "清洗"
    LIST_FIELDS = ["规则编号", "实体模型", "目标字段", "标准化函数", "修正字典", "异常处理", "先后顺序", "规则版本"]
    REQUIRED_FIELDS = ["规则编号", "实体模型", "目标字段"]
    STATUS_ORDER = ["草稿", "待校验", "已生效", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "停用规则": "已停用"}
    NEGATIVE_ACTIONS = ["停用规则"]

    STANDARD_FUNCTIONS: dict[str, Any] = {
        "trim": lambda v: v.strip() if isinstance(v, str) else v,
        "lower": lambda v: v.lower() if isinstance(v, str) else v,
        "upper": lambda v: v.upper() if isinstance(v, str) else v,
        "remove_spaces": lambda v: re.sub(r"\s+", "", v) if isinstance(v, str) else v,
        "format_phone": lambda v: re.sub(r"[^\d+]", "", v) if isinstance(v, str) else v,
        "format_id": lambda v: v.replace("-", "").replace(" ", "").upper() if isinstance(v, str) else v,
    }

    def cleanse_field_value(self, rule_id: int, raw_value: str) -> dict[str, Any]:
        """清洗字段值：按清洗规则执行标准化函数和修正字典映射。

        读取字段清洗规则，对原始字段值依次应用标准化函数和修正字典，
        校验清洗结果并返回清洗前值、清洗后值和采用的标准化函数。
        """
        rule = self.get_entry(rule_id)
        if not rule or rule.get("status") != "已生效":
            return {"ok": False, "reason": "清洗规则不可用", "raw": raw_value, "cleansed": raw_value}
        value = raw_value
        applied = []
        func_names = [f.strip() for f in rule.get("标准化函数", "").split(",") if f.strip()]
        for func_name in func_names:
            if func_name in self.STANDARD_FUNCTIONS:
                value = self.STANDARD_FUNCTIONS[func_name](value)
                applied.append(func_name)
        # 清洗字段值：应用标准化函数和修正字典完成字段转换
        dict_entries = [d.strip() for d in rule.get("修正字典", "").split(",") if ":" in d]
        for entry in dict_entries:
            wrong, correct = entry.split(":", 1)
            if isinstance(value, str) and wrong.strip() in value:
                value = value.replace(wrong.strip(), correct.strip())
                applied.append(f"dict:{wrong.strip()}->{correct.strip()}")
        return {"ok": True, "raw": raw_value, "cleansed": value, "applied_functions": applied}

    def batch_cleanse_records(self, rule_id: int, records: list[dict[str, Any]],
                               target_field: str) -> list[dict[str, Any]]:
        """批量清洗记录指定字段：遍历记录列表对目标字段执行清洗规则。

        读取清洗规则，对传入记录列表逐条清洗目标字段值，
        校验字段完整性并标准化字段内容，返回清洗后的记录列表。
        """
        rule = self.get_entry(rule_id)
        if not rule:
            return records
        for record in records:
            if target_field in record:
                result = self.cleanse_field_value(rule_id, str(record[target_field]))
                if result["ok"]:
                    # 清洗目标字段：标准化字段值并更新记录
                    record[target_field] = result["cleansed"]
                    record["_cleansed_fields"] = record.get("_cleansed_fields", [])
                    record["_cleansed_fields"].append(target_field)
        return records

    def validate_field_completeness(self, entity_model: str, records: list[dict[str, Any]],
                                     required_fields: list[str]) -> dict[str, Any]:
        """验证字段完整性：检查清洗后每条记录的必填字段是否均已填充。

        遍历清洗后的记录列表，逐一验证必填字段完整性，
        统计完备率、缺失字段分布和异常记录列表。
        """
        total = len(records)
        complete = 0
        field_missing: dict[str, int] = {}
        incomplete_records: list[dict[str, Any]] = []
        for i, record in enumerate(records):
            missing = [f for f in required_fields if not str(record.get(f, "")).strip()]
            if missing:
                incomplete_records.append({"index": i, "missing_fields": missing})
                for f in missing:
                    field_missing[f] = field_missing.get(f, 0) + 1
            else:
                complete += 1
        # 验证字段完整性：统计完备率和缺失字段分布
        completeness = round(complete / max(total, 1) * 100, 2)
        return {
            "entity_model": entity_model,
            "total_records": total,
            "complete_records": complete,
            "completeness_pct": completeness,
            "field_missing_distribution": field_missing,
            "incomplete_detail": incomplete_records,
        }

    def query_cleanse_rules_for_model(self, entity_model: str) -> list[dict[str, Any]]:
        """查询指定实体模型的所有已生效清洗规则，按先后顺序排列。

        遍历清洗规则存储，筛选已生效且匹配实体模型的规则，
        按先后顺序字段排序返回清洗规则执行序列。
        """
        rows = store.rows(self.MODULE)
        rules = [
            row for row in rows
            if row.get("实体模型") == entity_model and row.get("status") == "已生效"
        ]
        # 查询清洗规则并按先后顺序排序
        rules.sort(key=lambda r: int(r.get("先后顺序", "0") or "0"))
        return rules

    def standardize_field_values(self, records: list[dict[str, Any]],
                                  entity_model: str) -> list[dict[str, Any]]:
        """标准化字段值：对实体模型的所有记录执行完整清洗流水线。

        查询该实体模型的所有清洗规则，按先后顺序依次对每条记录的
        各目标字段执行标准化函数和修正字典转换，完成全链路清洗。
        """
        rules = self.query_cleanse_rules_for_model(entity_model)
        for rule in rules:
            target_field = rule.get("目标字段", "")
            if not target_field:
                continue
            for record in records:
                if target_field in record:
                    result = self.cleanse_field_value(rule["id"], str(record[target_field]))
                    if result["ok"]:
                        # 标准化字段值：执行完整清洗流水线并更新记录
                        record[target_field] = result["cleansed"]
        return records

    # ── 参考别名改动清洗试算（只读试算，不改生效参考数据与正式清洗记录） ──

    REF_TABLE = "mdm_reference"
    OVERRIDE_TABLE = "mdm_reference_alias_override"
    ADDRESS_TABLE = "address_raw_record"

    def _alias_entries(self, category: str, use_override: bool) -> list[dict[str, Any]]:
        """组装某一参考类别的别名解释表。

        use_override=False 时只取已生效参考数据（旧解释）；
        use_override=True 时在旧解释基础上叠加运营更正的试算别名（新解释）。
        更正别名与生效参考数据分表存放，叠加过程不回写任何生效记录。
        """
        entries: list[dict[str, Any]] = []
        for row in store.rows(self.REF_TABLE):
            if row.get("数据类别") != category or row.get("status") != "已生效":
                continue
            aliases = [a.strip() for a in str(row.get("别名列表", "")).split(",") if a.strip()]
            entries.append({
                "标准编码": row.get("标准编码", ""),
                "标准名称": row.get("标准名称", ""),
                "别名": [row.get("标准名称", ""), *aliases],
                "来源": "生效参考数据",
            })
        if use_override:
            for row in store.rows(self.OVERRIDE_TABLE):
                if row.get("数据类别") != category:
                    continue
                new_alias = str(row.get("更正别名", "")).strip()
                if not new_alias:
                    continue
                target = next(
                    (entry for entry in entries if entry["标准编码"] == row.get("标准编码")),
                    None,
                )
                if target is None:
                    target = {
                        "标准编码": row.get("标准编码", ""),
                        "标准名称": row.get("标准名称", ""),
                        "别名": [row.get("标准名称", "")],
                        "来源": "试算更正别名",
                    }
                    entries.append(target)
                if new_alias not in target["别名"]:
                    target["别名"].append(new_alias)
                target["来源"] = "试算更正别名"
        return entries

    @staticmethod
    def _resolve_alias(raw_address: str, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
        """按别名包含关系解析原始地址，命中多个别名时取最长匹配。"""
        best: dict[str, Any] | None = None
        for entry in entries:
            for alias in entry["别名"]:
                if alias and alias in raw_address:
                    if best is None or len(alias) > len(best["命中别名"]):
                        best = {
                            "标准编码": entry["标准编码"],
                            "标准名称": entry["标准名称"],
                            "命中别名": alias,
                            "来源": entry["来源"],
                        }
        return best

    def list_trial_categories(self) -> list[dict[str, Any]]:
        """列出存在试算别名更正的参考类别，供试算视图选择试算范围。"""
        categories: dict[str, dict[str, Any]] = {}
        for row in store.rows(self.OVERRIDE_TABLE):
            category = row.get("数据类别", "")
            item = categories.setdefault(category, {
                "数据类别": category,
                "更正条数": 0,
                "涉及标准编码": [],
            })
            item["更正条数"] += 1
            code = row.get("标准编码", "")
            if code not in item["涉及标准编码"]:
                item["涉及标准编码"].append(code)
        return sorted(categories.values(), key=lambda item: item["数据类别"])

    def query_alias_override(self, category: str | None = None) -> list[dict[str, Any]]:
        """查询试算别名更正清单（第二套别名解释），可按参考类别过滤。"""
        rows = store.rows(self.OVERRIDE_TABLE)
        if category:
            rows = [row for row in rows if row.get("数据类别") == category]
        return [dict(row) for row in rows]

    def query_address_records(self, region: str | None = None) -> list[dict[str, Any]]:
        """查询实际地址原始记录，可按受影响区域过滤。"""
        rows = store.rows(self.ADDRESS_TABLE)
        if region:
            rows = [row for row in rows if row.get("区域") == region]
        return [dict(row) for row in rows]

    def register_address_source(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """回源补录：为缺失原始地址的地区补登实际地址记录。

        补录只写原始地址表，不触碰已生效参考数据和正式清洗旧码；
        已回源记录重复补录时直接更新原始地址并保留原旧码，等待重新试算。
        """
        required = ["区域", "原始地址"]
        missing = [field for field in required if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(self.ADDRESS_TABLE)
        address_id = str(values.get("地址编号") or "").strip()
        existing = next(
            (row for row in rows if address_id and row.get("地址编号") == address_id),
            None,
        )
        if existing is not None:
            existing["原始地址"] = values["原始地址"].strip()
            existing["回源状态"] = "已回源"
            existing["status"] = "已回源"
            existing["pending"] = False
            existing["abnormal"] = False
            existing["回源时间"] = datetime.datetime.utcnow().isoformat()
            return dict(existing), []
        entry = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "status": "已回源",
            "pending": False,
            "abnormal": False,
            "地址编号": address_id or f"ADDR-{max((int(row.get('id', 0)) for row in rows), default=0) + 1:03d}",
            "区域": values["区域"].strip(),
            "原始地址": values["原始地址"].strip(),
            "当前旧码": str(values.get("当前旧码") or "").strip(),
            "回源状态": "已回源",
            "回源时间": datetime.datetime.utcnow().isoformat(),
        }
        rows.append(entry)
        return dict(entry), []

    def _classify_diff(self, record: dict[str, Any], old_hit: dict[str, Any] | None,
                       new_hit: dict[str, Any] | None) -> str:
        """判定单条地址记录的别名清洗差异类型。"""
        if record.get("回源状态") != "已回源" or not str(record.get("原始地址", "")).strip():
            return DIFF_PENDING_SOURCE
        old_code = old_hit["标准编码"] if old_hit else ""
        new_code = new_hit["标准编码"] if new_hit else ""
        if old_code == new_code:
            return DIFF_NONE
        if old_code and new_code:
            return DIFF_CODE_CHANGED
        if new_code:
            return DIFF_NEW_RESOLVED
        return DIFF_ALIAS_ONLY

    def preview_alias_cleansing_trial(self, category: str) -> dict[str, Any]:
        """生成参考别名改动的清洗试算视图（全程只读）。

        针对试算类别同时用旧、新两套别名解释解析每条实际地址记录，
        输出旧码/新码/参考类别/差异类型，并按区域汇总受影响情况与站点映射；
        未回源地区标记为“待回源确认”，不能算作没有影响。
        方法内不修改 mdm_reference 与地址记录的当前旧码（正式清洗记录）。
        """
        old_entries = self._alias_entries(category, use_override=False)
        new_entries = self._alias_entries(category, use_override=True)
        address_rows = store.rows(self.ADDRESS_TABLE)

        details: list[dict[str, Any]] = []
        for record in address_rows:
            raw_address = str(record.get("原始地址", "")).strip()
            old_hit = self._resolve_alias(raw_address, old_entries) if raw_address else None
            new_hit = self._resolve_alias(raw_address, new_entries) if raw_address else None
            diff_type = self._classify_diff(record, old_hit, new_hit)
            details.append({
                "地址编号": record.get("地址编号", ""),
                "区域": record.get("区域", ""),
                "原始地址": raw_address,
                "回源状态": record.get("回源状态", ""),
                "参考类别": category,
                "旧码": (old_hit or {}).get("标准编码", ""),
                "旧码名称": (old_hit or {}).get("标准名称", ""),
                "新码": (new_hit or {}).get("标准编码", ""),
                "新码名称": (new_hit or {}).get("标准名称", ""),
                "命中别名": (new_hit or old_hit or {}).get("命中别名", ""),
                "别名来源": (new_hit or old_hit or {}).get("来源", ""),
                "正式清洗旧码": record.get("当前旧码", ""),
                "差异类型": diff_type,
                "是否受影响": diff_type not in (DIFF_NONE,),
            })

        diffs = [item for item in details if item["差异类型"] != DIFF_NONE]
        region_summary = self._summarize_regions(category, details)
        site_mapping = self._build_site_mapping(category, details)
        return {
            "试算类别": category,
            "试算时间": datetime.datetime.utcnow().isoformat(),
            "只读说明": "试算仅读取生效参考数据与实际地址记录，不修改生效参考数据和正式清洗记录",
            "汇总": {
                "地址记录总数": len(details),
                "已回源记录数": sum(1 for item in details if item["回源状态"] == "已回源"),
                "待回源记录数": sum(1 for item in details if item["差异类型"] == DIFF_PENDING_SOURCE),
                "存在差异记录数": sum(
                    1 for item in details
                    if item["差异类型"] in (DIFF_CODE_CHANGED, DIFF_NEW_RESOLVED, DIFF_ALIAS_ONLY)
                ),
                "受影响区域数": sum(1 for item in region_summary if item["影响状态"] != "无影响"),
                "待回源区域数": sum(1 for item in region_summary if item["待回源数"] > 0),
            },
            "区域汇总": region_summary,
            "站点映射": site_mapping,
            "差异明细": diffs,
            "全量记录评估": details,
        }

    def _summarize_regions(self, category: str, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按区域汇总受影响情况：未回源区域不得算作没有影响。"""
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in details:
            grouped.setdefault(item["区域"], []).append(item)
        summary: list[dict[str, Any]] = []
        for region, items in sorted(grouped.items()):
            pending = sum(1 for item in items if item["差异类型"] == DIFF_PENDING_SOURCE)
            changed = sum(
                1 for item in items
                if item["差异类型"] in (DIFF_CODE_CHANGED, DIFF_NEW_RESOLVED, DIFF_ALIAS_ONLY)
            )
            if pending and changed:
                impact = "存在别名差异·待回源确认"
            elif pending:
                impact = "待回源确认"
            elif changed:
                impact = "存在别名差异"
            else:
                impact = "无影响"
            summary.append({
                "区域": region,
                "参考类别": category,
                "地址记录数": len(items),
                "已回源数": len(items) - pending,
                "待回源数": pending,
                "差异记录数": changed,
                "影响状态": impact,
                "涉及旧码": sorted({item["旧码"] for item in items if item["旧码"]}),
                "涉及新码": sorted({item["新码"] for item in items if item["新码"]}),
            })
        return summary

    def _build_site_mapping(self, category: str, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """汇总受影响站点的旧码→新码映射及覆盖区域，供运营安排重洗。"""
        mapping: dict[tuple[str, str], dict[str, Any]] = {}
        for item in details:
            if item["差异类型"] in (DIFF_NONE, DIFF_PENDING_SOURCE):
                continue
            key = (item["旧码"], item["新码"])
            entry = mapping.setdefault(key, {
                "参考类别": category,
                "旧码": item["旧码"],
                "旧码名称": item["旧码名称"],
                "新码": item["新码"],
                "新码名称": item["新码名称"],
                "覆盖区域": [],
                "记录数": 0,
            })
            if item["区域"] not in entry["覆盖区域"]:
                entry["覆盖区域"].append(item["区域"])
            entry["记录数"] += 1
        return sorted(mapping.values(), key=lambda item: (item["旧码"], item["新码"]))

    def effective_cleansing_snapshot(self, category: str) -> dict[str, Any]:
        """输出当前正式生效字段快照：核对试算期间生效数据未被改动。"""
        refs = [
            {
                "标准编码": row.get("标准编码", ""),
                "标准名称": row.get("标准名称", ""),
                "别名列表": row.get("别名列表", ""),
                "数据版本": row.get("数据版本", ""),
            }
            for row in store.rows(self.REF_TABLE)
            if row.get("数据类别") == category and row.get("status") == "已生效"
        ]
        address_codes = [
            {"地址编号": row.get("地址编号", ""), "当前旧码": row.get("当前旧码", "")}
            for row in store.rows(self.ADDRESS_TABLE)
        ]
        return {"参考类别": category, "生效参考数据": refs, "正式清洗旧码": address_codes}
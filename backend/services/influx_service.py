"""
能耗数据查询服务模块（MySQL 版）
============================
封装 MySQL 能耗时序数据查询，提供统一的能耗数据查询接口。
替代原 InfluxDB 版本，所有查询改为标准 SQL。

用法:
    from flask import current_app
    svc = EnergyQueryService(current_app.config)
    data = svc.query_trend(hours=24)
"""

from sqlalchemy import text


class EnergyQueryService:
    """能耗数据查询服务

    支持的方法：
        query_trend()              — 按小时聚合的能耗趋势
        query_building_comparison()— 各建筑总能耗对比
        query_peak_valley()        — 峰谷时段用电分析
        query_heatmap()            — 区域×建筑能耗热力图
        query_sub_items()          — 分项能耗（照明/空调/插座）
        query_historical_comparison() — 历史环比（日/周）
        classify_building()        — 建筑类型 → 分类标签 + 颜色
    """

    # 建筑类型 → 拓扑图分类 & 颜色映射
    BUILDING_CATEGORY_MAP = {
        "教学": ("academic", "#1890ff"),
        "办公": ("office", "#52c41a"),
        "宿舍": ("dormitory", "#fa8c16"),
        "食堂": ("canteen", "#f5222d"),
        "图书馆": ("library", "#722ed1"),
    }

    def __init__(self, config: dict = None):
        """初始化服务（config 参数保留兼容，实际从 Flask db 获取连接）"""
        self._config = config or {}

    # ---------- 上下文管理器 ----------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    # ---------- 内部查询方法 ----------

    def _db(self):
        """获取 SQLAlchemy db 实例（延迟导入避免循环依赖）"""
        from extensions import db
        return db

    def _query(self, sql: str, params: dict = None):
        """执行原生 SQL 查询，返回字典列表"""
        result = self._db().session.execute(text(sql), params or {})
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows]

    # ---------- 静态工具方法 ----------

    @staticmethod
    def classify_building(building_type: str):
        """根据建筑类型名称返回拓扑图分类标签和颜色"""
        for key, val in EnergyQueryService.BUILDING_CATEGORY_MAP.items():
            if key in building_type:
                return val
        return ("default", "#909399")

    def close(self):
        """关闭连接（MySQL 由 SQLAlchemy 连接池管理，无需手动关闭）"""
        pass

    # ---------- 能耗趋势 ----------

    def query_trend(self, hours: int = 24, building_id: str = None):
        """按小时聚合的能耗趋势曲线"""
        where = ""
        params = {"hours": hours}
        if building_id:
            where = "AND building_id = :building_id"
            params["building_id"] = building_id

        sql = f"""
            SELECT
                DATE_FORMAT(event_time, '%Y-%m-%d %H:00:00') AS time,
                building_id,
                ROUND(AVG(value), 2) AS value
            FROM energy_record
            WHERE event_time >= NOW() - INTERVAL :hours HOUR
              {where}
            GROUP BY time, building_id
            ORDER BY time
        """
        rows = self._query(sql, params)
        return [{
            "time": r["time"],
            "value": float(r["value"]),
            "building_id": r["building_id"],
        } for r in rows if r.get("value") is not None]

    # ---------- 建筑对比 ----------

    def query_building_comparison(self, hours: int = 24):
        """各建筑总能耗对比，降序排列"""
        sql = """
            SELECT building_id, ROUND(SUM(value), 2) AS total
            FROM energy_record
            WHERE event_time >= NOW() - INTERVAL :hours HOUR
            GROUP BY building_id
            ORDER BY total DESC
        """
        rows = self._query(sql, {"hours": hours})
        return [{
            "building_id": r["building_id"],
            "total": float(r["total"]),
        } for r in rows]

    # ---------- 峰谷分析 ----------

    def query_peak_valley(self, hours: int = 24):
        """峰时段(8-22点) vs 谷时段(22-次日8点)"""
        sql = """
            SELECT HOUR(event_time) AS h, SUM(value) AS total
            FROM energy_record
            WHERE event_time >= NOW() - INTERVAL :hours HOUR
            GROUP BY h
        """
        rows = self._query(sql, {"hours": hours})
        peak = sum(float(r["total"]) for r in rows if 8 <= int(r["h"]) < 22)
        valley = sum(float(r["total"]) for r in rows if int(r["h"]) < 8 or int(r["h"]) >= 22)
        total = peak + valley or 1
        return {
            "peak": round(peak, 2),
            "valley": round(valley, 2),
            "peak_ratio": round(peak / total * 100, 1),
            "valley_ratio": round(valley / total * 100, 1),
        }

    # ---------- 热力图 ----------

    def query_heatmap(self, hours: int = 24):
        """区域 × 建筑维度的平均能耗矩阵"""
        sql = """
            SELECT building_id, region_id, ROUND(AVG(value), 2) AS value
            FROM energy_record
            WHERE event_time >= NOW() - INTERVAL :hours HOUR
            GROUP BY building_id, region_id
        """
        rows = self._query(sql, {"hours": hours})
        return [{
            "building_id": r["building_id"],
            "region_id": r["region_id"],
            "value": float(r["value"]),
        } for r in rows if r.get("value") is not None]

    # ---------- 分项能耗 ----------

    def query_sub_items(self, building_id: str, hours: int = 24):
        """分项能耗（照明/空调/插座）"""
        sql = """
            SELECT sub_type, ROUND(SUM(value), 2) AS total
            FROM energy_sub_record
            WHERE event_time >= NOW() - INTERVAL :hours HOUR
              AND building_id = :building_id
            GROUP BY sub_type
        """
        rows = self._query(sql, {"hours": hours, "building_id": building_id})
        return {r["sub_type"]: float(r["total"]) for r in rows if r.get("total")}

    # ---------- 历史环比 ----------

    def query_historical_comparison(self, building_id: str):
        """今日/昨日、本周/上周历史环比"""
        sql = """
            SELECT
                DATE(event_time) AS day,
                ROUND(SUM(value), 2) AS total
            FROM energy_record
            WHERE event_time >= NOW() - INTERVAL 14 DAY
              AND building_id = :building_id
            GROUP BY day
            ORDER BY day
        """
        rows = self._query(sql, {"building_id": building_id})
        daily = [{"day": str(r["day"]), "total": float(r["total"])} for r in rows if r.get("total")]

        if len(daily) < 2:
            return {"today": 0, "yesterday": 0, "this_week": 0, "last_week": 0, "daily": daily}

        today = daily[-1]["total"]
        yesterday = daily[-2]["total"] if len(daily) >= 2 else 0
        week_size = min(7, len(daily))
        this_week = sum(d["total"] for d in daily[-week_size:])
        last_week_start = max(0, len(daily) - week_size * 2)
        last_week = sum(d["total"] for d in daily[last_week_start:len(daily) - week_size])

        return {
            "today": round(today, 2),
            "yesterday": round(yesterday, 2),
            "this_week": round(this_week, 2),
            "last_week": round(last_week, 2),
            "daily": daily,
        }

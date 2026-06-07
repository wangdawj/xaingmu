from config import Config


class InfluxService:
    def __init__(self):
        self.cfg = Config()
        self._v3_client = None
        self._v2_client = None

    def _is_v3(self):
        return self.cfg.INFLUXDB_VERSION == "3"

    def _v3(self):
        if self._v3_client is None:
            from influxdb_client_3 import InfluxDBClient3
            self._v3_client = InfluxDBClient3(
                host=self.cfg.INFLUXDB_URL,
                token=self.cfg.INFLUXDB_TOKEN,
                database=self.cfg.INFLUXDB_BUCKET,
                auth_scheme="Bearer",
            )
        return self._v3_client

    def _v2(self):
        if self._v2_client is None:
            from influxdb_client import InfluxDBClient
            self._v2_client = InfluxDBClient(
                url=self.cfg.INFLUXDB_URL,
                token=self.cfg.INFLUXDB_TOKEN,
                org=self.cfg.INFLUXDB_ORG,
            )
        return self._v2_client

    def _query_v3(self, sql: str):
        table = self._v3().query(query=sql, language="sql")
        return table.to_pylist()

    def query_trend(self, hours: int = 24, building_id: str = None):
        if self._is_v3():
            where = f"AND building_id = '{building_id}'" if building_id else ""
            rows = self._query_v3(f"""
                SELECT date_bin(interval '1 hour', time) AS time,
                       building_id,
                       AVG(value) AS value
                FROM electricity_data
                WHERE time > now() - interval '{hours} hours' {where}
                GROUP BY 1, 2
                ORDER BY time
            """)
            return [{
                "time": str(r["time"]),
                "value": round(float(r["value"]), 2),
                "building_id": r.get("building_id", ""),
            } for r in rows if r.get("value") is not None]

        filter_clause = ""
        if building_id:
            filter_clause = f'|> filter(fn: (r) => r["building_id"] == "{building_id}")'
        flux = f'''
        from(bucket: "{self.cfg.INFLUXDB_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "electricity_data")
          |> filter(fn: (r) => r["_field"] == "value")
          {filter_clause}
          |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
        '''
        tables = self._v2().query_api().query(flux, org=self.cfg.INFLUXDB_ORG)
        result = []
        for table in tables:
            for record in table.records:
                result.append({
                    "time": record.get_time().isoformat(),
                    "value": round(float(record.get_value()), 2),
                    "building_id": record.values.get("building_id", ""),
                })
        return result

    def query_building_comparison(self, hours: int = 24):
        if self._is_v3():
            rows = self._query_v3(f"""
                SELECT building_id, SUM(value) AS total
                FROM electricity_data
                WHERE time > now() - interval '{hours} hours'
                GROUP BY building_id
                ORDER BY total DESC
            """)
            return [{
                "building_id": r["building_id"],
                "total": round(float(r["total"]), 2),
            } for r in rows]

        flux = f'''
        from(bucket: "{self.cfg.INFLUXDB_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "electricity_data")
          |> filter(fn: (r) => r["_field"] == "value")
          |> group(columns: ["building_id"])
          |> sum()
        '''
        tables = self._v2().query_api().query(flux, org=self.cfg.INFLUXDB_ORG)
        result = []
        for table in tables:
            for record in table.records:
                result.append({
                    "building_id": record.values.get("building_id", ""),
                    "total": round(float(record.get_value()), 2),
                })
        return sorted(result, key=lambda x: x["total"], reverse=True)

    def query_peak_valley(self, hours: int = 24):
        if self._is_v3():
            rows = self._query_v3(f"""
                SELECT date_bin(interval '1 hour', time) AS time, AVG(value) AS value
                FROM electricity_data
                WHERE time > now() - interval '{hours} hours'
                GROUP BY 1
                ORDER BY time
            """)
            peak, valley = 0.0, 0.0
            for r in rows:
                if r.get("value") is None:
                    continue
                val = float(r["value"])
                hour_str = str(r["time"])
                try:
                    hour = int(hour_str[11:13])
                except (ValueError, IndexError):
                    hour = 12
                if 8 <= hour < 22:
                    peak += val
                else:
                    valley += val
            total = peak + valley or 1
            return {
                "peak": round(peak, 2),
                "valley": round(valley, 2),
                "peak_ratio": round(peak / total * 100, 1),
                "valley_ratio": round(valley / total * 100, 1),
            }

        flux = f'''
        from(bucket: "{self.cfg.INFLUXDB_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "electricity_data")
          |> filter(fn: (r) => r["_field"] == "value")
          |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
        '''
        tables = self._v2().query_api().query(flux, org=self.cfg.INFLUXDB_ORG)
        peak, valley = 0.0, 0.0
        for table in tables:
            for record in table.records:
                hour = record.get_time().hour
                val = float(record.get_value())
                if 8 <= hour < 22:
                    peak += val
                else:
                    valley += val
        total = peak + valley or 1
        return {
            "peak": round(peak, 2),
            "valley": round(valley, 2),
            "peak_ratio": round(peak / total * 100, 1),
            "valley_ratio": round(valley / total * 100, 1),
        }

    def query_heatmap(self, hours: int = 24):
        if self._is_v3():
            rows = self._query_v3(f"""
                SELECT building_id, region_id, AVG(value) AS value
                FROM electricity_data
                WHERE time > now() - interval '{hours} hours'
                GROUP BY building_id, region_id
            """)
            return [{
                "building_id": r["building_id"],
                "region_id": r["region_id"],
                "value": round(float(r["value"]), 2),
            } for r in rows if r.get("value") is not None]

        flux = f'''
        from(bucket: "{self.cfg.INFLUXDB_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "electricity_data")
          |> filter(fn: (r) => r["_field"] == "value")
          |> group(columns: ["building_id", "region_id"])
          |> mean()
        '''
        tables = self._v2().query_api().query(flux, org=self.cfg.INFLUXDB_ORG)
        result = []
        for table in tables:
            for record in table.records:
                result.append({
                    "building_id": record.values.get("building_id", ""),
                    "region_id": record.values.get("region_id", ""),
                    "value": round(float(record.get_value()), 2),
                })
        return result

    def close(self):
        if self._v3_client:
            self._v3_client.close()
        if self._v2_client:
            self._v2_client.close()

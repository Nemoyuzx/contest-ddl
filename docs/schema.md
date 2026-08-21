# 数据 Schema

顶层对象：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | string | 当前为 `1.0` |
| `generated_at` | ISO 8601 | 本轮生成时间，Asia/Shanghai |
| `source_health` | enum | `healthy` / `degraded` / `failed` |
| `stats` | object | 总量、活跃量、生命周期和类型统计 |
| `items` | array | 事件记录 |

事件的重要字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 由规范标题、类型、年份和来源身份生成的稳定 ID |
| `event_type` | enum | `competition`、`hackathon`、`summer_camp`、`pre_admission` |
| `categories` | string[] | 学科或活动方向，可多选 |
| `official_url` | URL | 首选官方活动页；聚合站记录会带核验提示 |
| `registration_start` | ISO 8601/null | 报名开始 |
| `registration_deadline` | ISO 8601/null | 报名截止 |
| `competition_start` | ISO 8601/null | 比赛/活动开始 |
| `competition_end` | ISO 8601/null | 比赛/活动结束 |
| `submission_deadline` | ISO 8601/null | 作品/材料提交截止 |
| `primary_deadline` | ISO 8601 | 用于列表排序：报名截止 → 提交截止 → 比赛开始 → 比赛结束 |
| `status` | enum | `registration_upcoming/open/closed`、`submission_open`、`upcoming`、`ongoing`、`ended`、`unknown` |
| `confidence` | enum | `high` / `medium` / `low` |
| `verification_status` | enum | `single_source`、`cross_source`、`maintainer_reviewed` |
| `source` | object | 当前优先证据，含 URL、权威等级、核验字段和时间 |
| `sources` | object[] | 合并时保留的全部来源证据 |
| `first_seen_at` / `last_seen_at` | ISO 8601 | 首次和最近观测时间 |
| `stale` / `archived` | boolean | 7/30 天未再观测的生命周期状态 |

所有时间必须带时区。仅有日期的中国来源按当天 `23:59:59+08:00` 解释为截止时间；如果原页面给出具体时间，则保留具体时间。

# Contest DDL

[![Daily update](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/update-pages.yml/badge.svg)](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/update-pages.yml)
[![Tests](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/ci.yml/badge.svg)](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/ci.yml)
[![GitHub Pages](https://img.shields.io/badge/Pages-Live-c9ff5b?logo=github)](https://nemoyuzx.github.io/contest-ddl/)

每天自动聚合大学生工科竞赛、黑客松、保研夏令营与预推免截止日期，输出可搜索的静态网站、JSON 和 ICS 日历。重点覆盖电子信息、计算机、通信、网络安全、自动化、机械、人工智能和机器人方向。

- 网站：<https://nemoyuzx.github.io/contest-ddl/>
- JSON：<https://nemoyuzx.github.io/contest-ddl/data/competitions.json>
- ICS：<https://nemoyuzx.github.io/contest-ddl/data/competitions.ics>
- 数据质量：[`data/quality-report.json`](data/quality-report.json)
- 数据源健康：[`data/source-status.json`](data/source-status.json)

> 聚合信息可能延迟或有误，参赛/提交前请点击记录中的官方链接复核。全国 DDL 不等于学校内部 DDL。

## 当前数据快照

<!-- DATA_SNAPSHOT_START -->
> 数据生成于 `2026-08-22T09:56:26+08:00`，共 281 条；数据源状态：`healthy`。

| 事件 | 类型 | 最近 DDL / 时间 | 状态 | 来源 |
| --- | --- | --- | --- | --- |
| [中国药科大学 · 人工智能学院（推免预报名）](https://lxy.cpu.edu.cn/b3/7a/c56a242554/page.htm) | summer_camp | 2026-08-22T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [同济大学 · 上海自主智能无人系统科学中心（推免研究生报名）](https://srias.tongji.edu.cn/cb/69/c17827a379753/page.htm) | summer_camp | 2026-08-23T17:00:00+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [中山大学 · 集成电路学院（推免研究生报名）](https://sic.sysu.edu.cn/rc/rc05/1421838.htm) | summer_camp | 2026-08-23T23:59:00+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [吉林大学 · 通信工程学院（校园学术活动开放日）](https://dce.jlu.edu.cn/info/1032/11402.htm) | summer_camp | 2026-08-24T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [南开大学 · 人工智能学院（推免预报名）](https://ai.nankai.edu.cn/info/1024/6632.htm) | summer_camp | 2026-08-25T12:00:00+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [同济大学 · 计算机科学与技术学院（推免研究生报名）](https://cs.tongji.edu.cn/info/1022/4119.htm) | summer_camp | 2026-08-25T12:00:00+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [哈尔滨工业大学 · 计算学部（推免研究生报名）](https://cs.hit.edu.cn/2026/0726/c11271a398409/page.htm) | summer_camp | 2026-08-25T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [中山大学 · 网络空间安全学院（推免研究生报名）](https://scst.sysu.edu.cn/article/502) | summer_camp | 2026-08-26T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [Midnight Virtual Hackathon [August]](https://events.mlh.com/events/14510-midnight-hackathon-august) | hackathon | 2026-08-28T09:11:11+08:00 | upcoming | Major League Hacking |
| [PEC HACKS 4.0](https://pechacks.org/) | hackathon | 2026-08-29T18:30:00+08:00 | upcoming | Major League Hacking |
| [南方科技大学 · 深港微电子学院（推免预报名）](https://mp.weixin.qq.com/s/p9QdSnhvbnqEKeDBs7MN7w) | summer_camp | 2026-08-31T23:59:00+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [中国科学院大学 · 电子电气与通信工程学院（推免研究生接收）](https://eece.ucas.ac.cn/index.php/zh-cn/2014-06-13-06-51-06/2715-2027) | summer_camp | 2026-09-01T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
<!-- DATA_SNAPSHOT_END -->

## 数据源

| 来源 | 用途 | 权威等级 | 采集方式 |
| --- | --- | --- | --- |
| 维护者核验 `data/manual.yml` | 主流全国赛与官方通知 | 高 | 带来源的人工录入 |
| 赛氪公开赛事页 | 国内工科竞赛发现 | 较低 | 公开 HTML，限速抓取、关键词过滤 |
| Major League Hacking | 国际高校黑客松 | 高 | 官方活动页结构化数据 |
| CS-BAOYAN BoardCaster | 工科夏令营 / 预推免 | 较高 | 社区维护 JSON，按工科院系过滤 |

完整说明见 [数据源文档](docs/sources.md)。本项目不调用赛氪内部接口，不绕过登录、验证码或访问控制，只读取浏览器可正常访问的公开页面。

## 每日自动化

`.github/workflows/update-pages.yml` 每天北京时间 **08:17** 运行：

```text
多源采集 → 规范化 → 工科筛选 → 标题/URL 去重 → 字段优先级合并
        → 时间线校验 → 生命周期处理 → JSON / ICS / README → GitHub Pages
```

来源故障不会清空历史数据：7 天未再次观测标记 `stale`，30 天后标记 `archived`，但始终保留在 JSON 中。字段冲突、无效时间线和人工覆盖均写入质量报告。详见 [数据治理规则](docs/data-governance.md)。

## 本地运行

需要 Python 3.11+：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m contestddl update
python -m pytest
python -m http.server 8000
```

打开 <http://localhost:8000>。只运行部分来源：

```bash
python -m contestddl update --source saikr --source mlh
```

## 数据 API

`data/competitions.json` 是无需鉴权的静态 API。一个事件区分：

- `registration_deadline`：报名截止
- `competition_start` / `competition_end`：比赛起止
- `submission_deadline`：作品或材料提交截止
- `primary_deadline`：网站排序使用的最近关键日期
- `source` / `sources`：当前字段来源和全部证据
- `stale` / `archived`：数据生命周期标记

字段定义见 [Schema](docs/schema.md)。

## 贡献数据

- 新赛事：提交 [Add event Issue](https://github.com/Nemoyuzx/contest-ddl/issues/new?template=add-event.yml)
- 更正日期：提交 [Report wrong DDL Issue](https://github.com/Nemoyuzx/contest-ddl/issues/new?template=correct-deadline.yml)
- 直接 PR：编辑 `data/manual.yml` 或 `data/overrides.yml`，必须附主办方/学校官方通知 URL

请勿提交“据说”“往年一般是”或仅有搜索摘要支持的日期。完整流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢

数据治理和采集规则参考了 [kelin-gpu/campus-competition-agent](https://github.com/kelin-gpu/campus-competition-agent)；夏令营数据来自 [CS-BAOYAN/BoardCaster](https://github.com/CS-BAOYAN/BoardCaster)。各来源数据版权与使用条款归原作者或平台所有。

## License

代码使用 [MIT License](LICENSE)。第三方数据不因本仓库的代码许可而改变其原有权利归属。

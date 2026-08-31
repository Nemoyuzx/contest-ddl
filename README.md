# Contest DDL

[![Daily update](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/update-pages.yml/badge.svg)](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/update-pages.yml)
[![Tests](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/ci.yml/badge.svg)](https://github.com/Nemoyuzx/contest-ddl/actions/workflows/ci.yml)
[![GitHub Pages](https://img.shields.io/badge/Pages-Live-c9ff5b?logo=github)](https://nemoyuzx.github.io/contest-ddl/)

每天自动聚合大学生工科竞赛、计算机学术会议、黑客松、保研夏令营与预推免截止日期，输出可搜索的静态网站、JSON 和 ICS 日历。重点覆盖电子信息、计算机、通信、网络安全、自动化、机械、人工智能和机器人方向。

网站中的 `★` 表示赛事名称已匹配到指定的 [`college-competition-ddl/competitions.json`](https://github.com/xcg1125/college-competition-ddl/blob/main/competitions.json) 条目，仅代表目录收录，不代表官方认证或赛事评级。

推免记录会显示结构化的 `985`、`211`、`双一流` 院校标签；同一学校可同时显示多个标签，名单来源和校区别名规则见[数据源文档](docs/sources.md)。

- 网站：<https://nemoyuzx.github.io/contest-ddl/>
- JSON：<https://nemoyuzx.github.io/contest-ddl/data/competitions.json>
- ICS：<https://nemoyuzx.github.io/contest-ddl/data/competitions.ics>
- 数据质量：[`data/quality-report.json`](data/quality-report.json)
- 数据源健康：[`data/source-status.json`](data/source-status.json)

> 聚合信息可能延迟或有误，参赛/投稿/提交前请点击记录中的官方链接复核。全国 DDL 不等于学校内部 DDL。

## 当前数据快照

<!-- DATA_SNAPSHOT_START -->
> 数据生成于 `2026-08-31T13:29:52+08:00`，共 454 条；数据源状态：`healthy`。

| 事件 | 类型 | 最近 DDL / 时间 | 状态 | 来源 |
| --- | --- | --- | --- | --- |
| [MSN 2026](https://ieee-msn.org/2026) | conference | 2026-08-31T19:59:59+08:00 | submission_open | CCFDDL Open Deadlines |
| [南方科技大学 · 深港微电子学院（推免预报名）](https://mp.weixin.qq.com/s/p9QdSnhvbnqEKeDBs7MN7w) | summer_camp | 2026-08-31T23:59:00+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [香港大学 · 计算与数据科学学院（2027研究型硕博早招第二轮）](https://www.cs.hku.hk/programmes/research-based/mphil-phd-admission) | summer_camp | 2026-08-31T23:59:00+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [2026年“数据要素×”大赛北京分赛暨北京数智创新大赛](https://new.saikr.com/vse/59501) | competition | 2026-08-31T23:59:59+08:00 | ongoing | 赛氪公开前端 API |
| [2026年度CCF量子计算编程挑战赛-量旋杯-量子国际象棋赛道](https://new.saikr.com/vse/lzxq2026) | competition | 2026-08-31T23:59:59+08:00 | ongoing | 赛氪公开前端 API |
| [南方科技大学 · 计算机科学与工程系](https://cse.sustech.edu.cn/notices/3775.html) | summer_camp | 2026-08-31T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [广西大学 · 计算机与电子信息学院（推免预报名）](https://yjsc.gxu.edu.cn/info/1021/4680.htm) | summer_camp | 2026-08-31T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [IEEE VR 2027](https://ieeevr.org/2027/) | conference | 2026-09-01T19:59:59+08:00 | submission_open | CCFDDL Open Deadlines |
| [PETS 2027](https://petsymposium.org/cfp27.php) | conference | 2026-09-01T19:59:59+08:00 | submission_open | CCFDDL Open Deadlines |
| [中国科学院大学 · 电子电气与通信工程学院（推免研究生接收）](https://eece.ucas.ac.cn/index.php/zh-cn/2014-06-13-06-51-06/2715-2027) | summer_camp | 2026-09-01T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [南方科技大学 · 计算机科学与工程系（国优计划）](https://cse.sustech.edu.cn/notices/3776.html) | summer_camp | 2026-09-01T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
| [西南财经大学 · 计算机与人工智能学院（推免研究生报名）](https://it.swufe.edu.cn/info/1166/22608.htm) | summer_camp | 2026-09-01T23:59:59+08:00 | registration_open | CS-BAOYAN BoardCaster |
<!-- DATA_SNAPSHOT_END -->

## 数据源

| 来源 | 用途 | 权威等级 | 采集方式 |
| --- | --- | --- | --- |
| 维护者核验 `data/manual.yml` | 主流全国赛与官方通知 | 高 | 带来源的人工录入 |
| 赛氪公开前端 API | 国内工科竞赛发现 | 较低 | 新版赛事页公开调用的列表/详情 JSON；采集正文、赛程与附件 |
| 赛事官网目录 | 国内主流工科赛事官网 | 高 | 每日抓取官网及少量通知页，提取明确时间标签与正文摘要 |
| CCFDDL Open Deadlines | 全球计算机学术会议 | 较高 | 读取社区维护 YAML，转换摘要/论文截止时区并保留 CCF、CORE、TH-CPL 标签 |
| Major League Hacking | 国际高校黑客松 | 高 | 官方活动页结构化数据 |
| CS-BAOYAN BoardCaster | 工科夏令营 / 预推免 | 较高 | 社区维护 JSON，按工科院系过滤 |

完整说明见 [数据源文档](docs/sources.md)。本项目只调用赛氪新版公开赛事页自身使用的只读前端接口，不调用管理接口，也不绕过登录、验证码或访问控制。

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
- `competition_start` / `competition_end`：比赛或活动起止
- `abstract_deadline`：论文摘要注册/提交截止
- `submission_deadline`：作品、材料或论文全文提交截止
- `primary_deadline`：网站排序使用的最近关键日期
- `description` / `schedule` / `attachments`：来源提供的具体介绍、分阶段赛程和公开附件
- `university_tiers`：推免院校的 `985` / `211` / `双一流` 标签，可多选
- `source` / `sources`：当前字段来源和全部证据
- `stale` / `archived`：数据生命周期标记

字段定义见 [Schema](docs/schema.md)。

## 贡献数据

- 新事件：提交 [Add event Issue](https://github.com/Nemoyuzx/contest-ddl/issues/new?template=add-event.yml)
- 更正日期：提交 [Report wrong DDL Issue](https://github.com/Nemoyuzx/contest-ddl/issues/new?template=correct-deadline.yml)
- 直接 PR：编辑 `data/manual.yml` 或 `data/overrides.yml`，必须附主办方、会议、期刊/出版社或学校的官方通知 URL

请勿提交“据说”“往年一般是”或仅有搜索摘要支持的日期。完整流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢

数据治理和采集规则参考了 [kelin-gpu/campus-competition-agent](https://github.com/kelin-gpu/campus-competition-agent)；赛事官网目录参考 [xcg1125/college-competition-ddl](https://github.com/xcg1125/college-competition-ddl/blob/main/competitions.json)；论文会议数据来自 MIT 许可的 [CCFDDL Open Deadlines](https://github.com/ccfddl/ccf-deadlines)；夏令营数据来自 [CS-BAOYAN/BoardCaster](https://github.com/CS-BAOYAN/BoardCaster)。各来源数据版权与使用条款归原作者或平台所有。

## License

代码使用 [MIT License](LICENSE)。第三方数据不因本仓库的代码许可而改变其原有权利归属。

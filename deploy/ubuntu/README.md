# 赛氪国内采集节点

仅迁移赛氪采集，GitHub Actions 继续负责 manual、官网核验、MLH、保研、CCFDDL、全量去重/生命周期、JSON/ICS 与 Pages 发布。此节点不运行 GitHub Runner、不持有 GitHub 写入凭据、不执行远程传来的代码或 URL。

## 部署

1. 在 Ubuntu 创建不可登录的专用系统用户/组 `contest-ddl-saikr`。
2. 将已审核源码放在 `/srv/contest-ddl-saikr/releases/<commit>`，以 `current` 符号链接指向运行版本。代码和虚拟环境由 root 持有，采集账号只读。
3. 用系统 Python 3.12 创建 `/srv/contest-ddl-saikr/venv`，通过该环境的 `pip install /srv/contest-ddl-saikr/current` 安装项目及既有依赖。unit 的 `PYTHONPATH` 始终指向当前发布源码。
4. 安装本目录的 service/timer 到 `/etc/systemd/system/`，执行 `systemctl daemon-reload`，先 `systemctl start contest-ddl-saikr.service`，确认成功后 `systemctl enable --now contest-ddl-saikr.timer`。
5. 在网站 Nginx 配置中只以精确路径 `/data/saikr-snapshot.json` 映射 `/var/lib/contest-ddl-saikr/snapshot.json`，仅允许 GET/HEAD；不要暴露整个状态目录。权威配置位于 `where_to_study-site/deploy/ubuntu/where-to-study.nginx`。
6. 确认 `https://where-to-study.cn/data/saikr-snapshot.json` 可读取且通过 `validate_snapshot` 后，再让 GitHub 以 `SAIKR_SOURCE=ubuntu` 执行聚合。

每天北京时间 07:40（最多随机延后 90 秒）采集，先于 GitHub 的 08:17 计划时间；错过的执行由 systemd 补跑。手动补采集使用 `systemctl start contest-ddl-saikr.service`。单次最多 72 条详情、3 并发，10 分钟超时，256 MiB 内存与 50% CPU 上限。

## 失败与校验

启动采集前原子发布进行中/失败标记；成功后再原子替换结果。全量成功副本单独保留为 `last-success.json`，不对外暴露。部分分类失败保留本轮确实取得的部分事件，但 `ok=false`；完全失败返回空事件，GitHub 的历史事件继续按原 7/30 天规则保留，绝不把旧成功副本重新盖上新时间。

GitHub 校验 SHA-256（传输完整性，不代替 HTTPS 身份验证）、版本、来源、条数、唯一 ID、原始赛氪证据及时间。超过 36 小时、未来时间、HTML、跳转或超 8 MiB 响应均视为失败，不回退到已无法提供国内数据的境外直采。快照导出始终调用 `collect_direct`，不受 `SAIKR_SOURCE` 影响。反复读取同一快照不推进赛事 `last_seen_at`。

用 `systemctl status contest-ddl-saikr.service contest-ddl-saikr.timer`、`journalctl -u contest-ddl-saikr.service` 检查节点；`data/source-status.json` 的 `saikr.details.transport` 显示节点采集时间与传输方式。这个只读供给端点的访问计入网站内部接口统计，不进入访客或装机推断。

## 回滚

停用此 timer 不影响网站或其他数据来源。若需回滚代码，先等采集结束，再把 `current` 原子切回已有发布目录；不要删除 `/var/lib/contest-ddl-saikr` 或历史成功副本。GitHub 仅在明确恢复境外直采可用后才移除 `SAIKR_SOURCE=ubuntu`；否则保留降级及历史记录，不伪装恢复。

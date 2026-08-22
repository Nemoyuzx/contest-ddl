from __future__ import annotations

import re


PROJECT_985_SOURCE = "https://www.moe.gov.cn/srcsite/A22/s7065/200612/t20061206_128833.html"
PROJECT_211_SOURCE = "https://www.moe.gov.cn/srcsite/A22/s7065/200512/t20051223_82762.html"
DOUBLE_FIRST_CLASS_SOURCE = "https://www.moe.gov.cn/srcsite/A22/s7065/202202/t20220211_598710.html"


# Historical "985 Project" membership (39 universities).
PROJECT_985_UNIVERSITIES = frozenset("""
北京大学 中国人民大学 清华大学 北京航空航天大学 北京理工大学 中国农业大学 北京师范大学 中央民族大学
南开大学 天津大学 大连理工大学 东北大学 吉林大学 哈尔滨工业大学 复旦大学 同济大学 上海交通大学
华东师范大学 南京大学 东南大学 浙江大学 中国科学技术大学 厦门大学 山东大学 中国海洋大学 武汉大学
华中科技大学 湖南大学 中南大学 国防科技大学 中山大学 华南理工大学 四川大学 电子科技大学 重庆大学
西安交通大学 西北工业大学 西北农林科技大学 兰州大学
""".split())


# Ministry of Education "211 Project" list, published in 2008. Historical
# institution names are intentionally retained; alias groups below bridge them
# to current names without rewriting the source snapshot.
PROJECT_211_UNIVERSITIES = frozenset("""
北京大学 中国人民大学 清华大学 北京交通大学 北京工业大学 北京航空航天大学 北京理工大学 北京科技大学
北京化工大学 北京邮电大学 中国农业大学 北京林业大学 北京中医药大学 北京师范大学 北京外国语大学
中国传媒大学 中央财经大学 对外经济贸易大学 北京体育大学 中央音乐学院 中央民族大学 中国政法大学
华北电力大学 南开大学 天津大学 天津医科大学 河北工业大学 太原理工大学 内蒙古大学 辽宁大学
大连理工大学 东北大学 大连海事大学 吉林大学 延边大学 东北师范大学 哈尔滨工业大学 哈尔滨工程大学
东北农业大学 东北林业大学 复旦大学 同济大学 上海交通大学 华东理工大学 东华大学 华东师范大学
上海外国语大学 上海财经大学 上海大学 第二军医大学 南京大学 苏州大学 东南大学 南京航空航天大学
南京理工大学 中国矿业大学 河海大学 江南大学 南京农业大学 中国药科大学 南京师范大学 浙江大学
安徽大学 中国科学技术大学 合肥工业大学 厦门大学 福州大学 南昌大学 山东大学 中国海洋大学
中国石油大学 郑州大学 武汉大学 华中科技大学 中国地质大学 武汉理工大学 华中农业大学
华中师范大学 中南财经政法大学 湖南大学 中南大学 湖南师范大学 国防科学技术大学 中山大学
暨南大学 华南理工大学 华南师范大学 广西大学 海南大学 四川大学 西南交通大学 电子科技大学
四川农业大学 西南财经大学 重庆大学 西南大学 贵州大学 云南大学 西藏大学 西北大学 西安交通大学
西北工业大学 西安电子科技大学 长安大学 西北农林科技大学 陕西师范大学 第四军医大学 兰州大学
青海大学 宁夏大学 新疆大学 石河子大学
""".split())


# Second-round Double First-Class construction universities, Ministry of
# Education 2022 attachment 1 (147 institutions).
DOUBLE_FIRST_CLASS_UNIVERSITIES = frozenset("""
北京大学 中国人民大学 清华大学 北京交通大学 北京工业大学 北京航空航天大学 北京理工大学 北京科技大学
北京化工大学 北京邮电大学 中国农业大学 北京林业大学 北京协和医学院 北京中医药大学 北京师范大学
首都师范大学 北京外国语大学 中国传媒大学 中央财经大学 对外经济贸易大学 外交学院 中国人民公安大学
北京体育大学 中央音乐学院 中国音乐学院 中央美术学院 中央戏剧学院 中央民族大学 中国政法大学 南开大学
天津大学 天津工业大学 天津医科大学 天津中医药大学 华北电力大学 河北工业大学 山西大学 太原理工大学
内蒙古大学 辽宁大学 大连理工大学 东北大学 大连海事大学 吉林大学 延边大学 东北师范大学 哈尔滨工业大学
哈尔滨工程大学 东北农业大学 东北林业大学 复旦大学 同济大学 上海交通大学 华东理工大学 东华大学
上海海洋大学 上海中医药大学 华东师范大学 上海外国语大学 上海财经大学 上海体育学院 上海音乐学院
上海大学 南京大学 苏州大学 东南大学 南京航空航天大学 南京理工大学 中国矿业大学 南京邮电大学 河海大学
江南大学 南京林业大学 南京信息工程大学 南京农业大学 南京医科大学 南京中医药大学 中国药科大学
南京师范大学 浙江大学 中国美术学院 安徽大学 中国科学技术大学 合肥工业大学 厦门大学 福州大学
南昌大学 山东大学 中国海洋大学 中国石油大学（华东） 郑州大学 河南大学 武汉大学 华中科技大学
中国地质大学（武汉） 武汉理工大学 华中农业大学 华中师范大学 中南财经政法大学 湘潭大学 湖南大学
中南大学 湖南师范大学 中山大学 暨南大学 华南理工大学 华南农业大学 广州医科大学 广州中医药大学
华南师范大学 海南大学 广西大学 四川大学 重庆大学 西南交通大学 电子科技大学 西南石油大学 成都理工大学
四川农业大学 成都中医药大学 西南大学 西南财经大学 贵州大学 云南大学 西藏大学 西北大学 西安交通大学
西北工业大学 西安电子科技大学 长安大学 西北农林科技大学 陕西师范大学 兰州大学 青海大学 宁夏大学
新疆大学 石河子大学 中国矿业大学（北京） 中国石油大学（北京） 中国地质大学（北京） 宁波大学 南方科技大学
上海科技大学 中国科学院大学 国防科技大学 海军军医大学 空军军医大学
""".split())


# Only explicit campus/name relationships are used. We deliberately avoid
# fuzzy containment so that research institutes and independent joint-venture
# universities do not inherit a parent university's tier by accident.
UNIVERSITY_ALIAS_GROUPS = (
    frozenset(("哈尔滨工业大学", "哈尔滨工业大学（深圳）", "哈尔滨工业大学（威海）")),
    frozenset(("山东大学", "山东大学（威海）")),
    frozenset(("中国人民大学", "中国人民大学（苏州校区）")),
    frozenset(("大连理工大学", "大连理工大学（盘锦校区）")),
    frozenset(("东北大学", "东北大学秦皇岛分校")),
    frozenset(("电子科技大学", "电子科技大学（沙河校区）")),
    frozenset(("北京邮电大学", "北京邮电大学（宏福校区）")),
    frozenset(("中国矿业大学", "中国矿业大学（北京）")),
    frozenset(("中国石油大学", "中国石油大学（北京）", "中国石油大学（华东）")),
    frozenset(("中国地质大学", "中国地质大学（北京）", "中国地质大学（武汉）")),
    frozenset(("国防科学技术大学", "国防科技大学")),
    frozenset(("第二军医大学", "海军军医大学")),
    frozenset(("第四军医大学", "空军军医大学")),
)


def _normalize_name(value: str) -> str:
    value = re.sub(r"\s+", "", str(value or "").strip())
    return value.replace("(", "（").replace(")", "）")


def _candidate_names(name: str) -> set[str]:
    normalized = _normalize_name(name)
    if not normalized:
        return set()
    candidates = {normalized}
    for group in UNIVERSITY_ALIAS_GROUPS:
        if normalized in group:
            candidates.update(group)
            break
    return candidates


def university_tiers(name: str) -> list[str]:
    """Return ordered, independently checkable tier labels for one university."""
    candidates = _candidate_names(name)
    tiers = []
    if candidates & PROJECT_985_UNIVERSITIES:
        tiers.append("985")
    if candidates & PROJECT_211_UNIVERSITIES:
        tiers.append("211")
    if candidates & DOUBLE_FIRST_CLASS_UNIVERSITIES:
        tiers.append("双一流")
    return tiers

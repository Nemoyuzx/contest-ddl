from contestddl.university_tiers import (
    DOUBLE_FIRST_CLASS_UNIVERSITIES,
    PROJECT_211_UNIVERSITIES,
    PROJECT_985_UNIVERSITIES,
    university_tiers,
)


def test_official_snapshot_sizes():
    assert len(PROJECT_985_UNIVERSITIES) == 39
    assert len(PROJECT_211_UNIVERSITIES) == 112
    assert len(DOUBLE_FIRST_CLASS_UNIVERSITIES) == 147


def test_university_can_have_all_three_tiers():
    assert university_tiers("清华大学") == ["985", "211", "双一流"]


def test_tiers_are_independent_labels():
    assert university_tiers("上海财经大学") == ["211", "双一流"]
    assert university_tiers("上海科技大学") == ["双一流"]


def test_explicit_campus_alias_inherits_parent_tiers():
    assert university_tiers("哈尔滨工业大学（深圳）") == ["985", "211", "双一流"]
    assert university_tiers("中国地质大学（武汉）") == ["211", "双一流"]


def test_unrelated_institutions_do_not_receive_fuzzy_matches():
    assert university_tiers("中国科学院沈阳自动化研究所") == []
    assert university_tiers("香港中文大学（深圳）") == []
    assert university_tiers("深圳大学") == []


"""The static page reads this site's published snapshot, not upstream sources."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_page_loading_message_describes_local_snapshot():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert '<span id="healthText">正在读取本站快照</span>' in html
    assert "正在连接数据源" not in html


def test_page_only_fetches_local_snapshots_with_normal_browser_caching():
    script = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
    fetches = re.findall(r'\bfetch\(\s*(["\'])(.*?)\1\s*(?:,\s*([^)]*))?\)', script)
    assert [(url, options) for _, url, options in fetches] == [
        ("./data/competitions.json", ""),
        ("./data/source-status.json", ""),
    ]
    assert 'cache: "no-store"' not in script

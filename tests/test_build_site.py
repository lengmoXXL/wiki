import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest

SITE_BASE = "/blog/"
TR_DIR = Path(__file__).resolve().parent.parent / "tr"
ARTICLE_MDS = [p for p in TR_DIR.glob("*.md") if p.name != "index.md"]


@pytest.fixture(scope="session")
def dist(tmp_path_factory):
    out = tmp_path_factory.mktemp("site") / "dist"
    subprocess.run(
        [
            "doc-research",
            "build",
            str(TR_DIR),
            "-o",
            str(out),
            "--title",
            "译文集",
            "--base",
            SITE_BASE,
        ],
        check=True,
    )
    return out


def article_pages(dist):
    return {p.name: p.read_text(encoding="utf-8") for p in dist.glob("*.html") if p.name != "index.html"}


def test_every_markdown_file_is_built(dist):
    assert len(list(dist.glob("*.html"))) - 1 == len(ARTICLE_MDS)


def test_heading_ids_use_unicode_slugs(dist):
    # toc 默认 slugify 会把中文标题 id 剥成 _1、_2，正文的 GitHub 风格锚点全部失配
    for name, html in article_pages(dist).items():
        assert not re.search(r'<h[1-6] id="_\d+"', html), name


def test_all_fragment_links_resolve(dist):
    for name, html in article_pages(dist).items():
        ids = set(re.findall(r'id="([^"]+)"', html))
        anchors = set(re.findall(r'href="(#[^"]+)"', html))
        missing = {a for a in anchors if a[1:] not in ids}
        assert not missing, f"{name}: {sorted(missing)[:5]}"


def test_only_index_has_base_href(dist):
    index = (dist / "index.html").read_text(encoding="utf-8")
    assert f'<base href="{SITE_BASE}">' in index
    for name, html in article_pages(dist).items():
        assert "<base " not in html, name


def test_referenced_images_are_copied(dist):
    for name, html in article_pages(dist).items():
        for src in re.findall(r'src="(raw/[^"]+)"', html):
            assert (dist / src).is_file(), f"{name}: {src}"


def test_index_entry_links_resolve(dist):
    index = (dist / "index.html").read_text(encoding="utf-8")
    links = re.findall(r'<a class="entry-slug" href="([^"]+)"', index)
    assert links
    for href in links:
        assert (dist / unquote(href)).is_file(), href


def test_index_entries_sorted_by_year_descending(dist):
    index = (dist / "index.html").read_text(encoding="utf-8")
    links = re.findall(r'<a class="entry-slug" href="([^"]+)"', index)
    years = [
        int(m.group(1)) if (m := re.search(r"-(\d{4})", unquote(href))) else 0
        for href in links
    ]
    assert years == sorted(years, reverse=True)
    assert 'class="entry-year"' in index


def test_index_md_rendered_on_homepage(dist):
    # tr/index.md 维护的首页附加内容（推荐阅读等）须渲染进首页，且不作为文章出现
    index = (dist / "index.html").read_text(encoding="utf-8")
    extra_urls = re.findall(
        r"\]\((https?://[^)]+)\)", (TR_DIR / "index.md").read_text(encoding="utf-8")
    )
    assert extra_urls
    for url in extra_urls:
        assert f'href="{url}"' in index, url

    assert 'class="index-content"' in index

def test_index_entries_are_pinnable(dist):
    index = (dist / "index.html").read_text(encoding="utf-8")
    for md in ARTICLE_MDS:
        assert f'data-slug="{md.stem}"' in index, md.stem
    assert 'class="pin"' in index
    assert '"pins:"' in index


def test_reading_progress_is_saved(dist):
    for name, html in article_pages(dist).items():
        assert '"progress:"' in html, name


def test_theme_toggle_and_to_top_buttons(dist):
    for name, html in article_pages(dist).items():
        assert 'id="theme-toggle"' in html, name
        assert 'id="to-top"' in html, name
        assert 'localStorage' in html, name
        # 手动切换依赖 data-theme 覆盖，系统偏好用 :not([data-theme="light"]) 兜底
        assert ':root[data-theme="dark"]' in html, name
        assert ':not([data-theme="light"])' in html, name


def test_unified_toc_collapses_on_narrow_screens(dist):
    # 目录只有一份（#toc）：桌面端左侧 sticky，窄屏由 #toc-toggle 滑出；首页没有目录
    for name, html in article_pages(dist).items():
        assert 'id="toc-toggle"' in html, name
        assert "#toc.open" in html, name
        assert html.count('<nav id="toc">') == 1, name
        # md.toc 输出自带 <div class="toc">，只应出现一次（不复制两份目录）
        assert html.count('<div class="toc">') == 1, name
    index = (dist / "index.html").read_text(encoding="utf-8")
    assert 'id="toc-toggle"' not in index


def test_toc_is_scrollable(dist):
    # 目录很长（如 ddia 700+ 条），面板须被约束在视口高度内才能滚动；
    # grid 子元素上的 align-self: start 会让窄屏 fixed 定位的高度解析成内容高度，曾导致无法滚动
    for name, html in article_pages(dist).items():
        assert "align-self: start" not in html, name
        assert "overscroll-behavior: contain" in html, name


def test_toc_locates_current_entry_when_opened(dist):
    # 展开目录面板时滚动定位到当前阅读的条目，并以 accent 色高亮
    for name, html in article_pages(dist).items():
        assert 'if (toc.classList.toggle("open")) locateCurrent();' in html, name
        assert ".toc a.active { color: var(--accent); }" in html, name


def test_nested_lists_render_nested(dist):
    # mdx_truly_sane_lists：2/3 空格缩进的子列表必须渲染为嵌套 <ul>（默认渲染器会拉平）
    html = (dist / "控制论与科学方法论-2025.html").read_text(encoding="utf-8")
    assert re.search(r'<li><strong><a href="#第一章[^"]*">[^<]+</a></strong>\s*<ul>', html, re.S)

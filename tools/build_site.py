#!/usr/bin/env python3

import html
import re
import shutil
from pathlib import Path
from urllib.parse import quote

import markdown
from markdown.extensions.toc import slugify_unicode
from pygments.formatters import HtmlFormatter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TR_DIR = PROJECT_ROOT / "tr"
DIST_DIR = PROJECT_ROOT / "dist"

MD_EXTENSIONS = [
    "tables",
    "footnotes",
    # 按列表标记宽度识别嵌套（默认渲染器要求子列表缩进 4 空格，2/3 空格会被拉平）
    "mdx_truly_sane_lists",
    "toc",
    "pymdownx.superfences",
    "pymdownx.highlight",
    "pymdownx.arithmatex",
]
# 译文保留原文的 GitHub 风格锚点链接（如 #acid-的含义），slugify 须保留中文
MD_EXTENSION_CONFIGS = {
    "toc": {"slugify": slugify_unicode, "permalink": " ¶", "permalink_class": "headerlink"},
    "pymdownx.highlight": {"guess_lang": False},
    "pymdownx.arithmatex": {"generic": True},
}


IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\.\./raw/([^)]+)\)")
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# 站点发布在域名 /blog/ 路径下；首页经由根路径访问时需用 <base> 修正相对链接
SITE_BASE = "/blog/"

# 暗色变量：@media 内（跟随系统且未手动指定浅色）与 [data-theme="dark"]（手动指定暗色）各展开一次
DARK_VARS = """    --bg: #0d1117;
    --fg: #e6edf3;
    --muted: #8b949e;
    --card: #161b22;
    --border: #2d333b;
    --accent: #58a6ff;
    --accent-soft: #12233d;
    --code-bg: #161b22;
    --shadow: 0 1px 2px rgb(0 0 0 / 30%), 0 4px 16px rgb(0 0 0 / 40%);"""
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
__BASE__
<script>var t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t;</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
__PYGMENTS_LIGHT__
@media (prefers-color-scheme: dark) {
__PYGMENTS_DARK_SYSTEM__
}
__PYGMENTS_DARK_FORCED__
:root {
  --bg: #fafbfc;
  --fg: #1f2328;
  --muted: #656d76;
  --card: #ffffff;
  --border: #e5e7eb;
  --accent: #2563eb;
  --accent-soft: #eff6ff;
  --code-bg: #f6f8fa;
  --shadow: 0 1px 2px rgb(0 0 0 / 4%), 0 4px 16px rgb(0 0 0 / 6%);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
__DARK_VARS__
  }
}
:root[data-theme="dark"] {
__DARK_VARS__
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.75 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Source Han Sans SC", "Noto Sans CJK SC", "Microsoft YaHei",
    system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.topnav {
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: saturate(180%) blur(12px);
  background: color-mix(in srgb, var(--bg) 82%, transparent);
  border-bottom: 1px solid var(--border);
}
.topnav-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
}
.topnav .brand { font-weight: 650; color: var(--fg); }
.topnav .back { color: var(--muted); }
.topnav .back:hover { color: var(--accent); text-decoration: none; }

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
  color: var(--muted);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease, opacity 0.2s ease, transform 0.2s ease;
}
.icon-btn:hover { color: var(--accent); border-color: var(--accent); }
#theme-toggle { margin-left: auto; }
#to-top {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 20;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  box-shadow: var(--shadow);
  opacity: 0;
  pointer-events: none;
  transform: translateY(8px);
}
#to-top.visible { opacity: 1; pointer-events: auto; transform: none; }
#toc-toggle {
  display: none;
  position: fixed;
  left: 24px;
  bottom: 24px;
  z-index: 20;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  box-shadow: var(--shadow);
}

.hero {
  max-width: 1080px;
  margin: 0 auto;
  padding: 72px 24px 40px;
}
.hero h1 {
  margin: 0 0 12px;
  font-size: 42px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  background: linear-gradient(120deg, var(--accent), #a855f7);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero p { margin: 0; color: var(--muted); font-size: 17px; }

.cards {
  max-width: 1080px;
  margin: 0 auto;
  padding: 8px 24px 96px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.card {
  display: block;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px 24px;
  color: var(--fg);
  box-shadow: var(--shadow);
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.card:hover {
  transform: translateY(-3px);
  border-color: var(--accent);
  text-decoration: none;
}
.card .card-title { font-size: 17px; font-weight: 600; line-height: 1.5; }
.card .card-slug { margin-top: 8px; font-size: 13px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

.layout {
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 24px 96px;
  display: grid;
  grid-template-columns: 260px minmax(0, 760px);
  gap: 48px;
  justify-content: center;
}

/* 同一个 #toc 元素：桌面端为左侧 sticky 栏，窄屏变为左侧滑出面板，由 #toc-toggle 控制 */
#toc {
  position: sticky;
  top: 76px;
  max-height: calc(100vh - 100px);
  overflow: auto;
  overscroll-behavior: contain;  /* 目录滚到底后不继续滚正文 */
  padding: 16px 18px;
  font-size: 13.5px;
  line-height: 1.6;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
}
@media (max-width: 1100px) {
  .layout { grid-template-columns: minmax(0, 760px); }
  #toc-toggle { display: inline-flex; }
  #toc {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 30;
    width: 300px;
    max-width: 85vw;
    max-height: none;
    border: none;
    border-right: 1px solid var(--border);
    border-radius: 0;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }
  #toc.open { transform: none; }
}
.toc ul { list-style: none; margin: 0; padding-left: 14px; }
.toc > ul { padding-left: 0; }
.toc li { margin: 2px 0; }
.toc a { color: var(--muted); display: block; padding: 2px 0; }
.toc a:hover { color: var(--accent); text-decoration: none; }


article { min-width: 0; }
article > h1:first-child {
  margin-top: 0;
  font-size: 32px;
  line-height: 1.3;
  letter-spacing: -0.01em;
}
h1, h2, h3, h4, h5, h6 { line-height: 1.4; margin: 1.8em 0 0.7em; scroll-margin-top: 68px; }
h2 { padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.headerlink { color: var(--muted); opacity: 0; font-size: 0.8em; }
h1:hover .headerlink, h2:hover .headerlink, h3:hover .headerlink,
h4:hover .headerlink, h5:hover .headerlink, h6:hover .headerlink { opacity: 1; }
.headerlink:hover { text-decoration: none; color: var(--accent); }

p, li { overflow-wrap: break-word; }
img {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
  display: block;
  margin: 12px auto;
}
blockquote {
  margin: 16px 0;
  padding: 2px 18px;
  color: var(--muted);
  border-left: 3px solid var(--accent);
  background: var(--accent-soft);
  border-radius: 0 8px 8px 0;
  font-size: 14.5px;
}
code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.88em;
}
p code, li code, td code, blockquote code {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.15em 0.4em;
}
.highlight {
  border-radius: 12px;
  border: 1px solid var(--border);
  overflow: hidden;
  margin: 16px 0;
  box-shadow: var(--shadow);
}
.highlight pre {
  margin: 0;
  padding: 16px 18px;
  overflow-x: auto;
  font-size: 13.5px;
  line-height: 1.65;
}
.highlight code { background: none; border: none; padding: 0; font-size: inherit; }
table {
  display: block;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14.5px;
}
th, td { border: 1px solid var(--border); padding: 8px 14px; }
th { background: var(--code-bg); font-weight: 600; }
tr:nth-child(even) td { background: color-mix(in srgb, var(--code-bg) 55%, transparent); }
hr { border: none; border-top: 1px solid var(--border); margin: 40px 0; }
.footnote { font-size: 13.5px; color: var(--muted); }
mjx-container { color: inherit; overflow-x: auto; overflow-y: hidden; }
</style>
<script>
window.MathJax = {
  tex: {
    inlineMath: [["\\\\(", "\\\\)"]],
    displayMath: [["\\\\[", "\\\\]"]]
  },
  options: { skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"] }
};
</script>
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
</head>
<body>
<header class="topnav"><div class="topnav-inner">
<span class="brand">译文集</span>
__NAV_EXTRA__
<button id="theme-toggle" class="icon-btn" type="button" aria-label="切换主题">
<svg class="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
<svg class="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
</button>
</div></header>
__BODY__
<button id="to-top" class="icon-btn" type="button" aria-label="回到顶部"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg></button>
<script>
(function () {
  var root = document.documentElement;
  var media = matchMedia("(prefers-color-scheme: dark)");
  var btn = document.getElementById("theme-toggle");
  function isDark() {
    return root.dataset.theme ? root.dataset.theme === "dark" : media.matches;
  }
  function update() {
    var dark = isDark();
    btn.setAttribute("aria-label", dark ? "切换到浅色模式" : "切换到深色模式");
    btn.querySelector(".icon-sun").style.display = dark ? "" : "none";
    btn.querySelector(".icon-moon").style.display = dark ? "none" : "";
  }
  btn.addEventListener("click", function () {
    root.dataset.theme = isDark() ? "light" : "dark";
    localStorage.setItem("theme", root.dataset.theme);
    update();
  });
  media.addEventListener("change", update);
  update();

  var toTop = document.getElementById("to-top");
  addEventListener("scroll", function () {
    toTop.classList.toggle("visible", scrollY > 400);
  }, { passive: true });
  toTop.addEventListener("click", function () { scrollTo(0, 0); });

  var toc = document.getElementById("toc");
  var tocToggle = document.getElementById("toc-toggle");
  if (toc && tocToggle) {
    tocToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      toc.classList.toggle("open");
    });
    toc.addEventListener("click", function (e) {
      if (e.target.closest("a")) toc.classList.remove("open");
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#toc")) toc.classList.remove("open");
    });
  }
})();
</script>
</body>
</html>
"""

ARTICLE_BODY = """<div class="layout">
<nav id="toc">__TOC__</nav>
<article>
__CONTENT__
</article>
</div>
<button id="toc-toggle" class="icon-btn" type="button" aria-label="目录"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M8 12h12M12 18h8"/></svg></button>
"""

INDEX_BODY = """<section class="hero">
<h1>译文集</h1>
<p>分布式系统与软件工程论文、图书的中文翻译，共 __COUNT__ 篇。</p>
</section>
<section class="cards">
__CARDS__
</section>
"""


def render_page(md_text: str) -> tuple[str, str, str]:
    md = markdown.Markdown(
        extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS
    )
    content = md.convert(md_text)
    title_match = TITLE_RE.search(md_text)
    title = title_match.group(1) if title_match else ""
    return content, title, md.toc  # pyright: ignore[reportAttributeAccessIssue] toc 扩展在 convert 时动态挂载该属性


def build() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    pygments_light = HtmlFormatter(style="default").get_style_defs(".highlight")
    dark_system = HtmlFormatter(style="monokai").get_style_defs(
        ':root:not([data-theme="light"]) .highlight'
    )
    dark_forced = HtmlFormatter(style="monokai").get_style_defs(
        '[data-theme="dark"] .highlight'
    )

    entries = []
    for md_path in sorted(TR_DIR.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        images = IMAGE_RE.findall(text)
        text = IMAGE_RE.sub(r"![](raw/\1)", text)

        for rel in images:
            src = PROJECT_ROOT / "raw" / rel
            dst = DIST_DIR / "raw" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        content, title, toc = render_page(text)
        title = title or md_path.stem
        page = (
            PAGE_TEMPLATE.replace("__PYGMENTS_LIGHT__", pygments_light)
            .replace("__PYGMENTS_DARK_SYSTEM__", dark_system)
            .replace("__PYGMENTS_DARK_FORCED__", dark_forced)
            .replace("__DARK_VARS__", DARK_VARS)
            .replace("__TITLE__", html.escape(title))
            .replace("__BASE__", "")
            .replace("__NAV_EXTRA__", '<a class="back" href="index.html">← 返回首页</a>')
            .replace(
                "__BODY__",
                ARTICLE_BODY.replace("__CONTENT__", content).replace("__TOC__", toc),
            )
        )
        (DIST_DIR / f"{md_path.stem}.html").write_text(page, encoding="utf-8")
        entries.append((md_path.stem, title))
        print(f"built {md_path.stem}.html ({len(images)} images)")

    cards = "\n".join(
        f'<a class="card" href="{quote(slug)}.html">'
        f'<div class="card-title">{html.escape(title)}</div>'
        f'<div class="card-slug">{html.escape(slug)}</div></a>'
        for slug, title in entries
    )
    index = (
        PAGE_TEMPLATE.replace("__PYGMENTS_LIGHT__", pygments_light)
        .replace("__PYGMENTS_DARK_SYSTEM__", dark_system)
        .replace("__PYGMENTS_DARK_FORCED__", dark_forced)
        .replace("__DARK_VARS__", DARK_VARS)
        .replace("__TITLE__", "译文集")
        .replace("__BASE__", f'<base href="{SITE_BASE}">')
        .replace("__NAV_EXTRA__", "")
        .replace(
            "__BODY__",
            INDEX_BODY.replace("__COUNT__", str(len(entries))).replace(
                "__CARDS__", cards
            ),
        )
    )
    (DIST_DIR / "index.html").write_text(index, encoding="utf-8")
    print(f"built index.html ({len(entries)} articles)")


if __name__ == "__main__":
    build()

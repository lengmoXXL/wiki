#!/usr/bin/env python3
"""重新生成 tr/index.md 的首页条目块。

条目块由 HTML 注释标记包围，标记外的内容（推荐阅读等）不动；
标记不存在时在首个二级标题前插入。排序：slug 尾缀年份倒序，同年按 slug 字典序。
"""

import re
from pathlib import Path

TR_DIR = Path(__file__).resolve().parent.parent / "tr"
BEGIN = "<!-- doc-research:entries -->"
END = "<!-- /doc-research:entries -->"
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---(?:\n|$)", re.S)
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def main() -> int:
    index_md = TR_DIR / "index.md"
    text = index_md.read_text(encoding="utf-8") if index_md.exists() else ""

    articles = []
    for md_path in sorted(TR_DIR.glob("*.md")):
        if md_path.name == "index.md":
            continue
        body = FRONTMATTER_RE.sub("", md_path.read_text(encoding="utf-8"), count=1)
        m = TITLE_RE.search(body)
        title = (m.group(1) if m else md_path.stem).replace("[", "(").replace("]", ")")
        articles.append((md_path.stem, title))

    def sort_key(item):
        slug = item[0]
        m = re.search(r"-(\d{4})$", slug)
        return (-int(m.group(1)) if m else 0, slug)

    articles.sort(key=sort_key)
    block = "\n".join([BEGIN] + [f"- [{t}]({s}.md)" for s, t in articles] + [END])

    if BEGIN in text and END in text:
        new_text = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S
        )
    else:
        section = f"## 文章\n\n{block}\n"
        m = re.search(r"^## ", text, re.M)
        if m:
            new_text = text[: m.start()] + section + "\n" + text[m.start() :]
        else:
            new_text = text.rstrip("\n") + ("\n\n" if text.strip() else "") + section

    if new_text == text:
        print(f"已是最新: {index_md}（{len(articles)} 篇）")
        return 0
    index_md.write_text(new_text, encoding="utf-8")
    print(f"已更新: {index_md}（{len(articles)} 篇）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

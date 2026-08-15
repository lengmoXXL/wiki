#!/usr/bin/env python3
"""把超长的译文行按标点断开（只拆不并）。用法：python tools/format.py tr/xxx.md …

约定见 README.md：正文按标点换行，一行尽可能短。行内公式、链接、斜体等片段
保持完整；代码块、表格、图片行、脚注定义与参考文献章节不参与换行。
"""

import re
import sys
from pathlib import Path

WIDTH = 60

# 允许作为行尾的标点
BREAK_CHARS = "，。、；：？！）〕】》」』,;:?!)]"
# 不可跨行的片段
HARD_RES = [
    re.compile(r"\$[^$]+\$"),             # 行内公式
    re.compile(r"`[^`]+`"),               # 行内代码
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),  # 图片
    re.compile(r"\[[^\]]*\]\([^)]*\)"),   # 链接
    re.compile(r"<[^>]+>"),               # 裸 URL
]
# 无标点断点时允许在内部空格处跨行的片段（斜体由 star_spans 单独配对）
SOFT_RES = [
    re.compile(r"\[[^\]]*\]"),            # 引用标记 [Lam01a, §2.4]
]
SKIP_RES = [
    re.compile(r"^\|"),                   # 表格
    re.compile(r"^!\["),                  # 图片引用行（alt 须单行）
    re.compile(r"^\$\$"),                 # 块级公式
    re.compile(r"^\[\^"),                 # 脚注定义
    re.compile(r"^<a "),                  # 锚点
]
PREFIX_RE = re.compile(r"^(\s*(?:[-*]|\d+\.)\s+|(?:>\s?)+|\s+)")  # 列表标记 / 引用前缀 / 裸缩进


def star_spans(text):
    """成对的单星号（斜体）区间；** 粗体标记不参与配对。"""
    stars, i = [], 0
    while i < len(text):
        if text[i] == "*":
            if i + 1 < len(text) and text[i + 1] == "*":
                i += 2
                continue
            stars.append(i)
        i += 1
    return [(a, b + 1) for a, b in zip(stars[::2], stars[1::2])]


def spans(res, text):
    return [(m.start(), m.end()) for r in res for m in r.finditer(text)]

def in_span(i, ss):
    return any(s < i + 1 < e for s, e in ss)


def wrap(text, width):
    """把 text 拆成若干行，每行不超过 width（无断点时允许超出）。"""
    hard, soft = spans(HARD_RES, text), spans(SOFT_RES, text) + star_spans(text)
    lines = []
    while len(text) > width:
        n = len(text)
        # 断点须在其后还留有足够内容（忽略行尾空格），避免产生只有标点的孤行
        rest_len = lambda i: len(text[i + 1:].strip())
        punct = [i for i, ch in enumerate(text) if ch in BREAK_CHARS
                 and rest_len(i) >= 4 and not in_span(i, hard + soft)]
        under = [p for p in punct if p < width] or [
            p for p, ch in enumerate(text)
            if ch == " " and rest_len(p) >= 4 and not in_span(p, hard) and p < width]
        if under:
            cut = max(under)
        else:
            after = [p for p in punct if rest_len(p) >= 8]
            if not after:
                break
            cut = min(after)
        rest = text[cut + 1:].lstrip()
        lines.append(text[:cut + 1].rstrip())
        shift = n - len(rest)
        text = rest
        hard = [(max(0, s - shift), e - shift) for s, e in hard if e > cut + 1]
        soft = [(max(0, s - shift), e - shift) for s, e in soft if e > cut + 1]
    lines.append(text)
    return lines


def format_lines(lines):
    out = []
    fence = bib = False
    for line in lines:
        if line.lstrip().startswith("```"):
            fence = not fence
        elif line.startswith("#"):
            bib = "参考文献" in line
        elif (not fence and not bib and line.strip()
              and not any(r.match(line) for r in SKIP_RES)):
            m = PREFIX_RE.match(line)
            prefix = m.group(1) if m else ""
            if len(line) > WIDTH:
                indent = prefix if prefix.startswith(">") else " " * len(prefix)
                first, *rest = wrap(line[len(prefix):], WIDTH - len(prefix))
                out.append(prefix + first)
                out.extend(indent + part for part in rest)
                continue
        out.append(line)
    return out


def main(paths):
    for path in map(Path, paths):
        text = path.read_text(encoding="utf-8")
        ended = text.endswith("\n")
        lines = text.split("\n")[:-1] if ended else text.split("\n")
        path.write_text("\n".join(format_lines(lines)) + ("\n" if ended else ""),
                        encoding="utf-8")
        print(f"formatted {path}")


if __name__ == "__main__":
    main(sys.argv[1:])

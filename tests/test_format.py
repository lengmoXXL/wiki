import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import format as fmt


def run(lines):
    return fmt.format_lines(lines)


def test_long_line_splits_at_punctuation():
    line = "其中与本文尤其相关的例子包括 Disk Paxos [GL03]、Cheap Paxos [LM04]、Fast Paxos [Lam05a] 和 Egalitarian Paxos [MAK13]。"
    out = run([line])
    assert len(out) == 2
    assert all(len(l) <= fmt.WIDTH for l in out)
    assert out[0].endswith("、") or out[0].endswith("]")
    joined = out[0] + "".join(l.lstrip() for l in out[1:])
    assert joined.replace(" ", "") == line.replace(" ", "")


def test_no_split_inside_math():
    line = "proposer 只有在收到 $\lfloor n_a/2, \rfloor + 1$ 个 acceptor 的承诺之后，才提出值，并且还要再写一段足够长的正文。"
    out = run([line])
    for l in out:
        assert l.count("$") % 2 == 0


def test_skip_blocks():
    lines = [
        "# 标题不处理不处理不处理不处理不处理不处理不处理不处理不处理不处理",
        "| 表格不处理不处理不处理不处理不处理不处理不处理不处理不处理不处理 |",
        "[^ch1-1]: 脚注定义不处理不处理不处理不处理不处理不处理不处理不处理不处理。",
        "```",
        "code 不处理不处理不处理不处理不处理不处理不处理不处理不处理不处理",
        "```",
    ]
    assert run(lines) == lines


def test_list_prefix_kept():
    line = "- 感谢我已毕业的同学 Natacha Crooks、Malte Schwarzkopf、Matthew Grosvenor、Shehar Bano，"
    out = run([line])
    assert out[0].startswith("- ")
    assert all(l.startswith("  ") for l in out[1:])


def test_blockquote_keeps_prefix():
    line = "> 图 2.1：一个 acceptor 与两个 proposer 之间的 SAA 示例运行，用来展示消息时序图的用法。"
    out = run([line])
    assert all(l.startswith("> ") for l in out)


def test_star_pairing_not_confused_by_bold():
    line = ("**定义 24。** 键 $k$ 处的*系数*是一个三元组 $\\left(\\mathcal{V}_k\\right)$，"
            "其中 $\\mathcal{V}_k$ 是定义 22 中的值类型，$\\mathcal{A}_k$ 是一组*系数运算*，即某个较长的结尾内容。")
    out = run([line])
    assert all(len(l) <= fmt.WIDTH for l in out)
    joined = "".join(l.lstrip() for l in out)
    assert joined.replace(" ", "") == line.replace(" ", "")
    # 不配对错位：斜体之外的逗号成为断点
    assert len(out) >= 3
def test_indented_math_line_kept_intact():
    line = "   $\\partial\\Gamma \\to \\partial\\Gamma \\times (\\partial\\Gamma \\to \\partial^2\\Gamma)$，即某个足够长的续行内容。"
    out = run([line])
    assert out == [line] or all(l.startswith("   ") and l.strip() for l in out)
    assert "" not in out


def test_bibliography_section_untouched():
    lines = [
        "# 参考文献",
        "",
        "[OO14] Diego Ongaro and John Ousterhout. In search of an understandable consensus algorithm. *ATC'14*.",
    ]
    assert run(lines) == lines


def test_citation_starting_prose_still_wraps():
    line = "[OO14, §5.1][VRA15, §3][MPSP10, §3]，通常与 Multi-Paxos 结合使用（见 3.6 节）。"
    out = run([line])
    assert len(out) > 1
    assert all(len(l) <= fmt.WIDTH for l in out)


def test_idempotent():
    line = "Chubby 又被 GFS [GGL03] 和 Bigtable [CDG+08] 等 Google 系统用于分布式协调和元数据存储。"
    once = run([line])
    assert run(once) == once

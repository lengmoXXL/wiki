# PDF 转 Markdown 并翻译

## 当前文档

- [A Critique of Snapshot Isolation](raw/critique-of-snapshot-isolation-2012/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/critique-of-snapshot-isolation-2012.pdf`
- [Bigtable: A Distributed Storage System for Structured Data](raw/bigtable-2006/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/bigtable-2006.pdf`
- [Building Event-Driven Microservices](raw/build-event-driven-microservices-2025/content_zh.md)：`oss://lengmo-asserts/books/build-event-driven-microservices-2025.pdf`
- [Designing Data-Intensive Applications](raw/ddia-2026/content_zh.md)：`oss://lengmo-asserts/books/ddia-2026.pdf`
- [The Google File System](raw/gfs-2003/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/gfs-2003.pdf`
- [Kafka: a Distributed Messaging System for Log Processing](raw/kafka-2011/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/kafka-2011.pdf`
- [The RocksDB Experience](raw/rocksdb-2021/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/rocksdb-2021.pdf`
- [Publish/Subscribe Systems: Design and Principles](raw/pubsub-systems-design-and-principles-2012/content_zh.md)：`oss://lengmo-asserts/books/pub:sub-systems-design-and-principles-2012.pdf`
- [Scaling Memcache at Facebook](raw/scaling-memcache-facebook-2013/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/scaling-memcache-facebook-2013.pdf`

## 1. 准备环境

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

在 `.env` 中填写 OSS 和 DocMind 使用的阿里云凭据：

```dotenv
ALIBABA_CLOUD_ACCESS_KEY_ID=...
ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
```

## 2. PDF 转 Markdown

`tools/parse_docmind.py` 接收 OSS 对象 key。例如，转换 Kafka 论文：

```bash
python tools/parse_docmind.py papers/distributed-systems/kafka-2011.pdf
```

转换结果为：

```text
raw/kafka-2011/
├── content.md
└── images/
```

脚本重跑时会先删除同名目录。例如，重跑上述命令会删除并重新生成 `raw/kafka-2011/`，因此需要先保存其中的人工修改。

## 3. 校对并翻译

以 `raw/kafka-2011/content.md` 为底稿，对照 PDF 校对内容，并将译文写入 `raw/kafka-2011/content_zh.md`。

校对和翻译以具体内容为准：

- 专业术语直接使用英文即可，例如 topic、broker、schema、producer、consumer；代码中的 `producer.send("topic1", set)` 保持不变。
- 将无语义图片说明补充完整，例如把 `![figure](images/figure-0001.png)` 改为 `![图 1：Kafka 架构](images/figure-0001.png)`。
- 正文中的图号应能对应到图。例如"如图 1 所示"应对应 `图 1：Kafka 架构`；Markdown 绘制的图表或公式不要求存在图片文件。
- 原书中编号为 Figure 但实际内容是表格的，标注为 `表 X-Y` 而非 `图 X-Y`。
- 书的目录（Table of Contents）应从点线加页码的形式改为指向标题的 Markdown 锚点链接，以支持文内跳转。例如把 `Preface......  xvii` 改为 `[Preface](#preface)`。注意处理重名标题：在目标标题前插入 `<a id="..."></a>` 锚点，目录链接指向该锚点。

### O'Reilly 书籍的校对要点

O'Reilly 图书（如 DDIA）还有一些特有的校对约定：

- **告警块转换**：O'Reilly 书中"提示/注意/警告"小图标会在正文中反复出现（DocMind 可能将其识别为重复的图片，如 `figure-0002.png`），应统一转换为 GitHub 风格告警块：
  - `> [!TIP]` — 提示
  - `> [!NOTE]` — 注意/说明
  - `> [!WARNING]` — 警告
  - 参考 `raw/ddia-2026/content_zh.md` 中的实际用法。

## 4. 检查改动

```bash
git diff --check
git diff
```

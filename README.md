# PDF 转 Markdown 并翻译

## 当前文档

- [A Critique of Snapshot Isolation](raw/critique-of-snapshot-isolation-2012/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/critique-of-snapshot-isolation-2012.pdf`
- [Bigtable: A Distributed Storage System for Structured Data](raw/bigtable-2006/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/bigtable-2006.pdf`
- [Designing Data-Intensive Applications](raw/ddia-2026/content_zh.md)：`oss://lengmo-asserts/books/ddia-2026.pdf`
- [The Google File System](raw/gfs-2003/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/gfs-2003.pdf`
- [Kafka: a Distributed Messaging System for Log Processing](raw/kafka-2011/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/kafka-2011.pdf`
- [The RocksDB Experience](raw/rocksdb-2021/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/rocksdb-2021.pdf`

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

- 术语首次出现时可保留英文，例如 `主题（topic）`、`代理节点（broker）`；代码中的 `producer.send("topic1", set)` 保持不变。
- 将无语义图片说明补充完整，例如把 `![figure](images/figure-0001.png)` 改为 `![图 1：Kafka 架构](images/figure-0001.png)`。
- 正文中的图号应能对应到图。例如“如图 1 所示”应对应 `图 1：Kafka 架构`；Markdown 绘制的图表或公式不要求存在图片文件。

## 4. 检查改动

```bash
git diff --check
git diff
```

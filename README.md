# PDF 转 Markdown 并翻译

## 当前文档

- [A Critique of Snapshot Isolation](raw/critique-of-snapshot-isolation-2012/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/critique-of-snapshot-isolation-2012.pdf`
- [Bigtable: A Distributed Storage System for Structured Data](raw/bigtable-2006/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/bigtable-2006.pdf`
- [Building Event-Driven Microservices](raw/build-event-driven-microservices-2025/content_zh.md)：`oss://lengmo-asserts/books/build-event-driven-microservices-2025.pdf`
- [Designing Data-Intensive Applications](raw/ddia-2026/content_zh.md)：`oss://lengmo-asserts/books/ddia-2026.pdf`
- [The Google File System](raw/gfs-2003/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/gfs-2003.pdf`
- [Kafka: a Distributed Messaging System for Log Processing](raw/kafka-2011/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/kafka-2011.pdf`
- [The RocksDB Experience](raw/rocksdb-2021/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/rocksdb-2021.pdf`
- [Scaling Memcache at Facebook](raw/scaling-memcache-at-facebook-2013/content_zh.md)：`oss://lengmo-asserts/papers/distributed-systems/scaling-memcache-at-facebook-2013.pdf`

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

- 专业术语直接使用英文。例如 `raw/kafka-2011/content_zh.md` 中，topic、broker、producer、consumer 在中文正文中直接使用：

  > 某种特定类型的消息流由一个主题（topic）定义。生产者可以向主题发布消息；发布的消息随后存储在一组称为代理节点（broker）的服务器上。消费者可以从代理节点订阅一个或多个主题，并通过从代理节点拉取数据来消费所订阅的消息。

  代码中的类名和方法名保持不变：

  ```java
  producer = new Producer(...);
  message = new Message("测试消息字符串".getBytes());
  set = new MessageSet(message);
  producer.send("topic1", set);
  ```

- 图片处理：
  - 无语义的图片说明要补充完整，如 `![figure](images/figure-0001.png)` 改为 `![图 1：Kafka 架构](images/figure-0001.png)`。
  - 正文中的图号应能对应到图，如"Kafka 的整体架构如图 1 所示"对应 `图 1：Kafka 架构`。
  - 每张图片除引用行 `![alt](url)` 外，**下方还须紧跟一行图注** `> 图 N。<完整描述>。`（blockquote 形式）。`alt` 渲染时不可见（仅读屏/悬停显示），图注才是图片正下方读者能看到的说明；`alt` 写简短图名，图注写完整描述，二者图号须一致。例如 `raw/bigtable-2006/content_zh.md` 中：

    ```markdown
    ![图 1：一个用于存储网页的示例表切片](images/figure-0001.png)

    > 图 1。一个用于存储网页的示例表切片。行名是反转后的 URL。`contents` 列族保存页面内容，`anchor` 列族保存所有指向该页面的锚文本。Sports Illustrated 和 MY-look 的首页都引用了 CNN 首页，因此该行包含名为 `anchor:cnnsi.com` 和 `anchor:my.look.ca` 的列。每个 `anchor` 单元格只有一个版本；`contents` 列有三个版本，时间戳分别为 $t_3$、$t_5$ 和 $t_6$。
    ```

- 原书中编号为 Figure 但实际内容是表格的，标注为 `表 X-Y` 而非 `图 X-Y`。例如 `raw/ddia-2026/content_zh.md` 中：

  > 表 1-1。事务处理系统与分析系统的特征比较。

- 书的目录（Table of Contents）应从点线加页码的形式改为指向标题的 Markdown 锚点链接，以支持文内跳转。例如 `raw/ddia-2026/content_zh.md` 中：

  ```markdown
  - **[前言](#前言)**

  1. **[数据系统架构中的权衡](#数据系统架构中的权衡)**
     - [事务处理系统与分析系统](#事务处理系统与分析系统)
     - [数据仓库](#数据仓库)
  ```

  处理重名标题时，在目标标题前插入 `<a id="..."></a>` 锚点，目录链接指向该锚点：

  ```markdown
  - [小结](#chapter-1-summary)
  ```

  ```markdown
  <a id="chapter-1-summary"></a>
  ```

- 正文与译文按标点换行，句号、逗号、问号、叹号等都可断行，一行尽可能短。例如 `raw/scaling-memcache-at-facebook-2013/content_zh.md` 中：

  > 此后，
  > 我们使用"memcached"来指代源代码或运行中的二进制文件，
  > 使用"memcache"来描述分布式系统。

  Markdown 仍会把这些短行识别为同一段落。图注 blockquote 同理。图片引用行 `![alt](url)` 的 alt 须保持单行，便于 git diff 逐行查看。

### O'Reilly 书籍的校对要点

O'Reilly 图书（如 DDIA）还有一些特有的校对约定：

- **告警块转换**：O'Reilly 书中"提示/注意/警告"小图标会在正文中反复出现（DocMind 可能将其识别为重复的图片，如 `figure-0002.png`），应统一转换为 GitHub 风格告警块。例如 `raw/ddia-2026/content_zh.md` 中：

  ```markdown
  > [!NOTE]
  > **术语：前端与后端**
  >
  > ...
  ```

  ```markdown
  > [!WARNING]
  > 如果你的数据库只支持键值模型，你可能会想在应用程序代码中创建从值到 ID 的映射，以此自行实现二级索引。如果选择这条路，就必须格外小心，确保索引与底层数据保持一致。
  ```

  - `> [!TIP]` — 提示
  - `> [!NOTE]` — 注意/说明
  - `> [!WARNING]` — 警告

## 4. 检查改动

```bash
git diff --check
git diff
```

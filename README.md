# PDF 转 Markdown 并翻译

## 当前文档

- [A Critique of Snapshot Isolation](tr/critique-of-snapshot-isolation-2012.md)：`oss://lengmo-asserts/papers/distributed-systems/critique-of-snapshot-isolation-2012.pdf`
- [Bigtable: A Distributed Storage System for Structured Data](tr/bigtable-2006.md)：`oss://lengmo-asserts/papers/distributed-systems/bigtable-2006.pdf`
- [Building Event-Driven Microservices](tr/build-event-driven-microservices-2025.md)：`oss://lengmo-asserts/books/build-event-driven-microservices-2025.pdf`
- [Database Internals](tr/database-internals-2019.md)：`oss://lengmo-asserts/books/database-internals-2019.pdf`
- [Cores that don't count](tr/cores-dont-count-2021.md)：`oss://lengmo-asserts/papers/machine/cores-dont-count-2021.pdf`
- [Designing Data-Intensive Applications](tr/ddia-2026.md)：`oss://lengmo-asserts/books/ddia-2026.pdf`
- [Efficient Memory Management for Large Language Model Serving with PagedAttention](tr/llm-serving-2023.md)：`oss://lengmo-asserts/papers/llm/llm-serving-2023.pdf`
- [The Google File System](tr/gfs-2003.md)：`oss://lengmo-asserts/papers/distributed-systems/gfs-2003.pdf`
- [Just for Fun](tr/just-for-fun-2002.md)：`oss://lengmo-asserts/books/just-for-fun-2002.pdf`
- [Kafka: a Distributed Messaging System for Log Processing](tr/kafka-2011.md)：`oss://lengmo-asserts/papers/distributed-systems/kafka-2011.pdf`
- [The RocksDB Experience](tr/rocksdb-2021.md)：`oss://lengmo-asserts/papers/distributed-systems/rocksdb-2021.pdf`
- [Scalable Leader Leases for Multi Consensus Groups in CockroachDB](tr/crdb-2026.md)：`oss://lengmo-asserts/papers/distributed-systems/crdb-2026.pdf`
- [Dynamo: Amazon's Highly Available Key-value Store](tr/dynamo-2007.md)：`oss://lengmo-asserts/papers/distributed-systems/dynamo-2007.pdf`
- [Amazon DynamoDB: A Scalable, Predictably Performant, and Fully Managed NoSQL Database Service](tr/dynamo-2022.md)：`oss://lengmo-asserts/papers/distributed-systems/dynamo-2022.pdf`
- [Distributed consensus revised](tr/distributed-consensus-revised-2019.md)：`oss://lengmo-asserts/papers/distributed-systems/distributed-consensus-revised-2019.pdf`
- [Scaling Memcache at Facebook](tr/scaling-memcache-at-facebook-2013.md)：`oss://lengmo-asserts/papers/distributed-systems/scaling-memcache-at-facebook-2013.pdf`
- [Silent Data Corruptions at Scale](tr/slient-data-corruptions-at-scale-2021.md)：`oss://lengmo-asserts/papers/machine/slient-data-corruptions-at-scale-2021.pdf`
- [Software Architecture: The Hard Parts](tr/software-architecture-2021.md)：`oss://lengmo-asserts/books/software-architecture-2021.pdf`
- [控制论与科学方法论](tr/控制论与科学方法论-2025.md)：`oss://lengmo-asserts/books/控制论与科学方法论-2025.pdf`（中文原著，仅校对）
- [若干重大决策与事件的回顾](tr/若干重大决策与事件的回顾-1991.md)：`oss://lengmo-asserts/books/若干重大决策与事件的回顾-1991.epub`（中文原著，仅校对）

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

## 2. 文档转 Markdown

`tools/parse_docmind.py` 接收 DocMind 支持的 PDF、EPUB 等 OSS 对象 key。
例如，转换 Kafka 论文：

```bash
python tools/parse_docmind.py papers/distributed-systems/kafka-2011.pdf
```

转换结果为：

```text
raw/kafka-2011/
├── raw.md
└── images/
    ├── figure-0001.png
    └── ...
```

其中 `raw.md` 是 DocMind 脚本直接转换的结果，**不需要做任何修改**。
`images/` 下的图片是脚本裁剪的原始图片，同样不应修改。
脚本重跑时会覆盖 `raw.md` 和 `images/`，但不会修改 `tr/` 下的译文。

## 3. 校对并翻译

以 `raw/kafka-2011/raw.md` 为底稿，对照 PDF 校对内容，并将译文写入 `tr/kafka-2011.md`。
`tr/` 下的文件名沿用对应的 `raw/` 子目录名。
中文原著（如《控制论与科学方法论》）不需要翻译，但仍需对照 PDF 校对，结果同样写入 `tr/<原目录名>.md`。

PDF 转换得到的所有图片均保留在 `raw/<原目录名>/images/` 下，
译文以 `../raw/<原目录名>/images/figure-XXXX.png` 引用其中需要的图片。
译文提交后目录结构如下：

```text
.
├── raw/
│   └── kafka-2011/
│       ├── raw.md
│       └── images/
│           ├── figure-0001.png   # 脚本原始输出，不应修改
│           └── ...
└── tr/
    └── kafka-2011.md
```

不同文档可能用到相同的图片（如 O'Reilly 的提示图标），
这些图片仍分别保留在各自的 `images/` 目录中。

校对和翻译以具体内容为准：

- 专业术语直接使用英文，除非中文译法已广泛使用（如"三模冗余""快照隔离"）。除缩写引入外，术语不以括注附另一种语言的译名。

  缩写首次出现时须给出英文全名，写作"英文全名（缩写）"，之后直接使用缩写。例如 `tr/build-event-driven-microservices-2025.md` 中：

  > 从历史上看，队列代理限制了记录在队列中存储的 time-to-live（TTL）。

  中文译法已广泛使用的术语，引入缩写时写作"中文译名（缩写）"，如"变更数据捕获（CDC）""物联网（IoT）"。

  例如 `tr/cores-dont-count-2021.md` 中，mercurial core、CEE、SDC、fail-stop、hyperscaler 直接使用英文：

  > 我们把出现这种行为的核称为 mercurial core。mercurial 核极为罕见，但在大规模服务器集群中，我们能观察到它们造成的破坏……

  `tr/kafka-2011.md` 中的主题、代理节点等通行译法则直接使用中文：

  > 某种特定类型的消息流由一个主题定义。生产者可以向主题发布消息；发布的消息随后存储在一组称为代理节点的服务器上。消费者可以从代理节点订阅一个或多个主题，并通过从代理节点拉取数据来消费所订阅的消息。

  代码中的类名和方法名保持不变：

  ```java
  producer = new Producer(...);
  message = new Message("测试消息字符串".getBytes());
  set = new MessageSet(message);
  producer.send("topic1", set);
  ```

- 图片处理：
  - 无语义的图片说明要补充完整，
    如 `![figure](../raw/kafka-2011/images/figure-0001.png)`
    改为 `![图 1：Kafka 架构](../raw/kafka-2011/images/figure-0001.png)`。
  - 正文中的图号应能对应到图，如"Kafka 的整体架构如图 1 所示"对应 `图 1：Kafka 架构`。
  - 每张图片除引用行 `![alt](url)` 外，**下方还须紧跟一行图注** `> 图 N：<完整描述>。`（blockquote 形式）。`alt` 渲染时不可见（仅读屏/悬停显示），图注才是图片正下方读者能看到的说明；`alt` 写简短图名，图注写完整描述，二者图号须一致。例如 `tr/bigtable-2006.md` 中：

    ```markdown
    ![图 1：一个用于存储网页的示例表切片](../raw/bigtable-2006/images/figure-0001.png)

    > 图 1：一个用于存储网页的示例表切片。行名是反转后的 URL。`contents` 列族保存页面内容，`anchor` 列族保存所有指向该页面的锚文本。Sports Illustrated 和 MY-look 的首页都引用了 CNN 首页，因此该行包含名为 `anchor:cnnsi.com` 和 `anchor:my.look.ca` 的列。每个 `anchor` 单元格只有一个版本；`contents` 列有三个版本，时间戳分别为 $t_3$、$t_5$ 和 $t_6$。
    ```

- 原书中编号为 Figure 但实际内容是表格的，标注为 `表 X-Y` 而非 `图 X-Y`。例如 `tr/ddia-2026.md` 中：

  > 表 1-1：事务处理系统与分析系统的特征比较。

- 书的目录（Table of Contents）应从点线加页码的形式改为指向标题的 Markdown 锚点链接，以支持文内跳转。例如 `tr/ddia-2026.md` 中：

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

- 原书中的页码交叉引用（如"参见第 84 页的……"）在 Markdown 中没有意义，翻译时应转换为等价的表达方式：改为指向对应标题的锚点链接，或直接引用章节名。例如：

  ```markdown
  参见[识别并确定组件大小模式](#识别并确定组件大小模式)。
  ```

- 正文与译文按标点换行，句号、逗号、问号、叹号等都可断行，一行尽可能短。例如 `tr/scaling-memcache-at-facebook-2013.md` 中：

  > 此后，
  > 我们使用"memcached"来指代源代码或运行中的二进制文件，
  > 使用"memcache"来描述分布式系统。

  Markdown 仍会把这些短行识别为同一段落。图注 blockquote 同理。图片引用行 `![alt](url)` 的 alt 须保持单行，便于 git diff 逐行查看。

### O'Reilly 书籍的校对要点

O'Reilly 图书（如 DDIA）还有一些特有的校对约定：

- **告警块转换**：O'Reilly 书中"提示/注意/警告"小图标会在正文中反复出现（DocMind 可能将其识别为重复的图片，如 `figure-0002.png`），应统一转换为 GitHub 风格告警块。例如 `tr/ddia-2026.md` 中：

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

### 导出 PDF 页面图片核对
校对公式、图表细节时，可以把 PDF 对应页导出为图片直接查看。步骤如下：
1. 从 OSS 下载 PDF（凭据见 `.env`）：
   ```bash
   .venv/bin/python - <<'EOF'
   import os, oss2
   from dotenv import load_dotenv
   load_dotenv(".env")
   auth = oss2.Auth(os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"], os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"])
   bucket = oss2.Bucket(auth, "https://oss-cn-beijing.aliyuncs.com", "lengmo-asserts")
   bucket.get_object_to_file("books/控制论与科学方法论-2025.pdf", "/tmp/book.pdf")
   EOF
   ```
2. 确定页码偏移：扫描版 PDF 没有文本层，且 PDF 页索引与书页码存在固定偏移（前置页所致）。
   先用一个已知地标确定偏移量，例如某公式在书页 13、在 PDF 第 32 页（0 基索引 31），偏移即 +18；
   之后「0 基页索引 = 书页码 + 偏移 - 1」。
   不知道书页码时，可按译文行号占全文的比例估算大致范围，再用第 4 步的拼图快速扫页定位。
3. 用 pymupdf 导出整页或裁剪局部：
   ```bash
   .venv/bin/python - <<'EOF'
   import fitz
   doc = fitz.open("/tmp/book.pdf")
   page = doc[31]  # 0 基页索引
   page.get_pixmap(dpi=100).save("/tmp/page.png")  # 整页
   r = page.rect
   clip = fitz.Rect(r.width*0.25, r.height*0.55, r.width*0.85, r.height*0.80)
   page.get_pixmap(dpi=200, clip=clip).save("/tmp/crop.png")  # 局部放大
   EOF
   ```
4. 连续扫页时用 ImageMagick 拼图（每行 4 页，两行 8 页一屏）：
   ```bash
   convert p030.png p031.png p032.png p033.png +append row1.png
   convert p034.png p035.png p036.png p037.png +append row2.png
   convert row1.png row2.png -append montage.png
   ```
核对时先用整页图确认章节位置，再用 200 dpi 裁剪图逐项核对上下标、分数线和符号方向。

## 4. 检查改动

```bash
git diff --check
git diff
```

## 5. 站点发布

```bash
python tools/build_site.py              # tr/*.md → dist/
python tools/publish_site.py --dry-run  # 只打印将上传/删除的对象
python tools/publish_site.py            # 同步 dist/ → oss://lengmo-asserts/blog/
python -m pytest tests/                 # 测试
```

发布后访问 http://lengmoxxl.top/。

## 6. 调试页面

用无头 Chromium 实测 `dist/` 产物：

```python
from pathlib import Path
from playwright.sync_api import sync_playwright

exe = str(Path.home() / ".cache/ms-playwright/chromium_headless_shell-1223"
           "/chrome-headless-shell-linux64/chrome-headless-shell")  # 或 playwright install 后省略 executable_path
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    page = b.new_page(viewport={"width": 800, "height": 1000}, has_touch=True)
    page.goto(f"file://{Path('dist/ddia-2026.html').resolve()}")
    page.click("#toc-toggle")
    print(page.evaluate("() => getComputedStyle(document.getElementById('toc')).height"))
    b.close()
```

`page.evaluate` 里读计算样式、几何属性，或直接改 `el.style` 对比验证。

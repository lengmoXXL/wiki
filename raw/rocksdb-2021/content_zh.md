# 面向大规模应用的键值存储，其开发优先级的演进：RocksDB 的经验  

Siying Dong、Andrew Kryczka、Yanqin Jin，Facebook Inc.；Michael Stumm，多伦多大学  

https://www.usenix.org/conference/fast21/presentation/dong  

本文收录于第 19 届 USENIX 文件与存储技术会议论文集。  

2021 年 2 月 23–25 日  

978-1-939133-20-5  

第 19 届 USENIX 文件与存储技术会议论文集的开放获取由 USENIX 赞助。  

# 面向大规模应用的键值存储，其开发优先级的演进：RocksDB 的经验  

Siying Dong†、Andrew Kryczka†、Yanqin Jin† 和 Michael Stumm‡  

†Facebook 公司，美国加利福尼亚州门洛帕克市 Hacker Way 1 号  

$^\ddagger$多伦多大学，加拿大多伦多  

## 摘要  

RocksDB 是一种面向大规模分布式系统、针对固态硬盘（SSD）优化的键值存储。本文介绍过去八年间我们开发 RocksDB 时的优先级如何演进。这种演进既源于硬件趋势，也源于多家组织在生产环境中大规模运行 RocksDB 所积累的丰富经验。我们说明 RocksDB 的资源优化目标如何以及为何从写放大转向空间放大，再转向 CPU 利用率。运行大规模应用的经验告诉我们：需要跨不同 RocksDB 实例管理资源分配；数据格式必须保持向后和向前兼容，以支持软件增量发布；还需要为数据库复制和备份提供适当支持。从故障处理方面获得的经验则告诉我们，必须更早地、在系统的每一层检测数据损坏错误。  

## 1 引言  

RocksDB [19, 54] 是 Facebook 于 2012 年基于 Google 的 LevelDB 代码库 [22] 创建的高性能持久化键值存储引擎。它针对固态硬盘（SSD）的特性进行了优化，面向大规模（分布式）应用，并被设计成嵌入上层应用的库组件。因此，每个 RocksDB 实例只管理单个服务器节点存储设备上的数据；它不处理复制、负载均衡等任何跨主机操作，也不执行检查点等高层操作——这些操作由应用自行实现，但 RocksDB 会提供适当支持，使应用能够高效完成它们。  

RocksDB 及其各个组件具有很强的可定制性，因而可以让存储引擎适应广泛的需求和工作负载。可定制项包括预写日志（WAL）的处理方式、压缩策略，以及压实策略（即移除失效数据并优化 LSM 树的过程，详见 §2）。RocksDB 可以针对高写吞吐量、高读吞吐量、空间效率或介于其间的目标进行调优。由于配置灵活，许多应用都在使用 RocksDB，覆盖非常广泛的使用场景。仅在 Facebook 内部，就有 30 多种不同应用使用 RocksDB，合计存储数百 PB 的生产数据。除了作为*数据库*的存储引擎（例如 MySQL [37]、Rocksandra [6]、CockroachDB [64]、MongoDB [40] 和 TiDB [27]）之外，RocksDB 还用于以下特征差异很大的服务类型（汇总于表 1）：  

• **流处理：** RocksDB 用于存储 Apache Flink [12]、Kafka Streams [31]、Samza [43] 和 Facebook Stylus [15] 中的暂存数据。  

• **日志/队列服务：** Facebook 的 LogDevice [5]（同时使用 SSD 和 HDD）、Uber 的 Cherami [8] 以及 Iron.io [29] 都使用 RocksDB。  

• **索引服务：** Facebook 的 Dragon [59] 和 Rockset [58] 使用 RocksDB。  

• **SSD 缓存：** Netflix EVCache [7]、奇虎 Pika [51] 和 Redis [46] 等内存缓存服务，使用 RocksDB 将从 DRAM 淘汰的数据存储到 SSD 上。  

此前的一篇论文分析了使用 RocksDB 的若干数据库应用 [11]。表 2 汇总了从生产工作负载中获得的一些关键系统指标。  

能够支持多种使用场景的存储引擎具有一项优势：不同应用可以共用同一个存储引擎。事实上，让每个应用自行构建存储子系统会带来问题，因为这项工作颇具挑战。即使是简单的应用，也需要使用校验和防范介质损坏，保证崩溃后的数据一致性，以正确顺序发出恰当的系统调用来保证写入持久性，并正确处理文件系统返回的错误。一套成熟的通用存储引擎能够在所有这些方面提供完善能力。  

当客户端应用运行在共同的基础设施中时，采用通用存储引擎还会带来更多好处：监控框架、性能剖析设施和调试工具都可以共享。例如，一家公司内部不同应用的负责人可以利用同一套内部框架，将统计数据上报到同一个仪表板，使用相同工具监控系统，并通过同一项嵌入式管理服务来管理 RocksDB。这种整合不仅让不同团队能够轻松复用专业知识，还能将信息汇总到共同门户，并促进管理工具的开发。  

| |读/写|读取类型|特殊特征|
| ---|---|---|---|
| 数据库|混合|Get + 迭代器|事务与备份|
| 流处理|写密集|Get 或迭代器|时间窗口与检查点|
| 日志/队列|写密集|迭代器|也支持 HDD|
| 索引服务|读密集|迭代器|批量装载|
| 缓存|写密集|Get|可丢弃数据|  

>表 1：RocksDB 的使用场景及其工作负载特征  

| |CPU|空间利用率|闪存耐久度|读带宽|
| ---|---|---|---|---|
| 流处理|11%|48%|16%|1.6%|
| 日志/队列|46%|45%|7%|1.0%|
| 索引服务|47%|61%|5%|10.0%|
| 缓存|3%|78%|74%|3.5%|  

>表 2：各应用类别中一个典型使用场景的系统指标。  

鉴于采用 RocksDB 的应用如此多样，其开发优先级自然也会不断演进。本文介绍过去八年中，随着我们从现实世界的应用（包括 Facebook 内部及其他组织的应用）中获得实践经验并观察到硬件趋势变化，开发优先级如何演进，以及我们如何因此重新审视一些早期假设。我们还会介绍 RocksDB 在不久将来的开发重点。  

§2 提供 SSD 和日志结构合并（LSM）树 [45] 的背景知识。RocksDB 从一开始就选择 LSM 树作为主要数据结构，以应对读写性能不对称以及闪存 SSD 耐久度有限的问题。我们认为，LSM 树一直很好地服务于 RocksDB，并主张即使面对即将到来的硬件趋势，它仍将十分适用（§3）。LSM 树这种数据结构，是 RocksDB 能够适应需求迥异的不同应用类型的原因之一。  

§3 介绍我们的主要优化目标如何从最小化写放大转向最小化空间放大，以及如何从优化性能转向优化效率。  

§4 介绍我们在服务大规模分布式系统时获得的经验，例如：（i）单台服务器可能托管多个 RocksDB 实例，因此必须跨实例管理资源分配；（ii）RocksDB 软件更新以增量方式部署或回滚，因此数据格式必须向后和向前兼容；（iii）为数据库复制和备份提供恰当支持十分重要。  

§5 介绍我们在故障处理方面的经验。大规模分布式系统通常通过复制实现容错和高可用。不过，要达到这一目标，必须妥善处理单节点故障。我们发现，仅仅识别并传播文件系统错误和校验和错误还不够。相反，必须尽早识别每一层中的故障（例如位翻转），并且应用应当能够指定策略，在可能的情况下自动处理这些故障。  

§6 阐述我们对改进键值接口的思考。核心接口凭借其灵活性，虽然简单却很强大，但它也限制了某些关键使用场景的性能。我们会介绍对独立于键和值的用户自定义时间戳的支持。  

§8 列出了 RocksDB 可以从未来研究中受益的几个领域。  

## 2 背景  

闪存的特性深刻影响了 RocksDB 的设计。读写性能的不对称以及有限的耐久度，给数据结构和系统架构的设计既带来挑战，也带来机遇。因此，RocksDB 采用对闪存友好的数据结构，并针对现代硬件进行优化。  

### 2.1 基于闪存 SSD 的嵌入式存储  

过去十年间，我们见证了基于闪存的 SSD 在在线数据服务中的普及。低延迟、高吞吐量的设备不仅要求软件充分利用其全部能力，也改变了许多有状态服务的实现方式。SSD 在读写两方面都能提供每秒数十万次输入/输出操作（IOPS），比旋转式硬盘快数千倍，还可以支持每秒数百 MB 的带宽。不过，由于编程/擦除周期的次数有限，高写带宽无法长期维持。这些因素给了我们重新思考存储引擎数据结构、使之针对这类硬件优化的机会。  

SSD 的高性能在很多情况下还使延迟和吞吐量的瓶颈都从设备 I/O 转移到了网络。对应用而言，采用本地 SSD 存储数据，而不是使用远程数据存储服务，成为更有吸引力的架构选择。这增加了对嵌入应用中的键值存储引擎的需求。  

![图](images/figure-0001.png)

>图 1：采用分层压实的 RocksDB LSM 树。每个白色方框都是一个 SSTable。  

RocksDB 正是为满足这些要求而创建的。我们希望构建一种灵活的键值存储，使用本地 SSD 驱动器服务广泛的应用，同时针对 SSD 的特性进行优化。LSM 树在实现这些目标的过程中发挥了关键作用。  

### 2.2 RocksDB 架构  

RocksDB 使用日志结构合并（LSM）树 [45] 作为存储数据的主要数据结构。  

写入。 每当数据写入 RocksDB 时，它都会被加入名为 MemTable 的内存写缓冲区，同时也写入磁盘上的预写日志（WAL）。MemTable 实现为跳表，使数据保持有序，插入和搜索开销为 O(log n)。WAL 用于故障后的恢复，但并非强制使用。MemTable 大小达到配置值后：（i）该 MemTable 和 WAL 变为不可变；（ii）为后续写入分配新的 MemTable 和 WAL；（iii）把 MemTable 的内容刷写到磁盘上的“有序字符串表”（Sorted String Table，SSTable）数据文件；（iv）丢弃已刷写的 MemTable 及相关 WAL。每个 SSTable 都按有序形式存储数据，并划分为大小一致的块。每个 SSTable 还带有一个索引块，其中每个 SSTable 数据块对应一个索引项，以支持二分查找。  

压实。 LSM 树包含多个层级的 SSTable，如图 1 所示。最新的 SSTable 由 MemTable 刷写产生，并置于 Level-0。高于 Level-0 的层级由称为压实的过程创建。给定层级上 SSTable 的总大小受配置参数限制。当层级 L 超过其目标大小时，系统会选取层级 L 中的一些 SSTable，并与层级 (L+1) 中键范围重叠的 SSTable 合并。在此过程中，已删除和已覆盖的数据会被移除，同时表会针对读取性能和空间效率进行优化。该过程逐渐把写入的数据从 Level-0 向最后一层迁移。压实 I/O 可以并行执行，而且只涉及整个文件的批量读写，因此效率很高。  

Level-0 的 SSTable 之间键范围相互重叠，因为每个 SSTable 都覆盖一个完整的有序游程。后续每一层仅包含一个有序游程，因此这些层中的 SSTable 构成该层有序游程的一个分区。  

*读取。* 在读取路径中，系统会在连续的各个层级查找一个键，直到找到该键，或确定最后一层也不存在该键。查找从所有 MemTable 开始，然后是所有 Level-0 SSTable，接着是逐层升高的 SSTable。每个层级都使用二分查找。布隆过滤器用于避免在 SSTable 文件内执行不必要的搜索。扫描则需要搜索所有层级。  

| 压实方式|写放大|最大空间开销|平均空间开销|使用布隆过滤器时每次 Get() 的 I/O 数|不使用过滤器时每次 Get() 的 I/O 数|迭代器每次 seek 的 I/O 数|
| ---|---|---|---|---|---|---|
| 分层压实|16.07|9.8%|9.5%|0.99|1.7|1.84|
| 分级压实|4.8|94.4%|45.5%|1.03|3.39|4.80|
| FIFO|2.14|N/A|N/A|1.16|528|967|  

>表 3：RocksDB 5.9 中三种主要压实方式的写放大、空间开销和读 I/O。分级压实的有序游程数设为 12；FIFO 压实则为每个键使用 20 位布隆过滤器。使用直接 I/O，块缓存大小设为完全压实后数据库大小的 10%。写放大按 SSTable 文件总写入量与已刷写 MemTable 字节数之比计算，不包括 WAL 写入。  

RocksDB 支持多种不同的压实方式。分层压实从 LevelDB 改造而来，之后又得到改进 [19]。在这种压实方式中，各层被分配指数增长的大小目标，如图 1 中的虚线框所示。分级压实（在 RocksDB 中称为通用压实）与 Apache Cassandra 或 HBase 所采用的方法类似。多个有序游程会延迟合并，直到有序游程数量过多，或数据库总大小与最大有序游程大小之比超过可配置阈值。最后，FIFO 压实会在数据库达到大小上限后直接丢弃旧文件，只执行轻量压实；它面向内存缓存应用。  

压实方式可配置，使 RocksDB 能够服务广泛的使用场景。通过采用不同压实风格，可以把 RocksDB 配置为读友好、写友好，或者针对特殊缓存工作负载的极度写友好。不过，应用负责人需要针对具体使用场景权衡不同指标 [2]。较为惰性的压实算法能够改善写放大和写吞吐量，但读取性能会受损；更积极的压实则会牺牲写性能，却能加快读取。日志或流处理服务可以使用写密集配置，数据库服务则需要更均衡的方案。表 3 以微基准测试结果展示了这种灵活性。  

![图](images/figure-0002.png)

>图 2：从 ZippyDB 和 MyRocks 应用中随机抽取 42 个样本，对其写放大和写入速率的调查。  

## 3 资源优化目标的演进  

本节介绍我们的资源优化目标如何随时间演进：从写放大，到空间放大，再到 CPU 利用率。  

### 写放大  

我们开始开发 RocksDB 时，遵循当时业界的一般看法（例如 [34]），最初关注的是节省闪存擦除周期，因而着重优化写放大。对于许多应用，尤其是写密集工作负载（表 1），这确实是一个重要目标，至今仍然如此。  

写放大会在两个层次出现。SSD 本身会引入写放大；根据我们的观察，其数值在 1.1 到 3 之间。存储和数据库软件也会产生写放大，有时可能高达 100（例如，不到 100 字节的变更却导致写出整个 4 KB、8 KB 或 16 KB 页面）。  

RocksDB 的分层压实通常会产生 10 到 30 的写放大，在许多情况下比使用 B 树好数倍。例如，在 MySQL 上运行 LinkBench 时，每个事务中 RocksDB 发出的写入量只有基于 B 树的存储引擎 InnoDB 的 5% [37]。不过，对于写密集应用，10–30 的写放大仍然过高。因此，我们加入了分级压实，将写放大降到 4–10，但读取性能也会降低；参见表 3。图 2 展示了不同数据摄入速率下 RocksDB 的写放大。写入速率较高时，RocksDB 应用负责人通常会选择一种能够降低写放大的压实方法；写入速率较低时，则更积极地压实，以实现空间效率和读取性能目标。  

### 空间放大  

经过数年开发，我们观察到，对大多数应用而言，空间利用率远比写放大重要，因为闪存写入周期和写入开销都不是限制因素。事实上，实际使用的 IOPS 相比 SSD 能够提供的数量很低（但即使忽略维护开销，也仍高到足以让 HDD 缺乏吸引力）。因此，我们把资源优化目标转向了磁盘空间。  

| |动态分层压实|动态分层压实|动态分层压实|LevelDB 风格压实|LevelDB 风格压实|LevelDB 风格压实|
| ---|---|---|---|---|---|---|
| 键数量（百万）|完全压实大小（GB）|稳态数据库大小（GB）|空间开销（%）|完全压实大小（GB）|稳态数据库大小（GB）|空间开销（%）|
| 200|12.0|13.5|12.4|12.0|15.1|25.6|
| 400|24.0|26.9|11.8|24.0|26.9|12.2|
| 600|36.0|40.4|12.2|36.4|42.5|16.9|
| 800|48.0|54.2|12.7|48.3|57.9|19.7|
| 1,000|60.1|67.5|12.4|60.3|73.8|22.4|  

>表 4：在微基准测试中测得的 RocksDB 空间效率：预先填充数据，每次写入的键从预填充键空间中随机选择。使用全部默认选项的 RocksDB 5.9，写入速率恒定为 2 MB/s。  

幸运的是，LSM 树由于采用非碎片化的数据布局，在针对磁盘空间优化时同样表现良好。不过，我们发现可以通过减少 LSM 树中的失效数据（即已删除和已覆盖的数据）来改进分层压实。我们开发了动态分层压实，其中树中每一层的大小会根据最后一层的实际大小自动调整，而不是静态设置各层大小 [19]。与分层压实相比，该方法可以获得更好、更稳定的空间效率。表 4 展示了随机写基准测试中测得的空间效率：动态分层压实将空间开销限制在 13% 以内，而分层压实可能增加超过 25% 的空间开销。此外，分层压实在最坏情况下的空间开销可高达 90%，动态分层的开销则保持稳定。事实上，Facebook 的主要数据库之一 UDB 从 InnoDB 替换为 RocksDB 后，空间占用降至原来的 50% [36]。  

### CPU 利用率  

有时人们会提出一种担忧：SSD 已经快到软件无法充分发挥其全部潜能。也就是说，使用 SSD 后，瓶颈已从存储设备转移到 CPU，因此必须从根本上改进软件。根据我们的经验，我们并不认同这种担忧；基于以下两个原因，我们也不认为它会成为未来基于 NAND 闪存的 SSD 的问题。第一，只有少数应用受 SSD 所提供 IOPS 的限制；如 §3.2 所述，大多数应用受空间限制。  

第二，我们发现，任何配备高端 CPU 的服务器都拥有足够的计算能力使一块高端 SSD 达到饱和。在我们的环境中，RocksDB 从未遇到无法充分利用 SSD 性能的问题。当然，也可以把系统配置成 CPU 成为瓶颈，例如一颗 CPU 搭配多块 SSD。但有效的系统通常会配置得较为均衡，而当今技术已经能够做到这一点。写入占绝对主导的密集工作负载也可能使 CPU 成为瓶颈。对其中一部分工作负载，可以通过配置 RocksDB 使用开销更小的压缩选项来缓解；对其他情况，该工作负载可能根本不适合 SSD，因为它会超出通常按 SSD 使用 2–5 年来设定的闪存耐久度预算。  

![图](images/figure-0003.png)

>图 3：四项指标上的资源利用率。每条线代表采用不同工作负载的一项部署。测量历时一个月，所有数值都是部署中全部主机的平均值。CPU 和读带宽采用该月中最高一小时的数值；闪存耐久度和空间利用率采用整月平均值。  

为了验证这一观点，我们调查了生产环境中 42 项不同的 ZippyDB [65] 和 MyRocks 部署，每项部署服务于不同的应用。结果如图 3 所示。大多数工作负载受空间限制。确实有一部分 CPU 负载较高，但主机通常不会被完全利用，以便为增长、数据中心或区域级故障留出余量（也可能是因为配置不当）。这些部署大多包含数百台主机，因此，考虑到工作负载可以在这些主机间自由地（重新）均衡（§4），平均值能够反映此类使用场景的资源需求。  

尽管如此，在降低空间放大方面唾手可得的优化成果已基本取得，因此降低 CPU 开销成为一项重要的优化目标。降低 CPU 开销可以改善少数真正受 CPU 限制的应用的性能。更重要的是，减少 CPU 开销的优化可以采用更具成本效益的硬件配置——直到几年前，CPU 和内存相对 SSD 还颇为便宜，但 CPU 和内存价格已大幅上涨，因此降低 CPU 开销和内存用量变得愈发重要。早期降低 CPU 开销的工作包括引入前缀布隆过滤器、在索引查找前应用布隆过滤器，以及对布隆过滤器进行其他改进。未来仍有进一步改善的空间。  

### 适应新技术  

与 SSD 相关的新架构改进很容易动摇 RocksDB 的适用地位。例如，开放通道 SSD [50, 66]、多流 SSD [68] 和 ZNS [4] 有望降低查询延迟并节省闪存擦除周期。然而，由于大多数 RocksDB 应用受空间限制，而非受擦除周期或延迟限制，这些新技术只会让少数应用受益。此外，让 RocksDB 直接适配这些技术，也会给统一的 RocksDB 使用体验带来挑战。一条值得探索的可能路径，是把适配这些技术的工作委托给底层文件系统，并由 RocksDB 提供额外提示。  

存内计算或许能够带来显著收益，但尚不清楚究竟有多少 RocksDB 应用能真正受益。我们怀疑 RocksDB 适配存内计算会颇具挑战，很可能需要改变整个软件栈的 API 才能充分利用它。我们期待未来研究能解答如何以最佳方式实现这一点。  

分离式（远程）存储似乎是更值得关注的优化目标，也是当前的优先事项。迄今为止，我们的优化都假定闪存连接在本地，因为系统基础设施主要以这种方式配置。不过，速度更快的网络目前允许在远程完成更多 I/O，因此越来越多的应用可以接受 RocksDB 搭配远程存储的性能。采用远程存储时，CPU 和 SSD 资源可以按需分别配置，因而更容易同时充分利用两者；而本地连接 SSD 很难做到这一点。因此，针对远程闪存存储优化 RocksDB 已成为优先事项。我们目前正尝试合并和并行化 I/O，以应对 I/O 延迟较长的挑战。我们已经改造 RocksDB，使其能够处理瞬态故障、向底层系统传递 QoS 要求并报告剖析信息。不过，仍需开展更多工作。  

存储级内存（SCM）是一项很有前景的技术。我们正在研究如何最大限度地利用它，有几种可能性值得考虑：1. 将 SCM 用作 DRAM 的扩展——这会引出两个问题：如何使用混合 DRAM 与 SCM 以最佳方式实现关键数据结构（例如块缓存或 MemTable），以及尝试利用其持久性时会引入哪些开销；2. 将 SCM 用作数据库的主要存储，不过需要指出，RocksDB 的瓶颈往往是空间或 CPU，而非 I/O；3. 将 SCM 用于 WAL，但考虑到我们只需要一小块暂存区，之后数据就会迁移到 SSD，仅这一使用场景是否足以证明 SCM 的成本合理，仍是一个问题。  

## 重新审视主要数据结构  

我们不断重新审视 LSM 树是否仍然合适，而结论始终是肯定的。SSD 的价格降幅还不足以改变大多数使用场景中的空间和闪存耐久度瓶颈；以更多 CPU 或 DRAM 换取更少 SSD 用量，也只对少数应用有意义。总体结论虽未改变，但我们经常听到用户要求进一步降低写放大，使其低于 RocksDB 当前能够提供的水平。不过，我们注意到，当对象较大时，可以通过分离键和值来降低写放大（例如 WiscKey [35] 和 ForestDB [1]），因此正在把这一能力加入 RocksDB（称为 BlobDB）。  

## 4 服务大规模系统的经验  

RocksDB 是许多大规模分布式系统的构建块，而这些系统的需求差异很大。随着时间推移，我们认识到，需要在资源管理、WAL 处理、批量文件删除、数据格式兼容性和配置管理方面作出改进。  

### 资源管理  

大规模分布式数据服务通常把数据划分为分片，并将分片分布到多个服务器节点上存储。分片的大小受到限制，因为分片是负载均衡和复制的基本单位，而且为此需要在节点间以原子方式复制分片。因此，每个服务器节点通常会托管数十或数百个分片。在我们的场景中，每个分片由一个独立 RocksDB 实例服务，这意味着一台存储主机会运行许多 RocksDB 实例。这些实例可以全部运行在同一个地址空间中，也可以各自运行在独立的地址空间中。  

一台主机可能运行许多 RocksDB 实例，这一事实会影响资源管理。由于这些实例共享主机资源，必须同时从全局（每台主机）和局部（每个实例）两个层面管理资源，以确保公平、高效地使用资源。在单进程模式下，设置全局资源上限非常重要，包括：（1）写缓冲区和块缓存的内存；（2）压实 I/O 带宽；（3）压实线程；（4）磁盘总用量；以及（5）文件删除速率（下文介绍）；而且可能需要按 I/O 设备分别设置这些限制。局部资源上限同样必要，例如，要确保单个实例无法过量占用任何资源。对于每一种资源，RocksDB 都允许应用创建一个或多个资源控制器（实现为传递给不同 DB 对象的 C++ 对象），也可以按实例创建。最后，还必须支持 RocksDB 实例之间的优先级划分，确保优先把资源分配给最需要的实例。  

在一个进程内运行多个实例还让我们获得了另一条经验：随意创建不属于线程池的线程可能带来问题，尤其是在这些线程生命周期很长时。线程过多会增加 CPU 竞争的概率，造成过高的上下文切换开销，使调试异常困难，并引发 I/O 峰值。如果 RocksDB 实例需要使用某个线程执行可能休眠或等待条件的工作，最好使用线程池，因为线程池的大小和资源用量很容易设定上限。  

当 RocksDB 实例运行在不同进程中时，由于每个分片只有局部信息，全局（每台主机）资源管理更具挑战性。可以采用两种策略。第一，每个实例都配置为保守使用资源，而非贪婪占用。例如，在压实方面，每个实例可以启动少于“正常”数量的压实任务，只有压实落后时才逐步增加。该策略的缺点是全局资源可能无法得到充分利用，造成次优的资源使用。第二种策略在运维上更具挑战：各实例彼此共享资源使用信息，并据此自适应，尝试从全局角度优化资源利用。要改进 RocksDB 的主机级资源管理，仍需开展更多工作。  

## WAL 处理  

传统数据库往往在每次写操作时强制写入预写日志（WAL），以确保持久性。相比之下，大规模分布式存储系统通常通过复制数据来实现性能和可用性，并提供不同程度的一致性保证。例如，如果同一份数据在多个副本中存在，其中一个副本损坏或无法访问，存储系统就会使用其他未受影响主机上的有效副本，重建故障主机的副本。对这类系统而言，RocksDB WAL 写入没有那么关键。此外，分布式系统常常有自己的复制日志（例如 Paxos 日志），此时完全不需要 RocksDB WAL。  

我们认识到，提供 WAL 同步行为的调优选项，有助于满足不同应用的需求。具体来说，我们引入了差异化的 WAL 运行模式：（i）同步 WAL 写入；（ii）缓冲式 WAL 写入；（iii）完全不写 WAL。在缓冲式 WAL 处理方式下，系统会在后台以低优先级周期性地把 WAL 写入磁盘，从而不影响 RocksDB 流量的延迟。  

### 限速文件删除  

RocksDB 通常通过文件系统与底层存储设备交互。这些文件系统能够感知闪存 SSD；例如，启用实时丢弃的 XFS 可能在每次删除文件时向 SSD 发出 TRIM 命令 [28]。人们普遍认为 TRIM 命令能够改善性能和闪存耐久度 [21]，我们的生产经验也验证了这一点。不过，它也可能引发性能问题。事实证明，TRIM 的干扰比我们最初设想的更严重：除了更新地址映射（大多位于 SSD 的内部存储器中）之外，SSD 固件还需要把这些变更写入闪存中的 FTL$^1$ 日志，进而可能触发 SSD 内部垃圾回收，造成大量数据移动，并对前台 I/O 延迟产生负面影响。为了避免 TRIM 活动突增及相关的 I/O 延迟上升，我们对文件删除引入了速率限制，防止同时删除多个文件（这种情况会在压实后发生）。  

## 数据格式兼容性  

大规模分布式应用在许多主机上运行服务，并期望停机时间为零。因此，软件升级会跨主机增量发布；出现问题时，更新则会回滚。在持续部署 [56] 的背景下，这类软件升级发生得十分频繁；RocksDB 每月发布一个新版本。因此，不同软件版本之间的磁盘数据必须同时保持向后和向前兼容。新升级（或回滚）的 RocksDB 实例必须能够理解前一个实例存储在磁盘上的数据。此外，为了构建副本或执行负载均衡，可能需要在分布式实例间复制 RocksDB 数据文件，而这些实例可能运行着不同版本。由于缺少向前兼容保证，一些 RocksDB 部署曾遇到运维困难，这促使我们加入该项保证。  

RocksDB 不遗余力地确保数据同时保持向前和向后兼容（新功能除外）。无论从技术还是流程上看，这都很有挑战，但我们发现这份投入物有所值。为实现向后兼容，RocksDB 必须理解过去写入磁盘的所有格式，这增加了软件和维护的复杂度。为实现向前兼容，则必须能够理解未来的数据格式；我们的目标是至少维持一年的向前兼容性。部分目标可以借助通用技术实现，例如 Protocol Buffers [63] 或 Thrift [62] 所采用的技术。对于配置文件条目，RocksDB 需要能够识别新字段，并尽力判断如何应用配置或何时将其丢弃。我们持续用不同版本的 RocksDB 测试不同版本的数据。  

## 配置管理  

RocksDB 具有很强的可配置性，使应用可以针对自身工作负载进行优化。然而，我们发现配置管理颇具挑战。最初，RocksDB 沿用了 LevelDB 配置参数的方式，即把参数选项直接嵌入代码中。这造成了两个问题。第一，参数选项常常与磁盘上存储的数据绑定；如果数据文件使用一种选项创建，而新配置的 RocksDB 实例采用另一种选项，就可能无法打开这些文件，造成兼容性问题。第二，代码未显式指定的配置选项会被自动设为 RocksDB 的默认值。当 RocksDB 软件更新更改了默认配置参数（例如增加内存用量或压实并行度）时，应用有时会遭遇意外后果。  

>$^{1}$FTL：闪存转换层（Flash Translation Layer）。  

| 配置领域：|压实|I/O|压缩|SSTable 文件|插件函数|
| ---|---|---|---|---|---|
| 配置数：|14|4|2|7|6|  

>表 5：39 项 ZippyDB 部署所使用的不同配置数量  

为了解决这些问题，RocksDB 首先加入了让 RocksDB 实例使用字符串参数打开数据库的能力，该参数中包含配置选项。之后，RocksDB 又支持把选项文件与数据库一同存储（可选）。我们还引入了两个工具：（i）验证工具，用于验证打开数据库的选项是否与目标数据库兼容；（ii）迁移工具，用于重写数据库，使其与所需选项兼容（不过该工具的能力有限）。  

RocksDB 配置管理中一个更严重的问题，是配置选项数量庞大。在 RocksDB 的早期，我们作出了一项支持高度定制的设计选择：引入大量新的调节项，并支持可插拔组件，所有这些都是为了让应用充分发挥性能潜力。事实证明，这一策略成功帮助 RocksDB 在早期获得采用。然而，如今常见的抱怨是选项实在太多，其效果太难理解；换言之，要指定“最优”配置已经变得非常困难。  

比需要调优大量配置参数更棘手的是，最优配置不仅取决于嵌入 RocksDB 的系统，还取决于上层应用产生的工作负载。例如，ZippyDB [65] 是内部开发的一种大规模分布式键值存储，其节点使用 RocksDB。ZippyDB 服务于许多不同应用，有时独立服务，有时采用多租户配置。尽管我们投入大量精力，尽可能在所有 ZippyDB 使用场景中采用统一配置，但不同场景的工作负载差异实在太大；当性能至关重要时，统一配置在实践中并不可行。表 5 显示，在抽样的 39 项 ZippyDB 部署中，使用了 25 种以上的不同配置。  

对于嵌入 RocksDB 并交付给第三方的系统，调优配置参数也尤其困难。设想第三方在自己的某个应用中使用 MySQL 或 ZippyDB 等数据库。第三方通常不太了解 RocksDB，也不知道如何进行最佳调优；数据库负责人也无意为客户逐一调优系统。  

这些现实经验促使我们改变配置支持策略。我们投入大量精力改善开箱即用的性能，并简化配置。目前的重点是提供自动适应能力，同时继续支持广泛的显式配置，因为 RocksDB 仍在服务专门化应用。需要指出，既追求适应能力，又保留显式可配置性，会产生大量代码维护开销；但我们认为，采用统一存储引擎的收益超过了代码复杂度带来的成本。  

## 复制与备份支持  

RocksDB 是一个单节点库。使用 RocksDB 的应用如果需要复制和备份，就要自行负责。出于合理原因，每个应用会以自己的方式实现这些功能，因此 RocksDB 为它们提供适当支持十分重要。  

通过从现有副本复制全部数据来引导新副本，可以采用两种方式。第一，可以从源副本读取所有键，再将其写入目标副本（逻辑复制）。在源端，RocksDB 支持数据扫描操作，同时提供尽量减少对并发在线查询影响的能力，例如允许选择不缓存这些操作的结果，从而避免缓存污染。在目标端，则支持批量装载，并专门针对这种场景进行了优化。  

第二，可以直接复制 SSTable 及其他文件（物理复制）来引导新副本。RocksDB 通过识别当前时点已有的数据库文件，并防止它们被删除或修改，来协助物理复制。支持物理复制是 RocksDB 把数据存储在底层文件系统上的一个重要原因，因为这样每个应用都可以使用自己的工具。我们认为，让 RocksDB 直接使用块设备接口或与 FTL 深度集成所带来的潜在性能收益，不足以抵消上述好处。  

备份是大多数数据库及其他应用的一项重要功能。对于备份，应用与复制一样可以在逻辑方式和物理方式之间选择。备份与复制的一项区别是，应用常常需要管理多个备份。尽管大多数应用会自行实现备份以满足自身要求，但如果备份需求简单，也可以使用 RocksDB 提供的备份引擎。  

我们看到该领域还有两个方面可以进一步改进，但二者都要求修改键值 API，详见 §6。第一个方面涉及在不同副本上以一致顺序应用更新，这会带来性能挑战。第二个方面涉及写请求逐一发出所造成的性能问题，以及副本可能落后、应用希望其更快追赶这一事实。不同应用已经实现了多种方案来解决这些问题，但它们都有局限 [20]。难点在于，应用无法乱序发出写入，也无法使用自己的序列号执行快照读取，因为 RocksDB 目前不支持带用户自定义时间戳的多版本机制。  

## 5 故障处理方面的经验  

通过生产实践，我们在故障处理方面获得了三条主要经验。第一，需要尽早检测数据损坏，以最大限度降低数据不可用或丢失的风险，并在此过程中准确定位错误源头。第二，完整性保护必须覆盖整个系统，以防静默损坏暴露给 RocksDB 客户端，或传播到其他副本（见图 4）。第三，需要区别对待不同错误。  

### 静默损坏的频率  

出于性能原因，RocksDB 用户通常不使用 SSD 提供的数据保护功能（例如 DIF/DIX）；存储介质损坏由 RocksDB 块校验和检测，这是所有成熟数据库的常规功能，因此本文不再分析。CPU/内存损坏确实偶尔发生，但很难准确量化。使用 RocksDB 的应用常常会运行数据一致性检查，通过比较副本来检验完整性。这可以捕获错误，但错误既可能由 RocksDB 引入，也可能由客户端应用引入（例如复制、备份或恢复数据时）。  

我们发现，可以通过比较同时具有主索引和二级索引的 MyRocks 数据库表中的这两类索引，来估算 RocksDB 层引入损坏的频率；任何不一致都应是在 RocksDB 层引入的，包括 CPU 或内存损坏。根据测量，对于每 100 PB 数据，RocksDB 层大约每三个月引入一次损坏。更糟糕的是，其中 40% 的情况下，损坏已经传播到了其他副本。  

传输数据时也会发生数据损坏，往往源于软件缺陷。例如，底层存储系统在处理网络故障时的一处缺陷，曾使我们在一段时期内每传输 1 PB 物理数据大约观察到 17 次校验和不匹配。  

## 多层保护  

需要尽早检测数据损坏，以最大限度减少停机时间和数据丢失。大多数 RocksDB 应用会把数据复制到多台主机；检测到校验和不匹配时，损坏的副本会被丢弃，并以正确副本替换。然而，只有在仍然存在正确副本的前提下，这种方案才可行。  

如今，RocksDB 会在多个层次对文件数据计算校验和，以识别其下各层的损坏。这些校验和以及计划加入的应用层校验和如图 4 所示。多层校验和很重要，主要是因为它们有助于尽早检测损坏，并且能够防范不同类型的威胁。从 LevelDB 继承的块校验和，可以防止文件系统层或其下层损坏的数据暴露给客户端。2020 年加入的文件校验和，可以防止底层存储系统造成的损坏传播到其他副本，也能防止通过网络传输 SSTable 文件时产生的损坏。对于 WAL 文件，交接校验和可以在写入时高效、尽早地检测损坏。  

块完整性。 每个 SSTable 块或 WAL 片段都附带一个校验和，在创建数据时生成。文件校验和只在移动文件时验证；与之不同，由于块校验和的作用范围较小，每次读取数据时都会对其进行验证。这样可以防止存储层损坏的数据暴露给 RocksDB 客户端。  

文件完整性。 文件内容在传输操作期间尤其容易损坏，例如执行备份或分发 SSTable 文件时。为此，每个 SSTable 都由创建表时生成的校验和保护。SSTable 的校验和记录在元数据的 SSTable 文件条目中；无论 SSTable 文件传输到哪里，都会同时验证该校验和。不过需要指出，WAL 文件等其他文件仍未受到这种方式的保护。  

交接完整性。 尽早检测写入损坏的一项成熟技术，是为将要写入底层文件系统的数据生成交接校验和，与数据一同向下传递，并由较低层进行验证 $ [48, 70] $。我们希望使用这样的写 API 保护 WAL 写入，因为与 SSTable 不同，WAL 适合在每次追加时进行增量验证。遗憾的是，本地文件系统很少支持这种功能；不过，Oracle ASM $ [49] $ 等一些专用软件栈支持它。  

另一方面，在远程存储上运行时，可以修改写 API，使其接受校验和，并接入存储服务内部的 ECC。RocksDB 可以对现有 WAL 片段校验和采用校验和组合技术，高效计算写入交接校验和。由于我们的存储服务在写入时执行验证，我们预计损坏要延迟到读取时才被发现的情况会极其罕见。  

### 端到端保护  

尽管上述各层保护在许多情况下能够防止损坏数据暴露给客户端，但它们并不全面。到目前为止所述保护的一项缺陷，是文件 I/O 层之上的数据不受保护，例如 MemTable 和块缓存中的数据。在这一层发生的数据损坏无法被检测，因而最终会暴露给用户。此外，刷写或压实操作可能会将损坏数据持久化，使损坏成为永久性的。  

*键值完整性。* 为解决这一问题，我们目前正在实现逐键值校验和，以检测文件 I/O 层之上发生的损坏。无论键/值被复制到哪里，该校验和都会一同传输；不过，如果文件数据已有其他完整性保护，我们会在其中省略该校验和。  

![图](images/figure-0004.png)

>图 4：四类校验和  

### 基于严重程度的错误处理  

RocksDB 遇到的大多数故障，都是底层存储系统返回的错误。这些错误可能源于多种问题，从只读文件系统等严重问题，到磁盘已满或访问远程存储时发生网络错误等瞬态问题。早期 RocksDB 遇到此类问题时，要么只向客户端返回错误消息，要么永久停止所有写操作。  

如今，我们的目标是只在错误无法局部恢复时才中断 RocksDB 操作；例如，瞬态网络错误不应要求用户介入并重启 RocksDB 实例。为此，我们改进了 RocksDB，使其在遇到被归类为瞬态的错误后，周期性地重试恢复操作。这带来了运维收益：对于很大一部分故障，客户端无须手动处置 RocksDB。  

## 6 键值接口方面的经验  

核心键值（KV）接口的通用性出人意料。几乎所有存储工作负载都可以由提供 KV API 的数据存储服务；我们很少见到无法用此接口实现所需功能的应用。这或许正是 KV 存储如此流行的原因。KV 接口非常通用，键和值都是变长字节数组。应用可以非常灵活地决定在每个键和值中封装什么信息，也可以从丰富的编码方案中自由选择。因此，解析和解释键值的责任落在应用上。KV 接口的另一个优点是可移植性：从一个键值系统迁移到另一个相对容易。不过，尽管许多使用场景通过这个简单接口获得了最优性能，我们也注意到它会限制某些应用的性能。  

例如，在 RocksDB 外部实现并发控制是可行的，却很难做到高效，尤其是在需要支持两阶段提交、因而事务提交前必须持久化某些数据时。正因如此，我们加入了事务支持，MyRocks（MySQL + RocksDB）使用了这项功能。我们还在不断增加功能，例如间隙/后继键锁和大事务支持。  

还有一些情况下，限制来自键值接口本身。因此，我们开始研究对基础键值接口进行可能的扩展，其中一项就是支持用户自定义时间戳。  

### 版本与时间戳  

过去几年中，我们逐渐认识到数据版本控制的重要性。我们得出的结论是：版本信息应当成为 RocksDB 中的一等公民，以便适当支持多版本并发控制（MVCC）、时间点读取等功能。要实现这一点，RocksDB 必须能够高效访问不同版本。  

迄今为止，RocksDB 一直在内部使用 56 位序列号区分不同版本的键值对。序列号由 RocksDB 生成，每次客户端写入时递增（因此所有数据在逻辑上都按序排列）。客户端应用无法影响序列号。不过，RocksDB 允许应用为数据库创建快照；此后，RocksDB 保证创建快照时存在的所有键值对都会一直保留，直到应用显式释放该快照。因此，具有同一个键的多个键值对可以同时存在，并通过序列号加以区分。  

这种版本控制方法并不充分，因为它无法满足许多应用的需求。要读取过去某个状态，必须早已在那个时间点创建快照。RocksDB 没有指定时间点的 API，因此不支持为过去创建快照。此外，以这种方式支持时间点读取效率很低。最后，每个 RocksDB 实例各自分配序列号，而且只能按单个实例获取快照。这使拥有多个分片（可能还带有副本）的应用难以进行版本控制，因为每个分片都是一个 RocksDB 实例。总而言之，要创建能够支持跨分片一致读取的数据版本，几乎不可能。  

应用可以把时间戳编码到键或值中，绕过这些限制。但无论采用哪一种方式，性能都会下降。编码到键中会牺牲点查性能；编码到值中，则会牺牲对同一个键乱序写入的性能，并使读取键的旧版本更加复杂。我们认为，由应用指定时间戳能够更好地解决这些限制：应用可以在键和值之外为数据标记可被全局理解的时间戳。  

我们已经加入了对应用指定时间戳的基础支持，并使用 DB-Bench 评估了这种方法。结果见表 6。  

| 工作负载|吞吐量提升|
| ---|---|
| fill_seq + read_random|1.2|
| fill_seq + read_while_writing|1.9|
| fill_random + read_random|1.9|
| fill_random +read_while_writing|2.0|  

>表 6：使用时间戳 API 的 DB_bench 微基准测试获得了 $\ge 1.2\text{X}$ 的吞吐量提升。  

每种工作负载都分为两个步骤：第一步填充数据库，我们在第二步测量性能。例如，在“fill_seq + read_random”中，先按升序写入若干键来填充初始数据库，再在步骤 2 中执行随机读取。与基线方法相比，应用指定时间戳 API 能够把吞吐量提高到 1.2 倍或更多；基线方法是应用把时间戳编码为键的一部分（RocksDB 无法感知）。改进来自把时间戳视为与用户键分离的元数据：这样便可使用点查而非迭代器来获取某个键的最新值，布隆过滤器也可以识别不包含该键的 SSTable。此外，可以把 SSTable 覆盖的时间戳范围存入其属性，利用该信息排除只可能包含过时值的 SSTable。  

我们希望这项功能让用户更容易在系统中实现多版本机制，无论是用于单节点 MVCC、分布式事务，还是解决多主复制中的冲突。不过，更复杂的 API 使用起来不够直观，可能容易被误用。此外，与不存储时间戳相比，数据库会占用更多磁盘空间，并且向其他系统迁移时的可移植性也会降低。  

## 7 相关工作  

RocksDB 的研发工作受益于许多领域的广泛研究。  

### 存储引擎库  

许多存储引擎都被构建为嵌入应用的库。与 BerkeleyDB [44]、SQLite [47] 和 Hekaton [18] 等系统相比，RocksDB 的 KV 接口更为原始。此外，RocksDB 与这些系统的不同之处，在于它关注现代服务器工作负载的性能；这类工作负载要求高吞吐量和低延迟，通常运行在高端 SSD 和多核 CPU 上。这与目标更为通用或针对速度更快存储介质构建的系统 [18, 30] 不同。  

### 面向 SSD 的键值存储  

多年来，人们投入大量精力优化键值存储，尤其是面向 SSD 的键值存储。早在 2011 年，SILT [34] 就提出了一种在内存效率、CPU 和性能之间取得平衡的键值存储。ForestDB [1] 使用 HB+ 树在日志之上建立索引。TokuDB [32] 等数据库使用 FractalTree/Bε 树。LOCS [67]、NoFTL-KV [66] 和 FlashKV [69] 面向开放通道 SSD，以改善性能。RocksDB 虽然从这些工作中获益，但我们改进性能的立场和策略有所不同，并继续依赖 LSM 树。若干研究比较了 RocksDB 与 InnoDB [41]、TokuDB [19][37] 和 WiredTiger [10] 等其他数据库的性能。  

### LSM 树改进  

还有若干系统使用 LSM 树并改善了其性能。写放大往往是首要优化目标，例如 WiscKey [35]、PebblesDB [52]、IAM-tree [25] 和 TRIAD [3]。这些系统在优化写放大方面比 RocksDB 更为深入，而 RocksDB 更关注不同指标之间的权衡。SlimDB [53] 针对空间效率优化 LSM 树；RocksDB 同样重视删除失效数据。Monkey [17] 尝试在 DRAM 与 IOPS 之间取得平衡。bLSM [57]、VT-tree [60] 和 cLSM [24] 则优化 LSM 树的整体性能。  

### 大规模存储系统  

分布式存储系统数量众多 $ [13, 14, 16, 26, 38, 64] $。它们通常拥有横跨多个进程、主机和数据中心的复杂架构，无法与作为单节点存储引擎库的 RocksDB 直接比较。其他系统（例如 MongoDB、MySQL $ [42] $、Microsoft SQL Server $ [38] $）可以使用模块化存储引擎；它们处理过与 RocksDB 类似的挑战，包括故障处理和时间戳的使用。  

故障处理。 校验和经常用于检测数据损坏 $ [9, 23, 42] $。我们认为既需要端到端校验和，也需要交接校验和；这一主张仍与经典的端到端论证 $ [55] $ 一脉相承，也类似于其他系统采用的策略：$ [61] $、ZFS $ [71] $、Linux $ [48] $ 和 $ [70] $。我们提出更早检测损坏，与 $ [33] $ 的观点相似，后者主张特定于领域的检查并不充分。  

时间戳支持。 若干存储系统提供时间戳支持：HBase [26]、WiredTiger [39] 和 BigTable [14]；Cassandra [13] 把时间戳作为普通列支持。在这些系统中，时间戳是从 UNIX 纪元开始计算的毫秒数。Hekaton [18] 使用单调递增计数器分配时间戳，与 RocksDB 的序列号类似。RocksDB 正在进行的用户时间戳工作，可以与上述成果互补。我们希望，扩展用户自定义时间戳的键值 API 能够让上层系统更容易支持数据版本相关功能，同时在性能和效率两方面都保持较低开销。  

## 8 未来工作与开放问题  

除了完成前文提到的改进，包括针对分离式存储进行优化、键值分离、多层校验和以及应用指定时间戳之外，我们还计划统一分层压实与分级压实，并提高适应能力。不过，以下若干开放问题可以从进一步研究中受益。  

1. 如何使用 SSD/HDD 混合存储提高效率？  

2. 连续删除标记很多时，如何减轻其对读取者的性能影响？  

3. 应当如何改进写入节流算法？  

4. 能否开发一种高效方法来比较两个副本，确保它们包含相同数据？  

5. 如何以最佳方式利用 SCM？是否仍应使用 LSM 树，又该如何组织存储层次？  

6. 能否设计一个通用的完整性 API，处理 RocksDB 与文件系统层之间的数据交接？  

### 9 结论  

RocksDB 已经从服务小众应用的键值存储，发展到如今被众多工业级大规模分布式应用广泛采用。LSM 树作为主要数据结构很好地服务了 RocksDB，因为它的写放大和空间放大表现都很出色。不过，我们对性能的看法随时间发生了演变。写放大和空间放大仍是主要关注点，但更多注意力已经转向 CPU 与 DRAM 效率，以及远程存储。  

运行大规模应用的经验告诉我们：需要跨不同 RocksDB 实例管理资源分配；数据格式必须保持向后和向前兼容，以支持软件增量部署；需要为数据库复制和备份提供恰当支持；配置管理应当直接明了，最好能够自动化。从故障处理中获得的经验则告诉我们，必须更早地、在系统的每一层检测数据损坏错误。键值接口凭借简单性而广受欢迎，但在性能方面也有一些限制。对接口作出某些简单修订，或许能取得更好的平衡。  

### 致谢  

RocksDB 的成功归功于 Facebook 现任及曾经的所有 RocksDB 团队成员、开源社区中的所有贡献者，以及 RocksDB 用户。我们尤其感谢多年来一直担任项目导师的 Mark Callaghan，以及 RocksDB 的主要创始成员 Dhruba Borthakur。我们还感谢 Jason Flinn 和 Mahesh Balakrishnan 对本文提出的意见。最后，感谢本文的指导人 Ethan Miller 和匿名审稿人提供宝贵反馈。  

>RocksDB 功能时间线  

| |性能|可配置性|功能|
| ---|---|---|---|
| 2012|多线程压实||压实过滤器；防止 SSTable 被删除|
| 2013|分级压实；前缀布隆过滤器；MemTable 布隆过滤器；供 MemTable 刷写使用的独立线程池|可插拔 MemTable；可插拔文件格式|合并操作符|
| 2014|FIFO 压实；压实限速器；缓存友好型布隆过滤器|基于字符串的配置选项；动态配置变更|备份引擎；支持多个键空间（“列族”）；物理检查点|
| 2015|动态分层压实；文件删除限速；并行执行 Level 0 和 Level 1 压实|独立配置文件；配置兼容性检查器|集成 SSTable 文件的批量装载；乐观事务与悲观事务|
| 2016|最后一层采用不同压缩方式；并行插入 MemTable|跨实例的 MemTable 总大小上限；压实迁移工具|DeleteRange()|
| 2017|最底层压实使用独立线程池；两级文件索引；Level 0 到 Level 0 的压实|块缓存和 MemTable 共用一个内存上限||
| 2018|字典压缩；数据块内的哈希索引||自动从空间不足错误中恢复；查询跟踪与重放工具|
| 2019|使用并行 I/O 的批量 MultiGet()|通过对象注册表配置插件函数|辅助实例|
| 2020|多线程单文件压缩||全文件校验和；自动从可重试错误中恢复；部分支持用户自定义时间戳|  

## B 经验总结  

我们获得的经验包括：  

1. 存储引擎能够调优以适应不同的性能特征，这一点很重要。（§1）  

2. 对大多数使用 SSD 的应用而言，空间效率是瓶颈。（$ \S $ 3，空间放大）  

3. CPU 开销变得愈发重要；降低它可以让系统运行得更高效。（$ \S $ 3，CPU 利用率）  

4. 当许多 RocksDB 实例运行在同一台主机上时，需要在全局范围按主机进行资源管理。（$ \S $ 4，资源管理）  

5. 让 WAL 处理方式可配置（同步 WAL 写入、缓冲式 WAL 写入或禁用 WAL），能够为应用带来性能优势。（$ §4 $，WAL 处理）  

6. SSD 的 TRIM 操作有利于性能，但必须对文件删除限速，以防偶发性能问题。（$ §4 $，限速文件删除）  

7. RocksDB 需要同时提供向后兼容性和“向前”兼容性。（$ §4 $，数据格式兼容性）  

8. 自动配置适应能力有助于简化配置管理。（§4，配置管理）  

9. 需要适当支持数据复制和备份。（§4，复制与备份支持）  

10. 尽早检测数据损坏，而不是最终才检测到，会带来益处。（§5）  

11. CPU/内存损坏确实会发生，虽然极其罕见，而且有时无法通过数据复制来处理。（§5）  

12. 完整性保护必须覆盖整个系统，防止损坏数据（例如 CPU/内存中的位翻转所造成的数据损坏）暴露给客户端或其他副本；只在数据静态存储或通过网络传输时检测损坏并不充分。（§5）  

13. 用户往往要求 RocksDB 自动从瞬态 I/O 错误中恢复，例如空间不足或网络问题造成的错误。（§5）  

14. 需要根据错误的原因和后果区别对待错误处理。（§5）  

15. 键值接口用途广泛，但存在一些性能限制；为键值增加时间戳，可以在性能与简单性之间取得良好平衡。（§6）  

## C 重新审视的设计选择总结  

一些经过重新审视的重要设计选择包括：  

1. 可定制性对用户总是有益的。（§4，配置管理）  

2. RocksDB 可以不感知 CPU 位翻转。（§5）  

3. 遇到任何 I/O 错误时触发严重故障是可以接受的。（§5）  

## 参考文献  

[1] Jung-Sang Ahn, Chiyoung Seo, Ravi Mayuram, Rahim Yaseen, Jin-Soo Kim, and Seungryoul Maeng. ForestDB: A fast key-value storage system for variable-length string keys. IEEE Trans. on Computers, 65(3):902–915, 2015.  

[2] Manos Athanassoulis, Michael S Kester, Lukas M Maas, Radu Stoica, Stratos Idreos, Anastasia Ailamaki, and Mark Callaghan. Designing access methods: The RUM conjecture. In Proc. Intl. Conf on Extending Database Technology (EDBT), volume 2016, pages 461–466, 2016.  

[3] Oana Balmau, Diego Didona, Rachid Guerraoui, Willy Zwaenepoel, Huapeng Yuan, Aashray Arora, Karan Gupta, and Pavan Konka. TRIAD: Creating synergies between memory, disk and log in log-structured key-value stores. In Proc. USENIX Annual Technical Conference (USENIX-ATC'17), pages 363–375, 2017.  

[4] Matias Björling. Zone Append: A new way of writing to zoned storage. In Proc. Usenix Linux Storage and Filesystems Conference (VAULT'20), 2020.  

[5] Facebook Engineering Blog. LogDevice: A distributed data store for logs. https://engineering.fb.com/core-data/logdevice-a-distributed-data-store-for-logs/. [Online; retrieved September 2020].  

[6] Instagram Engineering Blog. Open-sourcing a 10x reduction in Apache Cassandra tail latency. https://instagram-engineering.com/open-sourcing-a-10x-reduction-in-apache-cassandra-tail-latency-d64f86b43589. [Online; retrieved September 2020].  

[7] Netflix Technology Blog. Application data caching using SSDs: The Moneta project: Next generation EV-Cache for better cost optimization. https://netflixtechblog.com/application-data-caching-using-ssds-5bf25df851ef. [Online; retrieved September 2020].  

[8] Uber Engineering Blog. Cherami: Uber Engineering's durable and scalable task queue in Go. https://eng.uber.com/cherami-message-queue-system/. [Online; retrieved September 2020].  

[9] Dhruba Borthakur. HDFS architecture guide. *Hadoop Apache Project*, 53(1-13):2, 2008.  

[10] Mark Callaghan. MongoRocks and WiredTiger versus LinkBench on a small server. http://smalldatum.blogspot.com/2016/10/mongorocks-and-wiredtiger-versus.html. [Online; retrieved January 2021].  

[11] Zhichao Cao, Siying Dong, Sagar Vemuri, and David H.C. Du. Characterizing, modeling, and benchmarking RocksDB key-value workloads at Facebook. In 18th USENIX Conf. on File and Storage Technologies (FAST'20), pages 209–223, February 2020.  

[12] Paris Carbone, Asterios Katsifodimos, Stephan Ewen, Volker Markl, Seif Haridi, and Kostas Tzoumas. Apache Flink: Stream and batch processing in a single engine. Bulletin of the IEEE Computer Society Technical Committee on Data Engineering, 36(4), 2015.  

[13] Apache Cassandra. https://cassandra.apache.org/.[Online;retrievedSeptember2020].  

[14] Fay Chang, Jeffrey Dean, Sanjay Ghemawat, Wilson C Hsieh, Deborah A Wallach, Mike Burrows, Tushar Chandra, Andrew Fikes, and Robert E Gruber. Bigtable: A distributed storage system for structured data. ACM Trans. on Computer Systems (TOCS), 26(2):1–26, 2008.  

[15] Guoqiang Jerry Chen, Janet L Wiener, Shridhar Iyer, Anshul Jaiswal, Ran Lei, Nikhil Simha, Wei Wang, Kevin Wilfong, Tim Williamson, and Serhat Yilmaz. Realtime data processing at Facebook. In Proc. Intl. Conf. on Management of Data, pages 1087–1098, 2016.  

[16] James C Corbett, Jeffrey Dean, Michael Epstein, Andrew Fikes, Christopher Frost, Jeffrey John Furman, Sanjay Ghemawat, Andrey Gubarev, Christopher Heiser, Peter Hochschild, et al. Spanner: Google's globally distributed database. ACM Trans. on Computer Systems (TOCS), 31(3):1–22, 2013.  

[17] Niv Dayan, Manos Athanassoulis, and Stratos Idreos.
Monkey: Optimal navigable key-value store. In Proc.
Intl. Conf. on Management of Data (SIGMOD'17),
pages 79–94, 2017.  

[18] Cristian Diaconu, Craig Freedman, Erik Ismert, Per-Ake Larson, Pravin Mittal, Ryan Stonecipher, Nitin Verma, and Mike Zwilling. Hekaton: SQL server's memory-optimized OLTP engine. In Proc. ACM SIGMOD Intl. Conf. on Management of Data (SIGMOD'13), pages 1243–1254, 2013.  

[19] Siying Dong, Mark Callaghan, Leonidas Galanis, Dhruba Borthakur, Tony Savor, and Michael Stumm. Optimizing space amplification in RocksDB. In Proc. Conf. on Innovative Data Systems Research (CIDR'17), 2017.  

[20] Jose Faleiro. The dangers of logical replication and a practical solution. In Proc. 18th Intl. Workshop on High Performance Transaction Systems (HPTS'19), 2019.  

[21] Tasha Frankie, Gordon Hughes, and Ken Kreutz-Delgado. A mathematical model of the trim command in NAND-flash SSDs. In Proc. 50th Annual Southeast Regional Conference (ACM-SE'12), pages 59–64, 2012.  

[22] S. Ghemawat and J. Dean. LevelDB. https://github.com/google/leveldb, 2011.  

[23] Sanjay Ghemawat, Howard Gobioff, and Shun-Tak Leung. The Google File System. In Proc. 19th ACM Symp. on Operating Systems Principles (SOSP'03), pages 29–43, 2003.  

[24] Guy Golan-Gueta, Edward Bortnikov, Eshcar Hillel, and
Idit Keidar. Scaling concurrent log-structured data
stores. In *Proc. European Conf. on Computer Systems
(EUROSYS'15)*, pages 1–14, 2015.  

[25] Caixin Gong, Shuibing He, Yili Gong, and Yingchun Lei. On integration of appends and merges in log-structured merge trees. In Proc. 48th Intl. Conf. on Parallel Processing (ICPP'19), pages 1–10, 2019.  

[26] Apache HBase. https://hbase.apache.org/.[Online;retrievedSeptember2020].  

[27] Dongxu Huang, Qi Liu, Qiu Cui, Zhuhe Fang, Xiaoyu Ma, Fei Xu, Li Shen, Liu Tang, Yuxing Zhou, Menglong Huang, Wan Wei, Cong Liu, Jian Zhang, Jianjun Li, Xuelian Wu, Lingyu Song, Ruoxi Sun, Shuaipeng Yu, Lei Zhao, Nicholas Cameron, Liquan Pei, and Xin Tang. TiDB: A Raft-based HTAP database. Proc. VLDB Endow., 13(12):3072–3084, August 2020.  

[28] Intel. Trim overview. https://www.intel.com/content/www/us/en/support/articles/000016148/memory-and-storage.html.[Online;retrievedJan2021].  

[29] Iron.io. https://www.iron.io/. [Online; retrieved September 2020].  

[30] Hideaki Kimura. FOEDUS: OLTP engine for a thousand cores and NVRAM. In Proc. SIGMOD Intl. Conf. on Management of Data (SIGMOD'15), pages 691–706, 2015.  

[31] Jay Kreps. Introducing Kafka Streams: Stream processing made simple. Confluent. https://www.confluent.io/blog/introducing-kafka-streams-stream-processing-made-simple/. [Online; retrieved September 2020].  

[32] B Kuszmaul. How TokuDB fractal tree indexes work.
Technical report, Technical report, TokuTek, 2010.  

[33] Chuck Lever. End-to-end data integrity requirements for NFS. Oracle Corp. https://datatracker.ietf.org/meeting/83/materials/slides-83-nfsv4-2. [Online; retrieved September 2020].  

[34] Hyeontaek Lim, Bin Fan, David G Andersen, and Michael Kaminsky. SILT: A memory-efficient, high-performance key-value store. In Proc. 23rd ACM Symp. on Operating Systems Principles (SOSP'11), pages 1–13, 2011.  

[35] Lanyue Lu, Thanumalayan Sankaranarayana Pillai, Hariharan Gopalakrishnan, Andrea C Arpaci-Dusseau, and Remzi H Arpaci-Dusseau. WiscKey: Separating keys from values in SSD-conscious storage. ACM Trans. on Storage (TOS), 13(1):1–28, 2017.  

[36] Yoshinori Matsunobu. Migrating a database from InnoDB to MyRocks. Facebook Engineering Blog. https://engineering.fb.com/core-data/migrating-a-database-from-innodb-to-myrocks/, 2017. [Online; retrieved September 2020].  

[37] Yoshinori Matsunobu, Siying Dong, and Herman Lee.
MyRocks: LSM-tree database storage engine serving
Facebook's Social Graph. Proc. VLDB Endowment,
13(12):3217–3230, August 2020.  

[38] Microsoft. Microsoft SQL Server. https://www.microsoft.com/en-us/sql-server/.[Online;retrievedSeptember2020].  

[39] MongoDB. WiredTiger Storage Engine. https://docs.mongodb.com/manual/core/wiredtiger/.
[Online;retrievedSeptember2020].  

[40] MongoRocks. RocksDB storage engine module for MongoDB. https://github.com/mongodb-partners/mongo-rocks. [Online; retrieved September 2020].  

[41] MySQL. Introduction to InnoDB. https://dev.mysql.com/doc/refman/5.6/en/innodb-introduction.html.[Online;retrievedSeptember2020].  

[42] MySQL. MySQL. https://www.mysql.com/.[Online;retrievedSeptember2020].  

[43] Shadi A Noghabi, Kartik Paramasivam, Yi Pan, Navina Ramesh, Jon Bringhurst, Indranil Gupta, and Roy H Campbell. Samza: Stateful scalable stream processing at LinkedIn. *Proc. of the VLDB Endowment*, 10(12):1634–1645, 2017.  

[44] Michael A Olson, Keith Bostic, and Margo I Seltzer.
Berkeley DB. In USENIX Annual Technical Conference,
FREENIX Track, pages 183–191, 1999.  

[45] Patrick O'Neil, Edward Cheng, Dieter Gawlick, and Elizabeth O'Neil. The log-structured merge-tree (LSM-tree). Acta Informatica, 33(4):351–385, 1996.  

[46] Keren Ouaknine, Oran Agra, and Zvika Guz. Optimization of RocksDB for Redis on flash. In Proc. Intl. Conf. on Compute and Data Analysis, pages 155–161, 2017.  

[47] Mike Owens. *The definitive guide to SQLite*. Apress, 2006.  

[48] Martin K Petersen. Linux data integrity extensions. In
Linux Symposium, volume 4, page 5, 2008.  

[49] Martin K. Petersen and Sergio Leunissen. Eliminating silent data corruption with Oracle Linux. Oracle Corp. https://oss.oracle.com/~mkp/docs/data-integrity-webcast.pdf. [Online; retrieved September 2020].  

[50] Ivan Luiz Picoli, Niclas Hedam, Philippe Bonnet, and Pinar Tözün. Open-channel SSD (What is it good for). In Proc. Conf. on Innovative Data Systems Research (CIDR'20), 2020.  

[51] Qihoo. https://github.com/Qihoo360/pika. [Online; retrieved September 2020].  

[52] Pandian Raju, Rohan Kadekodi, Vijay Chidambaram, and Ittai Abraham. PebblesDB: Building key-value stores using fragmented log-structured merge trees. In Proc. 26th Symp. on Operating Systems Principles (SOSP'17), pages 497–514, 2017.  

[53] Kai Ren, Qing Zheng, Joy Arulraj, and Garth Gibson. SlimDB: A space-efficient key-value storage engine for semi-sorted data. *Proc. of the VLDB Endowment (VLDB'17)*, 10(13):2037–2048, 2017.  

[54] RocksDB.org. A persistent key-value store for fast storage environments. https://rocksdb.org.[Online;retrievedSeptember2020].  

[55] Jerome H Saltzer, David P Reed, and David D Clark.
End-to-end arguments in system design. ACM Trans. on
Computer Systems (TOCS), 2(4):277–288, 1984.  

[56] Tony Savor, Mitchell Douglas, Michael Gentili, Laurie Williams, Kent Beck, and Michael Stumm. Continuous deployment at Facebook and OANDA. In 2016 IEEE/ACM 38th International Conference on Software Engineering Companion (ICSE-C), pages 21–30. IEEE, 2016.  

[57] Russell Sears and Raghu Ramakrishnan. bLSM: a general purpose log-structured merge tree. In Proc. Intl. Conf. on Management of Data (SIGMOD '12), pages 217–228, 2012.  

[58] Arun Sharma. How we use RocksDB at Rockset. Rockset Blog. https://rockset.com/blog/how-we-use-rocksdb-at-rockset/. [Online; retrieved September 2020].  

[59] Arun Sharma. Dragon: A distributed graph query engine. Facebook Engineering Blog. https://engineering.fb.com/data-infrastructure/dragon-a-distributed-graph-query-engine/. [Online; retrieved September 2020].  

[60] Pradeep J Shetty, Richard P Spillane, Ravikant R Malpani, Binesh Andrews, Justin Seyster, and Erez Zadok. Building workload-independent storage with VT-trees. In Proc. 11th USENIX Conf. on File and Storage Technologies (FAST'13), pages 17–30, 2013.  

[61] Gopalan Sivathanu, Charles P Wright, and Erez Zadok.
Enhancing file system integrity through checksums.
Technical report, Citeseer, 2004.  

[62] Mark Slee, Aditya Agarwal, and Marc Kwiatkowski.
Thrift: Scalable cross-language services implementation.
Facebook White Paper, 5(8), 2007.  

[63] Google Open Source. Protobuf. https://opensource.google.com/projects/protobuf.[Online;retrievedSeptember2020].  

[64] Rebecca Taft, Irfan Sharif, Andrei Matei, Nathan Van-Benschoten, Jordan Lewis, Tobias Grieger, Kai Niemi, Andy Woods, Anne Birzin, Raphael Poss, Paul Bardea, Amruta Ranade, Ben Darnell, Bram Gruneir, Justin Jaffray, Lucy Zhang, and Peter Mattis. CockroachDB: The resilient geo-distributed SQL database. In Proc. ACM SIGMOD Intl. Conf. on Management of Data (SIGMOD'20), pages 1493–1509, 2020.  

[65] Amy Tai, Andrew Kryczka, Shobhit O. Kanaujia, Kyle Jamieson, Michael J. Freedman, and Asaf Cidon. Who's afraid of uncorrectable bit errors? Online recovery of flash errors with distributed redundancy. In 2019 USENIX Annual Technical Conference (USENIX ATC'19), pages 977–992, Renton, WA, July 2019.  

[66] Tobias Vinçon, Sergej Hardock, Christian Riegger, Julian Oppermann, Andreas Koch, and Ilia Petrov. NoFTL-KV: Tackling write-amplification on KV-stores with native storage management. In Proc. 21st Intl. Conf. on Extending Database Technology (EDBT'18), pages 457–460, 2018.  

[67] Peng Wang, Guangyu Sun, Song Jiang, Jian Ouyang, Shiding Lin, Chen Zhang, and Jason Cong. An efficient design and implementation of LSM-tree based key-value store on open-channel SSD. In Proc. 9th European Conf. on Computer Systems (EUROSYS'14), pages 1–14, 2014.  

[68] Fei Yang, K Dou, S Chen, JU Kang, and S Cho. Multi-streaming RocksDB. In Proc. Non-Volatile Memories Workshop, 2015.  

[69] Jiacheng Zhang, Youyou Lu, Jiwu Shu, and Xiongjun Qin. FlashKV: Accelerating KV performance with open-channel SSDs. ACM Trans on Embedded Computing Systems (TECS), 16(5s):1–19, 2017.  

[70] Yupu Zhang, Daniel S Myers, Andrea C Arpaci-Dusseau, and Remzi H Arpaci-Dusseau. Zettabyte reliability with flexible end-to-end data integrity. In Proc. 29th IEEE Symp. on Mass Storage Systems and Technologies (MSST'13), pages 1–14, 2013.  

[71] Yupu Zhang, Abhishek Rajimwale, Andrea C Arpaci-Dusseau, and Remzi H Arpaci-Dusseau. End-to-end data integrity for file systems: A ZFS case study. In Proc. 8th USENIX Conf. on File and Storage Technologies (FAST'10), pages 29–42, 2010.

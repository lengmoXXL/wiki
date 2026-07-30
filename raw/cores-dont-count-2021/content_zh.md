# 不算数的核心

Peter H. Hochschild、Paul Turner、Jeffrey C. Mogul、
Rama Govindaraju、Parthasarathy Ranganathan、
David E. Culler、Amin Vahdat

Google，Sunnyvale, CA, US

## 摘要

我们习惯于把计算机，
尤其是执行指令的核（core），
看作 fail-stop（失效即停）的，
大多数系统软件都隐含地依赖这一假设。
在 VLSI 时代的大部分时间里，
通过制造测试并在规格内运行的处理器，
让我们得以维持这种虚构。
随着制造工艺推向更小的特征尺寸和更复杂的计算结构，
以及为了提升性能而引入越来越多专门化的"指令—硅片"组合，
我们观察到了制造测试未能发现的短暂计算错误。
这些缺陷并不总能通过微码更新等技术来缓解，
而且可能与处理器内的特定部件相关，
使得微小的代码改动就能造成可靠性的大幅波动。
更糟的是，这些故障往往是"静默"的——唯一的症状就是计算结果错误。

我们把出现这种行为的核称为 mercurial core。
mercurial 核极为罕见，
但在大规模服务器集群中，
我们能观察到它们造成的破坏，
其频繁程度已足以让我们将其视为一个独特的问题——
一个需要硬件设计者、处理器厂商和系统软件架构师协作解决的问题。

本文呼吁系统研究界关注一个新的方向。
我们推测了若干基于软件的 mercurial 核应对方法，
从更好的检测与隔离机制，
到容忍其造成的 SDC 的方法。

## ACM 引用格式

Peter H. Hochschild, Paul Turner, Jeffrey C. Mogul, Rama Govindaraju, Parthasarathy Ranganathan, David E. Culler, and Amin Vahdat. 2021. Cores that don't count. In Workshop on Hot Topics in Operating Systems (HotOS '21), May 31–June 2, 2021, Ann Arbor, MI, USA. ACM, New York, NY, USA, 8 pages. https://doi.org/10.1145/3458336.3465297

## 1 引言

想象你正在生产环境中运行一个超大规模的数据分析流水线，
某天它开始给出错误的答案——流水线中某处，
有一类计算产生了损坏的结果。
调查指向一个令人意外的原因：对一个底层库的一次无害改动。
这次改动本身是正确的，
但它让服务器更频繁地使用一些原本很少用到的指令。
而且，反复造成错误的只是服务器机器中的一小部分。

这件事真实地发生在 Google。
更深入的调查表明，这些指令由于制造缺陷而发生故障，
其方式只有把这些指令的结果与预期结果核对才能发现；
这就是"静默"的 corrupt execution error（CEE）。
更广泛的调查发现：
CEE 有多种不同的类型；
其检出率远高于软件工程师的预期；
它们并非硬件错误本底率的简单上升；
它们可能在初次安装很久之后才显现；
而且它们通常影响多核 CPU 上的特定核，
而非整个芯片。
我们把这些核称为 mercurial 核。

由于 CEE 可能与核内特定的执行单元相关，
它们使我们在多种情况下暴露于突然且不可预测的巨大风险，
其中包括看似微小的软件改动。
hyperscaler 有责任保护客户免受此类风险。
出于商业原因，我们无法透露确切的 CEE 发生率，
但我们观察到每几千台机器中大约有几个 mercurial 核——
与 Facebook 报告的比例相近 [8]。
这个问题严重到我们已经为它投入了数十人年的工程量。

我们早就知道存储设备和网络会在数据静止或传输时损坏数据，
但我们习惯于把处理器看作 fail-stop 的。
VLSI 一直依靠复杂的制造测试来检测有缺陷的芯片。
当缺陷漏检，或随老化显现时，
人们假定它们会变成 fail-stop，
或者至少 fail-noisy：
触发机器检查（machine-check），
或对许多种指令给出错误答案。
而真正静默的故障发生时，
它们通常被那些我们总假定潜伏在大规模代码库中的、
未确诊的软件 bug 所掩盖。

为什么我们现在才发现 mercurial 核？
有许多看似合理的原因：服务器集群规模更大；
对整体可靠性更加重视；
软件开发的进步降低了软件 bug 的发生率。
但我们认为还有一个更根本的原因：
特征尺寸不断缩小，日益逼近 CMOS 缩放的极限，
再加上架构设计的复杂度不断增长。
两者共同给芯片厂商用来检测各种制造缺陷的验证方法带来了新的挑战——
尤其是那些只在边角情况中显现、
或只在部署后老化时才显现的缺陷。

尽管"CPU fail-stop"的假设从来就是一种虚构，
但我们再也不能忽视 CEE 问题了。
随着我们继续挑战硅片的极限，
并以架构创新应对摩尔定律终结造成的时钟频率之墙，
这个问题只会不断变得更难。
性能与硬件可靠性之间的权衡正变得越来越困难，
谨慎起见，我们不能指望芯片厂商永远都做对。
此外，已经存在庞大的脆弱芯片装机量，
我们需要找到可扩展的方法继续使用这些系统而不受频繁错误之苦，
而不是（以巨大代价）替换它们，
或者等上几年换取新的、更具韧性的硬件。
我们也正在进入这样一个时代：
不可靠的硬件越来越多地静默失效，
而不是 fail-stop，
这改变了我们的一些基本假设。

这对操作系统研究者来说是一个新的机会。
本文描述了这一挑战的背景、规模和风险，
并提出应对两大挑战的途径：
如何快速检测并隔离 mercurial 核，
以及如何创造更强的韧性来容忍 CEE。
（"把硬件做得更好"是另一篇论文的好题目。）

## 1.1 CEE 与 silent data corruption

大型部署的运营者早就知道 silent data corruption（SDC）：
主存、磁盘或其他存储中的数据在写入、读取或静止时被损坏，
却没有被立即发现。

我们将在第 8 节更详细地讨论部分 SDC 文献，
不过直到最近，SDC 主要被归因于随机原因，
如 α 粒子和宇宙射线，
以及超频等人为做法。
我们把 SDC 看作*症状*，
把高发生率的 CEE 看作 SDC 的一种新*病因*，
它给系统软件带来了新的挑战。

## 2 mercurial 核的影响

我们观察到 mercurial 核造成的多种症状。
下面按它们带来的风险从小到大分类：

- 几乎立即被发现的错误答案——通过自检、异常或段错误发现，或许可以自动重试。
- 机器检查，破坏性更大。
- 被发现、但发现时已来不及重试计算的错误答案。
- 永远不被发现的错误答案。

有缺陷的核常常既表现出错误结果，又表现出异常。
未被立即发现的错误答案可能带来现实世界的后果：
它们可以经由其他（正确的）计算传播，放大其影响——
例如，损坏的元数据可能导致整个文件系统丢失，
损坏的加密密钥可能使大量数据永久无法访问。
因此，mercurial 核引起的计算错误会不断复合，
显著扩大其可能造成的故障的爆炸半径。

我们对 CEE 影响的理解主要是经验性的。
我们的观察形式是"这段代码在那个核上算错了（或崩溃了）"。
我们可以控制哪些代码在哪些核上运行，
并部分控制运行条件（频率、电压、温度，即 f、V、T）。¹
借此，我们可以识别出一些 mercurial 核。
但由于我们对底层硬件细节知之甚少，
也无法使用芯片厂商拥有的硬件支持测试结构，
我们对根本原因推断不出多少。
更糟的是，我们并不总能立即发现错误的计算。

我们有一个中等规模的测试用例代码库，
其选取基于我们从生产事故、core dump 证据和故障模式猜测中形成的直觉。
这个代码库包括真实代码片段、
有意思的库（如压缩、哈希、数学、密码学、拷贝、锁、fork、系统调用），
以及一些专门编写的测试，其中一些来自 CPU 厂商。
然而，我们缺乏一套系统的方法来开发这些测试。

我们观察到的缺陷散布在许多功能中，
尽管存在一些总体规律，
也有许多（目前看来）属于离群的例子。
故障大多以可变的速率非确定性地出现。
有问题的核通常反复、间歇地失效，
并且常常随时间恶化；
我们有一些证据表明老化是一个因素。
在多核处理器中，通常只有一个核失效，
而且往往持续如此。
CEE 似乎是一个全行业的问题，
并非特定于某家厂商，
但发生率在不同 CPU 产品间并不均匀。

（给定特定工作负载或测试，）
不同缺陷核的损坏率可相差多个数量级，
而且对任何给定的核，
损坏率都可能高度依赖工作负载以及 f、V、T。
仅在少数情况下，我们能确定性地复现错误；
通常需要实现层面和环境层面的细节恰好凑齐。
数据模式也会影响损坏率，
但我们往往难以分辨。

> ¹现代 CPU 把 f 和 V 紧密耦合；
> 用户通常无法独立调节它们，而 T 在一定程度上可控。

我们见过 CEE 的一些具体例子：

- 违反锁语义，导致应用数据损坏和崩溃。
- 各种 load、store、向量和一致性操作表现出的数据损坏。
- 一次确定性的 AES 错误计算，它是"自反的"：在同一个核上加密再解密得到恒等函数，但在别处解密则得到乱码。
- 某存储系统中影响垃圾回收的损坏，导致存活数据丢失。
- 数据库索引损坏，导致某些查询的结果取决于由哪个副本（核）来服务，被非确定性地损坏。
- 字符串中特定比特位置反复出现比特翻转（显然不太可能是编码 bug）。
- 内核状态损坏，导致进程和内核崩溃以及应用故障。

CEE 比软件 bug 更难追根溯源，
因为我们通常假定可以通过在另一台机器上复现来调试软件 bug。

## 3 mercurial 核是新问题吗？

存储和网络栈的底层一直存在不可靠性。
我们已经通过冗余解决了存储故障问题，
使用纠删码、ECC 或端到端校验和等技术；
一般来说，这些技术并不需要大幅增加硬件成本或延迟。
对于容易磨损的介质，
我们可以隔离坏扇区/坏页并重映射访问，
以保住介质的可用性，
还可以 scrub 存储以检测静止数据的损坏 [21]。

类似地，为了应对网络链路上损坏的比特，
我们使用编码方案（如 CRC）来检测错误，
并通过重传不断尝试，
寄望于同一错误不会再次击中。

为什么计算错误是更难的问题？
首先，因为对于存储和网络，
"正确结果"是显然且易于校验的：就是恒等函数。
这使得基于编码的技术得以容忍中等发生率的可纠正底层错误，
换取更好的规模、速度和成本。

相反，检测 CEE 朴素地看似乎意味着多一倍的额外工作。
自动纠正似乎可能需要三倍的工作
（例如通过三模冗余）。
（第 6 节和第 7 节分别讨论检测与缓解。）
而且大多数计算故障无法用编码解决；
其中一些可以用另一种方法处理 [2]。

存储和网络之所以能更好地容忍底层错误，
是因为它们通常操作相对较大的数据块，
如磁盘块或网络包。
这让损坏校验的成本可以被摊薄，
而在逐条指令的尺度上，这样做似乎更难。

## 4 正确的度量指标

系统可靠性的改进往往由度量指标驱动，
但我们一直难以为 CEE 定义有用的指标。
以下是一些候选指标及其挑战：

- 表现出 CEE 的核（或机器）所占比例。挑战：依赖测试覆盖率（尤其是面对"零日"CEE 时——那些在我们知道要测试它们之前就造成损坏的 CEE）、投入测试的周期数，以及机器群体中持续到来的新型号 CPU。
- 发病年龄。挑战：如果许多 CEE 在芯片使用数年后才显现，这个指标取决于你能等多久，并且需要在机器整个生命周期内持续筛查。
- 应用可见损坏的发生率和性质——CEE 多久损坏一次"真实"工作负载的结果？损坏是否"黏稠"，即一次 CEE 经由后续计算传播，造成多个应用错误？挑战：这更多是程序的属性，而非 CEE 的属性。

即使指标可以定义，
在实践中量化其取值也同样困难且昂贵，
因为需要在许多机器上运行测试，
可能持续很长时间，
才能得到高置信度的结果——
我们甚至还不知道需要多少台机器、多长时间，
而且测试运行的顺序以及在 (f, V, T) 空间中扫描的方式，
都会影响失效发生的时间。

为了限制资源消耗，
我们应当用一组精炼的测试来代表真实应用软件的复杂度。
鉴于我们对什么样的软件构造会触发 CEE 知之甚少，
目前这只能靠碰运气。
由于看似微小的软件改动似乎会显著改变真实工作负载的 CEE 发生率，
我们今天还不知道如何创建一小组能可靠测量这些发生率的测试。

我们能否建立一个模型，
来推理不同类别软件可接受的 CEE 发生率，
并建立一个模型，
来权衡测量这些发生率时的误差与测量成本？
我们一直都在容忍少量错误，
但 mercurial 核让这些问题变得更加紧迫。
许多应用可能并不需要零故障硬件，
但那么，正确的目标发生率是多少？
能否把目标设定为让 CEE 的概率被软件 bug 或未检出内存错误的固有发生率所掩盖？

对于一个拥有多种 CPU 型号、来自多家厂商、机龄各异的大型集群，
我们该如何评估风险？

## 5 是什么导致了 mercurial 核？

我们理解 CPU 核测试之所以变得更多孔漏的部分原因，
其余的我们只能推测：

- CPU 规模和复杂度的持续增长。
- 硅片特征尺寸现在以纳米计，容错余量更小 [16]，老化后（潜伏）失效的风险或许也更大。
- 堆叠层等新技术增加了复杂度和制造风险。
- CPU 正逐渐变成围绕共享寄存器堆的一组离散加速器。这使得一些 CEE 所破坏的行为高度专门化，而核的其余大部分仍然正确，因而需要验证的行为面更大了。

温度、频率和电压都起作用，
但它们的影响各不相同：
例如，一些 mercurial 核的 CEE 发生率对频率非常敏感，
另一些则不敏感。
动态频率电压调节（DFVS）使频率和电压以复杂的方式紧密关联，
这是更低频率有时（出人意料地）反而提高故障率的若干原因之一。

我们发现了不止一个案例：
同一个 mercurial 核既在某些数据拷贝操作上表现出 CEE，
又在某些向量操作上表现出 CEE。
我们发现这两类操作共享同一硬件逻辑，
但指令到可能缺陷硬件的映射往往并不直观。

在某些方面，mercurial 核可以类比 Spectre 和 Meltdown [14]，
因为实现细节泄漏到了架构规范之外。
但那两个问题不是制造缺陷；
它们存在于每一颗芯片中，
而不是随机地静默出现，
而且既然我们现在知道如何谨慎地思考推测执行，
或许可以在未来的设计中避免它们 [24]。
设计出同样能抵御 CEE 的硬件也许（或也许不）可能——
这是一个开放的研究问题。
无论哪种情况，短期解决方案都可能要求我们避开某些让软件跑得更快的硬件特性。

我们希望厂商能找到经济有效的方法提供高置信度的验证，
让我们回到 mercurial 核发生率趋近于零的世界，
但我们大概不能指望这一点，
尤其是对晚年才出现的缺陷。
只要 CEE 的风险不可忽略，
我们就至少需要一个预警系统，
建立在我们下一节讨论的检测机制之上。

## 6 检测与隔离 mercurial 核

既然我们相信在可预见的未来 mercurial 核将是一种生活常态，
第一道防线必然是一个尽可能快地检测 mercurial 核的健壮基础设施；
实际上，测试成为 CPU *全生命周期*的一部分，
而不只是厂商或老化测试阶段的问题。
如果我们能检测到 mercurial 核，
就可以（见第 6.1 节）隔离它们，
防止进一步的破坏，
并支持更深入的分析。

基于硬件的检测是可行的；
例如，一些系统使用成对的核"锁步"（lockstep）运行，
基于两个核不会同时失效的假设来检测其中一个的失效 [26]。
但本文假定使用现有硬件，
聚焦于基于软件的检测。

mercurial 核检测之所以困难，
是因为它本质上涉及几种因素之间的权衡：
假阴性或延迟阳性（导致故障和数据损坏）、
假阳性（导致核被不当隔离而浪费）、
以及检测过程本身不可忽视的成本。

我们从几个维度对检测过程分类：
(1) 自动与人工；
(2) 部署前与部署后；
(3) 离线与在线；
(4) 基础设施层与应用层。

**自动与人工筛查：** 理想情况下，
mercurial 核检测应当完全自动化，
以实现规模、成本和准确性的目标。
和许多企业一样，
我们定期在集群上运行各种自动筛查机制。

然而，mercurial 核与复杂度相关的成因表明，
CEE 偶尔会有新的表现形式，
必须由人工来追根溯源。²
运营我们生产服务的人员在事故分诊、调试等过程中，
识别出许多可疑的核。
根据我们最近的经验，
这些人工识别的可疑对象中约有一半，
在深入调查后被证实确实是 mercurial 核——
我们必须通过进一步测试来取得"供述"
（往往要先开发一个新的可自动化测试）。
另一半则是误报和有限可复现性的混合体。

> ²Dixit 等人 [8] 详细描述了他们如何对一次具体的 CEE 追根溯源。

我们目前利用几种不同的可自动化"信号"来指示 CEE 的可能存在，
尤其是当我们能检测出这些信号的核特异性模式时。
这些信号包括用户进程和内核的崩溃，
以及对现有机器检查日志的分析。
现代工具链中的代码检查器
（如 Address Sanitizer [22]）能检测内存损坏
（如缓冲区溢出、释放后使用），
也提供了有用的信号。
"累犯"——来自同一个核的重复信号——
会增加我们对该核是 mercurial 核的信心。
可以想象，还可以基于已知实现细节的推断，
来改进可复现性和分诊。

**部署前与部署后筛查：** CPU 制造商在把芯片交付客户之前，
可以做相当多的自动化测试，
但显然这还有改进空间。
芯片厂商不易获得多样化的大规模工作负载，
无法直接观察并据以了解其测试的不足。
没有这样的反馈回路，
他们的测试最多只是"自洽"的，
只能捕获已建模问题中的大部分。
我们需要拓宽依赖运行环境和/或工作负载的测试集，
并找到办法把这些测试"上游化"给制造商，
或者把它们加入芯片厂商的客户中本已常见的验收测试和老化测试流程。

并非所有 mercurial 核筛查都能在 CPU 投入使用前完成——
首先，因为一些核要经过相当长时间才变成缺陷核；
其次，因为部署之后，
可能会针对新发现的缺陷模式开发新的测试。
随着我们和 CPU 厂商发现新的 CEE 类别，
我们的定期全集群测试已经扩展到这些新类别，
目前每年仍有几次。

**离线与在线筛查：** 部署后的测试，
既可以在 CPU 或核"离线"（不可调度真实任务）时进行，
也可以在线进行，
即以低优先级任务利用空闲周期。
在线筛查只要能做到不影响并发工作负载，
就是免费的（除了电费），
但并不总能完整覆盖所有的核或所有的症状。

离线筛查可以更具侵入性，
可以按计划确保覆盖所有的核，
还可以让 CPU 暴露在正常范围之外的运行条件（f、V、T）下。
然而，把工作负载从待测的核（或 CPU）上排空可能代价很高，
尤其是当相应任务迁移时必须迁移机器特定的存储。

**基础设施层与应用层筛查：** 检测 CEE 的测试，
既可以由基础设施（操作系统和守护进程）执行，
在某些情况下也可以由应用自己在线执行。
基础设施层的筛查可以更普遍，
能检测特权执行中的 bug，
并且给应用作者带来的负担更小。
然而，应用层的筛查可以更有针对性、
更易于精细调节，
并能支持应用层的缓解措施（见第 7 节）。

我们的许多应用已经在检查 SDC；
这种检查也能以极小的额外成本检测 CEE。
例如，Colossus 文件系统 [13] 用端到端校验和保护写路径。
Spanner 分布式数据库 [7] 以多种方式使用校验和。
其他系统在多个副本上并行执行相同的更新逻辑，
以避免网络依赖并获得 fail-stop 韧性，
我们可以利用这些双重计算来检测 CEE。
我们还在一些密码学应用中使用自筛查机制。

我们一个特别有用的工具是一个简单的 RPC 服务，
允许应用报告可疑的核或 CPU。
均匀分布在各个核上的报告大概不是 CEE；
而来自多个应用、似乎集中在少数几个核上的报告，
很可能就是 CEE，
可以成为隔离这些核的理由，
随后再做更仔细的检查。

图 1 展示了我们集群中每台机器的 CEE 事件的用户报告发生率和自动报告发生率
（以任意基线归一化）。
我们的自动检测器看到的发生率正在逐渐上升，
但我们不知道这是否反映了底层发生率的变化。

![图 1：报告的 CEE 发生率（归一化）](images/figure-0001.png)

> 图 1：报告的 CEE 发生率（归一化）。
> 每台机器的 CEE 事件报告发生率随时间的变化，
> 分为自动报告（Auto-reported）和用户报告（User-reported）两条曲线，
> 数值以任意基线归一化。

### 6.1 隔离技术

用现有的调度机制把一台机器从资源池中移除相对简单；
隔离某个特定的核可能更具挑战性，
因为这破坏了调度器关于同类型机器拥有相同资源的假设。
Shalev 等人 [23] 描述了一种在运行中的操作系统上移除故障核的机制。

更进一层的推测是：
也许可以识别出一组能在给定 mercurial 核上安全运行的任务
（只要这些任务避开缺陷执行单元），
从而避免闲置这些核的代价。
不过，目前还不清楚我们能否可靠地识别出
相对于特定缺陷核而言安全的任务。

## 7 缓解 CEE

尽管今天我们主要通过尽快检测和隔离来应对 mercurial 核，
但这并不总能避免对应用的影响，
而且检测也不可能完美。
我们能否设计出可以容忍 CEE 而又不产生过多开销的软件？

我们猜想，自动缓解可能从以下几个出发点展开：

- 让应用特定的机制承担一部分责任，应用"端到端论点"（End-to-End Argument）[20]——正确性往往最好在端点处检查，而不是在底层基础设施中检查。
- 系统支持高效的检查点（checkpointing），以便在计算失败后换一个核重启恢复。
- 经济有效的、应用特定的检测方法，用以决定是越过检查点继续，还是重试——例如，在提交事务前对一条数据库记录计算不变量，以检查其是否损坏（文件系统元数据同理）。Blum 和 Kannan [2] 讨论了若干存在高效检查器的算法类别。

例如，可以在两个核上运行同一个计算，
如果结果不一致，
就从检查点在另一对核上重启。

一种众所周知的方法是三模冗余 [15]：
同一个计算做三次，
（在至多一个失败的假设下）多数投票得出可靠结果。
也许编译器可以自动把计算复制到三个核上，
并借鉴确定性重放文献中的技术 [4]，
来选择尽可能大的计算粒度
（即应对非确定性输入，
并避免把不可靠的输出外化）。
然而，这依赖于投票机制本身的可靠性。

我们能想到的所有方法似乎都有显著的资源成本，
用于重复计算和/或存储。
由于我们的软件系统本来就会出于与 CEE 无关的原因重复某些计算，
为缓解关键代码中的 CEE 而进行三倍重复，
并不总是使现有成本变为三倍。
不过，某些计算足够关键，
值得我们付出两倍甚至三倍计算的开销。

为了让更广泛的应用开发者都能利用我们在应对 CEE 上的共同经验，
我们开发了一些带有自检实现的关键函数库，
如加密和压缩——在这些地方，
一次 CEE 就可能有很大的爆炸半径。

### 7.1 硬件缓解

CEE 无法完全在软件中缓解；
系统研究者必须与硬件设计者和厂商合作，
打造更健壮的硬件，包括：

- **可测试性设计**（design-for-test）：使检测带有细微制造缺陷的核更容易，并把这些测试功能开放给终端用户（用于 scrub 在用机器）；
- **持续验证**：功能单元始终检查自己的结果；
- 关键功能单元的保守设计，用一些额外的面积和功耗换取可靠性。例如，IBM z990 显然采用了双流水线和定制修改的缓存控制器，以提高韧性；这些改动增加了指令周期时间 [9]。

这类硬件特性虽然增加成本，
但仍可能比在软件中复制计算高效得多。

我们相信，系统研究者还可以帮助 CPU 设计者
重新思考现代处理器的机器检查架构——
它今天并不能很好地处理 CEE——
并改进 CPU 遥测（及其文档！），
让检测和追根溯源 mercurial 核变得容易得多。

## 8 相关工作

Dixit 等人 [8] 最近发表了他们在 Facebook 的 CEE 经历；
他们的观察与我们的一致。
他们的论文聚焦于把一次应用故障追根溯源到 CEE 的挑战。

高性能计算社区针对 α 粒子和宇宙射线等随机事件引起的 SDC 做了大量工作，
尤其是影响存储（DRAM、寄存器、磁盘、SSD）的那些。
Fang 等人 [10] 讨论了一种系统性的 SDC 应对方法。
另一些论文描述了排序算法的 SDC 韧性 [11]、
矩阵分解的 SDC 韧性 [27]，
以及 GPU 中辐射诱发的 SDC [25]。
我们没有发现 HPC 领域与 mercurial 核相关的先前工作。

Bartlett 等人 [1] 阐述了其容错操作系统背后的原则，
其中大多数也适用于容忍 CEE 的软件。
拜占庭容错 [3] 被提出用于抵御任意的非 fail-stop 错误 [6]；
BFT 在某些情况下可能适用于 CEE。

Rinard 等人 [19] 描述了让系统跨越内存错误继续计算的 failure-oblivious 技术；
目前还不清楚这些技术对 CEE 是否有效。

Gunawi 等人 [12] 讨论了硬件"性能故障"
（而非正确性错误）的普遍性；
他们指出"我们发现处理器相当可靠，
不会自发进入失效减速（fail-slow）模式"，
这似乎与我们更近的 CEE 经验相矛盾。

Nightingale 等人 [17] 分析了来自消费级 PC 的硬件故障，
并简要设想了设计一种"把故障硬件作为一等关注点的操作系统"。
他们没有讨论 CEE；
也许是他们的数据不足以检测到这类问题
（又或者十年前的 CPU 还没有表现出 CEE）。

许多先前的工作（如 [5, 18]）针对高噪声环境
（如汽车）中的瞬态错误。
这些与 CEE 的不同之处在于，
它们不会差别化地影响一个半稳定的少数核集合；
即便如此，其中一些方法可能在两个领域都有效。

## 9 下一步与研究方向

必须是 hyperscaler 才能在这个领域做研究吗？
我们希望不是，
尽管这本身就是一个有趣的挑战。
也许把 mercurial 核服务器从集群中隔离出来的 hyperscaler，
可以把这些服务器提供给研究者，
从而免去为了研究少数案例而购买大量服务器的需要。
访问方式可以经由 IaaS（虚拟机或裸金属云），
并配备机制以避免意外地把 mercurial 核分配给不知情的云客户
（或触发虚拟机逃逸）。

我们也许能开发周期级 CPU 模拟器，
允许注入已知的 CEE 行为，
甚至更细粒度的模拟器，
注入可能导致 CEE 的电路级故障。
类似地，我们可以开发故障注入器，
在真实硬件上测试软件的韧性。

系统研究界可以做出贡献的一种方式，
是开发检测新缺陷模式的方法，
并在大型集群中高效记录足够的取证证据。

也许编译器可以检测出正确执行尤为关键的代码块
（通过程序员标注或影响分析），
然后只自动复制这些计算。
更一般地，
我们能否把具有 SDC 韧性的算法类别扩展到排序和矩阵分解之外 [11, 27]？
那些先前工作用故障注入评估算法，
这种技术并不需要接触大型集群。

如今大量计算不仅在传统 CPU 上完成，
还在 GPU、ML 加速器、P4 交换机、NIC 等加速器硅片上完成。
这些加速器往往也在挑战规模、复杂度和功耗的极限，
因此人们大概也会在这些设备上看到 CEE。
在非 CPU 环境中检测和缓解 CEE，
可能会带来新的挑战。

## 参考文献

[1] Joel Bartlett, Wendy Bartlett, Richard Carr, Dave Garcia, Jim Gray, Robert Horst, Robert Jardine, Dan Lenoski, and Dix McGuire. Fault Tolerance in Tandem Computer Systems. In D. P. Siewiorek and R. Swartz, editors, *The theory and practice of reliable system design*. Digital Press, 1982.

[2] Manuel Blum and Sampath Kannan. Designing Programs That Check Their Work. J. ACM, 42(1):269–291, January 1995.

[3] Miguel Castro and Barbara Liskov. Practical Byzantine Fault Tolerance. In Proc. OSDI, 1999.

[4] Yunji Chen, Shijin Zhang, Qi Guo, Ling Li, Ruiyang Wu, and Tianshi Chen. Deterministic Replay: A Survey. ACM Comput. Surv., 48(2), September 2015.

[5] P. Cheynet, B. Nicolescu, R. Velazco, M. Rebaudengo, M. Sonza Reorda, and M. Violante. Experimentally evaluating an automatic approach for generating safety-critical software with respect to transient errors. IEEE Transactions on Nuclear Science, 47(6):2231–2236, 2000.

[6] Allen Clement, Manos Kaprisos, Sangmin Lee, Yang Wang, Lorenzo Alvisi, Mike Dahlin, and Taylor Riche. Upright Cluster Services. In Proc. SOSP, page 277–290, 2009.

[7] James C. Corbett, Jeffrey Dean, Michael Epstein, Andrew Fikes, Christopher Frost, J. J. Furman, Sanjay Ghemawat, Andrey Gubarev, Christopher Heiser, Peter Hochschild, Wilson Hsieh, Sebastian Kanthak, Eugene Kogan, Hongyi Li, Alexander Lloyd, Sergey Melnik, David Mwaura, David Nagle, Sean Quinlan, Rajesh Rao, Lindsay Rolig, Yasushi Saito, Michal Szymaniak, Christopher Taylor, Ruth Wang, and Dale Woodford. Spanner: Google's Globally Distributed Database. ACM Trans. Comput. Syst., 31(3), August 2013.

[8] Harish Dattatraya Dixit, Sneha Pendharkar, Matt Beardon, Chris Mason, Tejasvi Chakravarthy, Bharath Muthiah, and Sriram Sankar. Silent Data Corruptions at Scale. https://arxiv.org/abs/2102.11245, 2021.

[9] M. L. Fair, C. R. Conklin, S. B. Swaney, P. J. Meaney, W. J. Clarke, L. C. Alves, I. N. Modi, F. Freier, W. Fischer, and N. E. Weber. Reliability, availability, and serviceability (RAS) of the IBM eServer z990. IBM Journal of Research and Development, 48(3.4):519–534, 2004.

[10] Bo Fang, Panruo Wu, Qiang Guan, Nathan DeBardeleben, Laura Monroe, Sean Blanchard, Zhizong Chen, Karthik Pattabiraman, and Matei Ripeanu. SDC is in the Eye of the Beholder: A Survey and Preliminary Study. In IEEE/IFIP International Conference on Dependable Systems and Networks Workshop (DSN-W), pages 72–76, 2016.

[11] Qiang Guan, Nathan DeBardeleben, Sean Blanchard, and Song Fu. Empirical Studies of the Soft Error Susceptibility Of Sorting Algorithms to Statistical Fault Injection. In Proc. 5th Workshop on Fault Tolerance for HPC at Extreme Scale (FXTS), page 35–40, 2015.

[12] Haryadi S. Gunawi, Riza O. Suminto, Russell Sears, Casey Gollagher, Swaminathan Sundararaman, Xing Lin, Tim Emami, Weiguang Sheng, Nematollah Bidokhti, Caitie McCaffrey, Deepthi Srinivasan, Biswarajan Panda, Andrew Baptist, Gary Grider, Parks M. Fields, Kevin Harms, Robert B. Ross, Andree Jacobson, Robert Ricci, Kirk Webb, Peter Alvaro, H. Birali Runesha, Mingzhe Hao, and Huaicheng Li. Fail-Slow at Scale: Evidence of Hardware Performance Faults in Large Production Systems. ACM Trans. Storage, 14(3), October 2018.

[13] Dean Hildebrand and Denis Serenyi. Colossus under the hood: a peek into Google's scalable storage system. https://cloud.google.com/blog/products/storage-data-transfer/a-peek-behind-colossus-googles-file-system, 2021.

[14] M. D. Hill, J. Masters, P. Ranganathan, P. Turner, and J. L. Hennessy. On the Spectre and Meltdown Processor Security Vulnerabilities. IEEE Micro, 39(2):9–19, 2019.

[15] R. E. Lyons and W. Vanderkulk. The Use of Triple-Modular Redundancy to Improve Computer Reliability. IBM Journal of Research and Development, 6(2):200–209, 1962.

[16] Riccardo Mariani. Soft Errors on Digital Components. In A. Benso and P. Prinetto, editors, *Fault Injection Techniques and Tools for Embedded Systems Reliability Evaluation*, volume 23 of *Frontiers in Electronic Testing*. Springer, 2003.

[17] Edmund B. Nightingale, John R. Douceur, and Vince Orgovan. Cycles, Cells and Platters: An Empirical Analysis of Hardware Failures on a Million Consumer PCs. In Proceedings of the Sixth Conference on Computer Systems, EuroSys '11, page 343–356, 2011.

[18] S. Pandey and B. Vermeulen. Transient errors resiliency analysis technique for automotive safety critical applications. In 2014 Design, Automation Test in Europe Conference Exhibition (DATE), pages 1–4, 2014.

[19] Martin Rinard, Cristian Cadar, Daniel Dumitran, Daniel M. Roy, Tudor Leu, and William S. Beebee. Enhancing server availability and security through failure-oblivious computing. In Proc. OSDI, 2004.

[20] J. H. Saltzer, D. P. Reed, and D. D. Clark. End-to-End Arguments in System Design. ACM Trans. Comput. Syst., 2(4):277–288, November 1984.

[21] T.J.E. Schwarz, Qin Xin, E.L. Miller, D.D.E. Long, A. Hospodor, and S. Ng. Disk Scrubbing in Large Archival Storage Systems. In Proc. MASCOTS, 2004.

[22] Konstantin Serebryany, Derek Bruening, Alexander Potapenko, and Dmitry Vyukov. AddressSanitizer: A Fast Address Sanity Checker. In Proc. USENIX Annual Technical Conference, 2012.

[23] Noam Shalev, Eran Harpaz, Hagar Porat, Idit Keidar, and Yaron Weinsberg. CSR: Core Surprise Removal in Commodity Operating Systems. In Proc. ASPLOS, page 773–787, 2016.

[24] Jan Philipp Thoma, Jakob Feldtkeller, Markus Krausz, Tim Güneysu, and Daniel J. Bernstein. BasicBlocker: Redesigning ISAs to Eliminate Speculative-Execution Attacks. CoRR, abs/2007.15919, 2020.

[25] Devesh Tiwari, Saurabh Gupta, James Rogers, Don Maxwell, Paolo Rech, Sudharslan Vazhkudai, Daniel Oliveira, Dave Londo, Nathan DeBardeleben, Philippe Navaux, Luigi Carro, and Arthur Bland. Understanding GPU errors on large-scale HPC systems and the implications for system design and operation. In Proc. HPCA, pages 331–342, 2015.

[26] Jim Turley. ARM Cortex-A76AE Reliably Stays in Lock Step. Electronic Engineering Journal, October 2018. https://www.eejournal.com/article/arm-cortex-a76ae-reliably-stays-in-lock-step/.

[27] Panruo Wu, Nathan DeBardeleben, Qiang Guan, Sean Blanchard, Jieyang Chen, Dingwen Tao, Xin Liang, Kaiping Ouyang, and Zizhong Chen. Silent Data Corruption Resilient Two-Sided Matrix Factorizations. SIGPLAN Not., 52(8):415–427, January 2017.

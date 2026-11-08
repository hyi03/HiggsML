/* Bilingual explanation of the completed draft001 manuscript; aggregate inputs only. */
globalThis.DraftContent = (() => {
  'use strict';
  const en = document.documentElement.lang === 'en';
  const t = (zh,eng) => en ? eng : zh;
  const D = DraftManuscript;
  const f = x => Number(x).toFixed(6);
  const signed = x => (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(6);
  const pct = x => (100*x).toFixed(1) + '%';
  const list = rows => `<ul>${rows.map(x=>`<li>${x}</li>`).join('')}</ul>`;
  const box = (text,warning=false) => `<aside class="callout${warning?' caution':''}">${text}</aside>`;
  const table = (headers,rows,caption) => `<div class="table-wrap" tabindex="0" role="region" aria-label="${caption}"><table class="data-table"><caption>${caption}</caption><thead><tr>${headers.map(x=>`<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((x,i)=>i?`<td>${x}</td>`:`<th scope="row">${x}</th>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const notes = (zh,eng) => `<h3>${t('如何理解这一页','How to read this slide')}</h3>${t(zh,eng)}`;
  const flow = rows => `<ol class="flow">${rows.map((x,i)=>`<li><span class="step-number">${String(i+1).padStart(2,'0')}</span>${x}</li>`).join('')}</ol>`;
  const metric = (value,label) => `<div class="metric-card"><strong>${value}</strong><span>${label}</span></div>`;
  const image = (name,alt) => {
    const url = `../../paper/draft-v2/figures/basic-20261108/${name}.pdf`;
    return `<figure class="spectrum-figure"><object type="application/pdf" data="${url}#toolbar=0&amp;view=Fit" aria-label="${alt}"><p>${t('浏览器未嵌入 PDF，请打开原图。','PDF preview is unavailable in this browser; open the original figure.')}</p></object><figcaption><a href="${url}" target="_blank" rel="noopener">${t('打开报告原始 PDF 图','Open the original report PDF figure')}</a> · ${name==='deletion-differences'?t('三个面板为 ΔR_S、ΔR_B、ΔQ；细线为种子范围，不是置信区间。','Panels show ΔR_S, ΔR_B and ΔQ; segments span seeds, not confidence intervals.'):t('ABCD 在上、BCD 在下；信号在左、背景在右。','ABCD above, BCD below; signal left, background right.')}</figcaption></figure>`;
  };
  const link = (id,label) => `<a href="#${id}">${label}</a>`;
  const artificial = () => box(t('人工教学示例；不是实际 MC 结果。','Artificial teaching example; not an actual MC result.'),true);

  const ch = [t('01 · 目的与范围','01 · Purpose and scope'),t('02 · 样本与选择','02 · Samples and selection'),t('03 · 特征与网络','03 · Features and network'),t('04 · 指标与示例','04 · Metrics and examples'),t('05 · 完整比较','05 · Full comparison'),t('06 · 质量谱','06 · Mass spectra'),t('07 · 结论与来源','07 · Conclusions and sources')];
  const slides=[];
  const add=(id,chapter,title,lead,body,explanation,source,sourceFile='project-report-cn.tex')=>slides.push({id,chapter,title,lead,body,notes:explanation,source,sourceFile});
  const fractionPercent = (name,index) => D.mass_fractions_percent[name][index].toFixed(1) + '%';

add('overview',ch[0],t('不同特征组怎样影响筛选？','How do feature groups affect selection?'),
    t('同步 11 月 8 日基础指标报告：信号保留、背景抑制与质量谱。','Following the 8 November basic report: signal retention, background suppression and mass spectra.'),
    `<div class="hero-metrics">${metric('15',t('分别训练的模型','separately trained models'))}${metric('60 / 20 / 20',t('训练／验证／评估','train / validation / evaluation'))}${metric('3',t('并列解读的基础指标','basic metrics read together'))}</div><p class="hero-equation">H → ZZ* → 2e2μ</p>`+box(t('比较各自冻结工作点；不将信背比当作显著性或测量精度。','Compare each frozen working point; signal/background ratio is not significance or measurement precision.')),
    notes('<p>本讲解沿新版中文报告的七章顺序，面向物理本科高年级及希望补足机器学习知识的读者。先介绍方法，再做 ABCD/BCD 示例，最后比较全部十五个模型。</p><p>数值据报告显示精度转述，图片直接使用当前报告 PDF。当前报告身份以 a7e610 开头；同名历史 draft001 具有不同身份，其区间与补充诊断不能充当本次验证。</p>', '<p>Follow the updated Chinese report’s seven chapters, for advanced physics undergraduates and readers learning ML. Introduce methods, work through ABCD/BCD, then compare all fifteen models.</p><p>Numbers retain report display precision and figures are current report PDFs. The current report ID begins a7e610; the historical same-name draft001 has another identity. Its interval and supplemental diagnostics do not validate this run.</p>'), '§ 1; Appendix E');

add('question',ch[0],t('四个条件删组问题','Four conditional group deletions'),
    t('比较 ABCD 与分别删除 A、B、C、D 后重新训练的网络。','Compare ABCD with networks retrained after removing A, B, C or D.'),
    table([t('删除','Remove'),t('方案','Representation')],[['A','BCD'],['B','ACD'],['C','ABD'],['D','ABC']],t('每种方案保留全部三个种子','Keep all three seeds for every representation'))+box(t('删组还改变首层参数、优化轨迹和阈值；不等于独立物理贡献。','Deletion also changes first-layer size, optimization and thresholds; it does not isolate a physical contribution.')),
    notes('<p>共同划分、隐藏层、训练预算和背景加权中位数规则使比较口径一致，但不保证最终评估的背景效率相同。</p><p>不把三项指标合成总分，不搜索全部子集，也不宣称全局最优。</p>', '<p>Common splits, hidden layers, training budget and background weighted-median rule align the comparison, but do not enforce equal evaluation background efficiency.</p><p>Do not combine the metrics into one score, search every subset or claim global optimality.</p>'), '§ 1; § 4');

add('analysis-roadmap',ch[0],t('从网络分数到基础比较','From network score to basic comparison'),
    t('先定义总体，再冻结选择，最后联合看保留率与谱形。','Define the population, freeze selection, then read retentions and shapes together.'),
    flow([t('共同选择与物理权重','Common selection and physical weights'),t('训练 → AUC 选检查点 → 验证背景阈值','Train → AUC checkpoint → validation-background cut'),t('冻结后求 S、B、R_S、R_B、Q','After freeze: S, B, R_S, R_B, Q'),t('逐种子删组差值与质量谱','Within-seed deletion contrasts and mass spectra')])+list([link('worked-example',t('两个模型的计算示例','Two-model worked example')),link('all-results',t('全部十五个模型','All fifteen models')),link('spectrum-yields',t('当前来源质量谱','Current-source mass spectra'))]),
    notes('<p>输入标准化、训练、检查点选择和阈值确定各有自己的数据职责。评估只在冻结后进行，不用于调整工作点。</p><p>本版主线不再用 W68 排名；历史统计方法只在来源页交代，不与当前基础指标混合。</p>', '<p>Scaling, training, checkpoint selection and threshold choice have separate data roles. Evaluation follows the freeze and never adjusts working points.</p><p>This edition does not rank by W68. Historical statistical methods are mentioned only in provenance, separate from current basic metrics.</p>'), '§§ 1–7');

  add('physics',ch[0],t('四轻子末态提供什么信息？','What does the four-lepton final state provide?'),
    t('重建质量定位共振区域，其他运动学变量描述事件的组成与几何关系。','Reconstructed mass locates the resonant region; other kinematics describe event composition and geometry.'),
    flow([t('四个重建轻子','Four reconstructed leptons'),t('组成 Z₁、Z₂','Construct Z₁ and Z₂'),t('动量、质量、角度','Momenta, masses, angles'),t('网络分数与类别','Network scores and categories')])+list([t('约 125 GeV 的模拟 Higgs 信号；至少一个 Z 离壳。','A simulated Higgs signal near 125 GeV; at least one Z is off shell.'),t('信号与背景由指定模拟成员定义。','Signal and background are defined by the specified MC members.'),t('峰更明显不自动意味着统计显著或测量精度提高。','A more visible peak does not establish significance or a precision gain.')]),
    notes('<p>输入既有直接观测量，也有从同一组四动量导出的量。因此输入组之间并不互相独立。特征工程可能使关系更容易学习，而不增加独立自由度。</p><p>研究目标是把输入变化连接到一个明确定义的统计量，同时解释选择保留了哪些事件。质量谱是物理诊断；基础指标对整个质量窗口的高分产额求和。</p>', '<p>Inputs include direct observables and quantities derived from the same four-momenta. Feature groups therefore overlap in information. Engineering a useful representation need not add independent degrees of freedom.</p><p>The goal is to connect input changes to a defined statistical metric and explain the selected events. Spectra are physical diagnostics; basic metrics sum high-score yields across the mass window.</p>'), '§ 1');

  add('samples',ch[1],t('固定的两个受控 2020 MC 样本','Two fixed controlled 2020 MC members'),
    t('13 TeV、2e2μ、10 fb⁻¹；来源与物理范围均有明确边界。','13 TeV, 2e2μ, 10 fb⁻¹: explicit source and physical-scope boundaries.'),
    table([t('角色','Role'),'DSID',t('样本','Member')],[[t('信号','Signal'),'345060','ggH125_ZZ4lep'],[t('背景','Background'),'363490','llll']],t('ATLAS 2020 教育集合的指定模拟成员','Specified simulated members from the ATLAS 2020 educational collection'))+list([t('使用这两个成员的全部受控 MC，包含历史 test 中的事件。','Use all controlled MC from these members, including historical test events.'),t('不混用 2025 集合；不使用碰撞数据。','No mixing with the 2025 collection; no collision-data events.'),t('背景标签不能单独证明它是纯 q q̄ → ZZ。','The background label alone does not establish a pure q q̄ → ZZ process.')]),
    notes('<p>样本生产配置与发布前筛选仍待核实。其他 Higgs 产生模式和额外实验背景未进入比较，结论不能推广到完整实验分析。</p><p>全 MC 重新分组扩大了本次使用的来源总体，但其中有以前使用过的事件。新的名称或划分不能恢复独立性，访问历史仍属于结果资格的一部分。</p>', '<p>Production configuration and release preselection remain to be verified. Other Higgs production modes and additional experimental backgrounds are outside this comparison.</p><p>Reallocating all MC defines the current population but includes previously used events. A new name or split does not restore independence; source-access history remains part of result qualification.</p>'), '§ 2; § 7');

  add('selection',ch[1],t('所有模型共享同一个物理选择','Every model shares the physical selection'),
    t('先定义可比较的事件总体，再比较网络表示。','Define a comparable population before comparing network representations.'),
    list([t('触发、轻子识别、隔离、冲击参数与接受度要求。','Trigger, lepton identification, isolation, impact-parameter and acceptance requirements.'),t('恰好四个好轻子：两个电子、两个 μ 子；总电荷为零。','Exactly four good leptons: two electrons and two muons, with zero total charge.'),t('按 pT 排序；阈值为 20、15、10、7 GeV。','Order by pT; thresholds are 20, 15, 10 and 7 GeV.'),'50 < mZ₁ < 106 GeV; 12 < mZ₂ < 115 GeV; '+t('所有同味异号对质量 > 5 GeV。','every same-flavour opposite-sign pair mass > 5 GeV.'),'105 ≤ m₄ℓ < 140 GeV.'])+box(t('质量区间为半开区间：[105,140)。所有模型保留相同边界与配对规则。','The mass window is half-open: [105,140). All models retain the same boundaries and pairing rules.')),
    notes('<p>最接近名义 Z 质量的轻子对定义为 Z₁，剩余一对为 Z₂。轻子排序、配对与角度约定在模型之间保持一致。</p><p>报告中的“切前”已经通过这些共同选择；“切后”额外要求高网络分数。谱图不比较未经选择的原始样本与最终样本。</p>', '<p>The pair closest to the nominal Z mass defines Z₁; the remaining pair defines Z₂. Ordering, pairing and angular conventions are common across models.</p><p>“Before” in the spectra already passes this baseline. “After” additionally requires a high network score. The comparison is not raw unselected input versus final selection.</p>'), '§ 2; § 6');

  add('weights',ch[1],t('学习权重与物理产额不是同一件事','Learning weights and physical yields differ'),
    t('训练与验证使用绝对权重；物理产额保留权重符号。','Learning and validation use absolute weights; physical yields retain their signs.'),
    table([t('用途','Purpose'),t('度量','Measure')],[[t('训练优化','Training optimizer'),t('|物理权重| / 训练类别均值','|physical weight| / training-class mean')],[t('验证 AUC 与中位数阈值','Validation AUC and median threshold'),t('|物理权重|','|physical weight|')],[t('最终评估产额','Final-evaluation yield'),'physical_weight / 0.2']],t('三种权重职责','Three weight responsibilities'))+box(t('各子集估计同一个 10 fb⁻¹ 曝光，不能将它们相加成额外曝光。','Each subset estimates the same 10 fb⁻¹ exposure; their estimates must not be added as extra luminosity.')),
    notes('<p>按训练类别的平均绝对权重归一化，不保证两类的总训练权重相同。物理产额的正负符号不能被训练权重替代。</p><p>最终评估分配概率为 0.2，因此产额权重除以 0.2。MC 存储事件数与物理预期事件数应始终区分，负权重的存在也不能单独证明其物理来源。</p>', '<p>Dividing by a training-class mean absolute weight does not necessarily equalize total class contributions. Optimizer weights cannot replace signed weights in physical yields.</p><p>Final evaluation has assignment probability 0.2, so yield weights divide by 0.2. Stored MC counts and expected physical counts remain distinct. Negative weights alone do not identify their physical origin.</p>'), '§ 2');

  add('weighted-example',ch[1],t('一个事件组，三种权重职责','One event group, three weight responsibilities'),
    t('先合并相关行，再计算物理产额与 MC 方差。','Combine correlated rows before calculating physical yield and MC variance.'),
    artificial()+table([t('量','Quantity'),t('人工数值','Artificial values')],[[t('同组两行物理权重','Two same-group physical weights'),'w₁ = +0.4; w₂ = −0.1'],[t('评估产额贡献','Evaluation yield contribution'),'v = (0.4 − 0.1) / 0.2 = 1.5'],[t('该组方差贡献','Group variance contribution'),'v² = 2.25'],[t('若在训练角色，取绝对值','If in training, use absolute values'),'0.4 / m; 0.1 / m']],t('m 为该训练类别的平均绝对权重','m is the training-class mean absolute weight')),
    notes('<p>这里两行属于同一物理事件组、同一过程和同一类别。它们一起分配职责，并不同时用于训练和评估。表的最后一行只比较权重定义。</p><p>若错误地逐行平方，得到 (0.4/0.2)² + (−0.1/0.2)² = 4.25，而正确组贡献为 2.25。训练绝对权重则防止符号抵消成为优化目标；它不替换物理产额中的符号。训练类别均值归一化也不保证两类总权重相等。</p>', '<p>The two rows represent one physical group in the same process and category. They receive one common role; they are not simultaneously used in training and evaluation. The final row only compares weight definitions.</p><p>Incorrect row-wise squaring gives (0.4/0.2)² + (−0.1/0.2)² = 4.25 instead of the grouped contribution 2.25. Absolute learning weights keep signed cancellation out of the optimization objective; they do not replace signs in physical yields. Training-class mean normalization does not ensure equal total class weights.</p>'), 'Artificial arithmetic; nominal weight/group definitions, § 2');

  add('groups',ch[1],t('统计单位是物理事件组','Physical event groups are the statistical units'),
    t('相关的多行表示先求和，再计算方差和协方差。','Sum correlated representations within a group before computing variance and covariance.'),
    `<div class="formula">v<sub>gc</sub> = Σ<sub>i∈g,c</sub> wᵢ<br>Y<sub>c</sub> = Σ<sub>g</sub> v<sub>gc</sub><br>V<sub>cd</sub> = Σ<sub>g</sub> v<sub>gc</sub>v<sub>gd</sub></div>`+list([t('同组事件不跨越训练、验证、最终评估职责。','A physical group cannot cross the three data roles.'),t('切前／切后共享事件，误差相互相关。','Before/after curves share events and have correlated errors.'),t('保留率误差必须包含筛选前后共享事件协方差。','Retention errors must include covariance from shared before/after events.')]),
    notes('<p>如果把同一个物理事件的多个表示误当作独立条目，会误估 MC 方差。计算先将该组对每一类别的贡献合并，再形成外积。</p><p>这也解释了为何切前与切后曲线不能按两个独立测量处理。共同分母还会让归一化形状的各质量箱相关。</p>', '<p>Treating multiple representations of one physical event as independent rows misestimates MC variance. Contributions are first combined by group and category, then outer products are formed.</p><p>This explains why before/after spectra cannot be treated as independent measurements. Shared normalization also correlates bins within normalized shapes.</p>'), '§ 2; §§ 6–V');

  add('allocation',ch[1],t('已固定的 60 / 20 / 20 分配','The frozen 60 / 20 / 20 allocation'),
    t('划分不随行顺序、模型或训练种子改变。','The split does not change with row order, model or training seed.'),
    `<div class="allocation" aria-label="60% training, 20% validation, 20% evaluation"><span>${t('训练','Training')} 60%</span><span>${t('验证','Validation')} 20%</span><span>${t('评估','Evaluation')} 20%</span></div>`+table([t('职责','Role'),t('允许用途','Permitted use')],[[t('训练','Training'),t('拟合标准化与网络参数','Fit standardization and network parameters')],[t('验证','Validation'),t('选 checkpoint，确定背景加权中位数阈值','Select checkpoint and background weighted-median cut')],[t('最终评估','Final evaluation'),t('冻结后计算基础指标与质量谱','After freeze: basic metrics and mass spectra')]],t('分配概率，不是有限样本精确配额','Assignment probabilities, not exact finite-sample quotas')),
    notes('<p>独立版本的事件组哈希 h4l-draft-v2-role-v1 确定三种职责。训练种子只改变网络随机性，不产生新的数据总体。</p><p>本报告使用冻结后评估产额与诊断，因此它支持冻结工作点的描述性比较，不能当作独立验证。</p>', '<p>The versioned h4l-draft-v2-role-v1 group hash determines roles. Training seeds change network randomness, not the data population.</p><p>This report uses post-freeze evaluation yields and diagnostics. It supports a descriptive frozen-working-point comparison, not independent validation.</p>'), '§ 2');

  add('workflow',ch[2],t('从数据到报告：已执行的顺序','From data to report: the executed sequence'),
    t('所有十五个模型共同冻结，随后才读取最终评估载荷。','Freeze all fifteen models together before reading final-evaluation payloads.'),
    flow([t('共同选择与事件组划分','Common selection and grouped allocation'),t('训练十五个模型','Train fifteen models'),t('验证 checkpoint 与阈值','Validate checkpoints and cuts'),t('统一冻结＋访问批准','Common freeze and access approval'),t('最终评估及绑定报告','Final evaluation and bound report')])+box(t('冻结前，训练读取器在 JSON 解码前跳过最终评估事件载荷。','Before freeze, the training reader skips evaluation payloads before JSON decoding.')),
    notes('<p>模型参数、标准化参数、阈值、数据身份和报告规则全部绑定到同一冻结工件。本次最终评估之前已有绑定该冻结的明确用户批准。</p><p>评估之后没有更换模型、移动阈值、合并类别或调整分箱。若支持检查失败，程序保留失败状态，而不是根据评估结果修改规则。</p>', '<p>Model parameters, scalers, thresholds, data identities and reporting rules are bound to a common freeze. Explicit user approval tied to that freeze preceded this final evaluation.</p><p>No model, cut, category or binning was changed after evaluation. Unsupported results remain failures rather than triggering outcome-driven rule changes.</p>'), '§ 3','project-report-cn.tex');

  add('features',ch[2],t('十九个输入，四组物理描述','Nineteen inputs in four physical groups'),
    t('这些组的信息彼此重叠；显式 m₄ℓ 不在输入内。','The groups overlap in information; explicit m₄ℓ is not an input.'),
    table([t('组','Group'),t('内容','Content'),t('维数','Inputs')],[['A',t('四个轻子 pT 与四个 η','Four lepton pT and four η'),'8'],['B','mZ₁, mZ₂, ΔRZ₁, ΔRZ₂','4'],['C','pT4ℓ, ΔφZZ','2'],['D',t('五个衰变／产生角度','Five decay/production angles'),'5']],t('报告的输入分组','Report input groups'))+box(t('去掉质量列 ≠ 强制质量独立。其他运动学量仍可携带隐式质量信息。','Omitting the mass column does not enforce mass independence. Other kinematics can retain implicit mass information.'),true),
    notes('<p>A 描述实验室系中的单轻子，B 描述双轻子系统，C 描述集体运动学，D 描述角度关系。十九个输入不代表十九个互相独立的物理自由度。D 的具体输入为 cosθ*、cosθ₁、cosθ₂、衰变平面角与产生平面角。</p><p>m₄ℓ 仍用于共同质量窗和谱图诊断。本文没有增加 CDF 变换、对抗学习或显式质量开关控制。</p>', '<p>A describes individual leptons in the laboratory, B the dilepton systems, C collective motion and D angular relations. Nineteen inputs do not imply nineteen independent physical degrees of freedom. D contains cosθ*, cosθ₁, cosθ₂, the decay-plane angle and the production-plane angle.</p><p>m₄ℓ remains in the mass-window selection and diagnostics. No CDF transform, adversarial learner or explicit-mass on/off control is added.</p>'), '§ 3');

  add('model-widget',ch[2],t('互动：移除一组后，网络看到什么？','Explore the inputs after removing a group'),
    t('每种表示都单独训练；不是将完整模型的输入置零。','Each representation is trained separately, rather than zeroing inputs in a fitted full model.'),
    `<div class="model-options">${DraftTeaching.models.map(m=>`<button class="model-option" data-model="${m}" aria-pressed="false">${m}</button>`).join('')}</div><div id="model-output" class="widget-output" aria-live="polite"></div>`+box(t('共有 19、11、15、17、14 维；首层参数数量也会随维数变化。','The five dimensions are 19, 11, 15, 17 and 14; first-layer parameter counts also change.')),
    notes('<p>点击模型名称可以检查保留组与维数。这个互动只解释模型定义，不会在浏览器训练或推断。</p><p>网络的隐藏层结构一致，但输入维数变化意味着参数数量没有完全匹配。因此比较是在同一网络家族内的表示比较，不是严格等容量的理论信息测试。</p>', '<p>Select a model to inspect its retained groups and dimension. The widget explains definitions; it does not train or evaluate a model in the browser.</p><p>Hidden layers are common, but input dimensions change parameter counts. This compares representations within a shared network family, not perfectly capacity-matched learners or intrinsic information.</p>'), '§ 3');

  add('network',ch[2],t('标准化只从训练集学习','Fit standardization on training events only'),
    t('共同网络结构：64 → 64 → 32 → 标量分数。','Common network structure: 64 → 64 → 32 → scalar score.'),
    `<div class="layer-flow">${['Input','64','64','32','Sigmoid'].map(x=>`<div class="layer">${x}</div>`).join('<span aria-hidden="true">→</span>')}</div>`+list([t('训练集均值和标准差原样用于验证与最终评估。','Training means and standard deviations are reused for validation and evaluation.'),'LayerNorm + SiLU; '+t('前两隐藏块后 dropout = 0.1。','dropout = 0.1 after the first two hidden blocks.'),t('输出用于排序，不解释为校准后的物理信号概率。','The score ranks events; it is not a calibrated physical signal probability.')]),
    notes('<p>这是前馈全连接 MLP：a_j=ΣW_jk h_k+b_j。64、64、32 是中间节点数，不是事件数。LayerNorm 在同一事件的隐藏节点间归一化，SiLU 提供非线性；训练时前两层 Dropout 以 0.1 概率屏蔽节点，其余乘 1/0.9，验证和评估关闭屏蔽。它不删除事件或物理输入组。</p><p>如果用最终评估样本拟合标准化，即使不使用标签，也会让最终数据影响学习流程。本研究把标准化拟合限定在训练职责。</p><p>输出 sigmoid 是分类器的分数表达，并不使训练所用的绝对权重测度自动变成有符号物理产额下的概率。</p>', '<p>This is a feed-forward fully connected MLP: a_j=ΣW_jk h_k+b_j. Widths 64, 64 and 32 count hidden nodes, not events. LayerNorm normalizes hidden values within each event and SiLU supplies nonlinearity. During training, dropout masks nodes in the first two blocks with probability 0.1 and scales survivors by 1/0.9; masking is disabled for validation/evaluation. It deletes neither events nor input groups.</p><p>Fitting scaling on final evaluation would let that data influence learning even without labels. This study restricts scaler fitting to the training role.</p><p>A sigmoid output expresses a classifier score. It does not turn the absolute-weight learning measure into a probability under signed physical-yield weights.</p>'), '§ 3');

add('learning-ranking',ch[2],t('损失、AUC 与筛选指标的职责','Loss, AUC and selection metrics have different roles'),
    t('训练更新参数，验证选择检查点，冻结后才比较产额。','Training updates parameters, validation chooses checkpoints, and frozen evaluation compares yields.'),
    `<div class="formula">ℓᵢ = −aᵢ[yᵢ log sᵢ + (1−yᵢ) log(1−sᵢ)]<br>aᵢ = |wᵢ| / ${t('训练类别均值','training-class mean')}</div>`+flow([t('批平均损失 → 反向传播 → AdamW','Batch-mean loss → backpropagation → AdamW'),t('验证绝对权重 AUC → 最佳检查点','Validation absolute-weight AUC → best checkpoint'),t('验证背景加权中位数 → 阈值','Validation-background weighted median → cut'),t('高分子集 → 三项基础指标','High-score subset → three basic metrics')]),
    notes('<p>损失由 logits 稳定计算。信号低分、背景高分时损失增大；按批的算术平均反向传播。AdamW 学习率为 10⁻³、权重衰减为 10⁻⁴，使用 CPU float32。</p><p>AUC 衡量排序，0.5 为随机排序水平、1 为完全区分，不负责设定阈值。最终信号与背景保留率及信背比需联合解释；更高 AUC 不代表所有指标都更好。</p>', '<p>Loss is evaluated stably from logits. Low signal scores and high background scores increase it; the batch arithmetic mean drives backpropagation. AdamW uses learning rate 10⁻³ and weight decay 10⁻⁴ on CPU float32.</p><p>AUC measures ranking, with 0.5 at random-ranking level and 1 for perfect separation; it does not set the cut. Read signal retention, background retention and signal/background ratio together. Higher AUC does not guarantee improvement in every metric.</p>'), '§ 3');

  add('training',ch[2],t('固定训练规则，验证 AUC 选模型','Fixed training rules; validation AUC selects the checkpoint'),
    t('种子 42、43、44 改变训练随机性，共 15 个模型。','Seeds 42, 43 and 44 vary training randomness, giving fifteen models.'),
    table([t('设置','Setting'),t('数值','Value')],[['AdamW',t('学习率 10⁻³，权重衰减 10⁻⁴','Learning rate 10⁻³, weight decay 10⁻⁴')],[t('批大小','Batch size'),'1024'],[t('最大 epoch','Maximum epochs'),'200'],[t('早停','Early stopping'),t('耐心 20，最小改善 10⁻⁴','Patience 20, minimum improvement 10⁻⁴')],[t('checkpoint 指标','Checkpoint metric'),t('验证绝对权重 AUC','Validation absolute-weight AUC')]],t('没有新增架构或超参数搜索','No additional architecture or hyperparameter search')),
    notes('<p>200 是上限，而非要求每个模型必须运行满 200 轮。满足早停条件时，保留按验证 AUC 选出的 checkpoint。</p><p>AUC 汇总排序质量，阈值另由验证背景确定；最终工作点的三项指标需另外计算。种子 42 的 ABCD 第 87 轮停止、使用第 67 轮；BCD 第 86 轮停止、使用第 66 轮。</p>', '<p>Two hundred epochs is a cap, not a requirement to train every model for the full budget. Early stopping retains the checkpoint selected by validation AUC.</p><p>AUC summarizes ranking; a separate validation-background rule sets the cut. Calculate the three working-point metrics separately. At seed 42, ABCD stops at epoch 87 and uses epoch 67; BCD stops at 86 and uses 66.</p>'), '§ 3');

  add('median-widget',ch[2],t('互动：加权中位数如何决定切点？','Explore how the weighted median fixes the cut'),
    t('以下是人工教学例子；它们不表示本次 MC 产额或网络结果。','These hand-authored examples teach arithmetic; they are not MC yields or network results.'),
    `<label class="widget-label" for="median-example">${t('选择教学权重','Choose teaching weights')}</label><select id="median-example"><option value="report">${t('报告教学示例','Report teaching example')}</option><option value="balanced">${t('均等权重','Equal weights')}</option><option value="ties">${t('同分事件','Tied scores')}</option><option value="unequal">${t('非均等权重','Unequal weights')}</option></select><div id="median-output" aria-live="polite"></div>`+box(t('按分数升序累计绝对权重，首次达到一半处为阈值；score ≥ threshold 全部进入高侧。','Accumulate absolute weights in score order; the first score reaching half is the cut. All scores ≥ cut enter the high category.')),
    notes('<p>中位数规则不把同分事件拆开，所以高侧接受度不一定恰好为 50%。不均等权重例子中，高侧甚至可以包含全部事件。</p><p>正式阈值使用所选 checkpoint 的验证背景评分，而非最终评估背景。如果结果异常，也不能移动阈值挽救结果。</p>', '<p>Tied scores are never split, so high-side acceptance need not be exactly 50%. In the unequal-weight example it can even include all events.</p><p>The actual cut uses validation-background scores from the selected checkpoint, not evaluation scores. Unusual final results cannot be rescued by moving the cut.</p>'), '§ 3');

  add('freeze',ch[2],t('冻结绑定的是整条分析规则','The freeze binds the complete analysis'),
    t('不仅保存网络文件，还固定切点、数据身份和报告定义。','Bind cuts, data identities and reporting definitions as well as network files.'),
    list([t('15 个模型＋标准化参数＋各自验证阈值。','Fifteen models, scalers and their validation thresholds.'),t('共同 prepared 总体、协议及模型身份。','Common prepared population, protocol and model identities.'),t('固定质量区间、高低分组及基础指标展示规则。','Fixed mass window, high/low categories and basic-metric display rules.'),t('绑定冻结身份的明确访问记录，随后开展最终评估。','Explicit freeze-bound access record before final evaluation.')])+box(t('本次十五个模型汇总有效；不删除失败种子来完成比较。','All fifteen model summaries are valid; failed seeds must not be dropped to complete a comparison.')),
    notes('<p>访问批准允许按冻结方案执行，并不提高独立性或确认性资格。全 MC 的历史使用情况仍保留在访问记录中。</p><p>工件以不可变方式发布。网页读取的是当前报告显示值，没有访问事件、解码模型、申请评估许可或启动新的科学计算。</p>', '<p>Access approval permits the frozen execution; it does not upgrade independence or confirmatory eligibility. Prior use of the all-MC source remains recorded.</p><p>Artifacts are published immutably. The website reads current report display values, without events, model decoding, access approval or new scientific execution.</p>'), '§ 3; Appendix E');


  add("metrics-definitions",ch[3],t("三项指标一起看","Read three metrics together"),
    t("S、B 为高分产额；S₀、B₀ 为共同基线。","S and B are high-score yields; S₀ and B₀ are the common baseline."),
    `<div class="formula">R_S=S/S₀<br>R_B=B/B₀<br>Q=S/B=(S₀/B₀)(R_S/R_B)</div>`,
    notes("<p>R_S 越大保留信号越多，R_B 越小背景越少。Q 是由两项保留率决定的派生量，不是独立目标或显著性。</p>","<p>Higher R_S retains more signal; lower R_B retains less background. Q is derived from the two retentions, not an independent objective or significance.</p>"),"§ 4");

  add("counting-example",ch[3],t("事件组数不是预期产额","Group counts are not expected yields"),
    t("种子 42 的真实计数示例，不是人工产额。","Actual seed-42 group counts, not artificial yields."),
    table([t('过程','Process'),t('基线','Baseline'),'ABCD','BCD'],[[t('信号','Signal'),'9,049','8,761','8,563'],[t('背景','Background'),'698','386','378']],t('高分事件是共同基线的子集','High-score groups are subsets of the same baseline')),
    notes("<p>ABCD 的信号事件组比例为 8761/9049；物理产额保留率则为带符号权重和之比，必须分开计算。低分产额用于检查高低之和与基线一致。</p>","<p>ABCD signal group retention is 8761/9049; physical yield retention is a ratio of signed weight sums. Calculate them separately. Low-category yields check that high+low equals baseline.</p>"),"§ 4");

  add("signed-ratios",ch[3],t("分母与带符号权重","Denominators and signed weights"),
    t("不取绝对值来替代产额，不把异常比例裁剪掉。","Do not replace signed yields by absolute sums or clip unusual ratios."),
    list([t('基线非正：相应保留率不计算。','Nonpositive baseline: corresponding retention unavailable.'),t('背景高分产额非正：Q 不计算。','Nonpositive high-score background yield: Q unavailable.'),t('保留率可能超出通常范围，必须保留解释限制。','Retentions can leave the usual range; preserve their interpretation limits.')]),
    notes("<p>本次所有分母为正。规则仍须明确，以免将带符号 MC 比例错误当作普通计数概率。相同验证规则也不保证相同最终背景效率。</p>","<p>All denominators are positive here. Explicit rules prevent interpreting signed-MC ratios as ordinary count probabilities. A shared validation rule does not enforce equal final background efficiency.</p>"),"§ 4");

  add("paired-method",ch[3],t("先逐种子做差，再汇总","Subtract within seed before summarizing"),
    t("保留率差用百分点，信背比差用直接差值。","Retention differences use percentage points; Q differences are direct differences."),
    `<div class="formula">ΔR_S=R_S(reduced,r)−R_S(ABCD,r)<br>ΔR_B=R_B(reduced,r)−R_B(ABCD,r)<br>ΔQ=Q(reduced,r)−Q(ABCD,r)</div>`,
    notes("<p>三个差值排序取中间值，同时列最小至最大。负 ΔR_S 表示信号损失；负 ΔR_B 表示背景更少，不能把所有负值都称为退步。种子范围不是置信区间。</p>","<p>Sort three paired differences, take the middle value, and show min/max. Negative ΔR_S loses signal; negative ΔR_B leaves less background. Negative signs do not all mean deterioration. Seed ranges are not confidence intervals.</p>"),"§ 4");

  add("worked-example",ch[3],t("ABCD 与 BCD：显示精度算术","ABCD versus BCD: display-precision arithmetic"),
    t("以种子 42 演示，再看完整结果。","Work through seed 42 before the complete results."),
    `<div class="formula">ABCD: R_S≈2.6824/2.7710=96.80%<br>R_B≈1.2027/2.3553=51.06%<br>Q≈2.6824/1.2027=2.23<br>BCD: Q≈2.6215/1.1012=2.38</div>`,
    notes("<p>用表内舍入数值演示，删 A 后信号保留率约 −2.20 个百分点、背景约 −4.31 个百分点、Q 约 +0.15。更多信号损失换来更少背景，不构成普遍更优。正式差值直接转述未舍入汇总产生的报告表。</p>","<p>Using rounded cells, deleting A changes signal retention by about −2.20 pp, background by −4.31 pp and Q by +0.15. Extra signal loss buys less background, not universal superiority. Formal contrasts are transcribed directly from the report table computed from unrounded aggregates.</p>"),"§ 4");

  add("all-results",ch[4],t("全部十五个模型","All fifteen models"),
    t("不只展示某次最佳训练。","Do not select only the best training run."),
    table([t('方案','Model'),t('种子','Seed'),'S','B','R_S (%)','R_B (%)','Q'],D.rows.map(r=>[r.subset,r.seed,r.S,r.B,r.RS,r.RB,r.Q]),t('共同基线 S₀=2.7710、B₀=2.3553','Shared baseline S₀=2.7710, B₀=2.3553')),
    notes("<p>产额保留四位小数，保留率两位小数，Q 三位小数。它们是报告显示值，不是网页从舍入产额重新推算的高精度结果。</p>","<p>Yields retain four decimals, retentions two and Q three. These are report display values, not high-precision results reconstructed in the browser from rounded yields.</p>"),"§ 5");

  add("metrics-widget",ch[4],t("互动：切换种子与指标","Explore seeds and basic metrics"),
    t("看取舍，不合并为总分。","Inspect tradeoffs without combining metrics into one score."),
    `<label for="basic-metric">${t("指标","Metric")}</label><select id="basic-metric"><option value="RS">R_S (%)</option><option value="RB">R_B (%)</option><option value="Q">Q = S/B</option></select><label for="width-seed">${t("种子","Seed")}</label><select id="width-seed"><option>42</option><option>43</option><option>44</option></select><div id="width-output" aria-live="polite"></div>`,
    notes("<p>横条从零开始，RS/RB 使用百分数轴，Q 使用信背比轴。只切换已存报告值，不进行模型计算。</p>","<p>Bars start at zero. RS/RB use a percentage axis; Q uses a ratio axis. Controls select saved report values without model computation.</p>"),"§ 5");

  add("contrasts",ch[4],t("全部十二行删组差值","All twelve deletion-contrast rows"),
    t("每行保留三个种子、中位数和范围。","Keep all seeds, median and range in every row."),
    table([t('删组','Delete'),t('指标','Metric'),'42','43','44',t('中位数','Median'),t('最小至最大','Min/max')],D.deltas.map(r=>[r.group,r.metric==='Q'?'ΔQ':'Δ'+r.metric+' (pp)',...r.values,r.median,r.range]),t('差值据报告表转述','Contrasts transcribed from the report table')),
    notes("<p>这里的中位数和范围来自报告差值表；网页不从舍入基础指标重建。只有三个训练种子，方向一致不等于统计显著。</p>","<p>Medians and ranges come from the report contrast table; the browser does not reconstruct them from rounded basic metrics. Three-seed directional consistency does not establish significance.</p>"),"§ 5");

  add("contrast-widget",ch[4],t("互动：比较配对汇总","Explore paired summaries"),
    t("配对差值中位数通常不同于两组中位数之差。","A median paired contrast generally differs from a difference of medians."),
    `<label for="removed-group">${t("删组","Delete")}</label><select id="removed-group"><option>A</option><option>B</option><option>C</option><option>D</option></select><label for="contrast-metric">${t("指标","Metric")}</label><select id="contrast-metric"><option value="RS">R_S (pp)</option><option value="RB">R_B (pp)</option><option value="Q">Q</option></select><div id="contrast-output" aria-live="polite"></div>`,
    notes("<p>例如删 A 的 Q：报告配对中位数为 +0.033，而显示精度的两组 Q 中位数之差约 +0.034。舍入也会产生微小差别；本互动明确区分记录值与显示精度的另一算法。</p>","<p>For A deletion in Q, the recorded paired median is +0.033, while the difference of displayed Q medians is about +0.034. Rounding can also cause small differences; distinguish recorded values from the alternate calculation at display precision.</p>"),"§§ 4–5");

  add("deletion-plot",ch[4],t("图解删组变化与种子范围","Deletion changes and seed ranges"),
    t("圆点为种子，空心菱形为中位数。","Circles are seeds; open diamonds are medians."),
    image('deletion-differences',t('三项基础指标的逐种子删组差值','Within-seed deletion contrasts in three basic metrics')),
    notes("<p>细线连接最小值与最大值，不是置信区间。三面板依次为信号保留率差、背景保留率差、信背比差。三项指标须一起解释。</p>","<p>Segments connect min/max and are not confidence intervals. Panels show signal-retention, background-retention and Q differences. Read all three together.</p>"),"§ 5, deletion figure");

  add("group-C",ch[4],t("删 C：三个指标方向一致","Delete C: consistent directions across metrics"),
    t("限定于当前流程和各自冻结工作点。","Conditional on this procedure and each frozen working point."),
    table([t('指标','Metric'),'42','43','44',t('中位数','Median')],D.deltas.filter(r=>r.group==='C').map(r=>[r.metric==='Q'?'ΔQ':'Δ'+r.metric+' (pp)',...r.values,r.median]),t('逐种子差值','Within-seed differences')),
    notes("<p>ΔR_S 为 −5.05 至 −3.12 个百分点，ΔR_B 为 +0.68 至 +5.06 个百分点，ΔQ 为 −0.316 至 −0.119。三个种子均信号更少、背景更多、信背比更低。C 的两个变量不能进一步拆分贡献。</p>","<p>ΔR_S spans −5.05 to −3.12 pp, ΔR_B +0.68 to +5.06 pp and ΔQ −0.316 to −0.119. All seeds retain less signal, more background and lower Q. This cannot separate the contributions of the two C variables.</p>"),"§ 5, interpretation");

  add("group-A",ch[4],t("删 A：信号损失，其他取舍依种子","Delete A: signal loss and seed-dependent tradeoffs"),
    t("限定于当前流程和各自冻结工作点。","Conditional on this procedure and each frozen working point."),
    table([t('指标','Metric'),'42','43','44',t('中位数','Median')],D.deltas.filter(r=>r.group==='A').map(r=>[r.metric==='Q'?'ΔQ':'Δ'+r.metric+' (pp)',...r.values,r.median]),t('逐种子差值','Within-seed differences')),
    notes("<p>信号保留率均下降 −2.35 至 −1.47 个百分点。种子 42、43 以更多信号损失换取更少背景，44 则信号减少、背景增加；不能称为一致改善。</p>","<p>Signal retention drops by −2.35 to −1.47 pp. Seeds 42/43 trade extra signal loss for less background; seed 44 loses signal and gains background. This is not consistent improvement.</p>"),"§ 5, interpretation");

  add("group-B",ch[4],t("删 B：三个指标均有符号变化","Delete B: every metric changes sign across seeds"),
    t("限定于当前流程和各自冻结工作点。","Conditional on this procedure and each frozen working point."),
    table([t('指标','Metric'),'42','43','44',t('中位数','Median')],D.deltas.filter(r=>r.group==='B').map(r=>[r.metric==='Q'?'ΔQ':'Δ'+r.metric+' (pp)',...r.values,r.median]),t('逐种子差值','Within-seed differences')),
    notes("<p>42、43 信号和背景保留率略降、Q 提高；44 信号和背景均增加、Q 下降。中位数不能取代对方向变化的解释。</p>","<p>Seeds 42/43 slightly lower both retentions and increase Q; seed 44 increases both retentions and lowers Q. Medians cannot replace an account of directional changes.</p>"),"§ 5, interpretation");

  add("group-D",ch[4],t("删 D：多保留信号，不保证背景改善","Delete D: retain more signal without consistent background gain"),
    t("限定于当前流程和各自冻结工作点。","Conditional on this procedure and each frozen working point."),
    table([t('指标','Metric'),'42','43','44',t('中位数','Median')],D.deltas.filter(r=>r.group==='D').map(r=>[r.metric==='Q'?'ΔQ':'Δ'+r.metric+' (pp)',...r.values,r.median]),t('逐种子差值','Within-seed differences')),
    notes("<p>ΔR_S 全为正，范围 +0.54 至 +0.98 个百分点。42、43 背景减少、Q 增加，44 则方向相反。不能由此称 D 没有物理信息或 ABC 普遍更优。</p>","<p>ΔR_S is positive throughout, +0.54 to +0.98 pp. Background falls and Q rises for seeds 42/43; seed 44 reverses those directions. This does not show D lacks physical information or ABC is universally better.</p>"),"§ 5, interpretation");

  add("spectrum-population",ch[5],t("同一总体：计数、产额与误差","One population: counts, yields and errors"),
    t("ABCD/BCD，种子 42；均为当前报告来源。","ABCD/BCD at seed 42, from the current report source."),
    table([t('模型','Model'),t('过程','Process'),t('切前','Before'),t('高分','High'),t('保留率','Retention')],D.yield_rows.map(([m,p,...v])=>[m,t(p==='signal'?'信号':'背景',p),...v]),t('固定模型下的分组 MC 标准误差','Grouped MC standard errors conditional on fixed models')),
    notes("<p>误差计算为先组内带符号求和，再对各组贡献平方求和开方：σY=√ΣU_g²。不是对模拟事件数直接取平方根。保留率分子分母共享事件，误差含协方差；它们不是删组差值显著性。</p>","<p>For yield errors, sum signed contributions within group, then take σY=√ΣU_g². This is not the square root of the MC event count. Retention errors include shared-event covariance; they do not establish deletion-contrast significance.</p>"),"§ 4; Appendix C");

  add("spectrum-yields",ch[5],t("产额谱：定位信号与背景","Yield spectra: locate signal and background"),
    t("左信号、右背景；上 ABCD、下 BCD。","Signal left, background right; ABCD above, BCD below."),
    image('mass-yields',t('当前报告的绝对产额谱','Current-report absolute yield spectra')),
    notes("<p>信号集中在约 125 GeV，选择保留主要区域。蓝色圆点是基线，橙色圆点是高分；连线仅作视觉引导。七个 5 GeV 箱仅展示，基础指标对整个 [105,140) 积分。粗分箱不证明峰位、分辨率或物理宽度改善。</p>","<p>Signal is near 125 GeV and selection retains the main region. Blue circles mark baseline, orange circles high scores; lines only guide the eye. Seven 5 GeV bins are diagnostic; basic metrics integrate [105,140). Coarse bins do not establish improved peak position, resolution or physical width.</p>"),"§ 6, yield spectrum");

  add("spectrum-shapes",ch[5],t("归一化谱：背景不仅变少","Normalized shapes: background is also reshaped"),
    t("每条曲线除以自己的正带符号总产额。","Divide each curve by its own positive signed total yield."),
    image('mass-shapes',t('当前报告的归一化质量谱','Current-report normalized mass spectra')),
    notes("<p>信号 [120,130) 占比为 87.9%→88.6%/88.5%。背景该区域为 32.5%→51.8%/47.9%，[135,140) 为 22.0%→6.5%/9.0%。这些是描述性点估计，不判定显著性；仅覆盖 ABCD/BCD，不能解释 C 组机制。</p>","<p>Signal [120,130) shares are 87.9%→88.6%/88.5%. Background shares there are 32.5%→51.8%/47.9%, and in [135,140), 22.0%→6.5%/9.0%. These descriptive point estimates do not establish significance. Only ABCD/BCD are shown, so this cannot explain the C-group mechanism.</p>"),"§ 6, shape spectrum and region fractions");

  add("spectrum-support",ch[5],t("阴影、负值与相关误差","Shading, negative values and correlated errors"),
    t("标记限制，不删除箱或改变选择。","Flag limits without dropping bins or changing selection."),
    `<div class="formula">N_eff=Y²/V &lt; 20<br>ρ=|Y|/Σ|u_i| &lt; 0.2</div>`,
    notes("<p>无事件组、非正 Y/V 或满足上述任一条件均标阴影。ABCD 高分背景 [105,110) 为负；尾部支持不足。带符号归一化形状不是必然的概率密度。固定网络和阈值下的误差不覆盖完整训练与阈值估计不确定性。</p>","<p>Shade bins with no groups, nonpositive Y/V, or either criterion above. ABCD high-score background in [105,110) is negative and tails have low support. Normalized signed shapes need not be probability densities. Fixed-model/cut errors do not cover complete training and threshold-estimation uncertainty.</p>"),"§ 6; Appendix C");

  add("qualification",ch[6],t("描述性完成与科学资格","Descriptive completion and scientific qualification"),
    t("十五个模型齐全，不等于独立验证。","All fifteen models present does not mean independent validation."),
    `<dl class="qualification"><dt>Status</dt><dd>exploratory_posthoc</dd><dt>Independent</dt><dd>false</dd><dt>Selection-aware coverage</dt><dd>unvalidated</dd><dt>Primary claim eligible</dt><dd>false</dd></dl>`,
    notes("<p>当前基础指标没有建立差异的统计显著性或测量精度提升。三个种子范围只描述训练波动；源事件重新划分或重跑不恢复独立性。</p>","<p>Current basic metrics establish neither contrast significance nor measurement precision gains. Three-seed ranges only describe training variation; repartitioning or rerunning source events does not restore independence.</p>"),"§ 7; Appendix E");

  add("provenance",ch[6],t("以产物身份区分同名运行","Distinguish same-name runs by artifact identity"),
    t("当前来源为 11 月 8 日基础指标报告。","Current source: the 8 November basic-metric report."),
    `<dl class="identity-list"><dt>Report</dt><dd><code>${D.report_artifact_id}</code></dd>${Object.entries(D.binding).map(([k,v])=>`<dt>${k}</dt><dd><code>${v}</code></dd>`).join("")}</dl>`,
    notes("<p>当前来源为 a7e610…，网页只转述报告与 BASIC-20261108-EVIDENCE.md，未重读原始事件或原始汇总。历史 9aab6d… 与 validation001 曾研究区间、bootstrap 和 model-self 欠覆盖，未建立独立覆盖校准；不作为本次基础指标输入或验证。历史材料见 DRAFT001-EVIDENCE.md。</p>","<p>Current source is a7e610…. The page transcribes the report and BASIC-20261108-EVIDENCE.md without rereading events or original aggregates. Historical 9aab6d… and validation001 studied intervals, bootstrap and model-self undercoverage without independent coverage calibration. They are neither inputs nor validation for current basic metrics; see DRAFT001-EVIDENCE.md.</p>"),"Appendix E; BASIC-20261108-EVIDENCE.md");

  add("outstanding",ch[6],t("哪些问题仍需核实？","What still needs verification?"),
    t("记录已有证据范围，不补写未知内容。","State the evidence scope without filling unknowns."),
    list([t('生产配置、发布前选择与部分选择条件的外部依据。','Production configuration, release preselection and external support for some cuts.'),t('物理权重适用性与完整训练／阈值不确定性。','Physical-weight applicability and complete training/threshold uncertainty.'),t('当前汇总没有训练／验证计数，不沿用历史计数。','Current aggregates lack training/validation counts; do not reuse historical counts.')]),
    notes("<p>公开 ROOT 条目为信号 164,716、背景 554,279；评估物理组为 9,049、698。两种计数单位不保证一一对应，此表不是 cutflow，不能推算相对全部生成事件的效率。集合限定教育用途，不适用于科学出版。</p>","<p>Public ROOT entries are 164,716 signal and 554,279 background; evaluation physical groups are 9,049 and 698. Those counting units are not asserted one-to-one. This is not a cutflow or efficiency relative to all generated events. The collection is restricted to education and unsuitable for scientific publication.</p>"),"§§ 2, 7; Appendices A, E");

  add("takeaways",ch[6],t("保留、抑制、谱形一起解释","Read retention, suppression and shape together"),
    t("不将描述性取舍转化为普遍优劣。","Do not turn descriptive tradeoffs into universal rankings."),
    flow([t('删 C 的三个指标方向最一致。','C deletion has the most consistent directions across metrics.'),t('A/B/D 涉及取舍与种子依赖。','A/B/D involve tradeoffs and seed dependence.'),t('背景总量减少也伴随质量形状改变。','Background reduction also reshapes its mass distribution.')]),
    notes("<p>结论限于两份受控 MC、既定网络与冻结阈值。不是独立特征贡献、统计显著性、ATLAS/CMS 官方结果、希格斯发现或物理测量。报告正文不再以历史区间宽度为目标。</p>","<p>Conclusions are conditional on two controlled MC members, prescribed networks and frozen cuts. They are not independent feature contributions, significance, official ATLAS/CMS results, a Higgs discovery or a physics measurement. The report no longer centers historical interval width.</p>"),"§ 7");

  const supervisorIds=['spectrum-population','spectrum-yields','spectrum-shapes','spectrum-support'];
  for(const slide of slides) if(supervisorIds.includes(slide.id)) slide.supervisorRelated=true;
  slides[0].notes += `<p>${link('spectrum-population',t('产额与误差','Yields and errors'))} · ${link('spectrum-yields',t('信号与背景谱','Signal/background spectra'))} · ${link('spectrum-shapes',t('谱形改变','Shape changes'))} · ${link('spectrum-support',t('解释边界','Interpretation limits'))}</p>`;
  return Object.freeze({slides,t,en});
})();

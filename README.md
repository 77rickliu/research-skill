# research — 研究生科研全流程助手（Agent Skill）

一个覆盖研究生科研日常的 Agent Skill：从查文献、精读做笔记、写综述，到实验出图、写周报、做汇报 PPT，再到化学分子结构图。内置三级引用真实性校验，从机制上防止 AI 编造参考文献。

兼容实现了 [Agent Skills 规范](https://github.com/anthropics/agent-skills)的宿主（DSH、Claude Code、Cursor 等）。

## 能做什么（8 件事）

| 你说 | 它做 | 产物 |
|---|---|---|
| "帮我找几篇XX方向的论文" | 文献检索，按必读/选读/背景分档 | `research/lit/<主题>.md` |
| "精读这篇PDF" | 双栏感知抽取 + 结构化笔记（贡献/方法/实验/局限） | `research/notes/<key>.md` |
| "写个综述" | 汇总清单与笔记聚类成稿，逐条挂引用 | `research/review/<主题>.md` |
| "写周报 / 润色这段英文" | 周报月报、论文段落（LaTeX/docx）、润色附对照表 | `research/review/weekly/` 等 |
| "分析这组数据、画个图" | pandas 处理 + 统一风格出图（300DPI） | `research/exp/<日期>-<名称>/` |
| "最近XX有什么新论文" | arXiv 增量日报，只报上次之后的新论文 | 对话内报告 |
| "做成组会PPT" | markdown 大纲 → 16:9 演示文稿 | `research/review/*.pptx` |
| "画XX分子的结构" | RDKit 生成出版物级 2D 结构（单分子/网格） | `research/exp/<目录>/` |

## 安装

### 1. 放入 skills 目录

把整个 `research/` 文件夹拷到宿主的 skills 目录（DSH 为 `~/.dsh/skills/`，其他宿主见各自文档），重启会话即被识别。

### 2. 安装 Python 依赖

```
pip install -r requirements.txt
```

需要 Python 3.10+。各宿主捆绑的 Python 亦可（DSH 用户无需自装解释器）。

### 3. 开始用

不需要记任何命令，直接说人话。第一次使用时助手会展示能力全景并推荐起点；推荐的第一轮路径：

**找论文（lit）→ 精读（read）→ 综述（review）→ 写作（write）**

也可以用斜杠命令：`/research lit <主题>`、`/research read <pdf路径>` 等。

## 防编造机制（这个 skill 的核心卖点）

AI 写综述最常见的翻车是**编造参考文献**。本 skill 用三层校验堵死：

1. **入库验真**（verify_refs.py）：每条 BibTeX 入库时，拿 DOI 去 doi.org/Crossref/DataCite 官方注册库核对存在性 + 标题匹配（含词序检查，词序打乱的假论文能识别出来）；无 DOI 的会议论文走 OpenAlex 标题匹配
2. **查重**（bib.py）：同一论文不同渠道导出的条目，按引用键+DOI 双重判重，库里永远一份
3. **一致性终检**（cite_sync.py）：定稿前校验正文每条 `[key]` 引用在库中真实存在，缺一条不允许交付

所有文献 API（doi.org、Crossref、DataCite、arXiv、OpenAlex）均免费、无需注册。

## 已知限制

- 无法获取全文的论文只写摘要级笔记，会明确标注"基于摘要"
- 知网无公开 API，中文文献只出线索，DOI 需人工核对
- 扫描版 PDF 无文本层，会提示换源而非硬编内容
- 本机 LibreOffice 渲染 PPT 预览可能有图片位置偏差（XML 几何正确，PowerPoint 显示正常）
- 涉密课题注意：文献检索的关键词会发送到公开服务（skill 会在对话中主动提醒）

## 目录结构

```
research/（skill 根目录）
├── SKILL.md              # 给 agent 的执行指令
├── README.md             # 本文件
├── requirements.txt      # Python 依赖
└── scripts/
    ├── pdf_extract.py    # PDF 双栏感知抽取
    ├── bib.py            # BibTeX 查重/入库/检查
    ├── verify_refs.py    # DOI/arXiv 官方库验真
    ├── dblp_verify.py    # 纯标题条目 OpenAlex 验真
    ├── cite_sync.py      # 正文引用↔库一致性
    ├── arxiv_watch.py    # arXiv 增量日报
    ├── figstyle.py       # matplotlib 统一风格
    ├── make_deck.py      # markdown → PPTX
    ├── molfig.py         # RDKit 分子结构图
    └── templates/        # 产物模板 ×4
```

运行时会在你的工作区创建 `research/` 数据目录（lit/notes/review/exp/bib.bib），与 skill 本体分离。

## 许可与致谢

PPT 设计规则借鉴 [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)（MIT）。文献元数据来自 Crossref、DataCite、doi.org、arXiv、OpenAlex 的公开 API。

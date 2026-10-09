# MathorCup 大数据优秀论文 PDF 页面证据流水线

目标：使用 GitHub Actions 真正打开 2024 与 2025 年共 16 篇 PDF，提取**逐页**排版结构，不把“PDF 文件在目录里”称作“正文已阅读”。

入口：award-paper-audit/extract_layout.py；GitHub workflow：.github/workflows/audit-award-pdfs.yml。

输出：reports/records/YYYY-NN.json（逐 PDF 文件哈希、页数、字号/字体/颜色、短标题及页码、图表标签/路径统计）、reports/INDEX.md、RUN_SUMMARY.json。

机器提取不等于研究论证已被人工阅读；自动识别的标题与图表标签会有误判，必须对照具体 PDF 页面人工核验。不能把获奖论文中的排版参数伪装成官方规定，也不能以这种浅层统计确定模型方法优劣。

GitHub Actions 在 GitHub runner 上安装固定版 PyMuPDF 1.26.5，直接读取仓库 checkout 的 PDF。预览图仅作为七天到期的 Action artifact，不把全文或原图复制到新的公开文本仓库；repo 原始 PDF 不修改。

使用方法：打开 Actions → Audit 16 MathorCup award PDFs；在本分支提交代码会自动运行，合并后可通过 workflow_dispatch 手动重跑。PyMuPDF 安装：python -m pip install pymupdf==1.26.5。命令：python award-paper-audit/extract_layout.py。

安全与限制：仅统计指定两个论文目录下的 16 个真实 PDF，缺失时阻断；保留源 SHA-256；不发布全文、不做 OCR；扫描页标记为 partial_or_scanned；对用户隐私、作者身份、论文著作权保持谨慎。无 PDF 页面人工核验就保持 human_full_text_review=not_completed。

后续将 16 篇结构证据与当届官方论文规则分开整理，再用于改进 friendly-couscous 的可选学术论文写作与 LaTeX 风格。
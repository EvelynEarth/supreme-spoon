#!/usr/bin/env python3
"""Auditable, non-OCR PDF inventory. Does not claim human reading or quality."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

import fitz

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"^(2024|2025)年MathorCup大数据竞赛优秀论文/\1年MathorCup大数据竞赛优秀论文-(\d+)\.pdf$")
HEADING = re.compile(
    r"^(?:摘\s*要|关\s*键\s*词|目\s*录|参考文献|附\s*录|"
    r"第[一二三四五六七八九十\d]+章|"
    r"(?:[1-9]\d?)(?:\.\d{1,2}){0,2}[\s、．.]*(?:[\u4e00-\u9fff]|[A-Za-z]))"
)
FIGURE = re.compile(r"^(?:图\s*\d+|Fig(?:ure)?\.?\s*\d+)", re.I)
TABLE = re.compile(r"^(?:表\s*\d+|Table\s*\d+)", re.I)


def heading_candidate(text: str) -> bool:
    value = re.sub(r"\s+", " ", text).strip()
    return bool(HEADING.match(value)) and 2 <= len(value) <= 46


def locate_papers(root: Path) -> list[tuple[str, Path, int, int]]:
    entries = []
    for path in root.glob("*年MathorCup大数据竞赛优秀论文/*.pdf"):
        rel = path.relative_to(root).as_posix()
        match = PATTERN.match(rel)
        if match:
            entries.append((rel, path, int(match[1]), int(match[2])))
    entries.sort(key=lambda item: (item[2], item[3]))
    return entries


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha(path: Path) -> str:
    return subprocess.run(["git", "hash-object", str(path)], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def analyze(rel: str, path: Path, year: int, ordinal: int,
            preview_dir: Path | None = None) -> dict:
    doc = fitz.open(path)
    page_count = len(doc)
    if page_count < 1:
        raise RuntimeError("empty PDF: " + rel)
    heading_hits: list[dict] = []
    typographic: Counter[tuple[str, float, str]] = Counter()
    page_summaries = []
    extractable_pages = 0
    rendered = []
    sample_indices = sorted({0, min(1, page_count - 1), min(page_count - 1, max(2, page_count // 2))})
    for i in range(page_count):
        page = doc.load_page(i)
        data = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
        text_chars = 0
        figlabels = 0
        tablelabels = 0
        images = len(page.get_images(full=False))
        drawings = len(page.get_drawings())
        first_lines: list[float] = []
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = [sp for sp in line.get("spans", []) if sp.get("text", "").strip()]
                if not spans:
                    continue
                text = "".join(sp["text"] for sp in spans).strip()
                text_chars += len(text)
                x0, y0, x1, y1 = line["bbox"]
                if page.rect.height * .06 < y0 < page.rect.height * .94:
                    first_lines.append(round(x0, 1))
                if FIGURE.match(text):
                    figlabels += 1
                if TABLE.match(text):
                    tablelabels += 1
                for span in spans:
                    size = round(float(span["size"]), 1)
                    font = str(span["font"])[:70]
                    color = "#" + format(int(span.get("color", 0)) & 0xFFFFFF, "06X")
                    typographic[(font, size, color)] += len(span["text"])
                if heading_candidate(text) and y0 > page.rect.height * .045:
                    if len(heading_hits) < 24 and len(text) <= 34:
                        heading_hits.append({"page": i + 1, "short_heading": text[:34],
                                             "font_size_pt": round(max(float(sp["size"]) for sp in spans), 1),
                                             "x_left_pt": round(float(x0), 1)})
        extractable_pages += (text_chars >= 80)
        page_summaries.append({
            "page": i + 1, "text_characters": text_chars,
            "fig_label_count": figlabels, "table_label_count": tablelabels,
            "image_object_count": images, "vector_path_count": drawings,
            "page_width_pt": round(page.rect.width, 1),
            "page_height_pt": round(page.rect.height, 1),
            "text_left_percentiles_pt": sorted(first_lines)[::max(1, len(first_lines)//6)][:7]
        })
        if preview_dir is not None and i in sample_indices:
            target = preview_dir / f"{year}-{ordinal:02d}-page-{i+1:03d}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False).save(target)
            rendered.append(str(target.relative_to(ROOT)).replace("\\", "/"))
    doc.close()
    fonts = [
        {"font": name, "size_pt": size, "color": color, "characters": count}
        for (name, size, color), count in typographic.most_common(12)
    ]
    return {
        "paper_id": f"{year}-{ordinal:02d}", "source_path": rel,
        "source_sha256": sha256_file(path), "source_git_blob": git_blob_sha(path),
        "source_bytes": path.stat().st_size, "page_count": page_count,
        "text_extractable_pages": extractable_pages,
        "OCR_status": "not_attempted",
        "automated_extraction_status": "usable" if extractable_pages == page_count else "partial_or_scanned",
        "human_full_text_review": "not_completed",
        "human_visual_review": "not_completed",
        "page_specific_heading_candidates": heading_hits,
        "font_size_color_samples": fonts,
        "page_structure_counts": page_summaries,
        "temporary_visual_preview": rendered,
        "interpretation_limitations": (
            "Machine page and font statistics cannot identify academic quality, correct "
            "heading semantics, font names faithfully, or official award formatting. "
            "Human reading and visual inspection with recorded pages are still required."
        )
    }


def write_index(records: list[dict], outfile: Path) -> None:
    lines = [
        "# 2024–2025 MathorCup 大数据优秀论文：机器解析清单",
        "",
        "**范围：** 每篇 PDF 逐页由 PyMuPDF 实际打开，抽取布局统计、字体/颜色、短标题候选、图表标签数量；",
        "只保存最小结构信息，不转载正文、整张图或整页截图。此报告不代表逐篇人工阅读或获奖模板认证。",
        "",
        "| 论文 | PDF 页数 | 可提取文字页 | 图注标签数 | 表注标签数 | 排版原子记录 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in records:
        figures = sum(x["fig_label_count"] for x in r["page_structure_counts"])
        tables = sum(x["table_label_count"] for x in r["page_structure_counts"])
        name = r["paper_id"] + ".json"
        lines.append(
            f'| {r["paper_id"]} | {r["page_count"]} | {r["text_extractable_pages"]} | '
            f'{figures} | {tables} | [逐页记录](records/{name}) |'
        )
    lines += ["", "## 当前真实性边界", "",
              "- **机器已逐页解析**：只有全部 16 篇文档真实打开并提取时才成立；失败则工作流报错。",
              "- **不是 16 篇人工全文阅读**：标题候选不一定真是标题，字号亦非官方指定。",
              "- **视觉预览**：每篇首页、目录候选页、正文代表页仅上传为限期 Actions Artifact，",
              "  不推送回仓库；版权仍归原作者/授权方。",
              "- **后续写作应用**：必须结合页码、人工逐页检查结果及当届官方赛规作出有限结论。",
              "- **隐私**：不读取其他题目附件，输出不含整段论文正文或图片。",
              "", "## 校验摘要", "",
              f"- 实际解析记录数：{len(records)}。",
              f'- 可提取文本页占比：{sum(x["text_extractable_pages"] for x in records)}/'
              f'{sum(x["page_count"] for x in records)}。',
              ""]
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / "award-paper-audit/reports")
    parser.add_argument("--previews", type=Path)
    args = parser.parse_args()
    matches = locate_papers(args.root)
    if len(matches) != 16 or any(
        [x[3] for x in matches if x[2] == y] != list(range(1, 9)) for y in (2024, 2025)
    ):
        raise SystemExit(f"Expected 8 PDFs from each of 2024 and 2025; found {len(matches)}")
    records = []
    for rel, path, year, num in matches:
        record = analyze(rel, path, year, num, args.previews)
        records.append(record)
        output = args.out / "records" / f"{record['paper_id']}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{record['paper_id']}: {record['page_count']} pages, "
              f"{record['text_extractable_pages']} with extractable text")
    write_index(records, args.out / "INDEX.md")
    snapshot = {
        "schema_version": "1.0", "tool": "PyMuPDF automatic page-level audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(records), "paper_ids": [r["paper_id"] for r in records],
        "review_status": "machine_parsed_not_human_reviewed",
        "requires": "Per-page human visual reading, literature judgment, official year rules"
    }
    (args.out / "RUN_SUMMARY.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

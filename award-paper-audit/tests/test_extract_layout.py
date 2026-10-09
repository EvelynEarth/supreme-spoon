"""Synthetic contract tests; no academic quality claim."""
from __future__ import annotations
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "extract_layout.py"
spec = spec_from_file_location("extract_layout", SOURCE)
assert spec and spec.loader
module = module_from_spec(spec)
spec.loader.exec_module(module)

class LayoutContractTests(unittest.TestCase):
    def test_heading_candidates(self):
        self.assertTrue(module.heading_candidate("1 绪论"))
        self.assertTrue(module.heading_candidate("2.1 数据分析"))
        self.assertTrue(module.heading_candidate("参考文献"))
        self.assertFalse(module.heading_candidate("我们对此进行了较充分的研究，不认为此规律普遍成立。"))

    def test_figure_label_candidate(self):
        self.assertTrue(module.FIGURE.match("图 2 不同模型的误差曲线"))
        self.assertTrue(module.TABLE.match("表 3 参数对照"))
        self.assertFalse(module.FIGURE.match("该图说明前述异常"))

    def test_missing_pdfs_do_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(module.locate_papers(Path(td)), [])

if __name__ == "__main__":
    unittest.main()

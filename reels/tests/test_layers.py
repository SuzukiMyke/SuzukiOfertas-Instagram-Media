import tempfile
import unittest
from pathlib import Path

from reel_gen import brand
from reel_gen.layers import Layer, check_layers, contrast_ratio, wrap, wrap_balanced
from reel_gen.pipeline import prepare

from .helpers import cfg_from, pilot_cfg, raw_pilot

BOLD = "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf"


class TestLayers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.cfg = pilot_cfg()
        cls.plan = prepare(cls.cfg, work_root=Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_wrap_respects_real_width(self):
        f = brand.font(BOLD, 80)
        txt = "Achados de tecnologia para quem gosta de novidade todos os dias"
        for w in (300, 500, 896):
            for ln in wrap(txt, f, w):
                self.assertLessEqual(f.getlength(ln), w)

    def test_wrap_long_word_forced(self):
        f = brand.font(BOLD, 80)
        lines = wrap("Supercalifragilisticexpialidocious", f, 300)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(f.getlength(ln) <= 300 for ln in lines))

    def test_balanced_no_orphan_and_dash(self):
        f = brand.font(BOLD, 44)
        lines = wrap_balanced("DEMONSTRAÇÃO TÉCNICA — NÃO É PRODUTO À VENDA", f, 700)
        self.assertEqual(len(lines), 2)
        self.assertFalse(lines[1].startswith("—"))
        self.assertEqual(len(wrap_balanced("a b c", f, 2000)), 1)

    def test_contrast(self):
        self.assertAlmostEqual(contrast_ratio((255, 255, 255), (0, 0, 0)), 21.0, places=1)
        self.assertAlmostEqual(contrast_ratio((10, 10, 10), (10, 10, 10)), 1.0)

    def test_pilot_layers_ok(self):
        self.assertEqual(self.plan["errors"], [])
        layers = [la for sp in self.plan["segments"] for la in sp["layers"]]
        self.assertGreater(len(layers), 20)
        sz, o = self.cfg["safe_zone"], self.cfg["output"]
        for la in layers:
            x0, y0, x1, y1 = la.motion_bbox()
            self.assertGreaterEqual(x0, sz["left"], la.name)
            self.assertGreaterEqual(y0, sz["top"], la.name)
            self.assertLessEqual(x1, o["width"] - sz["right"], la.name)
            self.assertLessEqual(y1, o["height"] - sz["bottom"], la.name)
            self.assertTrue(Path(la.path).is_file())

    def test_font_minimums(self):
        v = self.cfg["validation"]
        for sp in self.plan["segments"]:
            for la in sp["layers"]:
                if la.role == "title":
                    self.assertGreaterEqual(la.font_px, v["min_title_px"])
                elif la.role in ("body", "label"):
                    self.assertGreaterEqual(la.font_px, v["min_body_px"])

    def test_logo_aspect_and_presence(self):
        logos = [la for sp in self.plan["segments"] for la in sp["layers"] if la.role == "logo"]
        self.assertEqual(len(logos), 5)  # gancho + 3 cenas + CTA
        for la in logos:
            self.assertAlmostEqual(la.w / la.h, 1.0, places=2)
        cta = [la for la in logos if la.name == "logo_cta"]
        self.assertEqual(len(cta), 1)
        self.assertGreater(cta[0].w, self.cfg["logo"]["size_px"])

    def test_demo_label_on_every_segment(self):
        for sp in self.plan["segments"]:
            names = [la.name for la in sp["layers"]]
            self.assertIn("label", names, sp["segment"].key)

    def test_no_price_layers(self):
        txt = " ".join(la.text for sp in self.plan["segments"] for la in sp["layers"])
        self.assertNotIn("R$", txt)
        self.assertNotIn("%", txt)

    def test_check_layers_detects_violations(self):
        bad = Layer("x", "p.png", 10, 100, 200, 50, 0, 1, role="body", font_px=30, contrast=2.0)
        logo = Layer("logo", "p.png", 100, 300, 150, 120, 0, 1, role="logo", meta={"source_aspect": 1.0})
        errs = check_layers([bad, logo], self.cfg, "t")
        self.assertTrue(any("margem segura" in e for e in errs))
        self.assertTrue(any("30px" in e for e in errs))
        self.assertTrue(any("contraste" in e for e in errs))
        self.assertTrue(any("proporção do logo" in e for e in errs))

    def test_overflow_reported(self):
        raw = raw_pilot()
        raw["cta"]["headline"] = "Texto muito longo " * 12
        with tempfile.TemporaryDirectory() as d:
            plan = prepare(cfg_from(raw), work_root=Path(d))
        self.assertTrue(any("não cabe" in e or "margem" in e for e in plan["errors"]))

    def test_logo_colors_untouched(self):
        lg = self.cfg["logo"]
        img = brand.logo_image(lg["path"], 300, 1.0, "none")
        from PIL import Image
        ref = Image.open(brand.resolve_path(lg["path"])).convert("RGBA").resize((300, 300), Image.LANCZOS)
        self.assertEqual(img.tobytes(), ref.tobytes())


if __name__ == "__main__":
    unittest.main()

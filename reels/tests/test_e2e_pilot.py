"""Ponta a ponta: renderiza o piloto e o modelo (sem mudar código) e valida.

Demora ~1,5 min (2 reels + 2 CTAs). Saídas em diretório temporário.
"""
import json
import tempfile
import unittest
from pathlib import Path

from reel_gen.config import REELS_ROOT, load_config
from reel_gen.pipeline import build, render_cta_only

CONFIGS = REELS_ROOT / "configs"


class TestE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.pilot = build(CONFIGS / "pilot_demo_01.json", out_root=cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pilot_approved(self):
        r = self.pilot
        self.assertTrue(r["approved_technical"], r["errors"])
        self.assertEqual([c for c in r["checks"] if c["blocking"] and not c["ok"]], [])
        self.assertTrue((self.out / "pilot_demo_01_report.json").is_file())
        self.assertTrue((self.out / "pilot_demo_01_report.md").is_file())
        json.loads((self.out / "pilot_demo_01_report.json").read_text(encoding="utf-8"))

    def test_pilot_specs(self):
        r = self.pilot
        v = r["video"]
        self.assertEqual((v["width"], v["height"], v["codec_name"], v["pix_fmt"]), (1080, 1920, "h264", "yuv420p"))
        self.assertEqual(v["r_frame_rate"], "30/1")
        self.assertTrue(15 <= r["duration_s"] <= 20)
        segs = r["timeline"]["segments"]
        self.assertLessEqual(segs[0]["duration_s"], 3.0)
        self.assertEqual(segs[0]["kind"], "hook")
        self.assertEqual(segs[-1]["kind"], "cta")
        self.assertGreaterEqual(segs[-1]["duration_s"], 2.5)

    def test_three_distinct_categories_synthetic_labeled(self):
        cfg = load_config(CONFIGS / "pilot_demo_01.json")
        cats = {s["category"].lower() for s in cfg["scenes"]}
        self.assertEqual(len(cats), 3)
        self.assertTrue(all(s["source"]["kind"] == "synthetic_demo" for s in cfg["scenes"]))
        self.assertTrue(cfg["demo_label"]["enabled"])
        for k in ("price", "discount", "stock", "rating"):
            self.assertTrue(all(k not in s for s in cfg["scenes"]))

    def test_frames_and_motion(self):
        names = [f["label"] for f in self.pilot["frames"]]
        self.assertIn("cta_cta_meio", names)
        self.assertEqual(sum(1 for n in names if n.startswith("scene_")), 3)
        motion = [c for c in self.pilot["checks"] if c["check"].startswith("movimento de câmera")]
        self.assertEqual(len(motion), 3)
        self.assertTrue(all(c["ok"] for c in motion))

    def test_second_config_without_code_change(self):
        r = build(CONFIGS / "example_template.json", out_root=self.out)
        self.assertTrue(r["approved_technical"], r["errors"])
        self.assertNotEqual(r["sha256"], self.pilot["sha256"])

    def test_cta_only_independent_and_deterministic(self):
        a = render_cta_only(CONFIGS / "pilot_demo_01.json", out_root=self.out / "a")
        b = render_cta_only(CONFIGS / "pilot_demo_01.json", out_root=self.out / "b")
        self.assertTrue(a["approved_technical"], a["errors"])
        self.assertEqual([s["kind"] for s in a["timeline"]["segments"]], ["cta"])
        # mesma config + assets -> mesmos quadros (pixel a pixel)
        self.assertEqual(a["frames_md5"], b["frames_md5"])

    def test_byte_identical_with_one_thread(self):
        raw = json.loads((CONFIGS / "pilot_demo_01.json").read_text(encoding="utf-8"))
        raw["output"]["threads"] = 1
        cfgp = self.out / "cta_1thread.json"
        cfgp.write_text(json.dumps(raw), encoding="utf-8")
        a = render_cta_only(cfgp, out_root=self.out / "t1a")
        b = render_cta_only(cfgp, out_root=self.out / "t1b")
        self.assertEqual(a["sha256"], b["sha256"])


if __name__ == "__main__":
    unittest.main()

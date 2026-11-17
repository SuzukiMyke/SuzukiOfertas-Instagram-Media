import unittest

from reel_gen.motion import camera_values, ease, frames_for, overlay_xy, smoothness_ratio, window, zoompan_filter
from reel_gen.timeline import check_timeline, plan_timeline

from .helpers import cfg_from, pilot_cfg, raw_pilot


class TestTimeline(unittest.TestCase):
    def test_pilot_offsets_and_total(self):
        cfg = pilot_cfg()
        tl = plan_timeline(cfg)
        self.assertEqual([s.key for s in tl.segments], ["hook", "s1", "s2", "s3", "cta"])
        durs = [2.5, 4.6, 4.6, 4.6, 3.6]
        trs = [0.4, 0.4, 0.4, 0.4]
        self.assertAlmostEqual(tl.total, sum(durs) - sum(trs), places=6)
        for prev, cur in zip(tl.segments, tl.segments[1:]):
            # o segmento seguinte começa quando a transição de saída do anterior começa
            self.assertAlmostEqual(cur.start, prev.end - prev.trans_out["duration"], places=6)
            self.assertEqual(cur.trans_in, prev.trans_out)
        self.assertIsNone(tl.segments[-1].trans_out)
        self.assertEqual(check_timeline(tl, cfg), [])
        self.assertTrue(15 <= tl.total <= 20)

    def test_frame_quantization(self):
        raw = raw_pilot()
        raw["scenes"][0]["duration"] = 4.567
        tl = plan_timeline(cfg_from(raw))
        s1 = tl.segments[1]
        self.assertEqual(s1.frames, 137)
        self.assertAlmostEqual(s1.duration * 30, round(s1.duration * 30), places=9)

    def test_hook_limit(self):
        raw = raw_pilot()
        raw["hook"]["duration"] = 3.5
        cfg = cfg_from(raw)
        self.assertTrue(any("gancho" in e for e in check_timeline(plan_timeline(cfg), cfg)))

    def test_cta_min(self):
        raw = raw_pilot()
        raw["cta"]["duration"] = 2.0
        cfg = cfg_from(raw)
        self.assertTrue(any("CTA" in e for e in check_timeline(plan_timeline(cfg), cfg)))

    def test_total_out_of_range(self):
        raw = raw_pilot()
        raw["scenes"] = raw["scenes"][:1]
        cfg = cfg_from(raw)
        self.assertTrue(any("duração total" in e for e in check_timeline(plan_timeline(cfg), cfg)))

    def test_transitions_consume_scene(self):
        raw = raw_pilot()
        raw["scenes"][1]["duration"] = 1.0
        raw["scenes"][0]["transition_out"]["duration"] = 0.6
        raw["scenes"][1]["transition_out"]["duration"] = 0.6
        cfg = cfg_from(raw)
        self.assertTrue(any("consomem" in e for e in check_timeline(plan_timeline(cfg), cfg)))

    def test_content_window(self):
        tl = plan_timeline(pilot_cfg())
        s2 = tl.segments[2]
        self.assertAlmostEqual(s2.content_start, 0.4)
        self.assertAlmostEqual(s2.content_end, s2.duration - 0.4)

    def test_cta_only(self):
        tl = plan_timeline(pilot_cfg(), cta_only=True)
        self.assertEqual([s.kind for s in tl.segments], ["cta"])
        self.assertAlmostEqual(tl.total, 3.6)


class TestMotion(unittest.TestCase):
    def test_easing_endpoints_monotonic(self):
        for name in ("linear", "ease_in", "ease_out", "ease_in_out"):
            vals = [ease(name, i / 50) for i in range(51)]
            self.assertAlmostEqual(vals[0], 0)
            self.assertAlmostEqual(vals[-1], 1)
            self.assertTrue(all(b >= a for a, b in zip(vals, vals[1:])), name)

    def test_camera_window_bounds_and_continuity(self):
        cam = {"zoom_start": 1.0, "zoom_end": 1.15, "pan_start": [0.5, 0.5], "pan_end": [0.0, 1.0],
               "easing": "ease_in_out"}
        n, iw, ih = 138, 2160, 3840
        prev = None
        for f in range(n):
            x, y, w, h = window(cam, n, f, iw, ih)
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, iw + 1e-6)
            self.assertLessEqual(y + h, ih + 1e-6)
            if prev:  # sem saltos: deslocamento por quadro limitado
                self.assertLess(abs(x - prev[0]), 12)
                self.assertLess(abs(w - prev[2]), 6)
            prev = (x, y, w, h)
        self.assertEqual(camera_values(cam, n, 0)[0], 1.0)
        self.assertAlmostEqual(camera_values(cam, n, n - 1)[0], 1.15)

    def test_zoompan_expression(self):
        cam = {"zoom_start": 1.0, "zoom_end": 1.2, "pan_start": [0.5, 0.5], "pan_end": [0.4, 0.6], "easing": "linear"}
        f = zoompan_filter(cam, 120, 1080, 1920, 30)
        self.assertTrue(f.startswith("zoompan=z='"))
        self.assertIn(":d=120:s=1080x1920:fps=30", f)
        self.assertIn("on/119", f)

    def test_overlay_slide(self):
        x, y = overlay_xy(64, 1000, "slide_up", 48, 0.5, 0.5)
        self.assertEqual(x, "64")
        self.assertIn("1000+48*", y)
        self.assertEqual(overlay_xy(10, 20, "fade", 48, 0, 1), ("10", "20"))

    def test_frames_and_smoothness(self):
        self.assertEqual(frames_for(4.6, 30), 138)
        self.assertAlmostEqual(smoothness_ratio([1, 1, 1, 2]), 2.0)


if __name__ == "__main__":
    unittest.main()

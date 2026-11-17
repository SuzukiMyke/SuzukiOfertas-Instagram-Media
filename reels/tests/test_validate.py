import subprocess
import tempfile
import unittest
from pathlib import Path

from reel_gen.validate import check_video, frame_stddev, moov_before_mdat, probe

from .helpers import pilot_cfg


def make_mp4(path, size="1080x1920", rate=30, dur=1, faststart=True, color=None):
    src = f"color=c={color}:s={size}:r={rate}:d={dur}" if color else f"testsrc2=s={size}:r={rate}:d={dur}"
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p", "-profile:v", "high", "-threads", "2"]
    if faststart:
        cmd += ["-movflags", "+faststart"]
    subprocess.run(cmd + [str(path)], check=True, shell=False)
    return path


class TestValidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.good = make_mp4(d / "good.mp4")
        cls.slow = make_mp4(d / "nofast.mp4", faststart=False)
        cls.small = make_mp4(d / "small.mp4", size="720x1280", rate=25)
        cls.cfg = pilot_cfg()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def by_name(self, res):
        return {c["check"]: c for c in res["checks"]}

    def test_good_minimal_mp4(self):
        res = check_video(self.good, self.cfg, None)
        failed = [c for c in res["checks"] if not c["ok"]]
        self.assertEqual(failed, [])

    def test_duration_range_enforced(self):
        res = check_video(self.good, self.cfg, (15, 20))
        self.assertFalse(self.by_name(res)["duração 15–20 s"]["ok"])

    def test_faststart_detection(self):
        self.assertTrue(moov_before_mdat(self.good))
        self.assertFalse(moov_before_mdat(self.slow))
        res = check_video(self.slow, self.cfg, None)
        self.assertFalse(self.by_name(res)["moov no início (faststart)"]["ok"])

    def test_wrong_resolution_and_fps(self):
        c = self.by_name(check_video(self.small, self.cfg, None))
        self.assertFalse(c["resolução 1080x1920"]["ok"])
        self.assertFalse(c["fps 30 constante"]["ok"])

    def test_probe_fields(self):
        info = probe(self.good)
        v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
        self.assertEqual(v["codec_name"], "h264")

    def test_uniform_frame_detected(self):
        d = Path(self.tmp.name)
        flat = d / "flat.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64",
                        "-frames:v", "1", str(flat)], check=True)
        self.assertLess(frame_stddev(flat), 1.0)


if __name__ == "__main__":
    unittest.main()


class TestValidateRejects(unittest.TestCase):
    def test_baseline_and_high_bitrate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "base.mp4"
            subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc2=s=1080x1920:r=30:d=1", "-c:v", "libx264", "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p", "-threads", "2", str(p)], check=True)
            c = {x["check"]: x for x in check_video(p, pilot_cfg(), None)["checks"]}
        self.assertFalse(c["perfil High/Main"]["ok"])
        self.assertFalse(c["bitrate de vídeo ≤ 12 Mbps"]["ok"])

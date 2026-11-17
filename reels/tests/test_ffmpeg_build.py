import inspect
import tempfile
import unittest
from pathlib import Path

from reel_gen import ffmpeg_build
from reel_gen.audio import build_audio
from reel_gen.ffmpeg_build import build_final_command, build_segment_command, final_graph, run
from reel_gen.pipeline import prepare

from .helpers import cfg_from, pilot_cfg, raw_pilot


class TestFFmpegBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.cfg = pilot_cfg()
        cls.plan = prepare(cls.cfg, work_root=Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_shell_true_anywhere(self):
        import reel_gen
        for f in Path(reel_gen.__file__).parent.glob("*.py"):
            self.assertNotIn("shell=True", f.read_text(encoding="utf-8"), f.name)
        self.assertIn("shell=False", inspect.getsource(ffmpeg_build.run))

    def test_run_rejects_string(self):
        with self.assertRaises(TypeError):
            run("ffmpeg -version")

    def test_segment_command(self):
        sp = self.plan["segments"][1]
        cmd = build_segment_command(sp, self.cfg, "/tmp/x.mp4")
        self.assertIsInstance(cmd, list)
        self.assertTrue(all(isinstance(a, str) for a in cmd))
        self.assertEqual(cmd[0], "ffmpeg")
        fc = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("zoompan=", fc)
        self.assertIn(f":d={sp['segment'].frames}:", fc)
        self.assertIn("overlay=", fc)
        self.assertIn("fade=t=in", fc)
        self.assertNotIn("drawtext", fc)  # texto vem de PNG (sem fontconfig/freetype no FFmpeg)
        self.assertEqual(cmd.count("-i"), 1 + len(sp["layers"]))
        self.assertEqual(cmd[cmd.index("-frames:v") + 1], str(sp["segment"].frames))

    def test_final_command_args(self):
        files = [f"/tmp/s{k}.mp4" for k in range(len(self.plan["segments"]))]
        cmd = build_final_command(files, self.plan, self.cfg, "/tmp/out.mp4")
        joined = " ".join(cmd)
        for frag in ("-c:v libx264", "-profile:v high", "-pix_fmt yuv420p", "-r 30", "-threads 2",
                     "-preset veryfast", "-crf 20", "-movflags +faststart", "-an", "-map_metadata -1"):
            self.assertIn(frag, joined)
        self.assertEqual(cmd[-1], "/tmp/out.mp4")
        # leitura na ordem da linha do tempo
        offs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-itsoffset"]
        self.assertEqual(len(offs), len(files))

    def test_xfade_offsets_match_timeline(self):
        graph, _ = final_graph(self.plan)
        segs = [sp["segment"] for sp in self.plan["segments"]]
        self.assertEqual(graph.count("xfade="), len(segs) - 1)
        for s in segs[1:]:
            self.assertIn(f"transition={s.trans_in['type']}", graph)
            self.assertIn(f"offset={round(s.start, 6):g}", graph)

    def test_silent_track_option(self):
        raw = raw_pilot()
        raw["audio"]["silent_track"] = True
        cfg = cfg_from(raw)
        a_in, parts, label = build_audio(cfg, 5, 18.3)
        self.assertIn("anullsrc=r=48000:cl=stereo", a_in)
        self.assertEqual(label, "[aout]")

    def test_licensed_audio_graph(self):
        raw = raw_pilot()
        tr = {"file": "reels/assets/audio_licensed/musica.m4a", "type": "music", "license_id": "L1",
              "license_url_or_proof": "doc", "author": "A", "start": 0, "gain_db": -12, "loop": True,
              "fade_in": 0.5, "fade_out": 1.0}
        voz = dict(tr, file="reels/assets/audio_licensed/voz.m4a", type="voice", loop=False, gain_db=0, start=0.5)
        raw["audio"] = {"mode": "licensed", "tracks": [tr, voz], "ducking": True}
        cfg = cfg_from(raw)
        a_in, parts, label = build_audio(cfg, 5, 18.3)
        g = ";".join(parts)
        self.assertIn("-stream_loop", a_in)
        for frag in ("volume=-12dB", "afade=t=in", "afade=t=out", "adelay=500", "sidechaincompress",
                     "amix=inputs=2", "loudnorm=I=-14"):
            self.assertIn(frag, g)
        self.assertEqual(label, "[aout]")


if __name__ == "__main__":
    unittest.main()

import unittest

from reel_gen.config import ConfigError, deep_merge, load_config, normalize, strip_comments

from .helpers import PILOT, raw_pilot


class TestConfig(unittest.TestCase):
    def test_pilot_loads_with_defaults(self):
        cfg = load_config(PILOT)
        self.assertEqual(cfg["output"]["width"], 1080)
        self.assertEqual(cfg["output"]["threads"], 2)            # padrão mesclado
        self.assertEqual(cfg["validation"]["hook_max"], 3.0)
        self.assertEqual(len(cfg["scenes"]), 3)

    def test_unknown_key_is_error(self):
        raw = raw_pilot()
        raw["scenes"][0]["preco_inventado"] = "R$ 10"
        with self.assertRaises(ConfigError) as cm:
            normalize(raw)
        self.assertTrue(any("chave desconhecida" in e for e in cm.exception.errors))

    def test_unknown_top_level_key(self):
        raw = raw_pilot()
        raw["extra"] = 1
        with self.assertRaises(ConfigError):
            normalize(raw)

    def test_missing_required(self):
        raw = raw_pilot()
        del raw["scenes"][1]["source"]["license"]
        with self.assertRaises(ConfigError) as cm:
            normalize(raw)
        self.assertTrue(any("license" in e and "obrigatório" in e for e in cm.exception.errors))

    def test_wrong_types(self):
        raw = raw_pilot()
        raw["output"]["fps"] = "30"
        raw["theme"]["palette"]["bg"] = "azul"
        raw["scenes"][0]["camera"]["pan_end"] = [1.5, 0.2]
        with self.assertRaises(ConfigError) as cm:
            normalize(raw)
        msgs = "\n".join(cm.exception.errors)
        self.assertIn("output.fps", msgs)
        self.assertIn("palette.bg", msgs)
        self.assertIn("pan_end", msgs)

    def test_enum_and_ranges(self):
        raw = raw_pilot()
        raw["scenes"][0]["transition_out"]["type"] = "explode"
        raw["output"]["crf"] = 80
        with self.assertRaises(ConfigError):
            normalize(raw)

    def test_hook_lines_limit(self):
        raw = raw_pilot()
        raw["hook"]["lines"] = ["a", "b", "c"]
        with self.assertRaises(ConfigError):
            normalize(raw)

    def test_comments_ignored(self):
        self.assertEqual(strip_comments({"_c": 1, "a": [{"_x": 2, "b": 3}]}), {"a": [{"b": 3}]})
        raw = raw_pilot()
        raw["_nota"] = "comentário"
        raw["output"]["_nota"] = "comentário"
        normalize(raw)  # não levanta

    def test_deep_merge(self):
        self.assertEqual(deep_merge({"a": {"b": 1, "c": 2}, "l": [1]}, {"a": {"c": 3}, "l": [2]}),
                         {"a": {"b": 1, "c": 3}, "l": [2]})


if __name__ == "__main__":
    unittest.main()

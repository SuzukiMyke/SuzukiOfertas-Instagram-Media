import unittest

from reel_gen.rules import check_rules, find_forbidden, fold, scene_label

from .helpers import cfg_from, raw_pilot


def errs_of(raw):
    return check_rules(cfg_from(raw))[0]


class TestRules(unittest.TestCase):
    def test_pilot_passes(self):
        errs, _ = check_rules(cfg_from(raw_pilot()))
        self.assertEqual(errs, [])

    def test_price_without_verification(self):
        raw = raw_pilot()
        raw["scenes"][0]["price"] = "R$ 99,90"
        self.assertTrue(any("verified_at" in e for e in errs_of(raw)))

    def test_price_with_verification_but_synthetic(self):
        raw = raw_pilot()
        sc = raw["scenes"][0]
        sc.update(price="R$ 99,90", verified_at="2026-11-17T10:00:00Z", source_url="https://loja.example/x")
        self.assertTrue(any("kind=real_photo" in e for e in errs_of(raw)))

    def test_discount_stock_rating_blocked(self):
        for k in ("discount", "stock", "rating"):
            raw = raw_pilot()
            raw["scenes"][1][k] = "algo"
            self.assertTrue(errs_of(raw), k)

    def test_forbidden_terms_any_field_and_accents(self):
        cases = [("hook", None, "IMPERDIVEL demais"), ("title", 0, "O menor preço"),
                 ("subtitle", 1, "Últimas unidades!"), ("highlight", 2, "Garantido")]
        for field, i, txt in cases:
            raw = raw_pilot()
            if field == "hook":
                raw["hook"]["lines"][0] = txt
            elif field == "highlight":
                raw["scenes"][i]["highlights"][0]["text"] = txt
            else:
                raw["scenes"][i][field] = txt
            self.assertTrue(any("termo proibido" in e for e in errs_of(raw)), txt)

    def test_forbidden_word_boundaries(self):
        self.assertEqual(find_forbidden("Ofertas garantidas", [fold("garantido")]), [])
        self.assertEqual(find_forbidden("É garantido!", [fold("garantido")]), ["garantido"])

    def test_extra_forbidden_terms(self):
        raw = raw_pilot()
        raw["policy"] = {"extra_forbidden_terms": ["achados"]}
        self.assertTrue(any("achados" in e for e in errs_of(raw)))

    def test_synthetic_requires_demo_label(self):
        raw = raw_pilot()
        raw["demo_label"]["enabled"] = False
        self.assertTrue(any("demo_label" in e for e in errs_of(raw)))

    def test_illustrative_gets_label(self):
        cfg = cfg_from(raw_pilot())
        sc = cfg["scenes"][0]
        sc["source"]["kind"] = "illustrative"
        self.assertEqual(scene_label(cfg, sc), "Imagem ilustrativa")
        sc["source"]["kind"] = "real_photo"
        self.assertIsNone(scene_label(cfg, sc))

    def test_product_model_on_non_real(self):
        raw = raw_pilot()
        raw["scenes"][0]["product_model"] = "Fone XYZ-123"
        self.assertTrue(any("modelo específico" in e for e in errs_of(raw)))

    def test_remote_and_missing_sources(self):
        raw = raw_pilot()
        raw["scenes"][0]["source"]["path"] = "https://exemplo.com/foto.jpg"
        raw["scenes"][1]["source"]["path"] = "reels/assets/synthetic/nao_existe.jpg"
        raw["scenes"][2]["source"]["path"] = "../../etc/passwd"
        errs = errs_of(raw)
        self.assertTrue(any("URL remota" in e for e in errs))
        self.assertTrue(any("não encontrado" in e for e in errs))
        self.assertTrue(any("fora de" in e for e in errs))

    def test_channels_official_only(self):
        raw = raw_pilot()
        raw["channels"]["telegram"]["url"] = "https://t.me/outro_canal"
        self.assertTrue(any("canal oficial" in e for e in errs_of(raw)))
        raw = raw_pilot()
        raw["channels"]["instagram"] = {"label": "Instagram", "url": "https://instagram.com/x", "display": "x"}
        self.assertTrue(any("não registrado" in e for e in errs_of(raw)))

    def test_button_without_channel(self):
        raw = raw_pilot()
        raw["cta"]["buttons"].append("Discord")
        self.assertTrue(any("Discord" in e for e in errs_of(raw)))

    def test_disclosure_required(self):
        raw = raw_pilot()
        raw["cta"]["disclosure"] = "  "
        self.assertTrue(any("disclosure" in e for e in errs_of(raw)))

    def test_audio_rules(self):
        raw = raw_pilot()
        track = {"file": "reels/assets/synthetic/s1_tecnologia.jpg", "type": "music", "license_id": "x",
                 "license_url_or_proof": "y", "author": "z", "start": 0, "gain_db": -6, "loop": False,
                 "fade_in": 0, "fade_out": 0}
        raw["audio"] = {"mode": "silent", "tracks": [track]}
        self.assertTrue(any("vazio no modo silent" in e for e in errs_of(raw)))
        raw["audio"] = {"mode": "licensed", "tracks": [track]}
        self.assertTrue(any("fora de audio_licensed" in e for e in errs_of(raw)))
        raw["audio"] = {"mode": "licensed", "tracks": []}
        self.assertTrue(any("ao menos uma faixa" in e for e in errs_of(raw)))


if __name__ == "__main__":
    unittest.main()

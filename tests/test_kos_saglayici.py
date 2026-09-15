"""Sağlayıcı sürücüsünün testleri — ağ yok, claude çağrısı yok, para harcamaz.

Kapsam: `saglayici: anthropic` (varsayılan) yoluna dokunulmadığı, `saglayici: nim`
yolunun Claude Code'u yerel proxy'ye yönlendirdiği, eksik anahtar/model durumunda
net Türkçe hata verildiği ve kuru koşunun sağlayıcıyı ekrana bastığı.

python3 -m unittest discover -s tests
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "bin"))
import kos  # noqa: E402
import model_proxy  # noqa: E402

TAKIM_MD = """---
name: {ad}
description: {ad} takımı — test.
saglayici: {saglayici}
model: {model}
tools: [Read, Write]
gerekli_anahtarlar: []
butce_usd: 2
---

# {ad}
"""


def sahte_kok(tmp, ad="deneme", saglayici="anthropic", model="sonnet"):
    """Geçici dizinde takimlar/<ad>/{takim.md,durum.json,kosu/} olan minik bir repo."""
    kok = Path(tmp) / "kok"
    dizin = kok / "takimlar" / ad
    (dizin / "kosu").mkdir(parents=True)
    (dizin / "takim.md").write_text(
        TAKIM_MD.format(ad=ad, saglayici=saglayici, model=model), encoding="utf-8")
    (dizin / "durum.json").write_text(json.dumps(
        {"takim": ad, "son_kosu": None, "son_sonuc": None, "kuyruk": []},
        ensure_ascii=False), encoding="utf-8")
    return kok


class AnthropicYoluTesti(unittest.TestCase):
    """Varsayılan yol dokunulmaz: hiçbir ANTHROPIC_* değişkeni eklenmez ya da silinmez."""

    def test_saglayici_yoksa_ortam_aynen_doner(self):
        temel = {"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-gercek"}
        ortam, model = kos.saglayici_ortami({"model": "sonnet"}, temel)
        self.assertEqual(ortam, temel)
        self.assertEqual(model, "sonnet")

    def test_saglayici_anthropic_yazilsa_da_ortam_aynen_doner(self):
        temel = {"ANTHROPIC_API_KEY": "sk-gercek"}
        ortam, model = kos.saglayici_ortami({"saglayici": "anthropic", "model": "opus"}, temel)
        self.assertEqual(ortam, temel)
        self.assertEqual(model, "opus")

    def test_model_yoksa_sonnet_varsayilir(self):
        _, model = kos.saglayici_ortami({}, {})
        self.assertEqual(model, "sonnet")

    def test_temel_ortam_degistirilmez(self):
        temel = {"ANTHROPIC_API_KEY": "sk-gercek", "NVIDIA_API_KEY": "nvapi-test"}
        kopya = dict(temel)
        kos.saglayici_ortami({"saglayici": "nim", "model": "meta/llama-3.3-70b-instruct"}, temel)
        self.assertEqual(temel, kopya, "girdi sözlüğü yerinde değiştirilmemeli")


class NimYoluTesti(unittest.TestCase):
    """`saglayici: nim` → ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY temizlenir."""

    TEMEL = {"PATH": "/bin", "NVIDIA_API_KEY": "nvapi-test", "ANTHROPIC_API_KEY": "sk-gercek"}

    def test_proxy_adresi_ve_bearer_token_verilir(self):
        ortam, model = kos.saglayici_ortami(
            {"saglayici": "nim", "model": "meta/llama-3.3-70b-instruct"}, self.TEMEL)
        self.assertEqual(ortam["ANTHROPIC_BASE_URL"], kos.NIM_PROXY_VARSAYILAN)
        self.assertTrue(ortam["ANTHROPIC_AUTH_TOKEN"])
        self.assertEqual(model, "meta/llama-3.3-70b-instruct")

    def test_anthropic_api_key_alt_surece_gecmez(self):
        """Anahtar kalırsa Claude Code Anthropic'e düşer; NIM koşusu sessizce ücretli olur."""
        ortam, _ = kos.saglayici_ortami(
            {"saglayici": "nim", "model": "meta/llama-3.3-70b-instruct"}, self.TEMEL)
        self.assertNotIn("ANTHROPIC_API_KEY", ortam)

    def test_arka_plan_isleri_de_ayni_modele_gider(self):
        """Haiku varsayılanı bırakılırsa oturum başlığı gibi işler proxy'de olmayan modele gider."""
        ortam, model = kos.saglayici_ortami(
            {"saglayici": "nim", "model": "meta/llama-3.3-70b-instruct"}, self.TEMEL)
        self.assertEqual(ortam["ANTHROPIC_DEFAULT_HAIKU_MODEL"], model)

    def test_takim_md_modeli_takma_adsa_env_NIM_MODEL_kullanilir(self):
        temel = {**self.TEMEL, "NIM_MODEL": "nvidia/llama-3.1-nemotron-70b-instruct"}
        _, model = kos.saglayici_ortami({"saglayici": "nim", "model": "sonnet"}, temel)
        self.assertEqual(model, "nvidia/llama-3.1-nemotron-70b-instruct")

    def test_takim_md_modeli_env_NIM_MODEL_i_ezer(self):
        temel = {**self.TEMEL, "NIM_MODEL": "meta/llama-3.1-8b-instruct"}
        _, model = kos.saglayici_ortami(
            {"saglayici": "nim", "model": "moonshotai/kimi-k2-instruct"}, temel)
        self.assertEqual(model, "moonshotai/kimi-k2-instruct")

    def test_proxy_adresi_ve_token_env_ile_degistirilebilir(self):
        temel = {**self.TEMEL, "NIM_PROXY_URL": "http://127.0.0.1:4999",
                 "LITELLM_MASTER_KEY": "sk-benim"}
        ortam, _ = kos.saglayici_ortami(
            {"saglayici": "nim", "model": "meta/llama-3.3-70b-instruct"}, temel)
        self.assertEqual(ortam["ANTHROPIC_BASE_URL"], "http://127.0.0.1:4999")
        self.assertEqual(ortam["ANTHROPIC_AUTH_TOKEN"], "sk-benim")

    def test_nvidia_anahtari_yoksa_net_hata(self):
        with self.assertRaises(ValueError) as tutamac:
            kos.saglayici_ortami({"saglayici": "nim", "model": "meta/llama-3.3-70b-instruct"},
                                 {"PATH": "/bin"})
        self.assertIn("NVIDIA_API_KEY", str(tutamac.exception))

    def test_model_secilmemisse_net_hata(self):
        with self.assertRaises(ValueError) as tutamac:
            kos.saglayici_ortami({"saglayici": "nim", "model": "sonnet"},
                                 {"NVIDIA_API_KEY": "nvapi-test"})
        self.assertIn("NIM_MODEL", str(tutamac.exception))

    def test_bilinmeyen_saglayici_net_hata(self):
        with self.assertRaises(ValueError) as tutamac:
            kos.saglayici_ortami({"saglayici": "ollama"}, {})
        self.assertIn("ollama", str(tutamac.exception))


class KomutTesti(unittest.TestCase):
    def test_claude_komutu_modeli_oldugu_gibi_tasir(self):
        komut = kos.claude_komutu("merhaba", ["Read"], 2, "meta/llama-3.3-70b-instruct")
        self.assertIn("--model", komut)
        self.assertEqual(komut[komut.index("--model") + 1], "meta/llama-3.3-70b-instruct")


class AltSureceGecenOrtamTesti(unittest.TestCase):
    """`_claude_kos` alt sürece gerçekten yamalı ortamı ve NIM modelini veriyor mu."""

    def test_nim_kosusunda_subprocess_ortami_yamalidir(self):
        fm = {"saglayici": "nim", "model": "meta/llama-3.3-70b-instruct", "tools": ["Read"]}
        sahte = mock.Mock(stdout=json.dumps({"is_error": False, "result": "ok"}), stderr="",
                          returncode=0)
        with mock.patch.dict("os.environ", {"NVIDIA_API_KEY": "nvapi-test",
                                            "ANTHROPIC_API_KEY": "sk-gercek"}, clear=False):
            with mock.patch.object(kos.subprocess, "run", return_value=sahte) as calisti:
                kos._claude_kos("istem", fm, "deneme", Path("/tmp/yok.md"))
        ortam = calisti.call_args.kwargs["env"]
        komut = calisti.call_args.args[0]
        self.assertEqual(ortam["ANTHROPIC_BASE_URL"], kos.NIM_PROXY_VARSAYILAN)
        self.assertNotIn("ANTHROPIC_API_KEY", ortam)
        self.assertEqual(komut[komut.index("--model") + 1], "meta/llama-3.3-70b-instruct")

    def test_anthropic_kosusunda_base_url_eklenmez(self):
        fm = {"model": "sonnet", "tools": ["Read"]}
        sahte = mock.Mock(stdout=json.dumps({"is_error": False, "result": "ok"}), stderr="",
                          returncode=0)
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-gercek"}, clear=False):
            with mock.patch.object(kos.subprocess, "run", return_value=sahte) as calisti:
                kos._claude_kos("istem", fm, "deneme", Path("/tmp/yok.md"))
        ortam = calisti.call_args.kwargs["env"]
        self.assertNotIn("ANTHROPIC_BASE_URL", ortam)
        self.assertEqual(ortam["ANTHROPIC_API_KEY"], "sk-gercek")


class KuruKosuTesti(unittest.TestCase):
    def test_kuru_kosu_saglayiciyi_ve_modeli_basar(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d, saglayici="nim", model="meta/llama-3.3-70b-instruct")
            with mock.patch.object(kos.ayar, "KOK", kok), mock.patch.object(kos, "KOK", kok):
                yakala = io.StringIO()
                with redirect_stdout(yakala):
                    kos.kos("deneme", kuru=True)
        cikti = yakala.getvalue()
        self.assertIn("nim", cikti)
        self.assertIn("meta/llama-3.3-70b-instruct", cikti)

    def test_nim_kosusu_anahtarsiz_atlanir_claude_cagrilmaz(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d, saglayici="nim", model="meta/llama-3.3-70b-instruct")
            with mock.patch.object(kos.ayar, "KOK", kok), mock.patch.object(kos, "KOK", kok), \
                    mock.patch.object(kos.ayar, "ENV_DOSYASI", kok / ".env"), \
                    mock.patch.object(kos.agents_uret, "uret"), \
                    mock.patch.dict("os.environ", {"NVIDIA_API_KEY": ""}, clear=False), \
                    mock.patch.object(kos.subprocess, "run") as calisti:
                yakala = io.StringIO()
                with redirect_stdout(yakala):
                    kos.kos("deneme", zorla=True)
        calisti.assert_not_called()
        self.assertIn("NVIDIA_API_KEY", yakala.getvalue())


class ProxyDurumTesti(unittest.TestCase):
    def test_anahtar_yokken_durum_net_konusur(self):
        metin = model_proxy.durum({"PATH": "/bin"}, ayakta=False)
        self.assertIn("NVIDIA_API_KEY", metin)
        self.assertIn("build.nvidia.com", metin)

    def test_anahtar_varken_maskelenir_ve_ayakta_bilgisi_gecer(self):
        metin = model_proxy.durum({"NVIDIA_API_KEY": "nvapi-1234567890abcdef",
                                   "NIM_MODEL": "meta/llama-3.3-70b-instruct"}, ayakta=True)
        self.assertNotIn("1234567890abcdef", metin)
        self.assertIn("meta/llama-3.3-70b-instruct", metin)
        self.assertIn("ayakta", metin)

    def test_config_anahtari_dosyaya_yazmaz(self):
        """Anahtar config.yaml'a düşerse repo dışına sızma riski doğar; os.environ ile okunmalı."""
        metin = model_proxy.config_metni("meta/llama-3.3-70b-instruct")
        self.assertIn("os.environ/NVIDIA_API_KEY", metin)
        self.assertIn("nvidia_nim/meta/llama-3.3-70b-instruct", metin)
        self.assertIn("drop_params", metin)

    def test_komut_uvx_ile_surum_sabitler_ve_global_kurulum_yapmaz(self):
        komut = model_proxy.baslat_komutu(Path("/tmp/config.yaml"), 4000)
        self.assertEqual(komut[0], "uvx")
        self.assertTrue(any("litellm[proxy]==" in p for p in komut))
        self.assertNotIn("pip", komut)


if __name__ == "__main__":
    unittest.main()

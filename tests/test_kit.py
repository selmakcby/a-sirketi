"""Kitin kendi testleri — ağ yok, claude çağrısı yok, para harcamaz.

python3 -m unittest discover -s tests
"""
import collections
import io
import json
import plistlib
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "bin"))
import ayar  # noqa: E402
import bekci  # noqa: E402
import dagitici  # noqa: E402
import gunluk  # noqa: E402
import kos  # noqa: E402
import telegram_dinle  # noqa: E402
import telegram_oku  # noqa: E402
import zamanla  # noqa: E402

TAKIM_MD = """---
name: {ad}
description: {ad} takımı — test.
model: sonnet
tools: [Read, Write]
gerekli_anahtarlar: []
butce_usd: 2
---

# {ad}
"""


def sahte_kok(tmp, takimlar=("x-icerik", "twitter-icerik")):
    """Geçici dizinde takimlar/<t>/{takim.md,durum.json,kosu/} olan minik bir repo."""
    kok = Path(tmp) / "kok"
    for ad in takimlar:
        dizin = kok / "takimlar" / ad
        (dizin / "kosu").mkdir(parents=True)
        (dizin / "takim.md").write_text(TAKIM_MD.format(ad=ad), encoding="utf-8")
        (dizin / "durum.json").write_text(json.dumps(
            {"takim": ad, "son_kosu": None, "son_sonuc": None, "kuyruk": [],
             "bekci": {"son_karar": None, "red_sayisi_7g": 0}, "defter_son_ders": None,
             "sayaclar": {}}, ensure_ascii=False), encoding="utf-8")
    return kok


class AyarTesti(unittest.TestCase):
    def test_env_yukle_export_ve_tirnak_tolere_eder(self):
        with tempfile.TemporaryDirectory() as d:
            yol = Path(d) / ".env"
            yol.write_text("export A=1\nB=\"iki\"\n# yorum\nC='üç'\nBOS=\n", encoding="utf-8")
            self.assertEqual(ayar.env_yukle(yol), {"A": "1", "B": "iki", "C": "üç", "BOS": ""})

    def test_eksik_anahtarlar(self):
        self.assertEqual(ayar.eksik_anahtarlar(["A", "B"], {"A": "1"}), ["B"])
        self.assertEqual(ayar.eksik_anahtarlar([], {}), [])

    def test_mesai_penceresi(self):
        gunduz = datetime(2026, 9, 11, 12, 0)
        gece = datetime(2026, 9, 11, 3, 0)
        self.assertTrue(ayar.mesaide_mi(gunduz))
        self.assertFalse(ayar.mesaide_mi(gece))
        self.assertEqual(ayar.sonraki_mesai(gece).hour, ayar.MESAI_BASLANGIC)

    def test_frontmatter_liste_ayristirir(self):
        fm, govde = ayar.frontmatter(TAKIM_MD.format(ad="x-icerik"))
        self.assertEqual(fm["name"], "x-icerik")
        self.assertEqual(fm["tools"], ["Read", "Write"])
        self.assertEqual(fm["butce_usd"], "2")
        self.assertTrue(govde.startswith("# x-icerik"))

    def test_gercek_takimlarin_frontmatteri_okunur(self):
        for ad in ("x-icerik", "youtube-analiz", "twitter-icerik"):
            fm = ayar.takim_bilgisi(ad)
            self.assertIsNotNone(fm, ad)
            self.assertEqual(fm["name"], ad)
            self.assertIsInstance(fm["tools"], list)


class KuruKosuTesti(unittest.TestCase):
    def test_kos_kuru_calisir_ve_hicbir_dosyaya_yazmaz(self):
        for ad in ("x-icerik", "youtube-analiz", "twitter-icerik"):
            oncesi = json.loads((KOK / "takimlar" / ad / "durum.json").read_text(encoding="utf-8"))
            yakala = io.StringIO()
            with redirect_stdout(yakala):
                kod = kos.main([ad, "--kuru"])
            self.assertEqual(kod, 0, ad)
            self.assertIn("kuru koşu", yakala.getvalue())
            self.assertIn("claude çağrılmadı", yakala.getvalue())
            sonrasi = json.loads((KOK / "takimlar" / ad / "durum.json").read_text(encoding="utf-8"))
            self.assertEqual(oncesi, sonrasi, f"{ad}: kuru koşu durum.json'u değiştirdi")
            self.assertEqual(list((KOK / "takimlar" / ad / "kosu").glob("*.md")), [])

    def test_istem_anayasayi_ve_kosu_kaydini_soyler(self):
        fm = ayar.takim_bilgisi("x-icerik")
        metin = kos.istem("x-icerik", fm, KOK / "takimlar/x-icerik/kosu/x.md", "2026-09-11T12:00:00+02:00")
        self.assertIn("ANAYASA.md", metin)
        self.assertIn("kurallar.md", metin)
        self.assertIn("SIRKET_KOSU", metin)
        self.assertIn("<kaynak>", metin)


class KimlikIstemiTesti(unittest.TestCase):
    """Koşu istemi: kimlik → ANAYASA → AJAN-KIMLIGI → kurallar → takim.md sırası."""

    def _istem(self, takim="x-icerik", fm=None):
        return kos.istem(takim, fm if fm is not None else {},
                         KOK / f"takimlar/{takim}/kosu/2026-09-11-1200.md", "2026-09-11 12:00")

    def test_istemin_ilk_satiri_kimlik(self):
        metin = self._istem()
        self.assertTrue(metin.startswith("Sen `x-icerik` ajanısın."), metin[:80])
        self.assertIn("A Şirketi'nde bir çalışansın", metin.splitlines()[0])
        self.assertIn("bir yapay zekâ ajanısın", metin.splitlines()[0])
        self.assertIn("Mesleğin:", metin.splitlines()[0])

    def test_istem_kimlik_dosyasini_okuma_sirasina_koyar(self):
        metin = self._istem()
        self.assertIn("sirket/AJAN-KIMLIGI.md", metin)
        self.assertLess(metin.index("ANAYASA.md"), metin.index("sirket/AJAN-KIMLIGI.md"))
        self.assertLess(metin.index("sirket/AJAN-KIMLIGI.md"), metin.index("takimlar/x-icerik/kurallar.md"))

    def test_istem_meslegi_takim_md_den_okur(self):
        """fm boş gelse bile description takim.md'den tamamlanır."""
        self.assertIn("X içerik takımı", self._istem())

    def test_istem_yetenek_satiri_ekler(self):
        metin = self._istem("deney", {"description": "deneme takımı — test.",
                                      "skills": ["kaynak-dogrulama", "zincir-yazimi"]})
        self.assertIn("Yeteneklerin: `skills/kaynak-dogrulama/SKILL.md`, `skills/zincir-yazimi/SKILL.md`", metin)
        self.assertIn("ilgili adımda oku ve uygula", metin)

    def test_istem_skillleri_takim_md_den_tamamlar(self):
        self.assertIn("`skills/kaynak-dogrulama/SKILL.md`", self._istem())

    def test_istem_skills_yoksa_yetenek_satiri_yok(self):
        metin = self._istem("yok-boyle-takim", {"description": "x", "skills": []})
        self.assertNotIn("Yeteneklerin:", metin)

    def test_istem_kendini_gelistirme_cumlesi(self):
        metin = self._istem()
        self.assertIn("kendini geliştir", metin)
        self.assertIn("defter.md", metin)

    def test_kuru_kosu_kimlik_satirini_basar(self):
        yakala = io.StringIO()
        with redirect_stdout(yakala):
            kos.main(["x-icerik", "--kuru"])
        cikti = yakala.getvalue()
        self.assertIn("kimlik (istemin ilk satırı): Sen `x-icerik` ajanısın.", cikti)
        self.assertIn("yetenekler: kaynak-dogrulama", cikti)

    def test_dagitici_kuru_calisir_ve_kuyruga_yazmaz(self):
        oncesi = (KOK / "takimlar/twitter-icerik/durum.json").read_text(encoding="utf-8")
        yakala = io.StringIO()
        with redirect_stdout(yakala):
            kod = dagitici.main(["--kuru"])
        self.assertEqual(kod, 0)
        self.assertIn("dağıtıcı", yakala.getvalue())
        self.assertIn("kuru koşu", yakala.getvalue())
        self.assertEqual(oncesi, (KOK / "takimlar/twitter-icerik/durum.json").read_text(encoding="utf-8"))

    def test_kosu_yolu_tarihli(self):
        yol = kos.kosu_yolu("x-icerik", "2026-09-11T12:05:00+02:00", kok="/x")
        self.assertEqual(str(yol), "/x/takimlar/x-icerik/kosu/2026-09-11-1205.md")

    def test_sonucu_cozumle(self):
        iyi = kos.sonucu_cozumle(json.dumps({"result": "bitti", "total_cost_usd": 0.12,
                                             "num_turns": 3, "is_error": False}))
        self.assertEqual(iyi["maliyet"], 0.12)
        self.assertFalse(iyi["hata"])
        self.assertTrue(kos.sonucu_cozumle("json değil")["hata"])


class ZincirTesti(unittest.TestCase):
    def test_x_tamam_olunca_twitter_kuyruguna_aci_dusr(self):
        with tempfile.TemporaryDirectory() as tmp:
            kok = sahte_kok(tmp)
            ayar.durum_guncelle("x-icerik", {"kuyruk": [
                {"id": "x-1234", "durum": "tamam", "not": "yazıya değer"}]}, kok)
            yazilan = dagitici.zinciri_isle(kok, "x-icerik")
            self.assertEqual([z["id"] for z in yazilan], ["aci-1234"])
            kuyruk = ayar.durum_oku("twitter-icerik", kok)["kuyruk"]
            self.assertEqual(kuyruk[0]["id"], "aci-1234")
            self.assertEqual(kuyruk[0]["durum"], "bekliyor")

    def test_zincir_iki_kez_calisinca_tekrar_yazmaz(self):
        with tempfile.TemporaryDirectory() as tmp:
            kok = sahte_kok(tmp)
            ayar.durum_guncelle("x-icerik", {"kuyruk": [{"id": "x-7", "durum": "tamam"}]}, kok)
            dagitici.zinciri_isle(kok, "x-icerik")
            self.assertEqual(dagitici.zinciri_isle(kok, "x-icerik"), [])
            self.assertEqual(len(ayar.durum_oku("twitter-icerik", kok)["kuyruk"]), 1)

    def test_bekleyen_madde_zincire_girmez(self):
        with tempfile.TemporaryDirectory() as tmp:
            kok = sahte_kok(tmp)
            ayar.durum_guncelle("x-icerik", {"kuyruk": [{"id": "x-9", "durum": "bekliyor"}]}, kok)
            self.assertEqual(dagitici.zinciri_isle(kok, "x-icerik"), [])


class TavanTesti(unittest.TestCase):
    SIMDI = datetime.fromisoformat("2026-09-11T15:00:00+02:00")

    def _bekleyen_kok(self, tmp):
        kok = sahte_kok(tmp)
        ayar.durum_guncelle("x-icerik", {"kuyruk": [{"id": "x-1", "durum": "bekliyor"}]}, kok)
        return kok

    def test_bos_kuyruk_kosmaz(self):
        with tempfile.TemporaryDirectory() as tmp:
            kossun, sebep = dagitici.tetik_karari(sahte_kok(tmp), "x-icerik", self.SIMDI)
            self.assertFalse(kossun)
            self.assertIn("bekleyen madde yok", sebep)

    def test_bekleyen_madde_kosturur(self):
        with tempfile.TemporaryDirectory() as tmp:
            kossun, _ = dagitici.tetik_karari(self._bekleyen_kok(tmp), "x-icerik", self.SIMDI)
            self.assertTrue(kossun)

    def test_mesai_disi_bekletir(self):
        with tempfile.TemporaryDirectory() as tmp:
            gece = self.SIMDI.replace(hour=3)
            kossun, sebep = dagitici.tetik_karari(self._bekleyen_kok(tmp), "x-icerik", gece)
            self.assertFalse(kossun)
            self.assertIn("mesai dışı", sebep)

    def test_kosular_arasi_bekleme_kurali(self):
        # Varsayılan ayar 0 (bekleme yok); kural mantığı ayar 30'a çekilerek sınanır.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(ayar, "KOSULAR_ARASI_DK", 30):
            kok = self._bekleyen_kok(tmp)
            yeni = self.SIMDI - timedelta(minutes=10)
            ayar.durum_guncelle("x-icerik", {"son_kosu": yeni.isoformat()}, kok)
            kossun, sebep = dagitici.tetik_karari(kok, "x-icerik", self.SIMDI)
            self.assertFalse(kossun)
            self.assertIn("30 dk", sebep)

    def test_bekleme_sifirsa_hemen_kosar(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(ayar, "KOSULAR_ARASI_DK", 0):
            kok = self._bekleyen_kok(tmp)
            yeni = self.SIMDI - timedelta(minutes=1)
            ayar.durum_guncelle("x-icerik", {"son_kosu": yeni.isoformat()}, kok)
            kossun, _ = dagitici.tetik_karari(kok, "x-icerik", self.SIMDI)
            self.assertTrue(kossun)

    def test_gunluk_kosu_tavani(self):
        with tempfile.TemporaryDirectory() as tmp:
            kok = self._bekleyen_kok(tmp)
            for saat in range(ayar.GUNLUK_KOSU_TAVANI):
                (kok / "takimlar/x-icerik/kosu" / f"2026-09-11-{saat:02d}00.md").write_text("x")
            kossun, sebep = dagitici.tetik_karari(kok, "x-icerik", self.SIMDI)
            self.assertFalse(kossun)
            self.assertIn("günlük koşu tavanı", sebep)

    def test_gunluk_maliyet_tavani(self):
        with tempfile.TemporaryDirectory() as tmp:
            kok = self._bekleyen_kok(tmp)
            (kok / "takimlar/twitter-icerik/kosu/2026-09-11-0900.md").write_text(
                "- maliyet: 10.50 USD · tur: 3\n", encoding="utf-8")
            kossun, sebep = dagitici.tetik_karari(kok, "x-icerik", self.SIMDI)
            self.assertFalse(kossun)
            self.assertIn("günlük bütçe", sebep)


class BekciTesti(unittest.TestCase):
    def test_on_kontrol_anahtar_desenlerini_yakalar(self):
        self.assertEqual(bekci.on_kontrol("anahtar sk-abc123def burada"), ["OpenAI anahtarı"])
        self.assertEqual(bekci.on_kontrol("AIzaSyD-abcdefghij"), ["Google anahtarı"])
        self.assertEqual(bekci.on_kontrol("ghp_abcdef123456"), ["GitHub token"])
        self.assertEqual(bekci.on_kontrol("12345678:AAEabcdefghijklmnopqrstuvwx-yz"),
                         ["Telegram bot token"])
        self.assertIn("e-posta adresi", bekci.on_kontrol("gönderen: biri@marka.com"))

    def test_on_kontrol_temiz_metni_gecirir(self):
        self.assertEqual(bekci.on_kontrol("3 link okundu, 2 tablo yazıldı, 1 ⛔ çıktı"), [])

    def test_bos_kosu_kaydi_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            kok = sahte_kok(tmp)
            (kok / "ANAYASA.md").write_text("1. Yayın düğmesi insanın.", encoding="utf-8")
            kosu = kok / "takimlar/x-icerik/kosu/2026-09-11-1200.md"
            kosu.write_text("   \n", encoding="utf-8")
            karar = bekci.denetle(kok, "x-icerik", kosu)
            self.assertEqual(karar["karar"], "red")
            self.assertIn("boş", karar["gerekce"])
            self.assertEqual(ayar.durum_oku("x-icerik", kok)["bekci"]["son_karar"], "red")

    def test_anahtar_sizan_kosu_llm_cagirmadan_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            kok = sahte_kok(tmp)
            kosu = kok / "takimlar/x-icerik/kosu/2026-09-11-1200.md"
            kosu.write_text("# Koşu\nAPIFY_TOKEN=sk-gizli123456 ile çektim\n", encoding="utf-8")
            with mock.patch.object(bekci, "openai_sor") as sahte_openai, \
                 mock.patch.object(bekci, "haiku_sor") as sahte_haiku:
                karar = bekci.denetle(kok, "x-icerik", kosu)
            sahte_openai.assert_not_called()
            sahte_haiku.assert_not_called()
            self.assertEqual(karar["karar"], "red")
            self.assertIn("## Bekçi", kosu.read_text(encoding="utf-8"))

    def test_haiku_yedegi_ayni_aile_uyarisi_yazar(self):
        yanit = json.dumps({"result": '{"karar":"kabul","gerekce":"temiz","ihlal_edilen_kural":null}'})
        with mock.patch.object(bekci.subprocess, "run",
                               return_value=mock.Mock(stdout=yanit, returncode=0)):
            karar = bekci.haiku_sor("istem")
        self.assertEqual(karar["karar"], "kabul")
        self.assertIn(bekci.AYNI_AILE_UYARISI, karar["gerekce"])

    def test_madde_3_gerekceli_red_gecersiz(self):
        red = {"karar": "red", "gerekce": "ANAYASA madde 3: denetleyen aynı aileden",
               "ihlal_edilen_kural": "3"}
        self.assertEqual(bekci.gecersiz_gerekceyi_ayikla(red)["karar"], "kabul")

    def test_icerik_gerekceli_red_korunur(self):
        red = {"karar": "red", "gerekce": "kaynaksız sayı: '8 bin abone'", "ihlal_edilen_kural": "2"}
        self.assertEqual(bekci.gecersiz_gerekceyi_ayikla(red)["karar"], "red")


class BelgeTutarliligiTesti(unittest.TestCase):
    def test_env_ornegi_ile_readme_ayni_anahtarlari_sayiyor(self):
        ornek = ayar.env_yukle(KOK / ".env.example")
        self.assertTrue(ornek, ".env.example okunamadı")
        readme = (KOK / "README.md").read_text(encoding="utf-8")
        for anahtar in ornek:
            self.assertIn(anahtar, readme, f"{anahtar} .env.example'da var ama README'de yok")

    def test_env_orneginde_gercek_deger_yok(self):
        for anahtar, deger in ayar.env_yukle(KOK / ".env.example").items():
            if anahtar == "KANAL":
                self.assertEqual(deger, "@ornek-kanal")
            else:
                self.assertEqual(deger, "", f"{anahtar} .env.example'da dolu!")

    def test_repoda_sizmis_anahtar_yok(self):
        desenler = [re.compile(p) for p in
                    (r"\bsk-[A-Za-z0-9]{20,}", r"\bAIza[0-9A-Za-z_-]{30,}",
                     r"\bgh[pousr]_[A-Za-z0-9]{30,}", r"\b\d{9,}:[A-Za-z0-9_-]{30,}")]
        atla = {".git", "__pycache__", "kosu", "cikti", "gelen", "veri"}
        for yol in KOK.rglob("*"):
            if not yol.is_file() or yol.name == "test_kit.py" or set(yol.parts) & atla:
                continue
            if yol.suffix not in (".py", ".md", ".json", ".sh", ".example", ".gitignore", ""):
                continue
            metin = yol.read_text(encoding="utf-8", errors="ignore")
            for desen in desenler:
                self.assertIsNone(desen.search(metin), f"{yol.name}: anahtara benzeyen metin")

    def test_gitignore_env_i_kapsiyor(self):
        satirlar = (KOK / ".gitignore").read_text(encoding="utf-8").splitlines()
        for beklenen in (".env", "takimlar/*/kosu/", "takimlar/*/cikti/", "takimlar/*/gelen/",
                         "takimlar/*/veri/", "__pycache__/", "*.jsonl"):
            self.assertIn(beklenen, satirlar)

    def test_stop_hook_bekciyi_cagiriyor(self):
        ayarlar = json.loads((KOK / ".claude/settings.json").read_text(encoding="utf-8"))
        komutlar = [h["command"] for madde in ayarlar["hooks"]["Stop"] for h in madde["hooks"]]
        self.assertTrue(any("bekci.py" in k for k in komutlar))
        self.assertEqual(list(ayarlar["hooks"]), ["Stop"])


MESAI_ICI = datetime(2026, 9, 11, 10, 0).astimezone()
MESAI_DISI = datetime(2026, 9, 11, 3, 0).astimezone()


def _mesaj(update_id, linkler=("https://x.com/a/status/1",), notu="bak şuna"):
    return {"update_id": update_id, "zaman": "2026-09-11T10:00:00+03:00",
            "metin": notu, "linkler": list(linkler), "not": notu}


def _guncelleme(update_id, chat_id, metin):
    return {"update_id": update_id,
            "message": {"chat": {"id": chat_id}, "date": 1788000000, "text": metin}}


class TelegramDinleTesti(unittest.TestCase):
    def test_kuyruk_maddesi_takim_sozlesmesindeki_id_yi_kurar(self):
        id_, notu = telegram_dinle.kuyruk_maddesi(_mesaj(42))
        self.assertEqual(id_, "x-42")
        self.assertIn("https://x.com/a/status/1", notu)
        self.assertIn("not: bak şuna", notu)
        self.assertIsNotNone(dagitici.zincir_esle(id_), "id zincire uymalı")

    def test_kuyruk_notu_dis_metni_tek_satira_indirip_kirpar(self):
        _, notu = telegram_dinle.kuyruk_maddesi(_mesaj(7, notu="satır1\nsatır2 " + "u" * 500))
        self.assertNotIn("\n", notu)
        self.assertLessEqual(len(notu.split("not: ", 1)[1]), telegram_dinle.NOT_SINIRI + 1)

    def test_linksiz_mesaj_kosturmaz_kuyruga_da_yazmaz(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            with mock.patch.object(telegram_dinle, "kostur") as sahte:
                etiket, _ = telegram_dinle.isle_mesaj(kok, _mesaj(1, linkler=()), MESAI_ICI)
            self.assertEqual(etiket, "linksiz")
            sahte.assert_not_called()
            self.assertEqual(ayar.durum_oku("x-icerik", kok).get("kuyruk"), [])

    def test_mesai_icinde_link_kuyruga_yazilir_ve_hemen_kosar(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            with mock.patch.object(telegram_dinle, "kostur") as sahte:
                etiket, _ = telegram_dinle.isle_mesaj(kok, _mesaj(30760576), MESAI_ICI)
            self.assertEqual(etiket, "kostu")
            sahte.assert_called_once_with(kok)
            kuyruk = ayar.durum_oku("x-icerik", kok)["kuyruk"]
            self.assertEqual([(o["id"], o["durum"]) for o in kuyruk], [("x-30760576", "bekliyor")])

    def test_mesai_disinda_kuyruga_yazilir_ama_kosmaz(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            with mock.patch.object(telegram_dinle, "kostur") as sahte:
                etiket, sebep = telegram_dinle.isle_mesaj(kok, _mesaj(5), MESAI_DISI)
            self.assertEqual(etiket, "bekletildi")
            self.assertIn("mesai dışı", sebep)
            sahte.assert_not_called()
            self.assertEqual([o["id"] for o in ayar.durum_oku("x-icerik", kok)["kuyruk"]], ["x-5"])

    def test_tavan_karari_dagiticinin_kurallarindan_gelir(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ayar, "KOSULAR_ARASI_DK", 30):
            kok = sahte_kok(d)
            az_once = (MESAI_ICI - timedelta(minutes=5)).isoformat(timespec="seconds")
            ayar.durum_guncelle("x-icerik", {"son_kosu": az_once}, kok)
            with mock.patch.object(telegram_dinle, "kostur") as sahte:
                etiket, sebep = telegram_dinle.isle_mesaj(kok, _mesaj(9), MESAI_ICI)
            self.assertEqual(etiket, "bekletildi")
            self.assertIn(f"{ayar.KOSULAR_ARASI_DK} dk", sebep)
            sahte.assert_not_called()

    def test_tur_gelen_yazar_ve_mesajlari_sirayla_isler(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            guncellemeler = [_guncelleme(11, 99, "https://x.com/a/status/1"),
                             _guncelleme(12, 99, "/start"),
                             _guncelleme(13, 5, "https://x.com/b/status/2")]  # başka chat — elenir
            sira = []
            with mock.patch.object(telegram_dinle.telegram_oku, "guncellemeleri_cek",
                                   return_value=guncellemeler) as cek, \
                 mock.patch.object(telegram_dinle, "isle_mesaj",
                                   side_effect=lambda k, m, *a: (sira.append(m["update_id"]),
                                                                 ("kostu", "test"))[1]):
                islenen = telegram_dinle.tur(kok, "gizli-token", 99, collections.deque(), bekleme=15)
            self.assertEqual(cek.call_args.kwargs["bekleme"], 15)
            self.assertEqual(islenen, 2)
            self.assertEqual(sira, [11, 12])
            yazilan = sorted(p.name for p in (kok / "takimlar/x-icerik/gelen").glob("*.json"))
            self.assertEqual(len(yazilan), 2)
            sayaclar = ayar.durum_oku("x-icerik", kok)["sayaclar"]
            self.assertEqual(sayaclar["telegram_son_update"], 12)

    def test_token_yoksa_sessizce_sifirla_cikar(self):
        with mock.patch.object(ayar, "ortam_yukle", return_value={}), \
             mock.patch.dict("os.environ", {}, clear=True), \
             redirect_stdout(io.StringIO()) as ekran:
            self.assertEqual(telegram_dinle.main(["--bir-kez"]), 0)
        self.assertNotIn("Traceback", ekran.getvalue())

    def test_log_sirri_maskeler(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()) as ekran:
            telegram_dinle.sir_ekle("123:AA-gizli-token")
            telegram_dinle._log(Path(d), "tur hatası: URLError: .../bot123:AA-gizli-token/getUpdates")
            yazilan = (Path(d) / "sirket-log" / telegram_dinle.LOG_ADI).read_text(encoding="utf-8")
        for metin in (ekran.getvalue(), yazilan):
            self.assertNotIn("gizli-token", metin)
            self.assertIn("***", metin)

    def test_kaynak_dosyasinda_token_degeri_loglanmiyor(self):
        """Log satırları token *değişkenine* dokunmamalı; anahtarın adını yazmak serbest."""
        metin = (KOK / "bin/telegram_dinle.py").read_text(encoding="utf-8")
        for satir in metin.splitlines():
            if "print(" in satir or "_log(" in satir:
                self.assertIsNone(re.search(r"\btoken\b", satir),
                                  f"log satırında token değişkeni: {satir.strip()}")


GUN = "2026-09-11"
KOSU_METNI = """# Koşu — {takim} — {gun}

- model: sonnet · bütçe: 2 USD

iş yapıldı.

---
- maliyet: {maliyet} USD · tur: 7 · hata: {hata}


## Bekçi
- karar: **{karar}**
- gerekçe: {gerekce}
- ihlal edilen kural: -
"""


def _kosu_yaz(kok, takim, saat, maliyet="0.500", hata="False", karar="kabul", gerekce="temiz"):
    yol = Path(kok) / "takimlar" / takim / "kosu" / f"{GUN}-{saat}.md"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(KOSU_METNI.format(takim=takim, gun=GUN, maliyet=maliyet, hata=hata,
                                     karar=karar, gerekce=gerekce), encoding="utf-8")
    return yol


class GunlukRaporTesti(unittest.TestCase):
    def test_kosu_oku_ozet_ve_bekci_kararini_ayiklar(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            kosu = gunluk.kosu_oku(_kosu_yaz(kok, "x-icerik", "0930", maliyet="1.250", karar="red"))
        self.assertEqual((kosu["gun"], kosu["saat"]), (GUN, "09:30"))
        self.assertEqual((kosu["maliyet"], kosu["tur"], kosu["hata"]), (1.25, 7, False))
        self.assertEqual((kosu["bekci"], kosu["atlandi"]), ("red", None))

    def test_kosu_oku_atlanan_kosuyu_tanir(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            yol = Path(kok) / "takimlar/x-icerik/kosu" / f"{GUN}-0300.md"
            yol.write_text("# Koşu\n\n**Atlandı:** mesai dışı (09:00-23:00); kuyrukta bekler\n",
                           encoding="utf-8")
            kosu = gunluk.kosu_oku(yol)
        self.assertIn("mesai dışı", kosu["atlandi"])
        self.assertEqual((kosu["maliyet"], kosu["bekci"]), (0.0, "-"))

    def test_gunun_kosulari_gune_gore_suzup_saate_gore_sirali_doner(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            _kosu_yaz(kok, "x-icerik", "1400")
            _kosu_yaz(kok, "twitter-icerik", "0930")
            (Path(kok) / "takimlar/x-icerik/kosu/2026-09-10-1000.md").write_text("dün", encoding="utf-8")
            kosular = gunluk.gunun_kosulari(kok, GUN)
        self.assertEqual([(k["saat"], k["takim"]) for k in kosular],
                         [("09:30", "twitter-icerik"), ("14:00", "x-icerik")])

    def test_bekci_telemetrisi_gune_gore_suzulur_bozuk_satir_atlanir(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            (Path(kok) / gunluk.TELEMETRI).write_text(
                json.dumps({"zaman": f"{GUN}T09:30:00+03:00", "takim": "x-icerik", "karar": "red"}) + "\n"
                + "{bozuk json\n"
                + json.dumps({"zaman": "2026-09-10T09:30:00+03:00", "takim": "x-icerik", "karar": "kabul"}) + "\n",
                encoding="utf-8")
            kararlar = gunluk.gunun_bekci_kararlari(kok, GUN)
        self.assertEqual([k["karar"] for k in kararlar], ["red"])

    def test_aksam_raporu_kosulari_kararlari_ve_dikkati_yazar(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            _kosu_yaz(kok, "x-icerik", "0930", maliyet="1.250", karar="red", gerekce="kaynak yok")
            (Path(kok) / gunluk.TELEMETRI).write_text(
                json.dumps({"zaman": f"{GUN}T09:45:00+03:00", "takim": "x-icerik", "karar": "red",
                            "gerekce": "kaynak yok", "ihlal_edilen_kural": "kaynak"},
                           ensure_ascii=False) + "\n", encoding="utf-8")
            metin = gunluk.aksam_raporu(kok, MESAI_ICI)
        self.assertIn("Akşam denetimi", metin)
        self.assertIn("Bugünün koşuları (1)", metin)
        self.assertIn("**red 1**", metin)
        self.assertIn("⛔ `x-icerik` 09:30 — bekçi **red**", metin)
        self.assertIn(f"/ {ayar.GUNLUK_MALIYET_TAVANI_USD:.0f} USD", metin)

    def test_temiz_gunde_uydurma_uyari_yok(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            _kosu_yaz(kok, "x-icerik", "0930")
            metin = gunluk.aksam_raporu(kok, MESAI_ICI)
        self.assertIn("temiz gün, işaretlenecek bir şey yok", metin)
        self.assertNotIn("⛔", metin)

    def test_sabah_raporu_dagitici_kararlarini_tasir(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            dagitici.kuyruga_yaz(kok, "x-icerik", "x-1", "telegram linki")
            dagitim = dagitici.dagit(kok, MESAI_ICI, kuru=True)
            metin = gunluk.sabah_raporu(kok, MESAI_ICI, dagitim)
        self.assertIn("Sabah raporu", metin)
        self.assertIn("| x-icerik | KOŞ |", metin)
        self.assertIn("| twitter-icerik | BEKLE |", metin)
        self.assertIn("Dün (2026-09-10)", metin)

    def test_sabah_kuru_kosu_hicbir_takimi_baslatmaz(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            dagitici.kuyruga_yaz(kok, "x-icerik", "x-1", "telegram linki")
            with mock.patch.object(dagitici, "_kostur") as sahte:
                gunluk.sabah(kok, MESAI_ICI, kuru=True)
            sahte.assert_not_called()
            self.assertFalse((Path(kok) / gunluk.RAPOR_DIZINI).exists())

    def test_haftalik_is_yalniz_pazartesi_kuyruga_duser(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d, takimlar=("youtube-analiz",))
            sali = gunluk.haftalik_kuyruk(kok, datetime(2026, 9, 15, 9, 0).astimezone())
            pazartesi = gunluk.haftalik_kuyruk(kok, datetime(2026, 9, 14, 9, 0).astimezone())
            tekrar = gunluk.haftalik_kuyruk(kok, datetime(2026, 9, 14, 9, 30).astimezone())
            kuyruk = ayar.durum_oku("youtube-analiz", kok)["kuyruk"]
        self.assertEqual(sali, [])
        self.assertEqual([h["id"] for h in pazartesi], ["yt-2026-W38"])
        self.assertEqual(tekrar, [], "aynı haftanın maddesi ikinci kez yazılmamalı")
        self.assertEqual([(o["id"], o["durum"]) for o in kuyruk], [("yt-2026-W38", "bekliyor")])

    def test_hafta_kimligi_cekicinin_veri_dosyasiyla_ayni(self):
        sys.path.insert(0, str(KOK / "bin"))
        import youtube_analiz_cek
        an = datetime(2026, 9, 14, 9, 0)
        self.assertEqual(gunluk.hafta_kimligi(an),
                         youtube_analiz_cek.hafta_dosyasi("/tmp/kok", an).stem)

    def test_pazartesi_sabahi_youtube_analiz_gercekten_kosar(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d, takimlar=("youtube-analiz",))
            with mock.patch.object(dagitici, "_kostur") as sahte:
                metin, _ = gunluk.sabah(kok, datetime(2026, 9, 14, 9, 0).astimezone())
            sahte.assert_called_once_with(kok, "youtube-analiz")
        self.assertIn("`yt-2026-W38` düştü", metin)
        self.assertIn("| youtube-analiz | KOŞ |", metin)

    def test_haftalik_is_olmayan_gunde_rapor_bunu_soyler(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            metin = gunluk.sabah_raporu(kok, MESAI_ICI, {"zincir": [], "kararlar": []})
        self.assertIn("bugün (Cuma) haftalık iş yok", metin)

    def test_rapor_dosyaya_yazilir(self):
        with tempfile.TemporaryDirectory() as d:
            kok = sahte_kok(d)
            yol = gunluk.yaz(kok, "aksam", gunluk.aksam_raporu(kok, MESAI_ICI), MESAI_ICI)
        self.assertEqual(yol.name, f"{GUN}-aksam.md")
        self.assertIn(gunluk.RAPOR_DIZINI, str(yol))


class ZamanlayiciTesti(unittest.TestCase):
    def test_saatler_ayardan_turer(self):
        saatler = {t["ad"]: t["saat"] for t in zamanla.TETIKLER}
        self.assertEqual(saatler["sabah"], ayar.MESAI_BASLANGIC)
        self.assertEqual(saatler["aksam"], ayar.MESAI_BITIS - 1)
        self.assertTrue(ayar.mesaide_mi(datetime(2026, 9, 11, saatler["aksam"], 0)))

    def test_plist_gunluk_py_yi_dogru_bayrakla_cagirir(self):
        for tetik in zamanla.TETIKLER:
            icerik = zamanla.plist_icerigi(tetik, kok="/tmp/kok", python="/usr/bin/python3")
            self.assertEqual(icerik["ProgramArguments"],
                             ["/usr/bin/python3", "/tmp/kok/bin/gunluk.py", tetik["bayrak"]])
            self.assertEqual(icerik["StartCalendarInterval"], {"Hour": tetik["saat"], "Minute": 0})
            self.assertEqual(icerik["WorkingDirectory"], "/tmp/kok")
            self.assertFalse(icerik["RunAtLoad"], "kurulum anında koşu başlatmamalı")
            self.assertIn("/usr/bin", icerik["EnvironmentVariables"]["PATH"])

    def test_plist_yazilabilir_bicimde(self):
        for tetik in zamanla.TETIKLER:
            ham = plistlib.dumps(zamanla.plist_icerigi(tetik))
            self.assertEqual(plistlib.loads(ham)["Label"], zamanla.etiket(tetik["ad"]))


if __name__ == "__main__":
    unittest.main()

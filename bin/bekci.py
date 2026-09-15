#!/usr/bin/env python3
"""Bekçi — koşuyu denetleyen ayrı kafa (ANAYASA 3). Stop hook + doğrudan mod.

İki katman:
  1. **Ön kontrol (LLM yok).** Koşu kaydında API anahtarı, token, e-posta deseni var mı — desen
     eşleşirse karar doğrudan `red`. Bu katman anahtarsız da çalışır.
  2. **Denetim (LLM).** `OPENAI_API_KEY` varsa OpenAI (üreten Claude, denetleyen başka aile).
     Anahtar **yoksa ya da geçersizse** (401/403) ve OpenAI'a ulaşılamazsa yedek yol
     `claude -p --model haiku`: karar verilir ama kayda **"bekçi aynı aileden — uyarı"** notu
     düşülür, çünkü aynı aile kendi hatasını aynı sebeple onaylar. Yedeğe düşüldüyse gerekçe
     bunu da söyler: `openai 401 → haiku yedeği`.

Modlar:
  Stop hook (stdin JSON): takım ve koşu dosyası `SIRKET_TAKIM` / `SIRKET_KOSU` ortamından okunur.
      red → {"decision":"block","reason":...} (en fazla 2 kez), kabul → sessiz.
  `--dogrudan <takim> [kosu]`: hook dışından denetle, kararı JSON bas.

Sözleşme: her zaman çıkış 0 — bekçi oturumu düşürmez. Anahtar yoksa karar "atlandi"dır, "kabul" değil.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ayar  # noqa: E402

KOK = ayar.KOK
MAKS_RED = 2
ZAMAN_ASIMI_SN = 60
OPENAI_MODEL = "gpt-5-mini"
AYNI_AILE_UYARISI = "bekçi aynı aileden — uyarı"
# Bu gerekçelerle gelen "atlandi" kararı koşuyu denetimsiz bırakır → Haiku yedeğine düşülür.
YEDEGE_DUSUREN = re.compile(r"^openai (401|403|ulaşılamadı)")

ON_KONTROL = {
    "e-posta adresi": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "OpenAI anahtarı": re.compile(r"\bsk-[A-Za-z0-9_-]{6,}"),
    "Google anahtarı": re.compile(r"\bAIza[0-9A-Za-z_-]{6,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{6,}"),
    "Telegram bot token": re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}"),
    "fal anahtarı": re.compile(r"\b[0-9a-f-]{20,}:[0-9a-f]{16,}"),
}
YANIT_SEMASI = {
    "type": "object",
    "properties": {"karar": {"type": "string", "enum": ["kabul", "red"]},
                   "gerekce": {"type": "string"},
                   "ihlal_edilen_kural": {"type": ["string", "null"]}},
    "required": ["karar", "gerekce", "ihlal_edilen_kural"],
    "additionalProperties": False,
}
# ANAYASA 3 (ayrı kafa) ve 4 (tavanlar) sürücünün kuralıdır, ajanın değil.
GECERSIZ_GEREKCE = re.compile(r"madde\s*[34]\b|§\s*[34]\b|ayrı kafa|aynı aile|tavan", re.IGNORECASE)


def on_kontrol(metin):
    """LLM'siz sert kontrol. İhlal adları listesi döner; boş liste = temiz."""
    return [ad for ad, desen in ON_KONTROL.items() if desen.search(metin or "")]


def _oku(yol, varsayilan=""):
    try:
        return Path(yol).read_text(encoding="utf-8")
    except OSError:
        return varsayilan


def _istem(anayasa, kurallar, kosu_metni):
    return (
        "Sen bir içerik şirketinin bağımsız denetçisisin. Üretici başka bir modeldir; onun koşu "
        "kaydını aşağıdaki ANAYASA ve takım kurallarına göre denetle. Kanıt olmadan 'kabul' verme; "
        "şüphede 'red'. Yalnızca JSON döndür.\n"
        "Not: ANAYASA madde 3 (bekçi ayrı kafa) ve madde 4 (tavanlar) senin ve sürücünün kuralıdır; "
        "koşu kaydı bunlardan söz etmiyor diye RED verme. Sen kaydın İÇERİĞİNİ denetle: kaynaksız "
        "sayı, kişi adı/e-posta/anahtar, kural dosyasındaki 'asla yapmaz' maddeleri, kaydın boş olması.\n"
        "'Kaynaksız sayı' yalnızca DIŞ DÜNYA iddiaları içindir (görüntülenme, abone, fiyat, gelir, "
        "tarih). Koşu altbilgisi (maliyet/tur/hata), kelime ve dosya sayıları, saatler ve kaydın kendi "
        "ölçümleri kaynak istemez. Kural dosyasındaki hedef aralıklardan %15'e kadar sapma RED sebebi "
        "değildir; gerekçeye 🟡 not düş, kararı 'kabul' ver.\n\n"
        f"<anayasa>\n{anayasa}\n</anayasa>\n\n<kurallar>\n{kurallar}\n</kurallar>\n\n"
        f"<kosu>\n{kosu_metni[:24000]}\n</kosu>")


def yaniti_ayristir(yanit):
    """OpenAI Responses çıktısından karar JSON'u; bulunamazsa atlandi."""
    for oge in yanit.get("output", []):
        for parca in oge.get("content", []) or []:
            try:
                karar = json.loads(parca.get("text") or "")
            except ValueError:
                continue
            if karar.get("karar") in ("kabul", "red"):
                return {"karar": karar["karar"], "gerekce": karar.get("gerekce", ""),
                        "ihlal_edilen_kural": karar.get("ihlal_edilen_kural")}
    return {"karar": "atlandi", "gerekce": "bekçi yanıtı çözümlenemedi", "ihlal_edilen_kural": None}


def openai_sor(anahtar, istem):
    """OpenAI Responses API — stdlib, şemaya bağlı çıktı. Ağ hatası → atlandi."""
    govde = {"model": os.environ.get("BEKCI_MODEL", OPENAI_MODEL), "input": istem,
             "text": {"format": {"type": "json_schema", "name": "bekci_karar",
                                 "schema": YANIT_SEMASI, "strict": True}}}
    istek = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=json.dumps(govde).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}",
                 "User-Agent": "a-sirketi-bekci/1.0"})
    try:
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI_SN) as yanit:
            return yaniti_ayristir(json.loads(yanit.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:   # URLError'dan önce: HTTPError onun alt sınıfı
        return {"karar": "atlandi", "gerekce": f"openai {exc.code}", "ihlal_edilen_kural": None}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return {"karar": "atlandi", "gerekce": f"openai ulaşılamadı: {type(exc).__name__}",
                "ihlal_edilen_kural": None}


def haiku_sor(istem):
    """Yedek bekçi: OpenAI anahtarı yoksa `claude -p --model haiku`, ayrı pencere.

    Aynı aile olduğu için karar dürüstçe işaretlenir: gerekçenin başına uyarı yazılır."""
    ortam = {k: v for k, v in os.environ.items()
             if k not in ("CLAUDECODE", "SIRKET_TAKIM", "SIRKET_KOSU")}
    ek = ('\n\nYalnızca şu JSON\'u döndür: {"karar":"kabul|red","gerekce":"...",'
          '"ihlal_edilen_kural":"..."|null}')
    try:
        sonuc = subprocess.run(["claude", "-p", istem + ek, "--model", "haiku", "--output-format",
                                "json", "--max-budget-usd", "0.2", "--allowedTools", ""],
                               capture_output=True, text=True, timeout=150, env=ortam)
        metin = json.loads(sonuc.stdout).get("result", "")
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return {"karar": "atlandi", "gerekce": f"yedek bekçi ulaşılamadı: {type(exc).__name__}",
                "ihlal_edilen_kural": None}
    basi, sonu = metin.find("{"), metin.rfind("}")
    if basi < 0 or sonu < 0:
        return {"karar": "atlandi", "gerekce": "yedek bekçi JSON döndürmedi", "ihlal_edilen_kural": None}
    karar = yaniti_ayristir({"output": [{"content": [{"text": metin[basi:sonu + 1]}]}]})
    return {**karar, "gerekce": f"[{AYNI_AILE_UYARISI}] " + karar["gerekce"]}


def llm_karari(anahtar, istem):
    """Denetim katmanı: OpenAI varsa o, anahtar yok/geçersiz/ulaşılamaz ise Haiku yedeği.

    Geçersiz anahtar koşuyu sessizce 'atlandi' bırakmaz — bekçi yine karar verir, gerekçe
    hangi yoldan geçildiğini söyler."""
    if not anahtar:
        return haiku_sor(istem)
    karar = openai_sor(anahtar, istem)
    if karar["karar"] != "atlandi" or not YEDEGE_DUSUREN.search(karar.get("gerekce") or ""):
        return karar
    yedek = haiku_sor(istem)
    return {**yedek, "gerekce": f"{karar['gerekce']} → haiku yedeği · {yedek['gerekce']}"}


def gecersiz_gerekceyi_ayikla(karar):
    """Madde 3/4 gerekçeli red geçersizdir (onlar sürücünün kuralı) → kabul, not düşülür.
    İçerik ihlali gerekçeleri (kaynaksız sayı, kişi adı, anahtar) dokunulmaz."""
    if karar.get("karar") != "red":
        return karar
    kural = str(karar.get("ihlal_edilen_kural") or "").strip()
    if GECERSIZ_GEREKCE.search(karar.get("gerekce") or "") or kural in ("3", "4"):
        return {"karar": "kabul", "ihlal_edilen_kural": None,
                "gerekce": "(madde 3/4 gerekçeli red geçersiz sayıldı — sürücünün kuralı) "
                           + (karar.get("gerekce") or "")[:300]}
    return karar


def _kaydet(kok, takim, kosu, karar):
    """Kararı koşu kaydının altına, durum.json'a ve bekçi telemetrisine yazar."""
    durum = ayar.durum_oku(takim, kok)
    onceki = dict(durum.get("bekci") or {})
    red = int(onceki.get("red_sayisi_7g", 0)) + (1 if karar["karar"] == "red" else 0)
    ayar.durum_guncelle(takim, {"bekci": {**onceki, "son_karar": karar["karar"],
                                          "gerekce": karar["gerekce"], "red_sayisi_7g": red,
                                          "zaman": ayar.simdi_iso()}}, kok)
    with open(kosu, "a", encoding="utf-8") as dosya:
        dosya.write(f"\n\n## Bekçi\n- karar: **{karar['karar']}**\n- gerekçe: {karar['gerekce']}\n"
                    f"- ihlal edilen kural: {karar.get('ihlal_edilen_kural') or '-'}\n")
    telemetri = Path(kok) / "takimlar" / "bekci-telemetri.jsonl"
    with open(telemetri, "a", encoding="utf-8") as dosya:
        dosya.write(json.dumps({"zaman": ayar.simdi_iso(), "takim": takim,
                                "kosu": Path(kosu).name, **karar}, ensure_ascii=False) + "\n")


def denetle(kok, takim, kosu):
    """Bir koşu kaydını denetler, kararı kaydeder ve döner."""
    kok = Path(kok)
    metin = _oku(kosu)
    if not metin.strip():
        karar = {"karar": "red", "gerekce": "koşu kaydı boş — ajan SIRKET_KOSU dosyasını yazmadı",
                 "ihlal_edilen_kural": "koşu kaydı"}
    elif ihlaller := on_kontrol(metin):
        karar = {"karar": "red", "gerekce": "ön kontrol: " + ", ".join(ihlaller) + " koşu kaydında geçiyor",
                 "ihlal_edilen_kural": "gizli veri"}
    else:
        istem = _istem(_oku(kok / "ANAYASA.md"),
                       _oku(kok / "takimlar" / takim / "kurallar.md", "(kural dosyası yok)"), metin)
        karar = gecersiz_gerekceyi_ayikla(llm_karari(os.environ.get("OPENAI_API_KEY"), istem))
    _kaydet(kok, takim, kosu, karar)
    return karar


def _deneme_sayaci(kosu):
    return Path(kosu).parent / ".bekci-deneme"


def engelle_mi(kok, takim, kosu):
    """Stop hook kararı: red ise ve deneme hakkı kaldıysa True (ajanı düzeltmeye gönder)."""
    karar = denetle(kok, takim, kosu)
    sayac = _deneme_sayaci(kosu)
    if karar["karar"] != "red":
        sayac.unlink(missing_ok=True)
        return False
    deneme = int(_oku(sayac, "0").strip() or 0) + 1
    sayac.write_text(str(deneme), encoding="utf-8")
    if deneme >= MAKS_RED:
        sayac.unlink(missing_ok=True)
        return False
    return True


def _son_kosu(kok, takim):
    kosular = sorted((Path(kok) / "takimlar" / takim / "kosu").glob("*.md"))
    return kosular[-1] if kosular else None


def _hook():
    try:
        veri = json.load(sys.stdin)
    except ValueError:
        veri = {}
    takim = os.environ.get("SIRKET_TAKIM")
    if not takim:
        return 0  # şirket koşusu değil — karışma
    kosu = os.environ.get("SIRKET_KOSU") or _son_kosu(KOK, takim)
    if not kosu:
        return 0
    if veri.get("stop_hook_active"):  # ikinci durma: engelleme, ama son kararı yeniden ver
        denetle(KOK, takim, kosu)
        _deneme_sayaci(kosu).unlink(missing_ok=True)
        return 0
    if engelle_mi(KOK, takim, kosu):
        gerekce = (ayar.durum_oku(takim).get("bekci") or {}).get("gerekce", "")
        print(json.dumps({"decision": "block",
                          "reason": f"🛑 BEKÇİ RED: {gerekce}\nKoşu kaydını ({kosu}) düzelt, sonra bitir."},
                         ensure_ascii=False))
    return 0


def main(argv):
    ayar.ortam_yukle()
    if argv and argv[0] == "--dogrudan" and len(argv) > 1:
        takim = argv[1]
        kosu = Path(argv[2]) if len(argv) > 2 else _son_kosu(KOK, takim)
        if not kosu:
            print(json.dumps({"karar": "atlandi", "gerekce": "koşu dosyası yok"}, ensure_ascii=False))
            return 0
        print(json.dumps(denetle(KOK, takim, kosu), ensure_ascii=False))
        return 0
    return _hook()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Şirketin tek ayar dosyası — mesai, tavanlar, yollar, anahtarlar.

Bütün betikler buradan okur; hiçbir sayı ikinci bir yerde yazılmaz.
Anahtarlar repo kökündeki `.env` dosyasındadır (`.env.example` kopyası) ve git'e girmez.
"""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
TAKIMLAR = KOK / "takimlar"
ENV_DOSYASI = KOK / ".env"

# --- mesai (ANAYASA 4) -----------------------------------------------------
MESAI_BASLANGIC = 9   # dahil
MESAI_BITIS = 23      # hariç
MESAI_METNI = f"{MESAI_BASLANGIC:02d}:00-{MESAI_BITIS:02d}:00"

# --- tavanlar (ANAYASA 4) --------------------------------------------------
KOSU_BUTCESI_USD = 2.0          # tek koşunun para tavanı
KOSU_SURESI_SN = 15 * 60        # tek koşunun süre tavanı
KOSULAR_ARASI_DK = 0            # aynı takımın iki koşusu arası — 0: bekleme yok
GUNLUK_KOSU_TAVANI = 4          # takım başına gün
GUNLUK_MALIYET_TAVANI_USD = 10.0  # tüm şirket, gün
ES_ZAMANLI_TAVAN = 2            # dağıtıcının aynı anda başlattığı takım sayısı

# --- model köprüsü (docs/07-farkli-model.md) -------------------------------
# Varsayılan sağlayıcı Anthropic'tir. `takim.md`'de `saglayici: nim` yazan takım
# `bin/model_proxy.py`'nin ayağa kaldırdığı yerel LiteLLM proxy'sine yönlendirilir.
NIM_PROXY_URL = "http://127.0.0.1:4000"   # yalnız yerel — dışarı açık değil
NIM_YEREL_TOKEN = "sk-a-sirketi-yerel"    # yerel proxy'nin bearer token'ı (gizli değil)
LITELLM_SURUM = "1.101.0"                 # uvx ile sabitlenir; bkz. model_proxy.YASAKLI_SURUMLER

ENV_SATIRI = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def simdi_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --- anahtarlar ------------------------------------------------------------

def env_yukle(yol=None):
    """`.env` dosyasını sözlük olarak okur; `export` ve tırnak toleranslı. Yoksa boş sözlük."""
    try:
        satirlar = Path(yol or ENV_DOSYASI).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    sonuc = {}
    for satir in satirlar:
        if satir.lstrip().startswith("#"):
            continue
        eslesme = ENV_SATIRI.match(satir)
        if eslesme:
            sonuc[eslesme.group(1)] = eslesme.group(2).strip("'\"")
    return sonuc


def ortam_yukle(yol=None):
    """`.env` içeriğini ortama yazar. **Proje `.env`'i kazanır**: kabukta aynı adla tanımlı bir
    değişken varsa üzerine yazılır — izleyici `.env`'e ne yazdıysa onu görür. `.env`'de geçmeyen
    değişkenlere dokunulmaz. Ortamın kopyasını döner."""
    for anahtar, deger in env_yukle(yol).items():
        os.environ[anahtar] = deger
    return dict(os.environ)


def eksik_anahtarlar(gerekli, ortam=None):
    ortam = ortam if ortam is not None else os.environ
    return [a for a in gerekli if not ortam.get(a)]


def kanal():
    """İzlenecek YouTube kanalı — `.env` içindeki KANAL değeri."""
    return os.environ.get("KANAL") or "@ornek-kanal"


# --- mesai -----------------------------------------------------------------

def mesaide_mi(simdi=None):
    an = simdi or datetime.now()
    return MESAI_BASLANGIC <= an.hour < MESAI_BITIS


def sonraki_mesai(simdi=None):
    an = simdi or datetime.now()
    aday = an.replace(hour=MESAI_BASLANGIC, minute=0, second=0, microsecond=0)
    return aday if aday > an else aday + timedelta(days=1)


# --- takim.md frontmatter --------------------------------------------------

def _deger(ham):
    ham = ham.strip()
    if ham.startswith("[") and ham.endswith("]"):
        ic = ham[1:-1].strip()
        return [p.strip().strip("'\"") for p in ic.split(",")] if ic else []
    return ham.strip("'\"")


def frontmatter(metin):
    """Basit YAML frontmatter: `anahtar: değer` ve `[a, b]` listeleri. (fm, gövde) döner."""
    if not metin.startswith("---"):
        return {}, metin
    parcalar = metin.split("---", 2)
    if len(parcalar) < 3:
        return {}, metin
    fm = {}
    for satir in parcalar[1].splitlines():
        if ":" not in satir or satir.lstrip().startswith("#"):
            continue
        anahtar, ham = satir.split(":", 1)
        fm[anahtar.strip()] = _deger(ham)
    return fm, parcalar[2].lstrip("\n")


def takim_bilgisi(takim, kok=None):
    """`takimlar/<takim>/takim.md` frontmatter'ı; dosya yoksa None."""
    yol = Path(kok or KOK) / "takimlar" / takim / "takim.md"
    if not yol.is_file():
        return None
    fm, _ = frontmatter(yol.read_text(encoding="utf-8"))
    return fm


# --- durum.json ------------------------------------------------------------

def durum_yolu(takim, kok=None):
    return Path(kok or KOK) / "takimlar" / takim / "durum.json"


def durum_oku(takim, kok=None):
    try:
        return json.loads(durum_yolu(takim, kok).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def durum_guncelle(takim, yama, kok=None):
    """Yeni sözlük yazar (immutable birleştirme); yazılan durumu döner."""
    yol = durum_yolu(takim, kok)
    yeni = {**durum_oku(takim, kok), **yama}
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(yeni, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return yeni


def ozet(simdi=None):
    """`python3 bin/ayar.py` çıktısı — üç satır. Önce `.env` yüklenir, kanal oradan okunur."""
    ortam_yukle()
    an = simdi or datetime.now().astimezone()
    durum = "içinde" if mesaide_mi(an) else "dışında"
    return "\n".join([
        f"{an:%Y-%m-%d %H:%M} — mesai {durum} ({MESAI_METNI}), sonraki açılış {sonraki_mesai(an):%a %H:%M}",
        f"tavanlar: koşu {KOSU_BUTCESI_USD} USD / {KOSU_SURESI_SN // 60} dk · "
        f"takım günde {GUNLUK_KOSU_TAVANI} koşu · arası {KOSULAR_ARASI_DK} dk · "
        f"şirket günde {GUNLUK_MALIYET_TAVANI_USD} USD",
        f"kanal: {kanal()} · .env: {'var' if Path(ENV_DOSYASI).exists() else 'yok'}",
    ])


if __name__ == "__main__":
    print(ozet())

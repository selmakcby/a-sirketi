#!/usr/bin/env python3
"""Dağıtıcı — döngüyü kapatan parça. LLM çağırmaz.

İki işi var:

1. **Karar → sonraki adım.** Bir takımın kuyruğundaki madde "tamam" olunca zincirin devamı
   `ZINCIR` tablosundan okunur ve bir sonraki takımın kuyruğuna yazılır.
   Tek kural: `x-icerik` bir X kaynağını "yazıya değer" bulduysa (`x-<id>`) →
   `twitter-icerik` kuyruğuna `aci-<id>`.
2. **Kuyruk → koşu.** Kuyruğa iş düşünce bir sonraki saat tetiğini beklemez; uygun takımı hemen
   koşturur — mesaiye ve tavanlara uyarak (takım/gün 4 koşu, arası `ayar.KOSULAR_ARASI_DK` dk, şirket/gün 10 USD).

Kullanım: python3 bin/dagitici.py --kuru   (kararları bas, hiçbir şey başlatma)
          python3 bin/dagitici.py          (uygula)
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ayar  # noqa: E402

KOK = ayar.KOK
LOG = KOK / "sirket-log" / "dagitici.log"
KOSU_DOSYA_ADI = re.compile(r"^(\d{4}-\d{2}-\d{2})-\d{4}\.md$")
MALIYET_DESENI = re.compile(r"maliyet:\s*([\d.]+)\s*USD", re.IGNORECASE)
KUYRUK_DURUMLARI = {"bekliyor", "yapiliyor", "tamam", "kacti"}

# Kuyruk id deseni → sonraki takımın kuyruğu. Zincir burada, kodda değil.
ZINCIR = [
    {"ad": "x-yaziya-deger", "desen": re.compile(r"^x-(.+)$"), "takim": "twitter-icerik",
     "id": "aci-{0}", "not": "x-icerik kaynağı yazıya değer buldu; article açısını çıkar"},
]


def _slug(metin):
    return re.sub(r"[^a-z0-9]+", "-", (metin or "").lower()).strip("-")


def zincir_esle(id_):
    """Kuyruk id'sine uyan ilk zincir maddesinin isteğini döner; yoksa None."""
    for kural in ZINCIR:
        eslesme = kural["desen"].match(id_ or "")
        if not eslesme:
            continue
        gruplar = [_slug(g) for g in eslesme.groups()]
        return {"ad": kural["ad"], "takim": kural["takim"],
                "id": kural["id"].format(*gruplar), "not": kural["not"]}
    return None


def kuyruga_yaz(kok, takim, id_, notu):
    """Takımın kuyruğuna 'bekliyor' maddesi ekler (immutable). Yazıldıysa True.
    Aynı id zaten varsa dokunmaz — zincir iki kez tetiklenirse tekrar iş açılmaz."""
    durum = ayar.durum_oku(takim, kok)
    if not durum:
        return False
    kuyruk = durum.get("kuyruk") or []
    if any(isinstance(o, dict) and o.get("id") == id_ for o in kuyruk):
        return False
    ayar.durum_guncelle(takim, {"kuyruk": [*kuyruk, {"id": id_, "durum": "bekliyor", "not": notu}]}, kok)
    return True


def zinciri_isle(kok, takim, kuru=False):
    """Takımın kuyruğundaki 'tamam' maddeleri için zinciri kurar. Yazılan istekleri döner."""
    yazilan = []
    for oge in ayar.durum_oku(takim, kok).get("kuyruk") or []:
        if not isinstance(oge, dict) or oge.get("durum") != "tamam":
            continue
        istek = zincir_esle(oge.get("id"))
        if not istek:
            continue
        varsa = any(k.get("id") == istek["id"]
                    for k in ayar.durum_oku(istek["takim"], kok).get("kuyruk") or [])
        if varsa:
            continue
        if kuru or kuyruga_yaz(kok, istek["takim"], istek["id"], istek["not"]):
            yazilan.append({**istek, "kaynak_takim": takim, "kaynak_id": oge.get("id")})
    return yazilan


# --- tetik kararı ----------------------------------------------------------

def _dt(metin):
    try:
        deger = datetime.fromisoformat(str(metin))
    except (TypeError, ValueError):
        return None
    return deger.astimezone()


def bekleyen_sayisi(durum):
    return sum(1 for o in (durum.get("kuyruk") or [])
               if isinstance(o, dict) and o.get("durum") == "bekliyor")


def bugunku_kosu_sayisi(kok, takim, bugun):
    dizin = Path(kok) / "takimlar" / takim / "kosu"
    if not dizin.is_dir():
        return 0
    return sum(1 for p in dizin.glob("*.md") if KOSU_DOSYA_ADI.match(p.name) and p.name.startswith(bugun))


def gunluk_maliyet(kok, bugun):
    """Bugünkü bütün koşu kayıtlarındaki `maliyet: N USD` satırlarının toplamı."""
    toplam = 0.0
    for kosu in sorted((Path(kok) / "takimlar").glob(f"*/kosu/{bugun}*.md")):
        for ham in MALIYET_DESENI.findall(kosu.read_text(encoding="utf-8", errors="ignore")):
            try:
                toplam += float(ham)
            except ValueError:
                continue
    return toplam


def tetik_karari(kok, takim, simdi):
    """(kossun_mu, sebep) — bu takım şimdi koşmalı mı, neden?"""
    if not ayar.mesaide_mi(simdi):
        return False, f"mesai dışı ({ayar.MESAI_METNI}); kuyruk {ayar.sonraki_mesai(simdi):%H:%M}'da açılır"
    fm = ayar.takim_bilgisi(takim, kok)
    if fm is None:
        return False, "takim.md yok"
    durum = ayar.durum_oku(takim, kok)
    bekleyen = bekleyen_sayisi(durum)
    if not bekleyen:
        return False, "kuyrukta bekleyen madde yok"
    son_kosu = _dt(durum.get("son_kosu"))
    if son_kosu is not None:
        gecen = int((simdi - son_kosu).total_seconds() // 60)
        if gecen < ayar.KOSULAR_ARASI_DK:
            return False, f"{ayar.KOSULAR_ARASI_DK} dk kuralı: {gecen} dk önce koştu"
    bugun = simdi.strftime("%Y-%m-%d")
    sayi = bugunku_kosu_sayisi(kok, takim, bugun)
    if sayi >= ayar.GUNLUK_KOSU_TAVANI:
        return False, f"günlük koşu tavanı: bugün {sayi} koşu (tavan {ayar.GUNLUK_KOSU_TAVANI})"
    maliyet = gunluk_maliyet(kok, bugun)
    if maliyet >= ayar.GUNLUK_MALIYET_TAVANI_USD:
        return False, (f"günlük bütçe doldu: {maliyet:.2f} USD "
                       f"(tavan {ayar.GUNLUK_MALIYET_TAVANI_USD:.0f} USD)")
    ne_zaman = f"son koşu {int((simdi - son_kosu).total_seconds() // 60)} dk önce" if son_kosu else "bugün hiç koşmadı"
    return True, f"kuyrukta {bekleyen} bekleyen madde; {ne_zaman}"


# --- dağıtım ---------------------------------------------------------------

def takimlar(kok):
    dizin = Path(kok) / "takimlar"
    if not dizin.is_dir():
        return []
    return sorted(p.name for p in dizin.iterdir()
                  if p.is_dir() and not p.name.startswith("_") and (p / "takim.md").is_file())


def _kostur(kok, takim):
    """bin/kos.py <takim> arka planda; kilit kos.py'de, çağıran bloklanmaz."""
    (Path(kok) / "sirket-log").mkdir(parents=True, exist_ok=True)
    log = open(Path(kok) / "sirket-log" / f"{takim}-tetik.log", "a")
    # start_new_session: launchd, ana süreç (gunluk.py) bittiğinde işin bütün çocuklarını öldürür.
    # Yeni oturum açılmazsa zamanlayıcıdan gelen koşu daha başlamadan ölür (sessizce, log bile yazmadan).
    subprocess.Popen([sys.executable, str(Path(kok) / "bin" / "kos.py"), takim],
                     stdout=log, stderr=log, cwd=str(kok), start_new_session=True)


def _log_yaz(kok, satirlar, simdi):
    if not satirlar:
        return
    yol = Path(kok) / "sirket-log" / "dagitici.log"
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "a", encoding="utf-8") as dosya:
        for satir in satirlar:
            dosya.write(f"{simdi.isoformat(timespec='seconds')} | {satir['takim']} | "
                        f"{satir['sonuc']} | {satir['sebep']}\n")


def dagit(kok, simdi=None, kuru=False):
    """Önce zinciri kurar, sonra tetik kararlarını verir ve uygun takımları başlatır.

    Döner: {"zincir": [...], "kararlar": [{"takim","sebep","sonuc"}]}
    sonuc: kostu | sirada | bekletildi."""
    simdi = simdi or datetime.now().astimezone()
    zincir = [z for takim in takimlar(kok) for z in zinciri_isle(kok, takim, kuru)]
    kararlar, baslatilan = [], 0
    for takim in takimlar(kok):
        kossun, sebep = tetik_karari(kok, takim, simdi)
        if not kossun:
            kararlar.append({"takim": takim, "sebep": sebep, "sonuc": "bekletildi"})
        elif baslatilan >= ayar.ES_ZAMANLI_TAVAN:
            kararlar.append({"takim": takim, "sonuc": "sirada",
                             "sebep": f"{sebep} · eşzamanlı tavan {ayar.ES_ZAMANLI_TAVAN}"})
        else:
            baslatilan += 1
            if not kuru:
                _kostur(kok, takim)
            kararlar.append({"takim": takim, "sebep": sebep, "sonuc": "kostu"})
    if not kuru:
        _log_yaz(kok, [k for k in kararlar if k["sonuc"] != "bekletildi"], simdi)
    return {"zincir": zincir, "kararlar": kararlar}


ETIKET = {"kostu": "KOŞ  ", "sirada": "SIRA ", "bekletildi": "BEKLE"}


def bas(sonuc, simdi, kuru):
    print(f"dağıtıcı — {simdi:%Y-%m-%d %H:%M}")
    for z in sonuc["zincir"]:
        print(f"  ZİNCİR {z['kaynak_takim']}/{z['kaynak_id']} → {z['takim']}/{z['id']} ({z['ad']})")
    if not sonuc["zincir"]:
        print("  ZİNCİR (yeni bağlantı yok)")
    for k in sonuc["kararlar"]:
        print(f"  {ETIKET[k['sonuc']]} {k['takim']:<16} — {k['sebep']}")
    kosan = [k["takim"] for k in sonuc["kararlar"] if k["sonuc"] == "kostu"]
    print(f"  → {len(kosan)} takım koşar: {', '.join(kosan) if kosan else '(yok)'}")
    if kuru:
        print("  (kuru koşu: kuyruğa yazılmadı, hiçbir takım başlatılmadı)")


def main(argv):
    kuru = "--kuru" in argv
    simdi = datetime.now().astimezone()
    bas(dagit(KOK, simdi, kuru=kuru), simdi, kuru)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

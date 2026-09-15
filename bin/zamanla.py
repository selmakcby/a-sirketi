#!/usr/bin/env python3
"""Zamanlayıcı kurucusu — macOS launchd. İki tetik kurar, başka hiçbir şey yapmaz.

  sabah  → `bin/gunluk.py --sabah`  · dağıtıcıyı koşturur, sabah raporunu yazar
  akşam  → `bin/gunluk.py --aksam`  · günün koşularını ve bekçi kararlarını denetler

Saatler `bin/ayar.py`'den türer (ANAYASA §4 tek yerde): sabah mesai açılışında, denetim
mesai kapanışından bir saat önce. Bilgisayar o saatte kapalı/uykudaysa launchd kaçan işi
açılışta koşturur — saat kaçmaz, iş kaçmaz.

Kullanım:
  python3 bin/zamanla.py --kuru     # kurulacak plist'leri bas, hiçbir şeye dokunma
  python3 bin/zamanla.py --kur      # plist'leri yaz ve launchd'ye yükle
  python3 bin/zamanla.py --durum    # yüklü mü, ne zaman koşacak
  python3 bin/zamanla.py --kaldir   # tetikleri kaldır (rapor dosyalarına dokunmaz)
"""
import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ayar  # noqa: E402

KOK = ayar.KOK
AJANLAR = Path.home() / "Library" / "LaunchAgents"
ON_EK = "com.a-sirketi"
LOG = "sirket-log/zamanlayici.log"

# Etiket köke bağlıdır: iki klon aynı launchd kaydını ele geçirmesin (klasör adı + yol hash'i).
# `com.a-sirketi.<klasor>-<hash6>.<tetik>`. Eski sürüm köksüz `com.a-sirketi.<tetik>` kullanırdı;
# `--durum` onu görürse "eski etiket" diye raporlar, kendiliğinden kaldırmaz.
IMZA_UZUNLUGU = 6

# Saatler ayar.py'den türer; ikinci bir yerde sayı yazmaz.
TETIKLER = [
    {"ad": "sabah", "saat": ayar.MESAI_BASLANGIC, "dakika": 0, "bayrak": "--sabah",
     "ne": "dağıtıcı + sabah raporu"},
    {"ad": "aksam", "saat": ayar.MESAI_BITIS - 1, "dakika": 0, "bayrak": "--aksam",
     "ne": "günün koşuları + bekçi kararları"},
]


def _yol_degeri():
    """launchd'nin dar PATH'i `claude`'u bulamaz; bulunduğu dizin öne eklenir."""
    dizinler = ["/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin", "/opt/homebrew/bin",
                str(Path.home() / ".local" / "bin")]
    claude = shutil.which("claude")
    if claude:
        dizinler.insert(0, str(Path(claude).parent))
    return ":".join(dict.fromkeys(dizinler))


def kok_imzasi(kok=None):
    """Kökü tek kelimeyle tanıtan imza: `<klasor>-<hash6>`. Aynı adlı iki klon çakışmaz."""
    yol = Path(kok or KOK).resolve()
    ozet = hashlib.sha1(str(yol).encode("utf-8")).hexdigest()[:IMZA_UZUNLUGU]
    return f"{yol.name}-{ozet}"


def etiket(ad, kok=None):
    return f"{ON_EK}.{kok_imzasi(kok)}.{ad}"


def eski_etiket(ad):
    """Köksüz eski etiket — yalnızca teşhis için; `--kur`/`--kaldir` buna dokunmaz."""
    return f"{ON_EK}.{ad}"


def plist_yolu(ad, kok=None):
    return AJANLAR / f"{etiket(ad, kok)}.plist"


def _plist_programi(yol):
    """plist'in çalıştırdığı betiğin yolu; dosya yoksa/bozuksa None."""
    try:
        with open(yol, "rb") as dosya:
            argv = plistlib.load(dosya).get("ProgramArguments") or []
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None
    return argv[1] if len(argv) > 1 else None


def plist_icerigi(tetik, kok=None, python=None):
    """Tek bir tetiğin plist sözlüğü. RunAtLoad yok — kurulum anında koşu başlatmaz."""
    kok = Path(kok or KOK)
    return {
        "Label": etiket(tetik["ad"], kok),
        "ProgramArguments": [python or sys.executable, str(kok / "bin" / "gunluk.py"), tetik["bayrak"]],
        "WorkingDirectory": str(kok),
        "EnvironmentVariables": {"PATH": _yol_degeri()},
        "StartCalendarInterval": {"Hour": tetik["saat"], "Minute": tetik["dakika"]},
        "StandardOutPath": str(kok / LOG),
        "StandardErrorPath": str(kok / LOG),
        "RunAtLoad": False,
        "ProcessType": "Background",
    }


def _launchctl(*argv):
    """launchctl çağrısı — (kod, çıktı). launchd yoksa ya da hata verirse istisna fırlatmaz."""
    try:
        sonuc = subprocess.run(["launchctl", *argv], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"launchctl çağrılamadı: {type(exc).__name__}"
    return sonuc.returncode, (sonuc.stdout + sonuc.stderr).strip()


def _hedef():
    return f"gui/{os.getuid()}"


def kur(kok=None):
    """plist'leri yazar ve yükler. Her tetik için (ad, yol, mesaj) döner."""
    AJANLAR.mkdir(parents=True, exist_ok=True)
    (Path(kok or KOK) / LOG).parent.mkdir(parents=True, exist_ok=True)
    sonuclar = []
    for tetik in TETIKLER:
        yol = plist_yolu(tetik["ad"], kok)
        with open(yol, "wb") as dosya:
            plistlib.dump(plist_icerigi(tetik, kok), dosya)
        _launchctl("bootout", f"{_hedef()}/{etiket(tetik['ad'], kok)}")   # varsa önce indir
        kod, cikti = _launchctl("bootstrap", _hedef(), str(yol))
        sonuclar.append({"ad": tetik["ad"], "yol": yol,
                         "mesaj": "yüklendi" if kod == 0 else f"yüklenemedi: {cikti or kod}"})
    return sonuclar


def kaldir(kok=None):
    sonuclar = []
    for tetik in TETIKLER:
        kod, cikti = _launchctl("bootout", f"{_hedef()}/{etiket(tetik['ad'], kok)}")
        yol = plist_yolu(tetik["ad"], kok)
        vardi = yol.exists()
        yol.unlink(missing_ok=True)
        sonuclar.append({"ad": tetik["ad"], "yol": yol,
                         "mesaj": "kaldırıldı" if (kod == 0 or vardi) else f"zaten yoktu ({cikti or kod})"})
    return sonuclar


def durum(kok=None):
    """Her tetik için: bu köke ait mi, yüklü mü, eski etiketle yüklü bir kalıntı var mı."""
    kok = Path(kok or KOK)
    bin_dizini = str((kok / "bin").resolve())
    sonuclar = []
    for tetik in TETIKLER:
        yol = plist_yolu(tetik["ad"], kok)
        program = _plist_programi(yol)
        # sembolik bağ farkı yanıltmasın: iki taraf da çözülerek karşılaştırılır
        baska = program if (program and not str(Path(program).resolve()).startswith(bin_dizini)) else None
        kod, _ = _launchctl("print", f"{_hedef()}/{etiket(tetik['ad'], kok)}")
        eski = eski_etiket(tetik["ad"])
        eski_kod, _ = _launchctl("print", f"{_hedef()}/{eski}")
        eski_yol = AJANLAR / f"{eski}.plist"
        sonuclar.append({**tetik, "etiket": etiket(tetik["ad"], kok),
                         "yuklu": kod == 0 and baska is None, "plist": yol.exists(),
                         "baska_kok": baska, "eski_etiket": eski,
                         "eski_yuklu": eski_kod == 0 or eski_yol.exists(),
                         "eski_kok": _plist_programi(eski_yol)})
    return sonuclar


def _eski_etiket_uyarisi():
    """Köksüz eski etiket hâlâ duruyorsa söyle — kaldırmak insanın kararı."""
    for tetik in TETIKLER:
        eski = eski_etiket(tetik["ad"])
        if (AJANLAR / f"{eski}.plist").exists() or _launchctl("print", f"{_hedef()}/{eski}")[0] == 0:
            print(f"⚠ eski etiket {eski} hâlâ yüklü — çift tetik olmasın diye kaldır: "
                  f"launchctl bootout {_hedef()}/{eski}")


def main(argv):
    if "--kuru" in argv:
        for tetik in TETIKLER:
            print(f"--- {etiket(tetik['ad'])} · her gün {tetik['saat']:02d}:{tetik['dakika']:02d} "
                  f"· {tetik['ne']}")
            print(plistlib.dumps(plist_icerigi(tetik)).decode("utf-8"))
        print("(kuru koşu: hiçbir dosya yazılmadı, launchd'ye dokunulmadı)")
        return 0
    if "--kur" in argv:
        for s in kur():
            print(f"{s['ad']:<6} {s['mesaj']} — {s['yol']}")
        _eski_etiket_uyarisi()
        return 0
    if "--kaldir" in argv:
        for s in kaldir():
            print(f"{s['ad']:<6} {s['mesaj']}")
        _eski_etiket_uyarisi()
        return 0
    if "--durum" in argv:
        print(f"etiket: {ON_EK}.{kok_imzasi()}.<tetik>  ({KOK})")
        for s in durum():
            if s["baska_kok"]:
                isaret = f"· başka kök için yüklü: {s['baska_kok']}"
            elif s["yuklu"]:
                isaret = "✓ yüklü"
            else:
                isaret = "· plist var, yüklü değil" if s["plist"] else "· kurulu değil"
            print(f"{s['ad']:<6} her gün {s['saat']:02d}:{s['dakika']:02d}  {isaret:<40} {s['ne']}")
            if s["eski_yuklu"]:
                nere = f" (→ {s['eski_kok']})" if s["eski_kok"] else ""
                print(f"       ⚠ eski etiket {s['eski_etiket']} yüklü{nere} — "
                      f"`python3 bin/zamanla.py --kur` ile yenile")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

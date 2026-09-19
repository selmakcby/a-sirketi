#!/usr/bin/env python3
"""Telegram dinleyici — bota mesaj düştüğü anda ilgili takım koşar. Zamanlayıcı yok.

Kullanım:
  python3 bin/telegram_dinle.py            # sonsuz long-poll döngüsü
  python3 bin/telegram_dinle.py --bir-kez  # tek tur döner (test)

Offset yönetimi ve chat id filtresi `bin/telegram_oku.py`'dedir; burada kopyası yok, çağrılır
(`guncellemeleri_cek` + `isle` → `durum.json` → `sayaclar.telegram_son_update`).

ANAYASA §4 tek yerde: sayılar `bin/ayar.py`'de, mesai/tavan kararı `dagitici.tetik_karari`'nda.
Dinleyici kendi başına saat ya da tavan bilmez, sorar. Mesai dışında mesaj `gelen/` altına yazılır
ve kuyruğa `bekliyor` düşer ama koşu başlamaz — sabah dağıtıcı alır.

Yönlendirme `takim_sec`'te, tek yerde: içinde "youtube" geçen her mesaj (link olsun olmasın)
`youtube-analiz`'e, "youtube" geçmeyen ama link taşıyan mesaj `x-icerik`'e gider. İkisi de
değilse (ör. `/start`, düz metin) mesaj yalnızca loglanır, hiçbir şey koşmaz.
Gelen kutusu ve Telegram offset'i `takimlar/x-icerik/` altında kalır — Telegram'ın tek bir
offset'i var, takımlara bölünmez.
Koşu önde yapılır: bir koşu sürerken düşen mesajlar Telegram'da bekler, sonra sırayla işlenir —
üst üste koşu olmaz (kilit ayrıca `bin/kos.py`'de).

TELEGRAM_BOT_TOKEN yoksa sessizce çıkar (0). Token hiçbir log satırına yazılmaz.
Telegram token'ı reddederse (401/403) ya da ağ yoksa dinleyici ölmez: turu atlar, loga yazar,
bir sonraki turda tekrar dener.
"""
import collections
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ayar  # noqa: E402
import dagitici  # noqa: E402
import telegram_oku  # noqa: E402

KOK = ayar.KOK
TAKIM = telegram_oku.TAKIM          # x-icerik — linkli mesajların varsayılan takımı
YT_TAKIM = "youtube-analiz"         # içinde "youtube" geçen mesajın takımı
YOUTUBE = re.compile(r"youtube", re.IGNORECASE)
KUYRUK_ONEKI = {TAKIM: "x", YT_TAKIM: "yt"}   # kuyruk id öneki; "x-" dağıtıcının zincir desenidir
BEKLEME_SN = 15                     # getUpdates long-poll süresi
TUR_ARASI_SN = 2                    # iki tur arası nefes (ağ hatasında sıkı döngüyü keser)
NOT_SINIRI = 200                    # kuyruğa yazılan dış metnin karakter tavanı
LINK_SINIRI = 120
LOG_ADI = "telegram-dinle.log"

_SIRLAR = []                        # loga asla düşmemesi gereken değerler; `_log` hepsini maskeler


def sir_ekle(deger):
    """Bir sırrı log maskesine yazar (bir kez, açılışta). Maskelenen sırların sayısını döner."""
    if deger and deger not in _SIRLAR:
        _SIRLAR.append(deger)
    return len(_SIRLAR)


def _log(kok, satir):
    """Tek satır log — ekrana ve `sirket-log/telegram-dinle.log`'a. Sırlar tek kapıdan maskelenir."""
    for sir in _SIRLAR:
        satir = satir.replace(sir, "***")
    damga = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{damga} | {satir}", flush=True)
    yol = Path(kok) / "sirket-log" / LOG_ADI
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "a", encoding="utf-8") as dosya:
            dosya.write(f"{damga} | {satir}\n")
    except OSError as exc:
        print(f"{damga} | log yazılamadı: {type(exc).__name__}", flush=True)


def _temiz(metin, sinir=NOT_SINIRI):
    """Dışarıdan gelen metin: tek satıra indir, kırp. Kuyruğa veri olarak girer, talimat olarak değil."""
    tek_satir = " ".join(str(metin or "").split())
    return tek_satir[:sinir] + ("…" if len(tek_satir) > sinir else "")


def takim_sec(mesaj):
    """Mesajı hangi takım karşılar? 'youtube' geçen her mesaj youtube-analiz'e (link olsun
    olmasın), link taşıyan geri kalanı x-icerik'e. İkisi de değilse None — kuyruğa yazılmaz.

    Dış metin ANAYASA §2 gereği veridir, talimat değil: yalnız desene bakılır, yorumlanmaz."""
    if YOUTUBE.search(mesaj.get("metin") or ""):
        return YT_TAKIM
    return TAKIM if mesaj.get("linkler") else None


def kuyruk_maddesi(mesaj, takim):
    """(id, not) — id `<önek>-<update_id>`. x-icerik'inki dağıtıcının zincir desenine uyar;
    `yt-` ile başlayan madde zincire takılmaz (bkz. `dagitici.ZINCIR`)."""
    parcalar = [f"telegram {str(mesaj.get('zaman') or '')[:16]}"]
    link = _temiz((mesaj.get("linkler") or [""])[0], LINK_SINIRI)
    if link:
        parcalar.append(link)
    notu = _temiz(mesaj.get("not"))
    if notu:
        parcalar.append(f"not: {notu}")
    return f"{KUYRUK_ONEKI[takim]}-{mesaj['update_id']}", " · ".join(parcalar)


def gelen_mesajlar(yollar):
    """`telegram_oku.isle`'nin yazdığı `gelen/*.json` dosyalarını okur; bozuk dosyayı atlar."""
    mesajlar = []
    for yol in yollar:
        try:
            mesajlar.append(json.loads(Path(yol).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return mesajlar


HABER = None                        # main() kurar: patrona Telegram'dan haber veren tek kapı


def bildir(haber, metin):
    """Patrona tek satır haber (Telegram). Bildirim hatası koşuyu düşürmez — sessizce geçilir."""
    haber = haber or HABER
    if not haber:
        return
    try:
        haber(metin)
    except Exception as exc:                      # noqa: BLE001 — haber yolu koşuyu bağlamaz
        print(f"bildirim gitmedi: {type(exc).__name__}", file=sys.stderr)


def sonuc_ozeti(kok, takim, id_):
    """Koşu bitince kuyruk maddesinin durumu + bekçi kararı — tek satırlık özet."""
    durum = ayar.durum_oku(takim, kok)
    madde = next((m for m in (durum.get("kuyruk") or []) if m.get("id") == id_), {})
    bekci = (durum.get("bekci") or {}).get("son_karar") or "kayıt yok"
    return f"{madde.get('durum', '?')} · {_temiz(madde.get('not') or '-', 300)} · bekçi: {bekci}"


def kostur(kok, takim):
    """Önce `kos.py <takim>` (bitene kadar beklenir), sonra `dagitici.py`.

    Dağıtıcı her koşudan sonra çağrılır: zinciri o kurar (ANAYASA §5), tavanları o bilir (§4)."""
    bin_dizini = Path(kok) / "bin"
    for komut in ([sys.executable, str(bin_dizini / "kos.py"), takim],
                  [sys.executable, str(bin_dizini / "dagitici.py")]):
        subprocess.run(komut, cwd=str(kok), check=False)


def isle_mesaj(kok, mesaj, simdi=None, haber=None):
    """Tek mesaj: takımını seç, kuyruğa yaz, §4 izin verirse hemen koş. (etiket, sebep) döner.

    etiket: ilgisiz | kostu | bekletildi. `haber` verilirse her adım patrona Telegram'dan bildirilir."""
    takim = takim_sec(mesaj)
    if not takim:
        return "ilgisiz", "link yok, 'youtube' da geçmiyor — koşu başlatılmadı"
    id_, notu = kuyruk_maddesi(mesaj, takim)
    dagitici.kuyruga_yaz(kok, takim, id_, notu)   # aynı id ikinci kez iş açmaz
    kossun, sebep = dagitici.tetik_karari(kok, takim, simdi or datetime.now().astimezone())
    if not kossun:
        bildir(haber, f"⏸ istek alındı · {takim} kuyruğu {id_}\nkoşmadı: {sebep}")
        return "bekletildi", f"{takim}/{id_}; {sebep}"
    bildir(haber, f"▶️ istek alındı · {takim} kuyruğu {id_}\n{takim} koşuyor…")
    kostur(kok, takim)
    bildir(haber, f"✅ koşu bitti · {id_}\n{sonuc_ozeti(kok, takim, id_)}")
    return "kostu", f"{takim}/{id_}; {sebep}"


def tur(kok, token, chat_id, kuyruk, bekleme=BEKLEME_SN):
    """Tek long-poll turu: çek → `gelen/` yaz → mesajları sıraya al → sırayla işle. İşlenen sayısı döner."""
    son = int((ayar.durum_oku(TAKIM, kok).get("sayaclar") or {}).get("telegram_son_update", 0))
    guncellemeler = telegram_oku.guncellemeleri_cek(token, offset=son + 1 if son else None,
                                                    bekleme=bekleme)
    for mesaj in gelen_mesajlar(telegram_oku.isle(kok, guncellemeler, chat_id)):
        kuyruk.append(mesaj)
        _log(kok, f"mesaj {mesaj.get('update_id')} · {len(mesaj.get('linkler') or [])} link "
                  f"· → {takim_sec(mesaj) or 'ilgisiz'} · sıraya alındı")
    islenen = 0
    while kuyruk:                       # sırayla, tek tek — koşu bitmeden sıradakine geçilmez
        mesaj = kuyruk.popleft()
        etiket, sebep = isle_mesaj(kok, mesaj)
        islenen += 1
        _log(kok, f"mesaj {mesaj.get('update_id')} · {etiket} — {sebep}")
    return islenen


def _kimlik():
    """(token, chat_id, cikis_kodu) — anahtarlar eksikse token None, kod dolu."""
    ayar.ortam_yukle()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN yok — dinleyici açılmadı.")
        return None, None, 0
    ham_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not ham_id:
        print("TELEGRAM_CHAT_ID yok (.env) — önce: python3 bin/telegram_oku.py --chat-id-bul",
              file=sys.stderr)
        return None, None, 1
    try:
        return token, int(ham_id), None
    except ValueError:
        print("TELEGRAM_CHAT_ID sayı değil (.env)", file=sys.stderr)
        return None, None, 1


def main(argv):
    token, chat_id, kod = _kimlik()
    if kod is not None:
        return kod
    sir_ekle(token)                 # bundan sonra hiçbir log satırında token görünemez
    global HABER
    HABER = lambda metin: telegram_oku._api(token, "sendMessage", chat_id=chat_id,
                                            text=metin, disable_web_page_preview="true")
    bir_kez = "--bir-kez" in argv
    kuyruk = collections.deque()
    _log(KOK, f"dinleyici açıldı · takımlar {TAKIM}, {YT_TAKIM} · long-poll {BEKLEME_SN} sn"
              + (" · tek tur" if bir_kez else ""))
    try:
        while True:
            try:
                tur(KOK, token, chat_id, kuyruk)
            except telegram_oku.TelegramHatasi as exc:   # token geçersiz ya da ağ yok
                _log(KOK, f"{exc} — bu tur atlandı")
            except Exception as exc:    # daemon hiçbir turda ölmez, ama sessiz de kalmaz
                _log(KOK, f"tur hatası: {type(exc).__name__}: {exc} — bu tur atlandı")
            if bir_kez:
                return 0
            time.sleep(TUR_ARASI_SN)
    except KeyboardInterrupt:
        _log(KOK, "dinleyici kapandı (Ctrl-C)")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

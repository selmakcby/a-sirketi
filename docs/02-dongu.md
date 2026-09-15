# 02 · Döngü ve tetikler

Bu şirketin "çalışıyor" demesi için birinin ajanları başlatması gerekir. Dört yol var, hepsi
aynı yere çıkar: `python3 bin/kos.py <takim>`.

Mimari ve `kos.py`'nin içi [01-nasil-calisir.md](01-nasil-calisir.md)'de.

---

## İki döngü: dış ve iç

Karıştırılması kolay iki şey var.

**Dış döngü — vardiya.** Gün içinde şirketin kendisi döner: sabah 09:00'da `gunluk.py --sabah`
haftalık işi kuyruğa düşürür ve dağıtıcıyı koşturur; gün boyu Telegram'a düşen her link
`x-icerik`'i o saniye başlatır; bir takım işini `tamam` yapınca dağıtıcı zinciri kurup bir
sonraki takımı çalıştırır; akşam 22:00'de `gunluk.py --aksam` günü denetler. Her vardiyanın
birimi **bir koşudur**: tek `claude -p` oturumu, 15 dakika, 2 USD.

**İç döngü — bir prompt'un arkasındaki araç turları.** Tek bir koşunun içinde ajan onlarca tur
atar: dosya okur, `bin/tweet_cek.py` çağırır, arama yapar, yazar, `durum.json`'u günceller.
Bu turların sayısı koşu kaydının altbilgisine yazılır (`tur: 19`). İç döngüyü kimse
tetiklemez — Claude Code'un kendi ajan döngüsüdür; sürücü ona yalnızca **tavan** koyar
(bütçe, süre, izinli araç listesi).

Bekçi iç döngünün **çıkışında** durur: ajan bitirmek istediğinde Stop hook ateşlenir ve red
gelirse ajan aynı oturumda düzeltmeye geri döner. Yani bekçi dış döngünün değil, iç döngünün
son halkasıdır. [03-bekci.md](03-bekci.md)

---

## Dört tetik yolu

### 1 · Olay tetiği — `bin/telegram_dinle.py`

Asıl yol, `x-icerik` için. Zamanlayıcı yok: bota mesaj düştüğü an koşu başlar.

```bash
python3 bin/telegram_dinle.py            # sonsuz long-poll döngüsü
python3 bin/telegram_dinle.py --bir-kez  # tek tur (test)
```

Bir tur şöyle işler (`tur()`):

1. `durum.json` → `sayaclar.telegram_son_update` okunur (offset).
2. `telegram_oku.guncellemeleri_cek(token, offset=son+1, bekleme=15)` — Telegram
   `getUpdates` çağrısı **15 saniye** long-poll bekler (`BEKLEME_SN`), sokete ayrıca pay bırakılır.
3. `telegram_oku.isle(...)` yalnızca **kendi chat id'nizden** gelen mesajları
   `takimlar/x-icerik/gelen/<tarih>-<update_id>.json` altına yazar ve offset'i ilerletir.
   Başkası bota yazarsa görmezden gelinir.
4. Her mesaj yerel bir `deque`'ye alınır, **sırayla, tek tek** işlenir — koşu bitmeden
   sıradakine geçilmez. Böylece üst üste koşu olmaz (ayrıca `kos.py`'de dosya kilidi var).
5. `isle_mesaj()`:
   - Mesajda link yoksa → `linksiz`, yalnızca loglanır, hiçbir şey koşmaz.
   - Link varsa → kuyruğa `x-<update_id>` maddesi yazılır (`durum: bekliyor`), notu
     `telegram <tarih> · <link> · not: <patronun notu>` biçiminde, dış metin tek satıra
     indirilip **200 karaktere** kırpılarak (`NOT_SINIRI`; link için `LINK_SINIRI` 120).
   - Sonra `dagitici.tetik_karari()` sorulur. İzin varsa `kos.py x-icerik` **beklenerek**
     çalıştırılır, hemen ardından `dagitici.py` — zincir `twitter-icerik`'e geçsin diye.
   - İzin yoksa `bekletildi` döner; madde kuyrukta kalır, sabah alınır.
6. Her adımda patrona Telegram'dan tek satır haber gider: `▶️ link alındı…`,
   `✅ koşu bitti · <id>` (kuyruk durumu + bekçi kararı), ya da `⏸ … koşmadı: <sebep>`.

Güvenlik notları: `TELEGRAM_BOT_TOKEN` açılışta log maskesine eklenir
(`sir_ekle`), böylece hiçbir log satırında görünemez. Token yoksa dinleyici sessizce
çıkar (kod 0). Turda hata olursa daemon ölmez, hata loglanır ve tur atlanır.

### 2 · Sabah 09:00 — `bin/gunluk.py --sabah`

launchd her sabah `gunluk.py --sabah` çalıştırır. Sırasıyla:

1. **Haftalık iş kuyruğa.** `HAFTALIK` tablosu tek maddedir:
   `{"takim": "youtube-analiz", "gun": 0, "id": "yt-{hafta}", "not": "haftalık kanal raporu — son 7 gün"}`
   — `gun: 0` pazartesi demektir. Hafta kimliği ISO biçiminde `YYYY-Www`
   (`hafta_kimligi`), `youtube_analiz_cek.py`'nin veri dosyası adıyla birebir aynı.
   Aynı haftanın maddesi ikinci kez yazılmaz.
2. **Dağıtıcı koşar** (`dagitici.dagit`) — zincir + tetik kararları.
3. **Sabah raporu** `sirket-log/rapor/YYYY-MM-DD-sabah.md`: haftalık iş, dağıtıcının kurduğu
   zincir bağlantıları, takım başına karar tablosu (KOŞ / SIRA / BEKLE + sebep), takımların
   durumu (son koşu, sonuç, bekleyen, bugünkü koşu, bekçi), dünün özeti
   (kaç koşu, kaç USD, kaç red, kaç hata) ve tavanlar bölümü.

`--kuru` eklerseniz rapor ekrana basılır, dosyaya yazılmaz ve hiçbir takım başlatılmaz.

### 3 · Zincir — `bin/dagitici.py`

Takımlar birbirine mesaj atmaz (ANAYASA §5). Aralarındaki tek bağ dağıtıcıdır ve zincir
tablo hâlinde, kodun içinde dağınık değil, tek yerdedir:

```python
ZINCIR = [
    {"ad": "x-yaziya-deger", "desen": re.compile(r"^x-(.+)$"), "takim": "twitter-icerik",
     "id": "aci-{0}", "not": "x-icerik kaynağı yazıya değer buldu; article açısını çıkar"},
]
```

Okunuşu: **`x-icerik` kuyruğundaki bir madde `x-<id>` desenine uyuyor ve durumu `tamam` ise,
`twitter-icerik` kuyruğuna `aci-<id>` maddesi `bekliyor` olarak düşer.**

- Yalnızca `tamam` maddeler zincire girer. `bekliyor` ve `bitti` girmez.
- Hedef kuyrukta aynı id zaten varsa hiçbir şey yazılmaz — zincir iki kez işlese de
  ikinci iş açılmaz.
- Id'nin içindeki grup "slug"laştırılır (`_slug`: küçük harf, alfasayısal olmayan her şey tire).

Dağıtıcı LLM çağırmaz, para harcamaz. Kuru koşusu güvenlidir:

```bash
python3 bin/dagitici.py --kuru   # kararları bas, kuyruğa yazma, takım başlatma
python3 bin/dagitici.py          # uygula
```

Çıktısı şuna benzer:

```
dağıtıcı — 2026-09-11 09:00
  ZİNCİR x-icerik/x-30760576 → twitter-icerik/aci-30760576 (x-yaziya-deger)
  KOŞ   twitter-icerik   — kuyrukta 1 bekleyen madde; bugün hiç koşmadı
  BEKLE x-icerik         — kuyrukta bekleyen madde yok
  BEKLE youtube-analiz   — kuyrukta bekleyen madde yok
  → 1 takım koşar: twitter-icerik
```

Başlatma arka plandadır (`subprocess.Popen`), çıktısı `sirket-log/<takim>-tetik.log`'a gider;
kilit `kos.py`'dedir, dağıtıcı bloklanmaz. `bekletildi` dışındaki kararlar
`sirket-log/dagitici.log`'a tek satır olarak yazılır.

### 4 · Elle

```bash
python3 bin/kos.py x-icerik           # normal koşu
python3 bin/kos.py x-icerik --kuru    # istemi göster, hiçbir şeye dokunma
python3 bin/kos.py x-icerik --zorla   # mesai kontrolünü atla
```

---

## Tetik kararı — `dagitici.tetik_karari()`

Bir takımın şimdi koşup koşmayacağına karar veren tek fonksiyon. Sırayla bakar,
ilk "hayır"da durur ve sebebini döner:

| Kontrol | Hayırsa sebep |
|---|---|
| Mesai içinde mi? | `mesai dışı (09:00-23:00); kuyruk 09:00'da açılır` |
| `takim.md` var mı? | `takim.md yok` |
| Kuyrukta `bekliyor` madde var mı? | `kuyrukta bekleyen madde yok` |
| Son koşudan `KOSULAR_ARASI_DK` geçti mi? | `0 dk kuralı: N dk önce koştu` |
| Bugünkü koşu sayısı < 4 mü? | `günlük koşu tavanı: bugün 4 koşu (tavan 4)` |
| Bugünkü toplam maliyet < 10 USD mi? | `günlük bütçe doldu: 10.50 USD (tavan 10 USD)` |

Hepsi geçerse `(True, "kuyrukta N bekleyen madde; son koşu M dk önce")`.

Üç not:

- **`KOSULAR_ARASI_DK` varsayılanı 0'dır** — yani aynı takım için iki koşu arasında bekleme
  yoktur. Kuyrukta iş varsa takım hemen koşar; freni günlük koşu sayısı ve günlük USD tavanı
  tutar (ANAYASA §4). Kuralın mantığı testte ayar 30'a çekilerek sınanır.
- **Günlük maliyet dosyadan sayılır**, ayrı bir defterden değil: o günün bütün
  `takimlar/*/kosu/YYYY-MM-DD*.md` dosyalarındaki `maliyet: N USD` satırları toplanır.
  Koşu kaydını silmek muhasebeyi de siler.
- **Bugünkü koşu sayısı** yine dosya adından sayılır (`YYYY-MM-DD-HHMM.md` deseni).
  Atlanmış koşular da dosya yazdığı için sayılır.

Dağıtıcı bir turda en fazla `ES_ZAMANLI_TAVAN` = **2** takım başlatır; fazlası `SIRA` etiketiyle
bir sonraki tura kalır.

---

## Kuyruk maddesi durumları

Kuyruk maddesi `{"id": …, "durum": …, "not": …}` biçimindedir. Kodda geçen değerler:

| Durum | Kim yazar | Ne demek |
|---|---|---|
| `bekliyor` | dağıtıcı (`kuyruga_yaz`), dinleyici, `gunluk.haftalik_kuyruk` | İş var, henüz yapılmadı. `tetik_karari` bunu sayar. |
| `tamam` | ajan | İş bitti **ve zincirin devamı var**. `zinciri_isle` yalnızca bunu taşır. |
| `bitti` | ajan | İş bitti, zincire girmiyor (örn. "yazıya değer değil"). Takım sözleşmesinde tanımlı, dağıtıcı dokunmaz. |

Ayrıca `not-` ile başlayan `bekliyor` maddeler **patronun elle bıraktığı notlardır**; ajan
kuyrukta önce onları işler (`sirket/AJAN-KIMLIGI.md`).

`atlandi` ve `hata` kuyruk maddesinin değil, **koşunun** sonucudur: `durum.json` kök seviyesindeki
`son_sonuc` alanı `tamam` · `red` · `hata` · `atlandi` değerlerinden birini alır.

> **Not (kodda tutarsızlık).** `bin/dagitici.py` içinde
> `KUYRUK_DURUMLARI = {"bekliyor", "yapiliyor", "tamam", "kacti"}` sabiti tanımlı ama hiçbir yerde
> kullanılmıyor; `yapiliyor` ve `kacti` değerlerini yazan da okuyan da yok. Gerçekte kullanılan
> üçlü yukarıdaki tablodur.

---

## Günlük raporlar — `bin/gunluk.py`

```bash
python3 bin/gunluk.py --sabah        # dağıtıcıyı koştur + sabah raporu
python3 bin/gunluk.py --aksam        # denetim raporu (hiçbir şey koşturmaz)
python3 bin/gunluk.py --sabah --kuru # hiçbir takımı başlatma, raporu ekrana bas
```

Raporlar `sirket-log/rapor/YYYY-MM-DD-{sabah,aksam}.md` altına yazılır ve `.gitignore`'dadır —
**dışarı hiçbir şey gitmez.** `gunluk.py` LLM çağırmaz; yalnızca `takimlar/*/kosu/*.md`,
`takimlar/*/durum.json` ve `takimlar/bekci-telemetri.jsonl` dosyalarını okur.

**Akşam denetimi** (22:00) günü kapatır ve hiçbir takımı başlatmaz. İçinde:

- Bugünün koşuları tablosu: saat, takım, maliyet, tur, hata, bekçi kararı, atlanma notu.
- Bekçi kararları: kabul / red / atlandı sayıları + karar tablosu (gerekçe 120 karaktere kırpılı).
- **Dikkat** bölümü — gözden kaçmaması gerekenler, uydurulmadan:
  `⛔ bekçi red`, `⛔ koşu hata ile bitti`, `🟡 atlandı: <sebep>`,
  `🟡 bekçi kararı kayda düşmemiş`, `🟡 bekçi denetleyemedi: <gerekçe>`.
  Hiçbiri yoksa "temiz gün, işaretlenecek bir şey yok".
- Tavanlar bölümü: günün toplam USD'si / 10 USD, takım başına koşu sayısı, mesai ve tavan satırı.

---

## Zamanlayıcı — `bin/zamanla.py` (macOS launchd)

```bash
python3 bin/zamanla.py --kuru     # kurulacak plist'leri bas, hiçbir şeye dokunma
python3 bin/zamanla.py --kur      # plist'leri yaz ve launchd'ye yükle
python3 bin/zamanla.py --durum    # yüklü mü, ne zaman koşacak
python3 bin/zamanla.py --kaldir   # tetikleri kaldır (rapor dosyalarına dokunmaz)
```

İki tetik kurar, başka hiçbir şey yapmaz:

| Etiket | Saat | Komut |
|---|---|---|
| `com.a-sirketi.<klasor>-<hash6>.sabah` | `MESAI_BASLANGIC` → 09:00 | `bin/gunluk.py --sabah` |
| `com.a-sirketi.<klasor>-<hash6>.aksam` | `MESAI_BITIS - 1` → 22:00 | `bin/gunluk.py --aksam` |

Etiket köke bağlıdır (`<klasor>-<hash6>`: klasör adı + tam yolun sha1 kısaltması): iki klon
aynı launchd kaydını ele geçirmez. `--durum` plist'in çalıştırdığı betiğin **bu köke** ait
olduğunu doğrular; başka köke bakıyorsa "başka kök için yüklü" der. Eski sürümün köksüz
`com.a-sirketi.sabah` etiketi hâlâ yüklüyse `--durum` bunu "eski etiket, `--kur` ile yenile"
diye raporlar — kendiliğinden kaldırmaz, çift tetik olmasın diye elle indirirsin:
`launchctl bootout gui/$(id -u)/com.a-sirketi.sabah`.

plist ayrıntıları: `StartCalendarInterval` ile saat/dakika; `RunAtLoad: False` — kurulum anında
koşu başlatmaz; `ProcessType: Background`; `StandardOutPath`/`StandardErrorPath`
→ `sirket-log/zamanlayici.log`; `WorkingDirectory` repo kökü. `EnvironmentVariables.PATH`
elle kurulur çünkü **launchd'nin dar PATH'i `claude`'u bulamaz** — `shutil.which("claude")`
ile bulunan dizin listenin başına eklenir, arkasından `/usr/bin`, `/bin`, `/usr/sbin`,
`/sbin`, `/usr/local/bin`, `/opt/homebrew/bin`, `~/.local/bin` gelir.

Bilgisayar o saatte kapalı ya da uykudaysa launchd kaçan işi açılışta koşturur — saat kaçar,
iş kaçmaz.

**macOS dışında.** `zamanla.py` yalnızca launchd bilir. Linux'ta aynı iki tetiği cron ile
kurabilirsiniz — `zamanla.py` kullanılmaz, `crontab -e` içine:

```cron
0 9  * * * cd /yol/a-sirketi && /usr/bin/python3 bin/gunluk.py --sabah >> sirket-log/zamanlayici.log 2>&1
0 22 * * * cd /yol/a-sirketi && /usr/bin/python3 bin/gunluk.py --aksam >> sirket-log/zamanlayici.log 2>&1
```

`claude` PATH'te değilse cron satırına `PATH=` ataması ekleyin; cron'un PATH'i de dardır.
Makine o saatte kapalıysa cron kaçan işi telafi **etmez** (launchd eder) — `anacron` ya da
`systemd` `OnCalendar` + `Persistent=true` bu farkı kapatır. Dinleyici (`telegram_dinle.py`)
sürekli çalışan bir süreçtir, zamanlayıcı işi değildir; `systemd` servisi ya da `tmux`
oturumu olarak açık tutulur.

---

## Sırada

- Denetim: [03-bekci.md](03-bekci.md)
- Bir şey tetiklenmiyorsa: [06-sorun-giderme.md](06-sorun-giderme.md)
- Gerçek bir koşu kaydı: [ornek-kosu/kosu-kaydi.md](ornek-kosu/kosu-kaydi.md)

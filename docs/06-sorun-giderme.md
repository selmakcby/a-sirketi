# 06 · Sorun giderme

Her madde üç satır: **belirti** → **sebep** → **çözüm**. Mesajlar koddaki gerçek metinlerdir;
aynen aratabilirsiniz.

Mimari [01-nasil-calisir.md](01-nasil-calisir.md)'de, tetikler
[02-dongu.md](02-dongu.md)'de, bekçi [03-bekci.md](03-bekci.md)'de.

---

## `telegram_oku.py --isle` boş dönüyor ama `gelen/` dolu

**Belirti.** `python3 bin/telegram_oku.py --isle` → `{"yeni": []}`, ama
`takimlar/x-icerik/gelen/` altında işlenmemiş `.json` dosyaları duruyor.

**Sebep.** Bu **hata değil, normal durumdur.** Dinleyici (`telegram_dinle.py`) mesajı çoktan
`gelen/` altına yazmış ve offset'i `durum.json` → `sayaclar.telegram_son_update` alanında
ilerletmiştir. Telegram bir güncellemeyi `offset` ile onaylandıktan sonra **bir daha vermez**;
ikinci `--isle` çağrısı doğal olarak boş döner.

**Çözüm.** `--isle`'nin çıktısına değil **klasöre** bakın. İşlenecek iş,
`gelen/islendi/` altına taşınmamış her `gelen/*.json` dosyasıdır. `takim.md` adım 1 bunu
açıkça söyler:

> `--isle` boş döner ama dosya oradadır — "yeni yok" deyip bitirme.

Ajan işini bitirince dosyayı `gelen/islendi/` altına taşır; klasörün gerçekten boş olması
"yeni link yok" demektir.

---

## Koşu "mesai dışı" diye atlanıyor

**Belirti.** Koşu kaydında tek satır: `**Atlandı:** mesai dışı (09:00-23:00); kuyrukta bekler`,
`durum.json` → `son_sonuc: "atlandi"`. Dağıtıcıda: `BEKLE x-icerik — mesai dışı (09:00-23:00);
kuyruk 09:00'da açılır`.

**Sebep.** ANAYASA §4: mesai 09:00–23:00. `ayar.mesaide_mi()` sistemin **yerel saatine** bakar
(`MESAI_BASLANGIC <= saat < MESAI_BITIS`). Sunucu UTC'deyse ya da makinenin saat dilimi
yanlışsa mesai penceresi kaydırılmış olur.

**Çözüm.** Tek seferlik tetik için `--zorla`:

```bash
python3 bin/kos.py x-icerik --zorla
```

Kalıcı olarak saati değiştirmek için `bin/ayar.py` içindeki `MESAI_BASLANGIC` / `MESAI_BITIS`.
Sayı orada tek yerdedir — `zamanla.py`'nin sabah/akşam tetikleri de oradan türer, o yüzden
değiştirdikten sonra `python3 bin/zamanla.py --kur` ile tetikleri yeniden yükleyin.
Saat dilimini önce `python3 bin/ayar.py` ile doğrulayın; ilk satır o anki saati ve mesai
durumunu basar.

---

## "eksik anahtar: APIFY_TOKEN"

**Belirti.** Koşu kaydında `**Atlandı:** eksik anahtar: APIFY_TOKEN`, `claude` hiç çağrılmamış,
maliyet 0.

**Sebep.** `takim.md` frontmatter'ındaki `gerekli_anahtarlar` listesindeki bir değişken ortamda
boş. `kos.py` `.env`'i yükledikten sonra bunu kontrol eder ve **eksikse `claude`'u hiç
başlatmaz** — para harcamadan, yarım iş üretmeden durur.

**Çözüm.**

```bash
cp .env.example .env      # yoksa
# .env içinde ilgili satırı doldur, sonra:
python3 bin/ayar.py       # son satır ".env: var" demeli
python3 bin/kos.py youtube-analiz --kuru   # "gerekli anahtarlar:" satırına bak
```

Dikkat: `ayar.ortam_yukle()` **`.env`'i kabuğun üzerine yazar; `.env` her zaman kabuğu ezer** —
proje dosyası kazanır.
Kabuğunuzda eski bir `APIFY_TOKEN` olsa bile koşu `.env`'deki değeri kullanır; dosyaya ne
yazdıysanız onu görürsünüz. Tersi de geçerli: `.env`'de satırı silmek kabuktaki eski değeri
geri getirir — anahtarı gerçekten kaldırmak istiyorsanız `unset APIFY_TOKEN` de deyin.

---

## Stop hook ateşlenmiyor (koşuda `## Bekçi` yok)

**Belirti.** Koşu kaydının sonunda `## Bekçi` başlığı yok; akşam raporunun **Dikkat**
bölümünde `🟡 <takim> <saat> — bekçi kararı kayda düşmemiş`.

**Sebep.** Üç ihtimal:
1. `.claude/settings.json` bozuk ya da `Stop` hook'u yok.
2. Koşu `kos.py` üzerinden başlatılmadı — hook `SIRKET_TAKIM` ortam değişkeni yoksa
   **bilerek hiçbir şey yapmaz** ve 0 döner (repoda elle açtığınız `claude` oturumuna karışmaz).
3. Hook 180 saniyelik `timeout` içinde bitmedi.

**Çözüm.** Önce ayarı doğrulayın — tek hook olmalı ve `bekci.py`'yi çağırmalı:

```bash
cat .claude/settings.json
python3 -m unittest tests.test_kit.BelgeTutarliligiTesti.test_stop_hook_bekciyi_cagiriyor
```

Sonra bekçiyi elle koşturun:

```bash
python3 bin/bekci.py --dogrudan x-icerik
```

Not: hook hiç çalışmasa bile denetim atlanmaz — `kos.py` koşu kaydında `## Bekçi` başlığını
göremezse `bekci.denetle()`'yi kendisi çağırır. "Bekçi kararı kayda düşmemiş" uyarısı
pratikte yalnız `kos.py` dışında başlatılan oturumlarda çıkar.

---

## Bekçi kararı "atlandi"

**Belirti.** `durum.json` → `bekci.son_karar: "atlandi"`; gerekçe şunlardan biri:
`bekçi ulaşılamadı: URLError` · `bekçi yanıtı çözümlenemedi` · `yedek bekçi ulaşılamadı:
TimeoutExpired` · `yedek bekçi JSON döndürmedi`. Akşam raporunda:
`🟡 <takim> — bekçi denetleyemedi: …`

**Sebep.** `atlandi` **"kabul" değildir** — denetim yapılamadı demektir. `OPENAI_API_KEY` geçersizse
(401/403) ya da OpenAI'a ulaşılamıyorsa bekçi **kendiliğinden Haiku yedeğine düşer** ve gerekçeye
`openai 401 → haiku yedeği` yazar; yani bu durumda karar `atlandi` kalmaz. Geriye kalan sebepler:
OpenAI 60 sn zaman aşımı, yedek yolda `claude` bulunamadı ya da 150 sn'de bitmedi, yahut model
şemaya uymayan bir yanıt döndürdü.

**Çözüm.** Elle tekrar denetleyin ve gerekçeyi okuyun:

```bash
python3 bin/bekci.py --dogrudan x-icerik takimlar/x-icerik/kosu/2026-09-11-1716.md
```

- `OPENAI_API_KEY` varsa doğruluğunu sınayın; farklı bir model denemek için
  `BEKCI_MODEL` ortam değişkeni (varsayılan `gpt-5-mini`).
- Anahtar yoksa **ya da geçersizse** yedek yol `claude -p --model haiku`'dur; `claude` PATH'te mi bakın.
- Karar `atlandi` kaldığı sürece o koşunun çıktısı **denetlenmemiştir**; kabul edilmiş gibi
  davranmayın.

---

## Telegram chat id'yi bulamıyorum

**Belirti.** `TELEGRAM_CHAT_ID yok (.env) — önce: python3 bin/telegram_oku.py --chat-id-bul`
ya da `TELEGRAM_CHAT_ID sayı değil (.env)`.

**Sebep.** Dinleyici yalnızca **sizin** chat id'nizden gelen mesajları işler; bot'a başkası
yazarsa görmezden gelinir. O yüzden id zorunludur ve tam sayı olmalıdır.

**Çözüm.**

```bash
# 1) @BotFather ile bot aç, token'ı .env → TELEGRAM_BOT_TOKEN
# 2) Bota Telegram'dan bir mesaj at (herhangi bir şey)
python3 bin/telegram_oku.py --chat-id-bul
# {"chat_idleri": [123456789]}
# 3) Çıkan sayıyı .env → TELEGRAM_CHAT_ID satırına yaz (tırnaksız, yalnız rakam)
```

`--chat-id-bul` offset'i **ilerletmez**, o yüzden istediğiniz kadar çalıştırabilirsiniz.
Boş liste dönüyorsa komut bunu kendisi söyler ("bota bir mesaj at, sonra tekrar koş"): bota hiç
mesaj atılmamış ya da mesajlar daha önce `--isle` ile onaylanmış demektir.

**Token geçersizse** komut artık sessiz kalmaz. Çıkış kodları:

| Kod | Anlamı |
|---|---|
| 0 | tamam |
| 1 | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` yok (`.env`) |
| 2 | `telegram: token geçersiz (401)` — @BotFather'daki değerle karşılaştırın |
| 3 | `telegram: ulaşılamadı` — ağ ya da Telegram sunucusu |

`telegram_dinle.py` bu hatalarda **ölmez**: turu atlar, `sirket-log/telegram-dinle.log`'a yazar,
bir sonraki turda tekrar dener.

---

## `tweet_cek.py` "cekilemedi" diyor

**Belirti.** `python3 bin/tweet_cek.py <link>` çıktısında `"kaynak": "cekilemedi"` ya da
`"kaynak": "x-linki-degil"`; `makale` alanı `null`.

**Sebep.** Üç ayrı durum:
- `x-linki-degil` — link `x.com/<hesap>/status/<id>` (veya `twitter.com/…`) desenine uymuyor.
- `cekilemedi` — fxtwitter aynası ulaşılamadı, zaman aşımına uğradı ya da `code != 200` döndü.
- `makale: null` — tweet var ama **X Article gövdesini ayna çoğu zaman vermez.** Elde yalnızca
  özet metin kalır.

**Çözüm.** Hiçbirinde tarayıcı açılmaz, metin uydurulmaz — bu kuralın kendisidir:

- `cekilemedi` ise doğrulama tablosu "metin çekilemedi" notuyla **⛔ ağırlıklı** yazılır
  (`takim.md` adım 2).
- `makale: null` ise koşu kaydına yazılır ve yazının tamamı varmış gibi özetlenmez
  (`bin/prompt-x-icerik.md`).
- Kaynağın kimliğinden şüphe varsa ya da elde yalnızca ekran görüntüsü varsa
  `skills/kaynak-kimlik-dogrulama/SKILL.md` devreye girer.

Ayna geçici olarak düşmüş olabilir; birkaç dakika sonra tekrar deneyin. `tweet_cek.py`
giriş yapmaz, tarayıcı kullanmaz — hesap riski yoktur.

---

## Apify maliyeti

**Belirti.** `youtube_analiz_cek.py` çıktısındaki `maliyet_usd` beklenenden yüksek, ya da
`{"hata": "HTTP 402"}` benzeri bir yanıt.

**Sebep.** Apify aktörleri **PAY_PER_EVENT** ile ücretlendirilir: her çağrı para harcar.
`bin/apify_cek.py`'nin dosya başındaki uyarısı budur. `youtube_analiz_cek.py` varsayılan olarak
en fazla 50 video (`AZAMI_VIDEO`) ve video başına 50 yorum (`--yorum 50`) ister; ayrıca yorum
aktörü nadiren boş döndüğü için **bir kez daha denenir** (`_video_yorumlari`) — yani kötü
durumda yorum çağrısı iki katına çıkabilir.

**Çözüm.**

```bash
# Önce küçük dene:
python3 bin/apify_cek.py apidojo/youtube-scraper '{"youtubeHandles":["@ornek-kanal"]}' --max 5
python3 bin/youtube_analiz_cek.py --son-7g --yorum 10 --azami-video 10
```

- `veri/YYYY-Www.json` tazeyse **yeniden çekmeyin** — `takim.md` adım 1 bunu zaten emreder.
  Aynı haftanın maddesi kuyruğa ikinci kez yazılmadığı için haftada bir çekim beklenir.
- Harcamayı doğrulamak için: her çekimin sonunda `maliyet_usd` alanı yazılır
  (`apify_cek.maliyet_topla`, o koşu sırasında başlayan Apify koşularının toplamı).
- Senkron uç nokta 300 saniyeyle sınırlıdır (`SENKRON_TAVAN_SN`); daha uzun işler için gereken
  async koş+yokla yolu bu kitte yoktur.
- Apify hesabınızda harcama limiti tanımlayın.

---

## `FAL_KEY` yok — kapak ne olacak

**Belirti.** `python3 bin/kapak_uret.py …` → çıkış kodu **2** ve
`kapak üretilmedi: FAL_KEY yok — pakete 'kapak: sen ekleyeceksin' notu düş`.
Ya da çıkış kodu **1** ve `kapak üretilemedi — pakete 'kapak: sen ekleyeceksin' notu düş`.

**Sebep.** `FAL_KEY` boş (kod 2) ya da üretim başarısız oldu (kod 1): fal işi `FAILED` döndü,
240 saniyede bitmedi, ya da PIL kurulu değil (`kapak: PIL yok (pip install pillow)`).

**Çözüm.** Bu **koşuyu düşürmeyen** bir durumdur, tasarım böyledir. `twitter-icerik` takımının
adım 4'ü açıkça söyler: çıkış kodu 2 ise pakete `kapak: sen ekleyeceksin` notunu yaz ve devam et.
Çıktı sözleşmesi de buna göredir: *"`kapak.png` 3840×736 **ya da** pakette 'kapak: sen
ekleyeceksin' notu — ikisinden biri mutlaka."*

Kapağı gerçekten üretmek isterseniz: `.env` → `FAL_KEY` (fal.ai → Keys) ve
`pip install pillow`. Başlık fal tarafından değil **yerelde PIL ile** basılır; gerekçesi
dosyanın başında yazar: üretken modeller Türkçe metni ve noktalama işaretlerini bozuyor.

---

## launchd tetiği yüklenmedi

**Belirti.** `python3 bin/zamanla.py --durum` →
`sabah  her gün 09:00  · plist var, yüklü değil` ya da `· kurulu değil`.
`--kur` çıktısında `yüklenemedi: <mesaj>`.

**Sebep.** `launchctl bootstrap gui/<uid> <plist>` başarısız oldu: plist zaten yüklü, izin
sorunu, ya da `launchctl` çağrılamadı (`launchctl çağrılamadı: FileNotFoundError` — macOS
dışındasınız).

Etiket **köke bağlıdır**: `com.a-sirketi.<klasor>-<hash6>.<tetik>`. İki klon aynı kaydı ele
geçirmez; `--durum` plist'in çalıştırdığı betiğin bu köke ait olduğunu doğrular ve değilse
`· başka kök için yüklü: <yol>` der. Eski sürümün köksüz `com.a-sirketi.sabah` /
`com.a-sirketi.aksam` etiketi hâlâ yüklüyse `--durum` bunu `⚠ eski etiket … — --kur ile yenile`
satırıyla bildirir. `--kur` yeni etiketi kurar, eskiyi **kaldırmaz** (başka bir kökün tetiği
olabilir); çift tetik istemiyorsanız elle indirin:
`launchctl bootout gui/$(id -u)/com.a-sirketi.sabah`.

**Çözüm.**

```bash
python3 bin/zamanla.py --kuru     # plist'i gör, hiçbir şeye dokunma
python3 bin/zamanla.py --kaldir   # varsa indir
python3 bin/zamanla.py --kur      # yeniden yükle (kur zaten önce bootout dener)
python3 bin/zamanla.py --durum    # "✓ yüklü" mü
```

Sık tuzak: **launchd'nin PATH'i dardır ve `claude`'u bulamaz.** `zamanla.py` bunu
`shutil.which("claude")` ile çözüp plist'e `EnvironmentVariables.PATH` yazar — ama plist'i
`claude` kurulu **olmayan** bir kabuktan ürettiyseniz o dizin listeye girmez. `which claude`
çalıştığı bir kabuktan `--kur` yapın. Hata ayıklamak için `sirket-log/zamanlayici.log`.

macOS dışındaysanız `zamanla.py` kullanılmaz; cron ya da systemd karşılığı
[02-dongu.md](02-dongu.md)'nin sonundadır.

---

## `.env` yanlışlıkla git'e girdiyse

**Belirti.** `git log --all -- .env` bir şey döndürüyor, ya da `git status`'ta `.env` izleniyor
görünüyor.

**Sebep.** `.gitignore`'un ilk satırı `.env`'dir, ama dosya **daha önce** izlemeye alınmışsa
`.gitignore` onu geri çıkarmaz.

**Çözüm — sırayla, ilk adım en önemlisi:**

1. **Anahtarları döndürün.** Git geçmişinden silmek yetmez; repo public'se anahtarlar
   çoktan okunmuş sayılır. Telegram: @BotFather → `/revoke` ve yeni token.
   Apify / fal / OpenAI: panelden anahtarı silin, yenisini üretin.
2. İzlemeden çıkarın: `git rm --cached .env` → commit.
3. Geçmişten temizleyin (`git filter-repo` ya da BFG) ve zorla push edin — ortak çalışılan
   bir repoda önce herkese haber verin.
4. Doğrulayın: `python3 -m unittest tests.test_kit.BelgeTutarliligiTesti` —
   `test_repoda_sizmis_anahtar_yok` repoda anahtara benzeyen metin arar,
   `test_env_orneginde_gercek_deger_yok` `.env.example`'ın boş olduğunu denetler.

Aynı korumanın koşu tarafındaki karşılığı bekçinin ön kontrolüdür: koşu kaydında anahtar ya da
e-posta deseni görürse LLM'e hiç sormadan **red** verir ([03-bekci.md](03-bekci.md)).

---

## `claude: command not found` / "claude başlatılamadı"

**Belirti.** Koşu kaydında `claude başlatılamadı: FileNotFoundError`, maliyet 0, tur 0,
`son_sonuc: "hata"`. Ya da bekçi `yedek bekçi ulaşılamadı: FileNotFoundError`.

**Sebep.** `claude` çalıştırılabilir dosyası PATH'te yok. `kos.py` `subprocess.run` ile onu
doğrudan çağırır; `OSError` yakalanır, istisna fırlamaz — koşu sessizce hataya döner.
En sık görüldüğü yer **launchd/cron ile başlatılan** koşulardır, çünkü oraların PATH'i dardır.

**Çözüm.**

```bash
which claude          # boşsa Claude Code kurulu değil ya da PATH'te değil
python3 bin/zamanla.py --kur   # plist'e doğru PATH'i yeniden yazar
```

cron kullanıyorsanız crontab'ın başına `PATH=` satırı ekleyin. Kuru koşu (`--kuru`) `claude`
çağırmadığı için bu hatayı **göstermez** — gerçek koşuyla sınayın.

---

## `--zorla` ne yapar, ne yapmaz

**Yapar:** yalnızca **mesai kontrolünü** atlar.

```bash
python3 bin/kos.py x-icerik --zorla
```

**Yapmaz:** bütçeyi, süre tavanını, anahtar kontrolünü, bekçiyi ve repo kilidini atlamaz.
Günlük koşu tavanı ile günlük USD tavanı **dağıtıcının** kararıdır (`tetik_karari`);
`kos.py` doğrudan çağrıldığında o kontroller zaten çalışmaz — yani `--zorla` ile elle koşmak
günlük tavanı da fiilen aşabilir. Tavanları tutan şey dağıtıcıdır; elle tetik insanın
sorumluluğundadır.

Yanındaki bayrak: `--kuru` hiçbir şeye dokunmaz, `claude` çağırmaz, kilide bile girmez —
istemi ve ayarları görmek için güvenli yol. İkisi birlikte verilirse `--kuru` kazanır.

---

## Hangi log nerede

| Dosya | İçinde ne var |
|---|---|
| `takimlar/<takim>/kosu/YYYY-MM-DD-HHMM.md` | Koşu kaydı: ajanın yazdığı gövde + `## Bekçi` + altbilgi (maliyet/tur/hata) |
| `takimlar/<takim>/durum.json` | Kuyruk, `son_kosu`, `son_sonuc`, bekçi kararı, sayaçlar |
| `takimlar/bekci-telemetri.jsonl` | Her bekçi kararı, satır başına bir JSON |
| `sirket-log/dagitici.log` | Dağıtıcının başlattığı/sıraya aldığı takımlar |
| `sirket-log/<takim>-tetik.log` | Dağıtıcının arka planda başlattığı koşunun stdout/stderr'i |
| `sirket-log/telegram-dinle.log` | Dinleyici turları (token maskeli) |
| `sirket-log/zamanlayici.log` | launchd tetiklerinin çıktısı |
| `sirket-log/rapor/YYYY-MM-DD-{sabah,aksam}.md` | Günlük raporlar |

Hepsi `.gitignore`'dadır — dışarı hiçbir şey gitmez.

---

## Sırada

- Örnek bir koşu kaydı ve bölümleri: [ornek-kosu/README.md](ornek-kosu/README.md)
- Mimari: [01-nasil-calisir.md](01-nasil-calisir.md)

# KURULUM — sıfırdan altı adım

Repoyu klonluyorsun: betikler, yetenekler, üç takım ve Stop hook ayarı zaten yerinde. Yapacağın şey
anahtarları koymak, iskeleti tanımak ve döngüyü bir kez kendi gözünle kapatmak.

**Gerekenler**

- `python3` (3.9+) — betiklerin tamamı standart kütüphane, `pip install` yok
- [Claude Code](https://claude.com/claude-code) CLI: `claude` komutu PATH'te olmalı — koşuları o çalıştırır
- `gh` (GitHub CLI) — yalnızca kendi kopyanı GitHub'a açacaksan gerekir
- macOS — `bin/zamanla.py` launchd kullanır (adım 6). Diğer adımlar Linux'ta da çalışır;
  Windows'ta WSL gerekir (`bin/kos.py` koşu kilidini POSIX `fcntl` ile kurar).

---

## Adım 1 · Klon ve anahtarlar

```bash
git clone https://github.com/selmakcby/a-sirketi.git
cd a-sirketi
cp .env.example .env
head -1 .gitignore     # ".env" — anahtar dosyası hiçbir zaman commit'e girmez
```

`.env`'i kendi editöründe aç ve doldur. Sekiz anahtarın hiçbiri zorunlu değil ama boş kalan her
anahtar bir takımı kapatır:

| Anahtar | Nereden alınır | Boşsa |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram'da @BotFather → `/newbot` | `x-icerik` koşmaz |
| `TELEGRAM_CHAT_ID` | aşağıdaki `--chat-id-bul` | `x-icerik` koşmaz |
| `APIFY_TOKEN` | apify.com → Settings → API tokens | `youtube-analiz` koşmaz |
| `FAL_KEY` | fal.ai → Keys | paket "kapak: sen ekleyeceksin" notuyla çıkar |
| `OPENAI_API_KEY` | platform.openai.com | **yoksa ya da geçersizse** bekçi Haiku'ya düşer, kararına "bekçi aynı aileden — uyarı" notu eklenir |
| `KANAL` | izlemek istediğin YouTube kanalı (`@kanal`) | `@ornek-kanal` varsayılır |
| `NVIDIA_API_KEY` | build.nvidia.com → model kartı → Get API Key | hiçbir şey değişmez; her takım Anthropic'te koşar ([docs/07](docs/07-farkli-model.md)) |
| `NIM_MODEL` | koşacak NIM modeli, tool-use desteklemeli | `takim.md`'deki `model:` satırı kullanılır; o da yoksa `saglayici: nim` koşusu atlanır |

**Telegram botu 30 saniyede:** @BotFather → `/newbot` → bota bir ad ver → verdiği token'ı
`TELEGRAM_BOT_TOKEN`'a yaz. Sonra kendi botuna herhangi bir mesaj at ve:

```bash
python3 bin/telegram_oku.py --chat-id-bul
```

Çıkan sayıyı `TELEGRAM_CHAT_ID`'ye yaz. Bu filtre olmadan bota yazan herkesin mesajı işlenirdi;
bu yüzden yalnız o chat id'den gelen mesajlar okunur.

`APIFY_TOKEN`, `FAL_KEY` ve `OPENAI_API_KEY` opsiyoneldir — üçü boşken de döngü döner.

> **`.env` her zaman kabuğu ezer.** Kabuğunda aynı adla eski bir değer duruyorsa bile koşu
> `.env`'deki değeri kullanır — dosyaya ne yazdıysan onu görürsün (`bin/ayar.py` → `ortam_yukle`).

---

## Adım 2 · Ayakta mı

```bash
python3 bin/ayar.py
python3 -m unittest discover -s tests
```

Birinci komut şirketin bütün sayılarını tek satırda basar: mesai penceresi, koşu başına para ve süre
tavanı, takım başına günlük koşu sayısı, şirketin günlük tavanı, izlenen kanal ve `.env` var mı.
Bu sayılar tek yerdedir — `bin/ayar.py`. Değiştirmek istersen orayı değiştirirsin, ikinci bir kopya yok.

İkinci komut reponun kendi testleridir: ajan dosyaları `takim.md` ile tutarlı mı, yetenek bağları
kopuk mu, `.gitignore` `.env`'i kapsıyor mu, Stop hook bekçiyi çağırıyor mu, repoda anahtara benzeyen
bir metin var mı. Hepsi geçmeden devam etme.

---

## Adım 3 · ANAYASA

```bash
cat ANAYASA.md
```

Beş madde: yayın düğmesi insanın · kaynaksız sayı yok · bekçi ayrı kafa · her koşunun tavanı var ·
defter ajanın, kural insanın. Bu dosya **insanındır**: ajan okur, değiştiremez — `.claude/agents/`
önsözü her koşuda onu ilk sıraya koyar.

Kendi şirketini kuruyorsan maddeleri kendin yazarsın. Buradaki hâli, kelimesi kelimesine dikte
edilen prompt'la üretildi: [prompts/P03-anayasa.md](prompts/P03-anayasa.md).

---

## Adım 4 · Takımları tanı, ajan dosyalarını üret

Üç takım hazır gelir:

```bash
ls takimlar/*/
sed -n '1,10p' takimlar/x-icerik/takim.md      # frontmatter: meslek, model, araçlar, anahtarlar, yetenekler, bütçe
```

Her takımda dört dosya var: `takim.md` (koşu adımları ve çıktı sözleşmesi), `kurallar.md` (sınırlar),
`defter.md` (ajanın dersleri), `durum.json` (kuyruk ve son sonuç). `takim.md` **tek kaynaktır**;
Claude Code'un okuduğu `.claude/agents/<takim>.md` ondan üretilir:

```bash
python3 bin/agents_uret.py            # .claude/agents/<takim>.md yazılır
head -8 .claude/agents/x-icerik.md    # ilk satır ajanın kimliğidir
python3 bin/agents_uret.py --check    # takim.md değişip üretim unutulmuşsa 1 döner
```

İlk satır şudur: **"Sen `x-icerik` ajanısın. A Şirketi'nde bir çalışansın ve bir yapay zekâ ajanısın.
Mesleğin: …"** — ardından okuma sırası (`ANAYASA.md` → `sirket/AJAN-KIMLIGI.md` →
`takimlar/x-icerik/kurallar.md`) ve yetenek satırı gelir. `skills:` alanı agent frontmatter'ına
sızmaz; önsözdeki tek satıra dönüşür.

Kendi takımını açmak istersen:

```bash
python3 bin/agents_uret.py            # takim.md'yi her değiştirdiğinde koş
bin/takim-olustur.sh <yeni-takim>     # iskeletten dört dosya
```

> Yeni takım `skills: []` ile gelir. **`takim.md`'de `skills:` alanını doldur (en az bir
> yetenek), yoksa testler kırmızı** — `tests/test_skills.py` her takımdan en az bir yetenek
> bekler. Sonra `python3 bin/agents_uret.py` koş.

Sonra `takim.md`'nin içini doldurursun. Bu üç dosya Claude Code'a yazdırıldı; kullanılan prompt'lar
[prompts/P05a-x-icerik-takim.md](prompts/P05a-x-icerik-takim.md),
[P05b](prompts/P05b-youtube-analiz-takim.md), [P05c](prompts/P05c-twitter-icerik-takim.md)
dosyalarında — kendi takımın için şablon olarak kullanabilirsin.

---

## Adım 5 · Döngüyü kapat

Önce kuru koşu: `claude` çağrılmaz, hiçbir dosyaya yazılmaz.

```bash
cat .claude/settings.json              # Stop → bin/bekci.py
python3 bin/kos.py x-icerik --kuru
```

Çıktı modeli, bütçeyi, araçları, yetenekleri, koşu kaydının yazılacağı yolu ve kurulan istemi basar.
En önemlisi **kimlik satırı** — ajanın koşuda gördüğü ilk cümle:

```
  yetenekler: kaynak-dogrulama, iddia-ayristirma-ve-kanit-defteri, kaynak-kimlik-dogrulama
  kimlik (istemin ilk satırı): Sen `x-icerik` ajanısın. A Şirketi'nde bir çalışansın ve bir
  yapay zekâ ajanısın. Mesleğin: X içerik takımı — …
```

Sonra gerçeği:

```bash
# 1) Telefonundan bota bir X linki at (yanına bir de not yazabilirsin)
python3 bin/telegram_oku.py --son 5     # mesajı gördün mü (durum değişmez)
python3 bin/telegram_oku.py --isle      # link → takimlar/x-icerik/gelen/*.json
python3 bin/kos.py x-icerik             # ajan koşar, bekçi Stop hook'ta denetler
tail -20 takimlar/x-icerik/kosu/*.md    # en altta "## Bekçi — karar: kabul/red"
python3 bin/dagitici.py --kuru          # zinciri göster: x-<id> → twitter-icerik/aci-<id>
python3 bin/dagitici.py                 # zinciri kur ve twitter-icerik'i koştur
```

Koşu birkaç dakika sürer. Bekçi red verirse ajan **aynı oturumda** düzeltmeye gider (en fazla iki
kez), sonra kayıt kapanır; kararın tamamı koşu kaydının altındadır ve `durum.json` → `bekci` alanına
düşer. İkinci kez `--isle` çalıştırmak boş döner — hata değil, Telegram aynı güncellemeyi ikinci kez
vermez.

Sonunda `takimlar/twitter-icerik/cikti/<tarih>-<slug>/article.html` durur. Hiçbir yere yayınlanmaz:
tarayıcıda açar, okursun, yayın kararını sen verirsin.

Gerçek bir koşunun kaydı ve çıktısı: [docs/ornek-kosu/](docs/ornek-kosu/).

---

## Adım 6 · Sürekli çalıştır

İki parça var: olay tetiği ve saatli tetik.

```bash
python3 bin/telegram_dinle.py --bir-kez     # tek tur — önce bunu dene
python3 bin/telegram_dinle.py               # sonsuz long-poll: mesaj düştüğü an x-icerik koşar
```

Dinleyici açıkken bota link attığın an koşu başlar; `--isle` yazmana gerek kalmaz. Mesai dışında
gelen mesaj `gelen/` altına yazılır ve kuyruğa `bekliyor` düşer, koşu sabaha kalır.

Saatli tetik sabah dağıtıcıyı koşturur, akşam günü denetler:

```bash
python3 bin/gunluk.py --sabah --kuru        # hiçbir takımı başlatmadan sabah raporunu ekrana bas
python3 bin/zamanla.py --kuru               # kurulacak launchd plist'lerini göster
python3 bin/zamanla.py --kur                # tetikleri yükle
python3 bin/zamanla.py --durum              # yüklü mü, ne zaman koşacak
```

Raporlar `sirket-log/rapor/YYYY-MM-DD-{sabah,aksam}.md` altına yazılır ve dışarı hiçbir şey gitmez.
Bu adımı Claude Code'a yaptırmak istersen: [prompts/P11-surekli-calistir.md](prompts/P11-surekli-calistir.md).
Bilgisayar o saatte kapalıysa launchd kaçan işi açılışta koşturur. Kaldırmak: `python3 bin/zamanla.py --kaldir`.

Ajanı Anthropic yerine NVIDIA'nın bedava modellerinden biriyle koşturmak istersen (iki satır, geri dönüşü tek satır): [docs/07-farkli-model.md](docs/07-farkli-model.md) · prompt hâli [prompts/P12-farkli-model.md](prompts/P12-farkli-model.md).

Kendi kopyanı GitHub'a açacaksan, önce `.env` sızmadığından emin ol:

```bash
git status                          # .env LİSTEDE OLMAMALI
git restore takimlar/*/durum.json   # gerçek koşular durum.json'a yazar; kuyruğunu paylaşmak istemiyorsan geri al
gh repo create <ad> --public --source=. --push
```

Kuru koşular (`--kuru`) hiçbir dosyaya dokunmaz; `durum.json`'u kirleten şey gerçek koşulardır
(`bin/kos.py <takim>`, `bin/telegram_oku.py --isle`, `bin/dagitici.py`).

---

## Sıfırdan kendin kurmak istersen

Bu repo hazır alınmak zorunda değil: boş bir klasörde, Claude Code'a sırayla 15 prompt vererek
aynı şirket sıfırdan kurulur — `CLAUDE.md`, `ANAYASA.md`, üç `takim.md`, ajan dosyaları, kuru koşu,
gerçek koşu, dağıtıcı, GitHub, sürekli çalıştırma. Prompt'ların tamamı, olduğu gibi
kopyalayıp yapıştırılacak hâlde:

**[prompts/](prompts/)** — sıra tablosu, her prompt ayrı dosyada, beklenen çıktısı ve dikkat notuyla.

Repoyu klonladıysan kopyalama adımları (P1, P2) sana gerekmez: o dosyalar zaten yerinde. Geri kalan
prompt'ları kendi klasöründe, kendi anayasan ve kendi takımlarınla tekrarlayabilirsin.

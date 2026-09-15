![A Şirketi](docs/kapak.png)

# A Şirketi

Üç Claude Code ajanı, bir bekçi, bir dağıtıcı — kapalı bir döngü. Telefonundan bota bir link atarsın;
bir ajan iddiaları kaynağına kadar doğrular, zincir devralır, yayına hazır bir paket çıkar ve orada durur:
**yayın düğmesi insanda.**

Bu bir iskelettir, bir ürün değil. Klonla, `.env`'i doldur, kendi takımlarını yaz.

![Üç ajan ve bekçi](docs/4-ajan.png)

## Üç takım

| Takım | Anahtar | Akan şey |
|---|---|---|
| **x-icerik** | `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` | Telegram'a attığın X linki → `gelen/*.json` → her iddia ✅/🟡/⛔ etiketli doğrulama tablosu + "yazıya değer mi" kararı (`cikti/YYYY-MM-DD-<update_id>-<hesap>.md`) |
| **youtube-analiz** | `APIFY_TOKEN` · `KANAL` | Apify aktörleri → `veri/YYYY-Www.json` → yalnız o dosyadaki sayılarla kaynaklı haftalık rapor (`cikti/YYYY-Www-rapor.md`) |
| **twitter-icerik** | — (`FAL_KEY` varsa kapak) | Dağıtıcının düşürdüğü `aci-<id>` maddesi → X Article paketi: `article.md`, `article.html`, `kapak.png` (`cikti/<tarih>-<slug>/`) |

Her takım `takimlar/<takim>/` altında aynı dört dosyayla yaşar: `takim.md` (kim ve ne yapar),
`kurallar.md` (neye göre), `defter.md` (ne öğrendi), `durum.json` (nerede). Her ajan koşuya aynı
sırayla başlar: `ANAYASA.md` → `sirket/AJAN-KIMLIGI.md` → `takimlar/<takim>/kurallar.md` →
`takim.md` → yetenekleri (`skills/<ad>/SKILL.md`).

## Döngü

```
   sen                                bin/telegram_dinle.py
  Telegram'a X linki  ───────────────►  (long-poll; mesaj düştüğü an)
                                                  │
                                       gelen/*.json + kuyruk: x-<update_id>
                                                  │  mesai içiyse hemen koştur
                                                  │  (dışındaysa sabah dağıtıcı alır)
                                      ┌───────────▼───────────┐
                                      │  bin/kos.py x-icerik  │
                                      │  claude -p (sonnet)   │
                                      │  tweet_cek + arama    │
                                      │  ✅/🟡/⛔ tablosu      │
                                      └───────────┬───────────┘
                                                  │ Stop hook
                                      ┌───────────▼───────────┐
                                      │  bin/bekci.py         │
                                      │  ön kontrol (LLM yok) │
                                      │  + ayrı kafa denetimi │
                                      └─────┬───────────┬─────┘
                                       red  │           │ kabul
                                   düzeltmeye           │
                                    (en fazla 2)        ▼
                                                  durum.json
                                             kuyruk: x-<id> tamam
                                                        │
                                          bin/dagitici.py — zincir
                                                        │
                            twitter-icerik kuyruğu: aci-<id> bekliyor
                                                        │
                    tavanlar: mesai 09:00-23:00 · koşu 2 USD / 15 dk ·
                    takım günde 4 koşu · şirket günde 10 USD (bin/ayar.py)
                                                        │
                                      bin/kos.py twitter-icerik
                                                        │
                                    cikti/<tarih>-<slug>/article.html
                                                        │
                                                       sen
                                                 (yayın düğmesi)
```

`youtube-analiz` aynı iskelette ayrı kulvarda döner: pazartesi sabahı `bin/gunluk.py --sabah`
kuyruğa `yt-<hafta>` maddesini düşürür → Apify → `veri/*.json` → kaynaklı rapor.

## Kurulum — 6 adım

Komut komut ayrıntılı hâli: **[KURULUM.md](KURULUM.md)**

1. `git clone … && cd a-sirketi` · `cp .env.example .env` — anahtarları doldur (aşağıdaki tablo)
2. `python3 bin/ayar.py` ve `python3 -m unittest discover -s tests` — iskelet ayakta mı
3. `ANAYASA.md`'yi oku — beş madde, şirketin değişmez çerçevesi; istersen kendi maddelerini yaz
4. Takımları tanı (`takimlar/*/takim.md`), sonra `python3 bin/agents_uret.py` ile
   `.claude/agents/<takim>.md` dosyalarını üret
5. Döngüyü kapat: `kos.py x-icerik --kuru` → Telegram'a link → `telegram_oku.py --isle` →
   `kos.py x-icerik` → `dagitici.py`
6. Sürekli çalıştır: `bin/telegram_dinle.py` (olay tetiği) + `bin/zamanla.py --kur` (sabah/akşam)

## Anahtarlar (`.env`)

`.env.example`'ı kopyalayıp doldurursun; `.env` `.gitignore`'un ilk satırındadır, git'e girmez.

| Anahtar | Ne için | Yoksa ne olur |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot gelen kutusu (@BotFather) | `x-icerik` koşmaz, "eksik anahtar" der |
| `TELEGRAM_CHAT_ID` | Yalnızca senin mesajların işlensin | aynı |
| `APIFY_TOKEN` | YouTube videoları + yorumları | `youtube-analiz` koşmaz |
| `FAL_KEY` | 3840×736 kapak görseli | pakete "kapak: sen ekleyeceksin" notu düşer, koşu devam eder |
| `OPENAI_API_KEY` | Bekçi — ayrı model ailesi (ANAYASA §3) | yedek yol `claude -p --model haiku`; karar "bekçi aynı aileden — uyarı" notuyla kaydedilir |
| `KANAL` | İzlenecek YouTube kanalı | `@ornek-kanal` varsayılır |
| `NVIDIA_API_KEY` | Ajanı Anthropic yerine NVIDIA'nın bedava modeliyle koşturmak ([docs/07](docs/07-farkli-model.md)) | hiçbir şey değişmez; her takım Anthropic'te koşar |
| `NIM_MODEL` | Koşacak NIM modeli (tool-use desteklemeli) | `takim.md`'deki `model:` satırı kullanılır; o da yoksa `saglayici: nim` koşusu atlanır |

## Komutlar

```bash
python3 bin/ayar.py                          # mesai penceresi, tavanlar, kanal, .env var mı
python3 bin/agents_uret.py [--check]         # takim.md → .claude/agents/<takim>.md (--check: sapma varsa 1)
python3 bin/kos.py <takim>                   # bir takımı bir kez koştur
python3 bin/kos.py <takim> --kuru            # claude çağırmadan akışı ve kurulan istemi bas
python3 bin/kos.py <takim> --zorla           # mesai dışında elle koştur
python3 bin/dagitici.py --kuru               # zinciri ve tetik kararlarını bas, hiçbir şey başlatma
python3 bin/dagitici.py                      # zinciri kur, uygun takımları koştur
python3 bin/bekci.py --dogrudan <takim> [kosu.md]   # hook dışından denetle, kararı JSON bas
python3 bin/telegram_oku.py --chat-id-bul | --son 5 | --isle
python3 bin/telegram_dinle.py [--bir-kez]    # olay tetiği: mesaj düştüğü an x-icerik koşar
python3 bin/gunluk.py --sabah [--kuru] | --aksam    # sabah dağıtıcı + rapor, akşam denetim
python3 bin/zamanla.py --kuru | --kur | --durum | --kaldir   # launchd tetikleri (macOS)
python3 bin/tweet_cek.py <x-linki>
python3 bin/youtube_analiz_cek.py --son-7g --yorum 50
python3 bin/kapak_uret.py "<başlık>" cikti/kapak.png
bin/takim-olustur.sh <yeni-takim>            # iskeletten yeni takım (dört dosya)
python3 -m unittest discover -s tests        # reponun kendi testleri
```

## Neden böyle

- **Ajan kim olduğunu bilir.** Koşu isteminin ve `.claude/agents/<takim>.md` dosyasının ilk satırı
  şudur: "Sen `x-icerik` ajanısın. A Şirketi'nde bir çalışansın ve bir yapay zekâ ajanısın.
  Mesleğin: …" — meslek `takim.md`'deki `description` alanıdır. Gerisini `sirket/AJAN-KIMLIGI.md`
  anlatır: hafızası yok, patron kim, bekçi kim, dağıtıcı ne yapar, neyi asla yapmaz.
- **Yetenek dosyaları.** Bir işin nasıl yapılacağı her koşuda baştan anlatılmaz; `skills/<ad>/SKILL.md`
  bir kez yazılır, ajan **sadece ilgili adımda** okur. Hangi takımın hangi yeteneği var:
  `takim.md` frontmatter'ındaki `skills: [...]` alanı; katalog `sirket/YETENEKLER.md`.
  Her yeteneğin sonunda `## Öğrenilenler` var — ajan koşuda aldığı veriyle kendini geliştirir.
- **Tek iskelet.** Dört dosya her takımda aynı yerde; yeni takım açmak `bin/takim-olustur.sh` ile
  kopyala-yapıştır.
- **Kural dosyada, kodda değil.** Ne yapılacağı `takim.md`'de, neye göre yapılacağı `kurallar.md`'de,
  zincir `bin/dagitici.py`'deki `ZINCIR` tablosunda. Kod yalnızca sürücüdür.
- **Bekçi ayrı süreçte.** Üretenin kendi kendini onaylaması yasak. Denetim Stop hook'ta, ayrı süreçte,
  tercihen ayrı model ailesinde. İlk katman LLM'siz ön kontroldür: koşu kaydında anahtar, token ya da
  e-posta deseni varsa karar doğrudan `red`.
- **Tetik saat değil, olay.** `x-icerik`'i başlatan şey bir zamanlayıcı değil, bota düşen mesaj
  (`bin/telegram_dinle.py`). Saatli tetik yalnız sabah dağıtıcıyı ve akşam denetimi koşturur.
- **Tavan her yerde.** Para, süre, koşu sayısı ve mesai penceresi tek dosyada (`bin/ayar.py`);
  tavana çarpan koşu sessiz ölmez, `durum.json`'a yazar.
- **Yayın insanda.** Şirket taslağa kadar gider, orada durur.

## Belgeler

| Dosya | Ne anlatır |
|---|---|
| [docs/01-nasil-calisir.md](docs/01-nasil-calisir.md) | Mimari: dört dosya, okuma sırası, `bin/kos.py` ne yapar |
| [docs/02-dongu.md](docs/02-dongu.md) | Tetikler, dağıtıcı ve zincir, tavanlar |
| [docs/03-bekci.md](docs/03-bekci.md) | Bekçi: ön kontrol, ayrı kafa, red akışı |
| [docs/04-yetenekler.md](docs/04-yetenekler.md) | `skills/` — ne, neden, nasıl bağlanır |
| [docs/05-yeni-takim.md](docs/05-yeni-takim.md) | Sıfırdan yeni takım açmak |
| [docs/06-sorun-giderme.md](docs/06-sorun-giderme.md) | Sık çıkan hatalar ve okunacak dosya |
| [docs/07-farkli-model.md](docs/07-farkli-model.md) | Ajanı Anthropic yerine NVIDIA'nın bedava modeliyle koşturmak (+ güvenlik notu) |
| [docs/ornek-kosu/](docs/ornek-kosu/) | Gerçek bir koşunun kaydı ve çıktısı |
| [prompts/](prompts/) | Şirketi sıfırdan kurmak için Claude Code'a sırayla verilen prompt'lar (P0–P12) |
| [ANAYASA.md](ANAYASA.md) · [CLAUDE.md](CLAUDE.md) | Beş madde · projenin kimliği |

## Lisans

MIT — bkz. [LICENSE](LICENSE).

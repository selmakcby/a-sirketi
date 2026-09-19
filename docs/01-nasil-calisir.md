# 01 · Nasıl çalışır

A Şirketi üç Claude Code ajanı, bir bekçi ve bir dağıtıcıdan oluşan kapalı bir döngüdür.
Bu belge **mimariyi** anlatır: hangi dosya neyi tutar, bir koşu adım adım ne yapar, sayılar nerede durur.

Döngünün ne zaman ve neyle tetiklendiği [02-dongu.md](02-dongu.md)'de,
denetim [03-bekci.md](03-bekci.md)'de, yetenekler [04-yetenekler.md](04-yetenekler.md)'de.

---

## Klasör yapısı

```
ANAYASA.md                 değişmez çerçeve — insanındır, ajan değiştiremez
CLAUDE.md                  reponun kendi tanıtımı (Claude Code'un kök bağlamı)
sirket/
  AJAN-KIMLIGI.md          "sen kimsin, kim kimdir, sistem nasıl döner"
  YETENEKLER.md            sekiz yeteneğin kataloğu ve kaynakları
bin/                       sürücüler ve araçlar (aşağıda tek tek)
takimlar/
  _iskelet/                yeni takımın kopyalandığı şablon
  x-icerik/                takim.md · kurallar.md · defter.md · durum.json · kosu/ · cikti/ · gelen/
  youtube-analiz/          takim.md · kurallar.md · defter.md · durum.json · kosu/ · cikti/ · veri/
  twitter-icerik/          takim.md · kurallar.md · defter.md · durum.json · kosu/ · cikti/
  bekci-telemetri.jsonl    her bekçi kararı, tek satır JSON
skills/<ad>/SKILL.md       yetenekler — her birinde kaynak ve lisans yazar
.claude/
  settings.json            tek hook: Stop → bin/bekci.py
  agents/<takim>.md        takim.md'den ÜRETİLİR, elle yazılmaz
sirket-log/                dağıtıcı log'u, dinleyici log'u, sabah/akşam raporları — git'e girmez
.env                       anahtarlar — git'e girmez (.env.example kopyalanır)
```

`.gitignore` şunları dışarıda tutar: `.env`, `.kos.lock`, `.kos-*.lock`, `__pycache__/`, `*.pyc`,
`*.jsonl`, `sirket-log/`, `takimlar/*/kosu/`, `takimlar/*/cikti/`,
`takimlar/*/gelen/`, `takimlar/*/veri/`, `.obsidian/`, `*.canvas`, `.DS_Store`.
Yani **koşu kayıtları ve çıktılar public repoya girmez** — örnek olarak elle konmuş bir tanesi
[ornek-kosu/kosu-kaydi.md](ornek-kosu/kosu-kaydi.md) dosyasındadır.

### `bin/` içindekiler

| Dosya | Ne yapar | LLM çağırır mı |
|---|---|---|
| `ayar.py` | Tek ayar dosyası: mesai, tavanlar, `.env` okuma, frontmatter ayrıştırma, `durum.json` okuma/yazma | hayır |
| `kos.py` | Koşu sürücüsü — bir takımı bir kez koşturur | evet (`claude -p`) |
| `bekci.py` | Stop hook denetçisi | evet (OpenAI ya da yedek Haiku) |
| `dagitici.py` | Zinciri kurar, tetik kararını verir, takımı başlatır | hayır |
| `gunluk.py` | Sabah/akşam raporu, haftalık işi kuyruğa düşürür | hayır |
| `zamanla.py` | launchd tetiklerini kurar/kaldırır | hayır |
| `telegram_dinle.py` | Long-poll dinleyici — mesaj düştüğü an ilgili takımı koşturur (`takim_sec`) | hayır |
| `telegram_oku.py` | `getUpdates`, chat id bulma, `gelen/` yazma | hayır |
| `agents_uret.py` | `takim.md` → `.claude/agents/<takim>.md` | hayır |
| `tweet_cek.py` | Bir X linkinin metnini fxtwitter aynasından çeker | hayır |
| `apify_cek.py` | Apify aktör istemcisi (stdlib) | hayır |
| `youtube_analiz_cek.py` | Kanalın videoları + yorumları → `veri/YYYY-Www.json` | hayır |
| `kapak_uret.py` | X Article kapağı 3840×736 (fal zemin + PIL başlık) | hayır (görsel modeli) |
| `takim-olustur.sh` | İskeletten yeni takım açar | hayır |

---

## Bir takım = dört dosya

Her takım `takimlar/<takim>/` altında dört dosyayla tanımlanır. Fazlası yok.

| Dosya | Kimin | Ne tutar |
|---|---|---|
| `takim.md` | insanın | **Kim ve ne.** Frontmatter (model, araçlar, gerekli anahtarlar, yetenekler, bütçe) + koşu adımları + girdi kaynakları + çıktı sözleşmesi. `.claude/agents/<takim>.md` bundan üretilir. |
| `kurallar.md` | insanın | **Sınır.** "Asla yapmaz" maddeleri ve çıktı kalite ölçütleri. Bekçi koşuyu **bu dosyaya göre** denetler. |
| `defter.md` | ajanın | **Ders.** Ajan her koşudan en fazla bir ders yazar; yeni ders üste. Ayrıca "kural önerileri (insana)" bölümü — ajan kuralı kendi değiştirmez, önerir. |
| `durum.json` | ikisinin | **Kuyruk ve durum.** `kuyruk`, `son_kosu`, `son_sonuc`, `bekci`, `defter_son_ders`, `sayaclar`. |

`durum.json`'un iskeleti (`takimlar/_iskelet/durum.json`):

```json
{
  "takim": "TAKIM",
  "son_kosu": null,
  "son_sonuc": null,
  "kuyruk": [],
  "bekci": { "son_karar": null, "red_sayisi_7g": 0 },
  "defter_son_ders": null,
  "sayaclar": {}
}
```

- `kuyruk` — `{"id": …, "durum": …, "not": …}` sözlükleri. Dağıtıcı ve dinleyici `bekliyor` yazar;
  ajan işi bitirince `tamam` (zincire girsin) ya da `bitti` (girmesin) yapar.
- `son_sonuc` — sürücünün yazdığı alan: `tamam` · `red` · `hata` · `atlandi`.
- `bekci` — son karar, gerekçe, 7 günlük red sayısı, zaman damgası. [03-bekci.md](03-bekci.md)
- `sayaclar` — takıma özel sayaçlar. `x-icerik`'te `telegram_son_update` (Telegram offset'i).

Yanlarında dört klasör olur (hepsi `.gitignore`'da): `kosu/` koşu kayıtları, `cikti/` ürün,
`gelen/` Telegram mesajları (yalnız `x-icerik`), `veri/` ham çekim (yalnız `youtube-analiz`).

---

## Okuma sırası

Her ajan her koşuda aynı sırayı izler. Sıra hem `CLAUDE.md`'de hem koşu isteminde hem de
üretilen agent dosyasının önsözünde yazılıdır — üç yerde aynı:

```
1. ANAYASA.md                      değişmez çerçeve (5 madde)
2. sirket/AJAN-KIMLIGI.md          kimsin, kim kimdir, sistem nasıl döner
3. takimlar/<takim>/kurallar.md    takımın sınırları
4. takimlar/<takim>/takim.md       koşu adımları ve çıktı sözleşmesi
5. skills/<ad>/SKILL.md            yalnızca ilgili adımda, yalnızca ilgili yetenek
```

Beşinci adımın "yalnızca ilgili adımda" olması kasıtlıdır: yetenek dosyası koşunun başında
toptan okunmaz, ilgili adıma gelince okunur. Gerekçesi [04-yetenekler.md](04-yetenekler.md)'de.

---

## `kos.py` bir koşuda tam olarak ne yapar

`python3 bin/kos.py <takim> [--kuru] [--zorla]`

```
                        python3 bin/kos.py x-icerik
                                   │
                    ┌──────────────┴──────────────┐
                    │  --kuru mu?                 │ evet → istemi bas, çık
                    └──────────────┬──────────────┘        (kilide bile girmez)
                                   │ hayır
                    ┌──────────────▼──────────────┐
                    │  .kos.lock — fcntl.flock    │  aynı anda iki koşu olmasın
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  takim.md frontmatter       │  yoksa "takım yok", çık
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  mesai 09:00-23:00 mi?      │ hayır → ATLANDI (--zorla atlar)
                    └──────────────┬──────────────┘
                                   │ evet
                    ┌──────────────▼──────────────┐
                    │  agents_uret.uret()         │  .claude/agents/<t>.md tazelenir
                    │  ayar.ortam_yukle()         │  .env → ortam (var olanı ezmez)
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  gerekli_anahtarlar dolu mu │ hayır → ATLANDI: "eksik anahtar: …"
                    └──────────────┬──────────────┘
                                   │ evet
                    ┌──────────────▼──────────────┐
                    │  istem() kurulur            │  ilk satır: "Sen `x-icerik` ajanısın…"
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  claude -p …                │  SIRKET_TAKIM + SIRKET_KOSU ortamda
                    │  --max-budget-usd 2         │  CLAUDECODE ortamdan SİLİNİR
                    │  timeout 900 sn             │  (iç içe koşu engeli)
                    └──────────────┬──────────────┘
                                   │
                                   │  ajan biterken → Stop hook → bekci.py
                                   │
                    ┌──────────────▼──────────────┐
                    │  koşu kaydı yazıldı mı?     │ hayır → dosyayı sürücü açar,
                    └──────────────┬──────────────┘        "Ajan koşu kaydı yazmadı", hata
                                   │
                    ┌──────────────▼──────────────┐
                    │  altbilgi eklenir           │  "- maliyet: … USD · tur: … · hata: …"
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Bekçi koştu mu?            │ hayır → bekci.denetle() doğrudan
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  durum.json: son_kosu,      │  tamam | red | hata | atlandi
                    │              son_sonuc      │
                    └─────────────────────────────┘
```

Adım adım, koddaki sırayla:

1. **Zaman damgası ve frontmatter.** `ayar.simdi_iso()` yerel saat dilimiyle ISO damga üretir;
   `ayar.takim_bilgisi(takim)` `takim.md` frontmatter'ını okur. Takım yoksa çıkar.
2. **Koşu kaydı yolu.** `takimlar/<takim>/kosu/YYYY-MM-DD-HHMM.md`. Dosya adı formatı
   dağıtıcının "bugün kaç koşu oldu" saymasında ve `gunluk.py`'nin rapor okumasında kullanılır.
3. **İstem kurulur** (`istem()`). Tek metin, şu parçalardan: kimlik satırı → tarih ve çalışma dizini →
   okuma sırası → yetenek satırı → defter/kendini geliştirme cümlesi → `<kaynak>` kuralı →
   koşu kaydı sözleşmesi → bütçe/süre → varsa `bin/prompt-<takim>.md` gövdesi.
   İstemin **ilk satırı** her zaman şudur:

   > `Sen \`x-icerik\` ajanısın. A Şirketi'nde bir çalışansın ve bir yapay zekâ ajanısın. Mesleğin: …`

   "Mesleğin" `takim.md`'deki `description` alanıdır (`agents_uret.meslek_metni`).
4. **`--kuru`** verildiyse burada durulur: model, bütçe, süre, araçlar, yazılacak koşu kaydı yolu,
   gerekli anahtarlar, yetenekler, kimlik satırı ve istemin ilk 400 karakteri basılır.
   Mesai dışıysa "gerçek koşu atlanırdı" notu düşer. **Hiçbir dosyaya yazılmaz, `claude` çağrılmaz.**
5. **Mesai kontrolü.** `ayar.mesaide_mi()` → 09:00–23:00 dışındaysa koşu kaydına
   `**Atlandı:** mesai dışı (09:00-23:00); kuyrukta bekler` yazılır, `son_sonuc: "atlandi"` olur.
   `--zorla` bu kontrolü atlar (insanın elle tetiği).
6. **Agents üretimi.** `agents_uret.uret(KOK)` — her `takimlar/*/takim.md` için
   `.claude/agents/<takim>.md` yeniden üretilir. Yani agent dosyası **her koşuda** tek kaynaktan tazelenir.
7. **`.env` yüklenir.** `ayar.ortam_yukle()` — `export` ve tırnak toleranslı, **zaten tanımlı
   değişkeni ezmez** (`os.environ.setdefault`).
8. **Anahtar kontrolü.** `takim.md`'deki `gerekli_anahtarlar` listesindeki her değişken ortamda dolu mu?
   Değilse koşu kaydına `**Atlandı:** eksik anahtar: APIFY_TOKEN` yazılır ve `claude` hiç çağrılmaz.
9. **`claude -p` çağrısı.** Komut:

   ```
   claude -p "<istem>" --output-format json --model <model>
          --max-budget-usd <butce_usd> --allowedTools <tools> --permission-mode acceptEdits
   ```

   - **Ortam:** `CLAUDECODE` değişkeni silinir (iç içe koşu engeli), yerine
     `SIRKET_TAKIM=<takim>` ve `SIRKET_KOSU=<koşu kaydı yolu>` konur. Bekçi bu ikisiyle çalışır.
   - **Süre tavanı:** `subprocess.run(..., timeout=ayar.KOSU_SURESI_SN)` → 15 dakika.
     Aşılırsa `{"hata": True, "metin": "süre tavanı aşıldı"}`.
   - **Bütçe tavanı:** `--max-budget-usd`, varsayılan `ayar.KOSU_BUTCESI_USD` = 2.0 USD;
     `takim.md`'de `butce_usd` varsa o geçerlidir (`twitter-icerik` 3 USD).
   - **Araçlar:** `takim.md`'deki `tools`; yoksa `Read, Write, Glob, Grep`.
   - `claude` başlatılamazsa (`OSError`) hata olarak döner — istisna fırlamaz, çıkış kodu yine 0.
10. **Çözümleme.** `--output-format json` çıktısından `is_error`, `total_cost_usd`, `num_turns`,
    `result` alınır. JSON değilse çıktının son 2000 karakteri hata olarak kaydedilir.
11. **Koşu kaydı garantisi.** Dosya yoksa sürücü açar, başına üstbilgiyi ve
    `**Ajan koşu kaydı yazmadı.**` satırını koyar ve koşuyu hata sayar. Sonra her durumda altbilgi eklenir:

    ```
    ---
    - maliyet: 0.388 USD · tur: 19 · hata: False
    ```

    Bu satırı `dagitici.gunluk_maliyet` ve `gunluk.kosu_oku` okur — günlük bütçe buradan sayılır.
12. **Bekçi.** Stop hook zaten koştuysa kayıtta `## Bekçi` başlığı vardır, tekrar çağrılmaz.
    Yoksa `bekci.denetle()` doğrudan çalıştırılır. Karar `red` ise koşu `red` biter.
13. **`durum.json`.** `son_kosu` ve `son_sonuc` yazılır. Ekrana tek satır:
    `x-icerik: tamam · 0.388 USD · takimlar/x-icerik/kosu/2026-09-11-1716.md`

**Çıkış kodu her zaman 0'dır** (argümansız çağrı hariç: 2, kullanım metni basar).
Sonucu çıkış kodundan değil `durum.json`'daki `son_sonuc`'tan okursunuz.

---

## `agents_uret.py` — tek kaynak `takim.md`

`.claude/agents/<takim>.md` **elle yazılmaz**, `takim.md`'den üretilir:

- `name`, `description`, `model`, `tools` → agent frontmatter'ına aynen geçer.
- `gerekli_anahtarlar`, `butce_usd`, `skills` → **şirket alanlarıdır** (`SIRKET_ALANLARI`),
  agent frontmatter'ına sızmaz; sürücü ve önsöz kullanır.
- Gövdenin başına önsöz eklenir: kimlik + okuma sırası + (varsa) yetenek satırı +
  `<kaynak>` kuralı + defter/kendini geliştirme cümlesi + koşu kaydı sözleşmesi.
- Sonra `takim.md`'nin gövdesi olduğu gibi gelir.

```bash
python3 bin/agents_uret.py          # üret (değişenleri yazar) → "yazıldı: x-icerik"
python3 bin/agents_uret.py --check  # sapma varsa 1 döner ve "SAPMA: …" basar, yazmaz
```

`--check` CI için: agent dosyası `takim.md` ile uyuşmuyorsa build kırılır.
`kos.py` zaten her koşunun başında `uret()` çağırdığı için pratikte sapma uzun yaşamaz.

---

## `ayar.py` — bütün sayılar tek yerde

ANAYASA §4'ün sayıları kodda **tek bir yerde** durur; hiçbir betik ikinci kez sayı yazmaz.

| Sabit | Değer | Ne demek |
|---|---|---|
| `MESAI_BASLANGIC` | `9` | Mesai başı (dahil) |
| `MESAI_BITIS` | `23` | Mesai sonu (hariç) — `MESAI_METNI` = `09:00-23:00` |
| `KOSU_BUTCESI_USD` | `2.0` | Tek koşunun para tavanı (takım `butce_usd` ile artırabilir) |
| `KOSU_SURESI_SN` | `15 * 60` | Tek koşunun süre tavanı — 15 dakika |
| `KOSULAR_ARASI_DK` | `0` | Aynı takımın iki koşusu arası bekleme — **yok** |
| `GUNLUK_KOSU_TAVANI` | `4` | Takım başına gün |
| `GUNLUK_MALIYET_TAVANI_USD` | `10.0` | Tüm şirket, gün |
| `ES_ZAMANLI_TAVAN` | `2` | Dağıtıcının aynı turda başlattığı takım sayısı |

`zamanla.py` sabah tetiğini `MESAI_BASLANGIC`'tan (09:00), akşam tetiğini `MESAI_BITIS - 1`'den
(22:00) türetir — orada da ikinci bir saat yazılı değildir.

Ayarı ekrana basmak için:

```bash
python3 bin/ayar.py
# 2026-09-13 21:40 — mesai içinde (09:00-23:00), sonraki açılış Pzt 09:00
# tavanlar: koşu 2.0 USD / 15 dk · takım günde 4 koşu · arası 0 dk · şirket günde 10.0 USD
# kanal: @ornek-kanal · .env: var
```

`ayar.py` ayrıca şunları sağlar: `.env` okuma (`env_yukle`, `ortam_yukle`, `eksik_anahtarlar`),
mesai hesabı (`mesaide_mi`, `sonraki_mesai`), frontmatter ayrıştırma (`frontmatter`,
`takim_bilgisi`) ve `durum.json` okuma/yazma (`durum_oku`, `durum_guncelle` — birleştirme
immutable, yeni sözlük yazar).

---

## Sırada

- Ne zaman ve neyle koşuyor: [02-dongu.md](02-dongu.md)
- Denetim nasıl işliyor: [03-bekci.md](03-bekci.md)
- Yetenekler: [04-yetenekler.md](04-yetenekler.md)
- Kendi takımını açmak: [05-yeni-takim.md](05-yeni-takim.md)
- Bir şey çalışmıyorsa: [06-sorun-giderme.md](06-sorun-giderme.md)

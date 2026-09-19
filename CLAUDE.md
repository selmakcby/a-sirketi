# A Şirketi

> Her gün elle yaptığım işleri yapan üç ajanlık küçük şirket. Yayın düğmesi insanda.

## Ne bu
- **x-icerik** — Telegram'dan gelen X linkini doğrular, iddia tablosu + karar yazar.
- **youtube-analiz** — haftalık video ve yorum verisini çeker, rapor çıkarır.
- **twitter-icerik** — doğrulanmış konudan X Article paketi kurar.
- **bekçi** (`bin/bekci.py`) — Stop hook'ta her koşuyu denetler; red verirse ajan aynı oturumda düzeltir.
- **dağıtıcı** (`bin/dagitici.py`) — zinciri kurar (x-icerik → twitter-icerik). Takımlar birbirine mesaj atmaz.
- **dinleyici** (`bin/telegram_dinle.py`) — bota mesaj düştüğü an ilgili takımı koşturur:
  içinde "youtube" geçen mesaj → youtube-analiz, linkli geri kalan → x-icerik; olay tetikli, zamanlayıcısız.
- **günlük** (`bin/gunluk.py`) — sabah 09:00 dağıtıcıyı koşturup rapor yazar, akşam 22:00 günü denetler.
  Zamanlayıcıyı `bin/zamanla.py --kur` kurar (launchd); raporlar `sirket-log/rapor/` altında, dışarı gitmez.

Döngü kapalı, ama **yayın düğmesi insanda**: hiçbir takım sosyal hesaba yazmaz, mail atmaz,
yorum bırakmaz — taslağa kadar gider ve durur.

## Okuma sırası (her ajan, her koşuda)
1. `ANAYASA.md` — değişmez çerçeve
2. `sirket/AJAN-KIMLIGI.md` — kimsin, nasıl çalışırsın
3. `takimlar/<takim>/kurallar.md` — takımın sınırları
4. `takimlar/<takim>/takim.md` — koşu adımları ve çıktı sözleşmesi
5. `skills/` — işi karşılayan yetenek varsa

## Klasör yapısı
```
bin/                  kos.py (koşu sürücüsü) · bekci.py (bekçi) · dagitici.py (dağıtıcı)
                      telegram_dinle.py (olay tetiği) · gunluk.py + zamanla.py (sabah/akşam)
sirket-log/rapor/     sabah raporu ve akşam denetimi — git'e girmez
takimlar/<takim>/     takim.md · kurallar.md · defter.md · durum.json · kosu/ · cikti/
skills/<ad>/SKILL.md  yetenekler — her birinde kaynak ve lisans yazar
sirket/               AJAN-KIMLIGI.md · YETENEKLER.md
.env                  anahtarlar — asla commit'e girmez
```
`defter.md` ajanındır (ders yazar), `kurallar.md` insanın. Koşu kaydı `kosu/`, ürün `cikti/`.

## Yasaklar
- `.env` okuma, açma, ekrana basma — anahtar yalnız süreç ortamından gelir
- Sosyal hesaba yazma, mail gönderme, yorum bırakma
- Para harcama — abonelik, satın alma, tavan dışı ücretli çağrı
- `ANAYASA.md` ve `kurallar.md` değiştirme — ikisi de insanındır

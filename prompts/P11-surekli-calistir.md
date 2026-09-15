# P11 · Sürekli çalıştır — dinleyici ve zamanlayıcı

**Ne zaman:** Döngü elle bir kez kapandıktan sonra (P8–P9). Bundan sonra sen başında olmadan döner.

```
Şirketi sürekli çalışır hâle getir. Önce python3 bin/telegram_dinle.py --bir-kez koştur ve tek turun ne yaptığını söyle. Sonra python3 bin/zamanla.py --kuru çıktısını göster: hangi iki tetik, hangi saatlerde, hangi komutla kurulacak (sabah 09:00 gunluk.py --sabah, akşam 22:00 gunluk.py --aksam; saatler bin/ayar.py'deki mesai penceresinden türer). Onaylarsam python3 bin/zamanla.py --kur koştur ve python3 bin/zamanla.py --durum ile yüklendiğini göster. Son olarak dinleyiciyi arka planda nasıl açık tutacağımı iki cümleyle anlat (tmux oturumu ya da launchd); macOS değilse cron satırlarını docs/02-dongu.md'deki gibi yaz.
```

> **Repoyu klonladıysan:** aynı prompt geçerli. Saatleri değiştirmek istersen tek yer
> [`bin/ayar.py`](../bin/ayar.py) (`MESAI_BASLANGIC`, `MESAI_BITIS`); zamanlayıcı oradan okur.

**Beklenen çıktı:** `~/Library/LaunchAgents/` altında iki plist yüklü — etiket köke bağlıdır:
`com.a-sirketi.<klasor>-<hash6>.sabah` ve `…aksam` (iki klon aynı kaydı ele geçirmesin diye).
`--durum` ikisini ve bir sonraki koşu saatini gösterir. Dinleyici açıkken bota link attığın an
`x-icerik` koşar; sabah 09:00 dağıtıcı kuyruğu işler ve rapor yazar, akşam 22:00 günü denetler.
Raporlar `sirket-log/rapor/` altındadır, git'e girmez.

**Dikkat:** `zamanla.py` yalnızca macOS launchd bilir; Linux'ta cron/systemd örneği
[`docs/02-dongu.md`](../docs/02-dongu.md) sonundadır. Bilgisayar o saatte kapalıysa launchd kaçan işi
açılışta koşturur, cron koşturmaz. Dinleyici sürekli bir süreçtir, zamanlayıcı işi değildir — kapanırsa
mesajlar Telegram'da bekler, `--isle` ile sonradan alınır. Kaldırmak: `python3 bin/zamanla.py --kaldir`.

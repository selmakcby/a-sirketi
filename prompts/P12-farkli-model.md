# P12 · Farklı model bağla — NVIDIA'nın bedava modeli

**Ne zaman:** Döngü Anthropic'le bir kez döndükten sonra (P8'den sonra). İsteğe bağlı:
şirketin çalışması buna bağlı değil.

**Önce:** [build.nvidia.com](https://build.nvidia.com) → ücretsiz hesap → bir model kartında
**Get API Key** → çıkan `nvapi-…` anahtarını kopyala. Kredi kartı istemez.

```
A Şirketi'nde bir takımı Anthropic yerine NVIDIA'nın bedava modeliyle koşturmak istiyorum. Şu sırayla yap ve her adımda ne olduğunu tek cümleyle söyle. Önce docs/07-farkli-model.md'yi oku, yolu ondan öğren. Sonra .env dosyama NVIDIA_API_KEY satırını doldurmam için bana söyle — anahtarı sen yazma, ben yapıştıracağım; NIM_MODEL satırına tool-use destekleyen bir model koy ve neden o modeli seçtiğini söyle (tool-use desteklemeyen model bu şirkette çalışmaz). Anahtarı yapıştırdıktan sonra python3 bin/model_proxy.py --durum koştur ve çıktıyı bana oku. Sonra python3 bin/model_proxy.py --kuru ile üretilecek config'i ve komutu göster; config dosyasında anahtarın kendisi değil os.environ/NVIDIA_API_KEY yazdığını bana kanıtla. Sonra takimlar/twitter-icerik/takim.md frontmatter'ına saglayici: nim satırını ekle ve model: satırını seçtiğin NIM modeliyle değiştir — başka hiçbir takıma dokunma. takim.md'yi değiştirdikten sonra python3 bin/agents_uret.py koştur (takim.md tek kaynak; .claude/agents/<takim>.md ondan üretilir) ve python3 bin/agents_uret.py --check ile sapma kalmadığını göster. python3 bin/kos.py twitter-icerik --kuru koştur ve "köprü:" satırını bana göster. Son olarak python3 -m unittest discover -s tests koştur, hepsi yeşil mi söyle. Proxy'yi sen başlatma, komutu bana ver: ayrı terminalde ben açacağım.
```

> **Repoyu klonladıysan:** aynı prompt geçerli. `bin/model_proxy.py`, `bin/kos.py` ve
> `docs/07-farkli-model.md` zaten yerinde; Claude Code yalnızca `.env`'i ve bir `takim.md`'yi
> değiştirir.

**Beklenen çıktı:** `takimlar/twitter-icerik/takim.md` frontmatter'ında `saglayici: nim` ve NIM
model adı; `bin/kos.py twitter-icerik --kuru` çıktısında `sağlayıcı: nim` ve
`köprü: http://127.0.0.1:4000 → NVIDIA NIM` satırları; `sirket/model-proxy/config.yaml` üretilmiş
ve içinde `os.environ/NVIDIA_API_KEY` yazıyor (anahtarın kendisi değil); testler yeşil.
Gerçek koşu için ayrı terminalde `python3 bin/model_proxy.py`, sonra
`python3 bin/kos.py twitter-icerik --zorla`.

**Dikkat:** Bu prompt Claude Code'a **anahtar yazdırmaz** — anahtarı `.env`'e sen yapıştırırsın.
`saglayici` satırı olmayan takım Anthropic'te kalır; değişiklik tek takımı etkiler. Geri dönmek
için o iki satırı silmen yeterli. Kamerada söylenecek cümle: *bu koşunun istemi ve okuduğu dosyalar
NVIDIA'ya gidiyor, Anthropic'in koşulları orada geçmiyor, ne kadar güvenli bilmiyorum — karar sizin.*
Güvenlik notlarının tamamı [`docs/07-farkli-model.md`](../docs/07-farkli-model.md) sonundadır;
LiteLLM'in 1.82.7 / 1.82.8 sürümleri zararlıdır, sürüm `bin/ayar.py`'de sabitlidir.

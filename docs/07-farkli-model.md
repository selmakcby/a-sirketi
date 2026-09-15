# 07 · Farklı model bağlamak

Şirketin varsayılan modeli Anthropic'in Sonnet'i. Ama ajan bir dosya değil, bir **rol**:
kimliği `takim.md`'de, kuralı `kurallar.md`'de, hafızası `defter.md`'de. Modeli altından
çekip başkasını koymak sistemi bozmaz — aynı ajan, başka bir beyinle koşar.

Bu sayfa NVIDIA'nın **ücretsiz** sunduğu modellerden birini bağlamayı anlatıyor.

---

## Neden araya bir köprü giriyor

Claude Code tek bir dil konuşur: Anthropic'in `/v1/messages` biçimi. NVIDIA NIM ise OpenAI
biçimini konuşur. Claude Code'un üçüncü taraf bir OpenAI ucunu doğrudan çağırma yolu yok —
[Anthropic'in belgesi](https://code.claude.com/docs/en/llm-gateway) tek destekli yolu
**gateway** olarak tarif ediyor: `ANTHROPIC_BASE_URL` Claude Code'u bir proxy'ye yöneltir,
`ANTHROPIC_AUTH_TOKEN` o proxy'nin kimlik bilgisidir.

Araya giren proxy [LiteLLM](https://docs.litellm.ai/docs/tutorials/claude_non_anthropic_models):
Anthropic isteğini alır, OpenAI isteğine çevirir, `https://integrate.api.nvidia.com/v1`
adresine yollar, cevabı geri çevirir.

```
claude -p  ──ANTHROPIC_BASE_URL──▶  LiteLLM (127.0.0.1:4000)  ──▶  NVIDIA NIM
   Anthropic biçimi                    çevirmen                      OpenAI biçimi
```

Proxy yalnız `127.0.0.1`'e bağlanır; dışarıya açık değildir. `bin/model_proxy.py` onu
`uvx` ile geçici ortamda, **sürümü sabitlenmiş** olarak başlatır — global `pip install` yok.

---

## Model seçerken: tool-use şart

Ajan `Read`, `Write`, `Bash` kullanır. Bunlar model tarafında **tool-use (fonksiyon çağrısı)**
demektir. Tool-use desteklemeyen model bu şirkette işe yaramaz: koşu ya boş döner ya hata verir.
Model kartında "function calling" / "tool calling" yazmıyorsa alma.

Ücretsiz katmanda tool-use desteklediği bilinen adaylar:

| Model | Not |
|---|---|
| `meta/llama-3.3-70b-instruct` | En güvenli başlangıç; tool-use'u yaygın test edilmiş |
| `nvidia/llama-3.1-nemotron-70b-instruct` | NVIDIA'nın kendi ince ayarı, aynı boyut |
| `mistralai/mistral-large` | Alternatif aile; araç çağrısında sağlam |

build.nvidia.com'daki model kartı desteklenen özellikleri açıkça listeler — **listeye bak,
buradaki tabloya güvenme**: katalog değişiyor.

---

## Adım adım

### 1 · Anahtarı al

[build.nvidia.com](https://build.nvidia.com) → ücretsiz hesap (kredi kartı istemez) → bir model
kartı → **Get API Key**. Çıkan anahtar `nvapi-` ile başlar. Ücretsiz katman kredi ve dakikalık
istek sınırıyla gelir; sınır dolunca koşu hata verir, para harcanmaz.

### 2 · `.env`

```bash
NVIDIA_API_KEY=nvapi-…
NIM_MODEL=meta/llama-3.3-70b-instruct
```

`.env` git'e girmez (`.gitignore` ilk satırı). Anahtar config dosyasına da yazılmaz —
`bin/model_proxy.py` üretilen config'e `os.environ/NVIDIA_API_KEY` koyar, değeri değil.

### 3 · Köprüyü ayağa kaldır

```bash
python3 bin/model_proxy.py --durum    # anahtar var mı, proxy ayakta mı
python3 bin/model_proxy.py --kuru     # ne çalışacak, hiçbir şey başlatmadan
python3 bin/model_proxy.py            # başlat — Ctrl-C ile durur
```

İlk çalıştırmada `uvx` LiteLLM'i indirir (bir dakika sürebilir). Terminali açık bırak;
koşuyu ikinci bir terminalden başlat.

### 4 · Takıma iki satır

`takimlar/<takim>/takim.md` frontmatter'ı:

```yaml
saglayici: nim
model: meta/llama-3.3-70b-instruct
```

`saglayici` yazılmamışsa varsayılan `anthropic`'tir — mevcut takımların hiçbiri etkilenmez.
`model:` satırını `sonnet` bırakırsan `.env`'deki `NIM_MODEL` kullanılır.

### 5 · Koştur

```bash
python3 bin/kos.py <takim> --kuru     # köprü satırını gör, claude çağrılmaz
python3 bin/kos.py <takim> --zorla    # gerçek koşu
```

Kuru koşu şunu basar:

```
  sağlayıcı: nim · model: meta/llama-3.3-70b-instruct · bütçe: 2 USD · süre: 15 dk
  köprü: http://127.0.0.1:4000 → NVIDIA NIM · model: meta/llama-3.3-70b-instruct
```

Koşu kaydının üstbilgisine de sağlayıcı yazılır: hangi koşunun hangi beyinle döndüğü sonradan
belli olur.

### 6 · Geri dön

`saglayici: nim` satırını sil (ya da `anthropic` yap). Başka hiçbir şeye dokunmaya gerek yok.

---

## Kod tarafında ne oluyor

`bin/kos.py` içindeki `saglayici_ortami(fm, temel)` tek karar noktası:

- `anthropic` → ortam **aynen** döner, hiçbir `ANTHROPIC_*` değişkenine dokunulmaz.
- `nim` → alt sürece şunlar verilir:

| Değişken | Değer | Neden |
|---|---|---|
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:4000` | Claude Code'u proxy'ye yöneltir |
| `ANTHROPIC_AUTH_TOKEN` | yerel master key | Proxy'nin `Authorization: Bearer` kimliği |
| `ANTHROPIC_API_KEY` | **silinir** | Kalırsa Claude Code Anthropic'e düşer, koşu sessizce ücretli olur |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | seçilen NIM modeli | Oturum başlığı gibi arka plan işleri de proxy'ye gitsin |
| `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` | `1` | NIM modelleri Anthropic'in `thinking` alanını anlamaz |

Anahtar ya da model eksikse koşu başlamaz: `durum.json`'a `atlandi` yazılır ve koşu kaydında
ne eksik olduğu Türkçe durur. Sessiz düşme yok.

Testleri: `tests/test_kos_saglayici.py` (`python3 -m unittest discover -s tests`).

---

## Güvenlik — okumadan geçme

Bu yolu açmak birkaç şeyi değiştirir. Hiçbiri gizli değil, hepsi senin kararın:

- **Veri üçüncü tarafa gider.** Koşudaki istem, okuduğu dosyalar ve ürettiği metin NVIDIA'nın
  sunucularına gider. Anthropic'in veri işleme koşulları orada geçmez; NVIDIA'nın kendi
  koşulları geçer. Şirket dosyalarında özel bir şey varsa bunu bilerek yap.
- **Anahtarın üzerinden akar.** `NVIDIA_API_KEY` yerel proxy'ye, oradan NVIDIA'ya gider.
  `.env` git'e girmez, config dosyasına yazılmaz — ama makinende düz metindir.
- **Proxy bir üçüncü taraf yazılımıdır.** LiteLLM'in PyPI'daki **1.82.7 ve 1.82.8** sürümleri
  kimlik bilgisi çalan zararlı kodla yayınlandı. `bin/model_proxy.py` sürümü sabitler
  (`ayar.LITELLM_SURUM`) ve `uvx` ile izole ortamda koşar; sürümü elle değiştirirken buna dikkat et.
- **Anthropic bu yolu desteklemiyor.** Belge açıkça diyor: Anthropic üçüncü taraf gateway
  ürünlerini denetlemez ve Claude Code'un Claude dışı modellere yönlendirilmesini desteklemez.
  Bozulursa destek yok.
- **Bedava değil, sınırlı.** Ücretsiz katman kredi ve dakikalık istek sınırıyla gelir.
  Sınır dolunca koşu hata verir.
- **Kalite aynı değil.** 70B'lik açık bir model uzun araçlı koşuda Sonnet gibi davranmaz.
  Bekçi (`docs/03-bekci.md`) yerinde durur: kötü çıktı yine reddedilir.
- **Bekçiyi ayrı tut.** ANAYASA madde 3 denetleyenin ayrı kafa olmasını ister. Üreten takımı
  NIM'e alıp bekçiyi Anthropic'te bırakmak bu maddeyi güçlendirir; ikisini birden aynı NIM
  modeline almak zayıflatır.

---

## Windows / Linux

- **Linux:** her şey aynı çalışır. `uvx` yoksa: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **Windows:** `bin/model_proxy.py` ve `bin/kos.py` çalışır (ortam değişkenleri Python
  tarafından alt sürece verilir, kabuk `export`'u gerekmez). `uv` için
  `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`. Kabuktan elle değişken
  koyacaksan `set` değil PowerShell'de `$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:4000"`.
  Şirketin saatli tetiği (`bin/zamanla.py`) macOS launchd'ye bağlıdır; Windows'ta Görev
  Zamanlayıcı ile elle kurulur — model köprüsüyle ilgisi yok.

---

## Kaynaklar

- [Claude Code — LLM gateway](https://code.claude.com/docs/en/llm-gateway) ·
  [gateway'e bağlan](https://code.claude.com/docs/en/llm-gateway-connect) — `ANTHROPIC_BASE_URL`,
  `ANTHROPIC_AUTH_TOKEN`, desteklenmeme notu
- [LiteLLM — Claude Code ile Anthropic dışı modeller](https://docs.litellm.ai/docs/tutorials/claude_non_anthropic_models)
- [LiteLLM — NVIDIA NIM sağlayıcısı](https://docs.litellm.ai/docs/providers/nvidia_nim) — `nvidia_nim/<model>`
- [build.nvidia.com](https://build.nvidia.com) — ücretsiz model kataloğu ve API anahtarı

#!/usr/bin/env python3
"""Model köprüsü — NVIDIA NIM modellerini Claude Code'un anladığı biçime çeviren yerel proxy.

Claude Code yalnızca Anthropic'in `/v1/messages` biçimini konuşur; NVIDIA NIM ise
OpenAI biçimini. Arada LiteLLM proxy durur: Claude Code'dan gelen Anthropic isteğini
OpenAI isteğine çevirir, `https://integrate.api.nvidia.com/v1` adresine yollar, cevabı
geri çevirir. Proxy yalnız `127.0.0.1`'e bağlanır — dışarı açık değildir.

Kullanım:
    python3 bin/model_proxy.py --durum     # anahtar var mı, proxy ayakta mı
    python3 bin/model_proxy.py --kuru      # ne çalıştırılacağını bas, hiçbir şey başlatma
    python3 bin/model_proxy.py             # config üret ve proxy'yi başlat (Ctrl-C ile durur)

Global `pip install` yapılmaz: LiteLLM `uvx` ile geçici ortamda, sürümü sabitlenmiş
olarak koşar. Anahtar config dosyasına yazılmaz, ortamdan okunur.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ayar  # noqa: E402

KOK = ayar.KOK
CONFIG_YOLU = KOK / "sirket" / "model-proxy" / "config.yaml"
NIM_TABANI = "https://integrate.api.nvidia.com/v1"

# LiteLLM'in 1.82.7 ve 1.82.8 sürümleri PyPI'da zararlı kodla yayınlandı; sürüm sabitlenir.
YASAKLI_SURUMLER = ("1.82.7", "1.82.8")


def port_bul(url=None):
    """Proxy adresinden port; adres bozuksa varsayılan port."""
    ayristirilmis = urlparse(url or ayar.NIM_PROXY_URL)
    return ayristirilmis.port or 4000


def config_metni(model):
    """LiteLLM proxy config'i. Anahtar dosyaya YAZILMAZ — `os.environ/` ile ortamdan okunur.

    `drop_params`: Claude Code'un yolladığı Anthropic'e özgü alanları (thinking, cache_control)
    NIM anlamaz; LiteLLM bunları düşürür, istek hata vermek yerine geçer.
    `"*"` satırı: takim.md'de modeli değiştirince config'i yeniden üretmek gerekmesin diye
    her NIM model adı aynı sağlayıcıya yönlenir.
    """
    return (
        "# bin/model_proxy.py tarafından üretildi — elle düzenleme, üzerine yazılır.\n"
        "litellm_settings:\n"
        "  drop_params: true\n\n"
        "general_settings:\n"
        "  master_key: os.environ/LITELLM_MASTER_KEY\n\n"
        "model_list:\n"
        f"  - model_name: {model}\n"
        "    litellm_params:\n"
        f"      model: nvidia_nim/{model}\n"
        "      api_key: os.environ/NVIDIA_API_KEY\n"
        f"      api_base: {NIM_TABANI}\n"
        "      max_tokens: 4096\n"
        '  - model_name: "*"\n'
        "    litellm_params:\n"
        '      model: "nvidia_nim/*"\n'
        "      api_key: os.environ/NVIDIA_API_KEY\n"
        f"      api_base: {NIM_TABANI}\n")


def config_yaz(model, yol=None):
    """Config'i üretip diske yazar; yazılan yolu döner."""
    hedef = Path(yol or CONFIG_YOLU)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(config_metni(model), encoding="utf-8")
    return hedef


def baslat_komutu(config, port, surum=None):
    """`uvx` ile geçici ortamda, sürümü sabitlenmiş LiteLLM proxy komutu."""
    return ["uvx", "--from", f"litellm[proxy]=={surum or ayar.LITELLM_SURUM}", "litellm",
            "--config", str(config), "--host", "127.0.0.1", "--port", str(port)]


def ayakta_mi(url=None, saniye=2):
    """Proxy cevap veriyor mu — `/health/liveliness` uç noktası."""
    hedef = (url or ayar.NIM_PROXY_URL).rstrip("/") + "/health/liveliness"
    try:
        with urllib.request.urlopen(hedef, timeout=saniye) as cevap:
            return cevap.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _maskele(deger):
    return f"{deger[:6]}…{deger[-4:]}" if len(deger) > 12 else "(çok kısa)"


def durum(ortam=None, ayakta=None):
    """İnsanın okuyacağı tek paragraf: anahtar, model, proxy ve eksikse ne yapılacağı."""
    ortam = ortam if ortam is not None else ayar.env_yukle()
    anahtar = (ortam.get("NVIDIA_API_KEY") or "").strip()
    model = (ortam.get("NIM_MODEL") or "").strip()
    url = (ortam.get("NIM_PROXY_URL") or "").strip() or ayar.NIM_PROXY_URL
    calisiyor = ayakta_mi(url) if ayakta is None else ayakta
    satirlar = [f"model köprüsü — {url}"]
    if anahtar:
        satirlar.append(f"  NVIDIA_API_KEY: var ({_maskele(anahtar)})")
    else:
        satirlar.append("  NVIDIA_API_KEY: YOK — build.nvidia.com'da ücretsiz hesap aç, "
                        "bir model kartında 'Get API Key' de, çıkan `nvapi-…` anahtarını "
                        "`.env` dosyasına `NVIDIA_API_KEY=` satırına yapıştır.")
    eksik_model = "YOK — .env'e NIM_MODEL yaz ya da takim.md'de `model:` satırına"
    satirlar.append(f"  NIM_MODEL: {model or eksik_model}")
    satirlar.append(f"  proxy: {'ayakta' if calisiyor else 'kapalı — `python3 bin/model_proxy.py` ile başlat'}")
    if anahtar and model and calisiyor:
        satirlar.append("  → hazır: takim.md'ye `saglayici: nim` yaz ve koştur.")
    return "\n".join(satirlar)


def baslat(kuru=False):
    ortam = ayar.ortam_yukle()
    anahtar = (ortam.get("NVIDIA_API_KEY") or "").strip()
    model = (ortam.get("NIM_MODEL") or "").strip()
    if not anahtar or not model:
        print(durum(ortam))
        print("\nEksik var — proxy başlatılmadı.")
        return 1
    ortam.setdefault("LITELLM_MASTER_KEY", ayar.NIM_YEREL_TOKEN)
    port = port_bul(ortam.get("NIM_PROXY_URL"))
    if kuru:  # kuru koşu hiçbir dosyaya yazmaz
        print(f"config (yazılacak yol): {CONFIG_YOLU}\n{config_metni(model)}")
        print("komut: " + " ".join(baslat_komutu(CONFIG_YOLU, port)))
        print("ortam: NVIDIA_API_KEY=(gizli) LITELLM_MASTER_KEY=(gizli)")
        print("→ hiçbir şey yazılmadı, hiçbir şey başlatılmadı.")
        return 0
    config = config_yaz(model)
    print(f"config: {config} · model: {model} · port: {port}")
    print("proxy başlıyor — Ctrl-C ile durur. Ayrı bir terminalde koşuyu başlat.")
    try:
        return subprocess.run(baslat_komutu(config, port), env=ortam).returncode
    except FileNotFoundError:
        print("uvx bulunamadı — kur: `curl -LsSf https://astral.sh/uv/install.sh | sh`")
        return 1
    except KeyboardInterrupt:
        print("\nproxy durduruldu.")
        return 0


def main(argv):
    if "--durum" in argv:
        print(durum())
        return 0
    if "--yasakli" in argv:
        print(json.dumps({"sabit_surum": ayar.LITELLM_SURUM, "yasakli": YASAKLI_SURUMLER}))
        return 0
    return baslat(kuru="--kuru" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env bash
# Yeni takım açar (iskeletten kopyalar, adı yerleştirir).
# Kullanım: bin/takim-olustur.sh <takim-adi>    (ASCII kebab-case)
set -euo pipefail
KOK="$(cd "$(dirname "$0")/.." && pwd)"
AD="${1-}"
[[ -n "$AD" ]] || { echo "takım adı gerekli — örnek: bin/takim-olustur.sh x-icerik" >&2; exit 2; }
[[ "$AD" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "ad ASCII kebab-case olmalı: $AD" >&2; exit 1; }
HEDEF="$KOK/takimlar/$AD"
[[ -e "$HEDEF" ]] && { echo "zaten var: takimlar/$AD" >&2; exit 1; }

cp -R "$KOK/takimlar/_iskelet" "$HEDEF"
mkdir -p "$HEDEF/kosu" "$HEDEF/cikti"
for f in takim.md kurallar.md defter.md durum.json; do
  python3 - "$HEDEF/$f" "$AD" <<'PY'
import sys
from pathlib import Path
yol, ad = Path(sys.argv[1]), sys.argv[2]
yol.write_text(yol.read_text(encoding="utf-8").replace("TAKIM", ad), encoding="utf-8")
PY
done
echo "kuruldu: takimlar/$AD — şimdi takim.md'yi doldur (akan şey, araçlar, koşu adımları, çıktı sözleşmesi)"
cat <<UYARI

  ⚠ ŞİMDİ YAPILACAK — takimlar/$AD/takim.md'de skills: alanını doldur (en az bir skill),
    yoksa testler kırmızı: tests/test_skills.py her takımdan en az bir yetenek bekler.
      1. skills/<ad>/SKILL.md dosyasının takimlar: alanına "$AD" ekle
      2. takim.md'de  skills: [<ad>]  yaz
      3. python3 bin/agents_uret.py && python3 -m unittest discover -s tests
UYARI

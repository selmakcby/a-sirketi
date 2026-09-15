---
name: TAKIM
description: TAKIM takımı — (tek cümle: ne girer, ne çıkar)
saglayici: anthropic
model: sonnet
tools: [Read, Write, Glob, Grep]
gerekli_anahtarlar: []
skills: []
butce_usd: 2
---

# TAKIM

## Akan şey
Girdi: (yol / araç)
Çıktı: `takimlar/TAKIM/cikti/…`

## Koşu adımları
1. `durum.json`'daki kuyruğa bak; `bekliyor` madde varsa ondan başla.
2. Girdi kaynağını oku (aşağıda).
3. Çıktıyı `takimlar/TAKIM/cikti/` altına tarihli dosya olarak yaz.
4. `durum.json`'u güncelle: `son_kosu`, kuyruk maddelerinin `durum` alanı, `defter_son_ders`.
5. `defter.md`'ye bu koşudan çıkan **tek** dersi ekle (ders yoksa ekleme).
6. Koşu kaydını `SIRKET_KOSU` yoluna yaz: ne okudun, ne ürettin, ne kaldı, hangi kaynaklardan.

## Yetenekler
Koşu adımında ilgili dosyayı oku ve uygula. (Yetenek eklediğinde frontmatter'daki `skills:`
alanına adını yaz ve `skills/<ad>/SKILL.md` dosyasının `takimlar:` alanına bu takımı ekle.)
- (henüz yetenek yok)

## Girdi kaynakları
- (yol / araç)

## Çıktı sözleşmesi
- (dosya adı deseni ve içinde ne olduğu)

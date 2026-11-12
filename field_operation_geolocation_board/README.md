# Field Operation Route Board

> **"Günün Rotaları"** — ofis/dispeçer için tek ekranlık harita panosu: günün tüm
> ekiplerinin rotaları, her takım kendi renginde, sağ panelde filtreler, canlı
> konumlar. Odoo 19 · AGPL-3 · Softteknik Bilişim
> Modül: `apps/saha/field_operation_geolocation_board` · `19.0.1.0.0`

Bu modül `field_operation_geolocation`'ın üzerine **opsiyonel** bir köprü modüldür.
Pano istenmeyen veritabanlarına kendiliğinden kurulmasın diye `auto_install=False`
bırakılmıştır: **Apps > Update Apps List** sonrası elle **Install** edilir ya da
`-i field_operation_geolocation_board` ile kurulur. `soft_web_map` bağımlılığı
kurulum sırasında otomatik gelir. Mevcut planlama sihirbazını değiştirmez; onu
**okur** ve planı düzenlemek için takım kartındaki kalemle açar.

## Ne yapar?

- **Menü:** *Saha Servisi > Günün Rotaları* (Head Office grubu). Takım formunda da
  **Rotalar** butonu vardır (panoyu o takıma odaklayarak açar).
- **Harita:** takım renginde kapalı döngü (başlangıç → duraklar → başlangıç),
  **numaralı durak işaretçileri**, ev/depo başlangıç ikonu, **canlı takım konumu**
  ("canlı" etiketli, 45 sn'de bir yenilenen), durağa tıklayınca müşteri/saat/adres/
  telefon ve **İşi Aç** / **Yol Tarifi** butonları.
- **Sağ panel:** takım listesi (renk, durak/konumsuz sayısı, km, son görülme),
  arama, **Sadece canlı / Rota kaydedilmemiş / Konumsuz** filtreleri, göz (haritada
  göster) ve kalem (planı aç) aksiyonları, tümünü seç/temizle, solo mod.
- **Üst çubuk:** tarih gezinme (‹ Bugün ›, Yarın, tarih seçici), canlı takip aç/kapa,
  seçili takımların KPI'ları (takım, durak, km, konumsuz), yenile.
- **Alt çubuk:** seçili toplamlar, "kuş uçuşu" notu, son güncelleme saati.

## Veri ve yetki

- İki JSON uç: `POST /field_operation_geolocation_board/day_board` (`date`), canlı
  yenileme için `POST /field_operation_geolocation_board/live` (`team_ids`).
- İş mantığı modelde: `field.operation.team._day_board_data(day, team_ids=None)` ve
  `_live_positions(team_ids=None)` → `TransactionCase` ile test edilir.
- Sıralama **plan sihirbazıyla ortak**: `field_operation_geolocation` 19.0.1.8.0
  ve üzerinde varsa `field.operation._day_operations_for_team` kullanılır; daha
  eski sürümlerde aynı gün/sıra `_board_legacy_day_operations` fallback'i ile
  üretilir. Böylece pano ile plan ekranı aynı günü ve aynı sırayı gösterir.
- Yetki: menü/aksiyon **Head Office** (`field_operation.service_group_all`) grubuna
  açıktır; uçlar da aynı grubu ister (`AccessError`). Saha çalışanı panoyu göremez.
  Kayıt kuralları gereği kullanıcı yalnız görebildiği işleri/takımları alır.
- **Çok şirket:** pano sorguları kullanıcının şirketleriyle sınırlıdır
  (`company_id in env.companies`); başka şirketin takımı/GPS'i dönmez.
- Harita tile'ları `soft_web_map.tile_url` / `soft_web_map.copyright` sistem
  parametrelerinden gelir; Leaflet `soft_web_map.assets_leaflet` bundle'ından yüklenir.

## Bilinen sınırlar (v0)

- Pano **salt-okunur**: sıra değiştirme/kaydetme sihirbazda yapılır (panodan "Planı aç").
- Rota geometrisi **düz segment** (haversine); gerçek yol geometrisi/ETA v2'dedir.
- Takımsız işler yalnız sayı olarak gösterilir; haritada gösterilmez (v2).
- Takım başına durak üst sınırı yok; 100+ duraklı günlerde performans ölçülmeli.
- Pano yalnız Head Office'e açık; gerçek "Rota Dispeçeri" grubu v2'de eklenecek.
- Tarayıcı/OWL/Leaflet davranışı bu geliştirme ortamında uçtan uca test edilmedi;
  staging'de menüden açıp doğrulanmalı (yükleme ve Python testleri temiz).

## Teknik notlar

- Dosyalar: `models/field_operation_team.py` (payload), `controllers/day_board.py`
  (uçlar), `static/src/js/day_board_action.js` (OWL client action + tarih/filtre/
  polling), `day_board_map.js` (Leaflet katmanları), `day_board_helpers.js`,
  `static/src/xml/day_board.xml` (OWL şablonları), `static/src/scss/day_board.scss`,
  `views/day_board_views.xml` (client action + menü + takım butonu), `i18n/tr.po`.
- Renkler Odoo kanban paletidir (`team.color`, 0–11); `color=0` olan takıma boş
  renklerden otomatik atanır.
- Test: `tests/test_day_board.py` (22 test): sıra, kapalı döngü, konumsuz durak,
  renk, canlı konum, plan sihirbazı ile aynı sıra, yetki ve geçersiz tarih.

## Kurulum / doğrulama

**Önemli:** `auto_install=False` — modül kendiliğinden kurulmaz, açıkça kurulur.
Modül `ir_module_module`'da hiç görünmüyorsa Uygulamalar listesi taranmamıştır;
`-i` komutu veya **Apps > Update Apps List** gerekir. `soft_web_map` kurulu değilse
kurulum sırasında bağımlılık olarak kendisi gelir.

Bilinen eski bir veritabanında (`uzman_v19` gibi: `field_operation` 2.5.0,
`field_operation_geolocation` 1.6.1, `soft_web_map` kurulu değil) doğrulanan tek komut:

```bash
cd C:\odoo\v19
.\.venv\Scripts\python.exe odoo\odoo-bin -c conf\uzman.conf -d uzman_v19 \
    -i field_operation_geolocation_board --stop-after-init --no-http
```

Bu komut `soft_web_map`'i bağımlılık olarak kendisi kurar. Pano, geolocation
**19.0.1.6.x** ile de çalışır (gün sırası için geriye uyumlu fallback vardır); yani
pano için geolocation/base güncellemesi **şart değildir**. Geolocation'ı da güncellemek
isterseniz önce base'i güncelleyin (kategori kaydı oradan gelir):

```bash
.\.venv\Scripts\python.exe odoo\odoo-bin -c conf\uzman.conf -d uzman_v19 \
    -u field_operation,field_operation_geolocation --stop-after-init --no-http
```

Kurulumdan sonra **Saha Servisi > Günün Rotaları** menüsü görünür (Head Office grubu).

```bash
# testler
./.venv/Scripts/python.exe odoo/odoo-bin -c conf/uzman.conf -d <db> \
    -u field_operation_geolocation_board \
    --test-tags /field_operation_geolocation_board --stop-after-init --no-http
```

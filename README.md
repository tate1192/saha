# saha — Saha Operasyon Modülleri

Softteknik Bilişim'in saha servis operasyon suite'i — Odoo 19 Community modülleri.

Lisans: AGPL-3 · Yazar: Softteknik Bilişim · Kod ve docstring İngilizce, doküman Türkçe

## Modüller

| Modül | Ne yapar |
|---|---|
| `field_operation` | İş kaydı, ekip/bölge planlama, durum akışı, portal erişimi, PDF servis teslim formu |
| `field_operation_sale` | Servis ↔ satış köprüsü: işten satış siparişi üretimi (wizard), sipariş satırlarından servis üretimi, fatura servis referansı |
| `field_operation_invoice` | Servis ↔ fatura köprüsü: tekli ve konsolide (çoklu) fatura sihirbazı, iş ↔ fatura çift yönlü bağ, faturalama/ödeme rozetleri |
| `field_operation_forms` | Servis ↔ form köprüsü: işten otomatik form üretimi, ekip/atanan personel görünürlüğü, müşteri + personel e-imzası (portal), durum akışı |
| `field_operation_pest` | Haşere formu detayları (hijyen/infestasyon/uygulama), pesticide satırları (BIO- serisi), stok sevkiyat entegrasyonu, pest tipi yönetimi |
| `field_operation_disinfect` | Dezenfeksiyon formu: pH/klor ölçümleri (öncesi/sonrası), dezenfeksiyon satırları (DIS- serisi), ürün/tank yönetimi, form e-postası |
| `field_operation_contract` | Sözleşme yönetimi: satır/servis planı, tekrarlayan üretim (cron + manuel), siparişten sözleşmeye dönüşüm, portal (görüntüleme + imza + PDF), müşteri imzası |
| `field_operation_contract_repeat` | Sözleşmeden elle toplu tekrarlayan iş üretimi: rrule sihirbazı (günlük/haftalık/aylık/yıllık, `count`/`until`), saat dilimi dönüşümü, mükerrer atlama, 500 kayıt sınırı; `group_field_operation_recurring` grubuna açık |
| `field_operation_contractor` | Taşeron işleri: taşeron partner + sorumlu kullanıcı + main/sub tip, müşteri bağlantısı, saha operasyonunda taşeron ataması, partner formunda smart buton |
| `field_operation_agreement` | Sözleşme (agreement) yönetimi: tip/durum/tarih/tutar, imza + PDF çıktısı, şablon + değişken yer tutucuları (`{{1}}`), bağlı saha operasyonları, günlük süre-bitimi cron'u (kapalı kurulur) |
| `field_operation_attendance` | Aylık puantaj raporu: ay/yıl seçimi, personel bazlı gün ve saat dağılımı (dönem sınırında kırpılır), hafta sonu ayrımı, PDF + Excel (xlsxwriter) / CSV çıktısı |
| `field_operation_geolocation` | Takım konum takibi: harita sağlayıcı ayarları (`maps.website`, anahtar maskeli), takım GPS alanları, konum geçmişi (kayıt kuralıyla korunur), tarayıcı takibi (OWL 2) + günlük adres→koordinat cron'u (kapalı kurulur) |
| `field_operation_map` | `field.operation` için harita görünümü (Leaflet; görünüm tipi **dış bağımlılık** `soft_web_map`'ten gelir) + adres gösterim alanı; kaldırmada aksiyonu temizleyen dar kapsamlı hook |
| `field_operation_worker` | Saha personeli arayüzü: worker'a özgü liste/kanban/form görünümleri + "My Jobs" filtresi + worker grubuna görünür menü (görünürlük base `rule_service_worker` kayıt kuralıyla) |
| `field_operation_gantt` | `field.operation` için Gantt (zaman çizelgesi) görünümü — görünüm tipi **dış bağımlılık** `soft_gantt`'tan gelir; duruma göre renk/ilerleme, ay penceresi, ekibe göre satırlar, sürükle-bırak yeniden planlama; `view_mode`'a mod **ekler** (sibling'ların modlarını düşürmez) |
| `field_operation_stock` | Sarf tüketimi: servis formunda sarf satırları (SL serisi, `editable` liste), tüketim tipi (servise dahil / garanti), onayda tek outgoing transfer ile gerçek stok çıkışı, iş bazlı parasal maliyet toplamları |
| `field_operation_whatsapp` | Müşteriye WhatsApp mesajı **açan** sihirbaz (gerçek API yok, deep-link: mobil `api.whatsapp.com` / masaüstü `web.whatsapp.com`), `{yer tutucu}` şablonları (bilinmeyen tutucu kayıtta reddedilir), kullanıcı saat diliminden bağımsız; servis raporu linki **access_token'lı** ek olarak; mesaj günlüğü **şirket kuralıyla** ayrılmış, silme yöneticide |
| `field_operation_holiday` | İzin ↔ saha köprüsü: onaylı iznin **her günü** için "İzinli" servis tipinde bir iş (personel + izin bağlantısı ile); izin iptal/silinince işler kalkar, tarih değişip yeniden onaylanınca yeniden üretilir; mevcut izin-çakışma kontrolü korunur |
| `field_operation_grease_duct` | Yağlı kanal temizliği: davlumbaz/dikey-yatay kanal/filtre ölçüm satırları (adet + metre), erişim durumu ve notu, sonraki temizlik tarihi, `GRD-<yıl>-` sertifika numarası ve **değerleri basan** sertifika PDF'i (müşteri, teknisyenler, ölçüm tablosu, imzalar) |

## Sürüm düzeni

Odoo sürümleri **branch** ile ayrılır; modüller repo kökünde durur:

    19.0   aktif sürüm
    20.0   sıradaki sürüm

Yeni sürüm açmak: `git checkout -b 20.0`, modülleri uyarla, push. Eski branch dokunulmadan kalır.

Bir modülü alt dizine koyarsan o dizini de `addons_path`'e eklemen gerekir: Odoo addons yolunun
yalnız *birinci seviye* alt dizinlerini modül sayar, özyinelemeli taramaz.

## Kurulum

Modül dizinini `addons_path`'e ekleyip uygulama listesini güncelle:

    odoo-bin -c <odoo.conf> -d <db> -u field_operation

## Test

    odoo-bin -c <odoo.conf> -d <test_db> -u field_operation \
        --stop-after-init --test-tags /field_operation

Sonucu log'dan oku: `odoo.tests.result: N failed, M error(s) of K tests`.

## Araçlar

- `.editorconfig` — satır sonu LF, 4 boşluk girinti, sonda boşluk yok, sonda satır sonu.
- `ruff.toml` — ruff: bugbear (`B`), döngü karmaşıklığı (`C90`), uzun satır (`E501`),
  import sırası (`I`), pyupgrade (`UP`).
- `.pre-commit-config.yaml` — commit öncesi kontrol (boşluk/satır sonu, XML kontrolü,
  `ruff` + `ruff-format`). Etkinleştirmek için:

      pip install pre-commit     # ya da: uv tool install pre-commit
      pre-commit install
      pre-commit run --all-files

## Kod kuralları

1. Kod ve docstring İngilizce; doküman/README Türkçe olabilir.
2. Tek README: modül açıklaması README'de tutulur, manifest'e `description` yazılmaz (Odoo 19'da
   manifest `description` verilirse README'yi ezer).
3. `attrs` kullanılmaz (Odoo 17'de kaldırıldı); `t-esc` / `t-raw` yerine `t-out`.
4. Yeni model varsa `security/ir.model.access.csv` zorunlu; kayıt kuralları `security/*.xml`.
5. Her modülde `tests/` altında en az bir test.
6. Satır sonu LF (`.gitattributes`), girinti boşluk, sonda boşluk yok.
7. Sürüm `19.0.<major>.<minor>.<patch>`; sürüm yalnız manifestte tutulur.
8. Yorumlanmış ölü kod bırakılmaz (geçmiş git'te duruyor); yorum yalnızca *neden*i anlatır.

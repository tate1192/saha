# Field Operation Map

> Map and Route functionality for Field Operation
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `apps/saha_legacy/field_operation_map` · 14 dosya · yeni model yok (görünüm + alan genişletmesi)

Bu modül, `field.operation` aksiyonuna harita görünümü ekleyen ve operasyon kaydına adres metni alanı
kazandıran küçük bir yapıştırıcıdır. Kendi JS katmanı, kendi modeli veya kendi ACL'i yoktur.

## 1. Genel Bakış

`field.operation` aksiyonuna harita (Leaflet/OpenStreetMap) görünümü ekler ve operasyon kaydına adres
metni alanı kazandırır. Harita altyapısı (view tipi ve tüm render sınıfları) `soft_web_map` modülünden gelir.

- `leaflet_map` view: `service_latitude` / `service_longitude` ile işaretçi, `limit="80"`
- Operasyon formuna `display_address` alanı (`address_id._display_address(without_company=True)`)
- Ana `field_operation` aksiyonuna `leaflet_map` view_mode ve `ir.actions.act_window.view` (sequence 8) eklenir
- Kaldırma kancası (`uninstall_hook`): yalnız bu modülün değiştirdiği tek aksiyondan (`field_operation.action_field_operation`)
  `leaflet_map` view_mode'unu çıkarır; başka aksiyonlara dokunmaz ve hiçbir aksiyonu silmez

Kapsam dışı: yeni model/alan yok, rota optimizasyonu kodu bu modülde yok (rota/waypoint kodları
`field_operation_geolocation` modülündedir).

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli ve `action_field_operation` aksiyonu genişletilir |
| `base_geolocalize` | Adres koordinatları (`partner_latitude` / `partner_longitude`) |
| `soft_web_map` | `leaflet_map` view tipini ve `MapArchParser` / `MapController` / `MapModel` / `MapRenderer` / `MapSearchModel` sınıflarını sağlar |

**`soft_web_map` bu repoda DEĞİLDİR.** Softteknik'in kendi modülüdür, kaynağı `apps/soft/soft_web_map`
altındadır (51 dosya) ve `leaflet_map` görünüm tipini kaydeder. Bu modül kurulmadan `field_operation_map`
kurulamaz; `soft_web_map` ayrıca kurulur ve saha reposuna dahil edilmez.

## 3. Ana Modeller

Yeni model tanımlanmaz; `models/` dizininde tek genişletme vardır.

| Model | Kaynak | Not |
|---|---|---|
| `field.operation` | `field_operation` | `display_address` (compute, store değil) — `models/field_operation.py` |
| `ir.actions.act_window`, `ir.actions.act_window.view` | Odoo base | Aksiyon `view_mode` güncellemesi ve harita görünümü sırası |
| `ir.ui.view` | Odoo base | `leaflet_map` ve devralınan form görünümü |

## 4. Roller ve Güvenlik

- **ACL yok:** Bu modülde `security/` dizini bulunmaz. Modülün kendi modeli olmadığı için ACL dosyası gerekmez.
- `field.operation` erişimi `field_operation` modülünün ACL ve `ir.rule` kayıtlarından gelir
  (worker: atanmış işler, draft hariç tüm statüler; user: kendi dokümanları).
- Harita görünümü için ayrı grup kısıtı yoktur; görünürlük aksiyonu görebilen herkesle aynıdır.

## 5. Ana Akış

Menü eklenmez; harita, mevcut **Field Operation → Field** aksiyonunun görünüm değiştiricisine eklenir.

| Adım | Kayıt | Detay |
|---|---|---|
| Görünüm | `view_field_operation_map` | `model=field.operation`, `name=field_operation.list.map`, arch `<leaflet_map latitude="service_latitude" longitude="service_longitude" limit="80">` |
| Aksiyon güncellemesi | `field_operation.action_field_operation` | `view_mode = kanban,list,form,activity,leaflet_map` |
| Görünüm sırası | `action_field_operation_map_view` | `ir.actions.act_window.view`, sequence 8, view_mode `leaflet_map` |
| Form katkısı | `field_operation_inh_view` | `field_operation.view_field_operation_form` devralınır, `create_date` alanından sonra `display_address` |

Harita işaretçileri ve popup içeriği `soft_web_map` modülünün varsayılanlarıyla çizilir; bu modülün kendi
JS/şablon katmanı yoktur.

## 6. Alan Eşlemeleri / Liste Kolonları

| Alan | Rolü |
|---|---|
| `service_latitude` / `service_longitude` | Harita konumu (kaynak: `field_operation` modeli) |
| `address_id` | Servis adresi; `display_address` bunun üzerinden hesaplanır |
| `display_address` | `leaflet_map` görünümünde ve formda gösterilen adres metni |
| `display_name` | Harita işaretçisi etiketi (`view_field_operation_map` alan listesi) |

## 7. Arama Filtreleri

Bu modül kendi arama/filtre katmanını sağlamaz; harita arama kutusu `soft_web_map` varsayılan davranışını kullanır.

## 8. Test Kapsamı

`tests/test_field_operation_map.py` — `TransactionCase`, `@tagged('post_install', '-at_install')`, 4 test:

| Test | Kapsam |
|---|---|
| `test_display_address_reflects_partner_address` | Adresli kayıtta `_display_address(without_company=True)` sonucunu verir; adressiz kayıtta falsy |
| `test_map_view_and_action_view_record` | `view_field_operation_map` tipi `leaflet_map`; `action_field_operation_map_view` → view_mode `leaflet_map`, sequence 8, doğru `view_id` / `act_window_id` |
| `test_action_view_mode_includes_leaflet_map` | `field_operation.action_field_operation.view_mode` içinde `leaflet_map` var |
| `test_uninstall_hook_removes_only_leaflet_map` | Hook `leaflet_map`'i çıkarır, diğer modların sırasını korur, ikinci çağrıda idempotent kalır ve ilgisiz bir `leaflet_map` aksiyonunu silmez/silmez (daraltma regresyonu) |

Son doğrulanan çalıştırma (map_verify DB, Odoo 19):

```
venv/bin/python odoo/odoo-bin -c v19.conf -d map_verify --http-port 9089 \
  --logfile ... -u field_operation_map --stop-after-init --test-tags /field_operation_map
# odoo.tests.result: 0 failed, 0 error(s) of 4 tests
```

Harita görünümünün gerçek render'ı için JS tour gerekir; bu test kapsamı dışındadır.

## 9. Geliştirici Notları

- Migration dizini yok; veri dosyası yok. `data/` ve `static/src/` (boş/işe yaramaz kalıntılar) temizlendi.
- Görseller: yalnız `static/description/icon.png`, `icon.svg`, `index.html`.
- View tipi mimarisi tamamen `soft_web_map` üzerine kuruludur; bu modül JS içermez.
- i18n: `.pot` / `tr.po` dosyaları `odoo-bin i18n export` ile koddan üretilir. Yeni bir kullanıcıya dönük
  `_()` metni eklenirse `cd /home/tate/odoo/v19 && venv/bin/python odoo/odoo-bin i18n export -c v19.conf
  -d <db> -o i18n/field_operation_map.pot field_operation_map` ile yeniden üretip `tr.po`'yu güncelleyin.
  `i18n/tr.mo` repoda tutulmaz.

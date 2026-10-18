# Field Operation Forms Extension

> Servis formuna harita ve konumlandırma kısayolları — servis adresini koordinattan haritada
> açar, adresi coğrafi olarak konumlandırır.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `apps/saha/field_operation_forms_ext` · 9 dosya · kendi modeli yok (genişletme modülü)

Bu doküman modül kodundan üretilmiştir (manifest + models + views + security + data). Kanıtı
olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

`field.operation.forms` modeline iki eylem ve üç alan ekler; yeni model ya da görünüm tanımlamaz,
yalnız mevcut liste/form görünümlerini genişletir.

- `service_latitude` / `service_longitude` — servis adresinin koordinatları (related, stored)
- `display_address` — şirket satırı olmadan biçimlendirilmiş adres (compute)
- `action_open_map` — kullanıcı tercihindeki harita sağlayıcısıyla yeni sekmede harita açar
- `action_geolocate_address` — servis adresini `geo_localize()` ile konumlandırır ve sonucu
  dürüstçe bildirir (eşleşme yoksa **warning**)
- Liste görünümüne **Open Maps** satır butonu, form button-box'ına **Map** ve **Geolocate**

Kapsam dışı: kayıt kuralı (`ir.rule`) tanımlamaz, cron kurmaz, kendi arama/gruplama görünümünü
eklemez, yeni alanlar için ACL gerektirmez.

<!-- DOLDURULACAK: Standart kurulumda hangi harita sağlayıcıları varsayılan atanıyor (Google Maps / OSM)? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation_forms` | `field.operation.forms` modeli, inherit edilen `field_operation_forms_list_view` ve `field_operation_forms_form_view` kayıtları |
| `field_operation_geolocation` | `res.users.map_website_id` tercihi, `maps.website` modeli (`lat_lon_url`, `requires_api_key`, `api_key`) ve `res.partner.geo_localize()` altyapısı (`base_geolocalize`) |

## 3. Ana Modeller

Modül kendi modelini tanımlamaz; `models/__init__.py` yalnızca `field_operation_forms` modülünü
import eder.

| Model | Rol |
|---|---|
| `field.operation.forms` | **Genişletilir** (`_inherit`): 3 alan + 3 metod |
| `res.users` | `map_website_id` — kullanıcı bazlı harita sağlayıcı tercihi (kaynak modül) |
| `maps.website` | `lat_lon_url` (zorunlu), `requires_api_key`, `api_key` (kaynak modül) |
| `res.partner` | `partner_latitude` / `partner_longitude` — koordinat kaynağı |

## 4. Roller ve Güvenlik

- **Yeni grup / kural yok:** Modülde `security/` dizini yoktur; yüklediği hiçbir güvenlik kaydı bulunmaz. (Eski `security/ir.model.access.csv` var olmayan `operation.forms.route.wizard` modelini işaret ediyordu ve manifest `data` listesinde de yoktu; silindi.)
- **Fiilî erişim:** `field.operation.forms` üzerindeki tüm okuma/yazma yetkisi `field_operation_forms` modülünün `forms_user` / `forms_manager` / portal kural setinden gelir; bu modül yeni kısıt eklemez, mevcut kısıtları gevşetmez.
- **Kullanıcı tercihi bağımlılığı:** `action_open_map` kullanıcının `map_website_id` alanına bağlıdır; alan boşsa işlem `UserError` ile durur. Varsayılan atama `field_operation_geolocation` modülü tarafından kurulum sırasında (`hooks.py`, `models/res_users.py`) yapılır.

## 5. Ana Akış

| Giriş noktası | Kayıt | Davranış |
|---|---|---|
| Liste satır butonu | `view_field_operation_forms_map_list` | `field_operation.forms.route.list`; `//list` içine `action_open_map` butonu (metin "Open Maps") |
| Form button-box — Map | `field_operation_forms_map_message_form_view` | `field_operation_forms.route.form`; `//div[@name='button_box']` içine `action_open_map` (`oe_stat_button`, `icon="fa-map-marker"`) |
| Form button-box — Geolocate | aynı view | `action_geolocate_address` (`oe_stat_button`, `icon="fa-location-arrow"`, `groups="base.group_user"`) |

`action_open_map` kendi URL üretimini yapmaz: `field_operation_geolocation.models.geo_helpers`
içindeki `open_map_action()` çağrılır — kullanıcı sağlayıcısı, "çift sıfır = koordinat yok"
kuralı ve `{LATITUDE}` / `{LONGITUDE}` / `{API_KEY}` yer tutucuları orada tek yerde durur.

`action_geolocate_address` aynı modülün `geolocate_service_address()` +
`geolocation_notification()` çiftini kullanır: eşleşme bulunamazsa **warning** döner. (Eski
kopya, `geo_localize()` eşleşme bulamadığında bile "success" diyordu.)

## 6. Alan Eşlemeleri / Liste Kolonları

| Alan | Tip | Tanım | Not |
|---|---|---|---|
| `service_latitude` | `Float` | `related='address_id.partner_latitude'`, `store=True` | Adres değişince yeniden hesaplanır |
| `service_longitude` | `Float` | `related='address_id.partner_longitude'`, `store=True` | Adres değişince yeniden hesaplanır |
| `display_address` | `Char` | `compute='_compute_display_address'`, `@api.depends('address_id')` | `address_id._display_address(without_company=True)` |

Liste görünümüne yeni kolon eklenmez, form görünümüne yeni alan eklenmez; alanlar buton
bağlamında kullanılır.

## 7. Arama Filtreleri

Bu modül arama görünümü tanımlamaz ve mevcut arama görünümünü değiştirmez.
`field_operation_forms` modülündeki filtre/gruplama seti (My Tasks, My Task, New, Completed, Team,
Assigned Person) aynen geçerlidir; `service_latitude`/`service_longitude` için hazır arama veya
harita domaini yoktur.

## 8. Test Kapsamı

`tests/test_field_operation_forms_shortcuts.py` (**5 test**,
`@tagged('post_install','-at_install')`):

- liste/form arch'larında **Open Maps / Map / Geolocate** butonları var, **WhatsApp** yok;
- harita URL'i kaydın koordinatlarını taşır ve hiç yer tutucu kalmaz;
- çift sıfır "koordinat yok" sayılır (`UserError`);
- `geo_localize()` eşleşme bulamazsa **warning**, bulursa **success** (geokodlayıcı mock'lanır).

## 9. Geliştirici Notları

- `migrations/`, `controllers/`, `wizard/`, `templates/` dizinleri yok; modül yalnız Python model eklentisi ve iki view inherit kaydından oluşur.
- `models/field_operation_forms.py` içinde `_logger` tanımlanır ama hiç kullanılmaz (kaldırıldı).
- Koordinat alanları `store=True` olduğu için adres değişmedikçe yeniden hesaplanmaz; adres değişiminde `@api.depends` üzerinden güncellenir.
- Harita sağlayıcı varsayılanları `field_operation_geolocation` modülünün kurulum kancalarında (`hooks.py`, `models/res_users.py`) kullanıcılara atanır; bu modül varsayılan atamaz, yalnız okur.
- Görseller: `static/description/icon.png` ve `icon.svg`; `portal.png` yoktur (form portalı `field_operation_forms` modülünden gelir).
- **WhatsApp kısayolu kaldırıldı:** `field_operation_whatsapp` henüz hazır değil; bağımlılık ve
  buton (`action_message_send`) bu turda çıkarıldı. Modül hazır olduğunda `depends`'e
  `field_operation_whatsapp` eklenip buton geri konabilir.

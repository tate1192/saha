# Field Operation Geolocation

> Saha operasyonlarına konum (geolocation) ve GPS takip yeteneği ekler: takım canlı
> konumu, konum geçmişi, harita sağlayıcı yapılandırması, rota ve çoklu nokta harita
> bağlantıları; servis formu (`field.operation.forms`) için de aynı harita/konumlandırma kısayolları.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.2.0`
> Modül: `apps/saha/field_operation_geolocation` · 37 dosya · 2 yeni model + 5 genişletme

Bu doküman modül kodundan üretilmiştir (manifest + Python + XML + JS). Kodda kanıtı
olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

- **Harita sağlayıcı soyutlaması:** `maps.website` `{LATITUDE}` / `{LONGITUDE}` yer tutuculu
  URL şablonları ve `provider_type` seçimi tutar; rota ve çoklu nokta URL üretimini belirler.
- **Kullanıcı tercihleri:** `res.users` üzerinde `map_website_id`,
  `multi_locations_map_website_id`, `route_map_website_id`; varsayılan OSM'i arar, yoksa ilk kayıt.
- **Operasyon haritası:** `action_open_map`, `action_show_multi_locations_mark()`,
  `action_show_selected_routes()` (ilk kayıt başlangıç, son kayıt varış) ve `action_geolocate_operation()`.
- **Servis formu kısayolları (bu sürümde eklendi):** `field.operation.forms` üzerinde
  `service_latitude` / `service_longitude` + `action_open_map` ve `action_geolocate_address`;
  listede **Open Maps**, formda **Map** ve **Geolocate** butonları. `field_operation_forms_ext`
  (ayrı modül) bu kopyaları taşıyordu; modül kaldırıldı, mantık burada tek kaynak.
- **Ortak mantık:** iki modelin aynı davranışı paylaşması için `models/geo_helpers.py`
  (düz fonksiyonlar) + `maps.website._get_lat_lon_url()` + `res.users._get_map_provider()`.
  Not: ORM mixin'i (`AbstractModel` + `_inherit` listesi) burada KULLANILAMAZ — alanı olmayan
  soyut mixin `models_to_check` refleksiyonuna girmediği için `ir_model_inherit.parent_id` NULL
  olur ve kayıt defteri yüklenmez (ölçüldü); düz Python mixin'i de Odoo 19'da `__bases__`
  yeniden yazımı yüzünden çalışmaz (bkz. §10).
- **Takım GPS takibi:** `field.operation.team` üzerinde `latitude`, `longitude`, `accuracy`,
  `device_id`, `battery_level`, `signal_strength`, `status`, `is_online` (300 sn kuralı) ile
  `action_start_gps_tracking` / `action_stop_gps_tracking`, `action_show_on_map`,
  `action_show_team_locations`, `action_show_route_history` (son 24 saat, en fazla 50 nokta).
- **Konum geçmişi ve tarayıcı:** `team.location.history` kaydı aynı takım için 300 sn'den sık
  yazılmaz; `gps_tracking.js` içinde `fieldTeamGPS` servisi (`navigator.geolocation`,
  `getBattery`, `connection`), systray ikonu ve start/stop client action kayıtları vardır.
- **Dış servisler:** Adres → koordinat dönüşümü `geo_localize()` ile yapılır; çekirdek
  `base_geolocalize` akışı OpenStreetMap **Nominatim**'i (`nominatim.openstreetmap.org/search`)
  çağırır. Harita/rota bağlantıları yalnızca URL üretimidir, tarayıcıda açılır
  (`openstreetmap.org`, `graphhopper.com`, `google.com/maps`, `bing.com/maps`, `here.com`).
  *Kanıt: `odoo/addons/base_geolocalize/models/base_geocoder.py:83-96`.*

> **Yasal dayanak notu (işletme doldurur — kurulumdan ÖNCE):** Bu modül saha çalışanının
> konumunu toplar ve işler. Teknik gerçekler: (1) takip, kullanıcı backend'e her girişinde
> **otomatik** başlar (systray bileşeni tarayıcı konum iznini ister; ayrıca elle başlat/durdur
> ikonu vardır), (2) vardiya boyunca ~5 dakikada bir konum/batarya/sinyal gönderilir,
> (3) `team.location.history` tablosu **sınırsız büyür** (temizlik/arşiv politikası yok —
> bilinçli bırakıldı), (4) görünürlük kullanıcının kendi takımı + manager ile sınırlıdır
> (kayıt kuralları). KVKK kapsamındaki dayanak (açık rıza / sözleşmenin ifası / meşru menfaat)
> ve çalışan aydınlatma metni bu gerçeklere göre **belgelenmelidir**; bu satır o karar
> verilene kadar açık işarettir (2026-10-15 incelemesi, karar e).

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation`, `field.operation.team`, `service_group_user`, `menu_field_operation_config` |
| `hr` | `hr.employee` doğrudan kullanılır (kullanıcı → takım eşlemesi, `controllers/gps_tracking.py`); artık `field_operation` üzerinden dolaylı değil, açıkça bildirilir |
| `base_geolocalize` | `partner.geo_localize()` ve çekirdek geokodlama akışı |
| `field_operation_forms` | `field.operation.forms` modeli ve form/liste görünümleri; harita ve konumlandırma kısayolları o modelde de sunulur |

## 3. Ana Modeller

| Model | Tür | Not |
|---|---|---|
| `maps.website` | `_name` (yeni) | Harita sağlayıcı kaydı; `_order = sequence, id`; URL yer tutucu doğrulaması `@api.constrains` |
| `team.location.history` | `_name` (yeni) | `team_id` (cascade), `latitude`, `longitude`, `accuracy`, `timestamp`, `battery_level` |
| `field.operation` | `_inherit` | Harita/rota aksiyonları, `address_id` onchange'inde geolocalize |
| `field.operation.forms` | `_inherit` | `service_latitude` / `service_longitude` (related, stored), `action_open_map`, `action_geolocate_address` |
| `field.operation.team` | `_inherit` | GPS alanları, çevrimiçi hesabı, harita aksiyonları |
| `res.users` | `_inherit` | 3 harita sağlayıcı tercihi + `action_set_default_map_settings` |
| `res.partner` | `_inherit` | `action_cron_update_company_geolocations(limit=50)` + `geo_localize_attempted` (son deneme, yeniden deneme penceresi) |

## 4. Roller ve Güvenlik

- Modül kendi yetki kategorisini kurar: **Field Operation Route** (`ir.module.category`,
  sequence 23) altında `group_user_field_operation_route`,
  `group_manager_field_operation_route` (root + admin) ve `field.operation` üzerinde iki
  `ir.rule` (User: `user_id = user.id`, Manager: `[(1,'=',1)]`) — ikinci görünürlük katmanı.
- `security/ir.model.access.csv`: `team.location.history` ve `maps.website` için ofis
  grubu (`field_operation.service_group_user`) **salt-okunur** (`1,0,0,0`); yazma/oluşturma/
  silme ofis yöneticisi (`service_group_manager`) ve yerel Route Manager gruplarındadır.
  Listedeki **Maps** butonu `base.group_user` ile sınırlıdır; aynı şekilde
  `field.operation.forms` listesindeki **Open Maps** ve formdaki **Geolocate** butonları da
  `base.group_user` taşır (**Map** butonu ek yetki gerektirmez, gated değildir).
- **Konum uçları kullanıcının kendi takımıyla sınırlıdır (gizlilik sertleştirmesi):**
  geriye **iki uç** kaldı — `/field_team/get_my_team` (yalnız isteği yapan kullanıcının kendi
  takımı) ve `/field_team/update_gps` (durum/kod yazımı yalnız kendi takımı için; gelen
  enlem/boylam aralık, pil ve seçim değerleri doğrulanır). Bir konum kişisel veridir; bir saha
  çalışanı başka takımın konumunu göremez. Tüm takımları okuyan
  `/field_team/get_positions` ve `/field_team/get_team_positions/<id>` uçları **kaldırıldı**
  (hiçbir çağıranı yoktu; kendi-takım kısıtı yüzünden dispeçere de veri döndürmüyorlardı).
  *Kanıt: `controllers/gps_tracking.py`.*
- **Harita sağlayıcı kayıtları:** `maps.website` ofis grubunda **salt-okunur**; gerçek API
  anahtarı `api_key` alanına `password=True` ile yazılır, yani alan maskeli gösterilir
  (`models/maps_website.py`). Düzenleme ofis/Route **Manager** gruplarındadır. Yönetici
  anahtarı girer; `data/maps_website_data.xml` `noupdate="1"` ile yüklendiğinden yükseltmeler
  bu düzenlemeleri ezmez.
- **Konum geçmişi kayıt kuralı:** `team.location.history` kayıtları (`security/security.xml`)
  *Team Location History: Own Team Only* kuralıyla kullanıcının üye/başkan/lider olduğu
  takıma sınırlanır; *Team Location History: Manager* kuralı yöneticilere tam görünürlük
  verir. Ofis grubu salt-okunur erişir.
- **Cron KAPALI kurulur:** `data/geo_company_cron.xml` (`ir.cron`, `active=False`) modül
  kurulumunda **devre dışı** yüklenir; günlük şirket konumlandırması Ayarlar > Teknik >
  Zamanlanmış Eylemler'den elle etkinleştirilmeden çalışmaz.

## 5. Ana Akış

Tarayıcı tarafı (systray ikonu veya `start_gps_tracking` client action'ı):

| Adım | Çağrı | Detay |
|---|---|---|
| Takım bul | `rpc("/field_team/get_my_team")` | `hr.employee` üzerinden `team_members_ids` / `team_head_id` eşleşen tek takım; aralık sabit **5** dakika |
| Konum al | `navigator.geolocation.getCurrentPosition` | `enableHighAccuracy: true`, `timeout: 10000`, `maximumAge: 0` |
| Gönder | `rpc("/field_team/update_gps", payload)` | `latitude`, `longitude`, `accuracy`, `device_id`, `battery_level`, `status`, `signal_strength`; sunucu aralık/seçim doğrulaması yapar |
| Döngü | `browser.setInterval` | 5 dakikada bir; `stopGPSWatcher()` `clearInterval` çağırır |

Sunucu tarafı: `action_open_map` → `maps.website._get_lat_lon_url()` (+ `{API_KEY}` gerekirse);
`action_show_multi_locations_mark` → `_get_multi_location_marker_url()`;
`action_show_selected_routes` → `_get_route_url(start, waypoints)`; `team.action_show_on_map`
ve `action_show_route_history` harita yoksa OSM / **GraphHopper** URL'ini elle kurar.

**Koordinat kuralı (tek yerde: `geo_helpers.has_point`; kayıt üzerinden `has_coordinates`):** Float alanlarda ORM, veritabanındaki
NULL ile gerçek `0.0`ı ayırt edemez (kolon NULL, okuma `0.0`). Bu yüzden `is None` kontrolü hiç
ateşlenmez; kural **çift sıfır "koordinat yok"** kabul edilir (tam (0,0) bir servis adresi olmaz).
Geçerli `lat=0.0, lon≠0.0` (ekvator) kabul edilir.

**Konumlandırma dürüstlüğü:** `res.partner.geo_localize()` eşleşme bulamazsa hata **atmaz**, bus
bildirimi gönderip `True` döner; ayrıca test modunda hiçbir şey yapmaz. Bu yüzden `action_geolocate_*`
işlemden sonra koordinatlara bakıp **warning** bildirimi döner, kör bir "başarılı" demez.

Geçmiş yazımı sunucu tarafındadır: son kayıttan 300 sn'den az geçtiyse kayıt atlanır,
aksi halde `team.location.history` kaydı oluşturulur. Kurulumda `post_init_hook` mevcut
kullanıcıları tarar; cron tanımı ve günlük çalışma ayrıntısı §8'dedir.

## 6. Alan Eşlemeleri / Liste Kolonları

`field.operation` formuna `service_latitude`, `service_longitude`, `date_localization`
(mevcut `create_date` sonrası) eklenir; `button_box`'a `action_open_map` (fa-map-marker),
listeye **Maps** butonu gelir. Kaynaklar `address_id.partner_latitude`/`partner_longitude`.

`field.operation.forms` görünümlerine: listeye **Open Maps** (`groups="base.group_user"`),
form `button_box`'ına **Map** (fa-map-marker) ve **Geolocate** (fa-location-arrow,
`groups="base.group_user"` — `geo_localize()` caride yazma gerektirir). Butonlar yalnız
buton bağlamında kullanılır; forma `service_latitude`/`service_longitude` alanı eklenmez.

`field.operation.team` formunda yeni **GPS Information** grubu — formda yalnızca şu alanlar
gösterilir:

| Alan | Tip | Not |
|---|---|---|
| `latitude`, `longitude` | Float (10,7) | GPS konumu |
| `accuracy` | Float | Hassasiyet (m), `tracking=True` |
| `last_update` | Datetime | Formda `readonly=1` |
| `timestamp` | Datetime | Formda `readonly=1` |
| `device_id` | Char | Tarayıcıda üretilip `localStorage`'da saklanan kısa cihaz jetonu (`navigator.userAgent` artık gönderilmez) |

Model üzerinde ayrıca GPS grubuna dahil edilmeyen `battery_level` (Integer, yüzde),
`signal_strength` (Selection `0..4`: `No Signal` → `Excellent`), `status`
(`idle` / `moving` / `working` / `break`, header'da badge), `is_online` (Boolean, **store'suz**
compute — `last_update` 300 sn içindeyse `True`; `boolean_toggle readonly="1"`) ve
`location_history_count` (Integer, compute — `button_box`'ta GPS History butonu) alanları
bulunur. `is_online` bilerek store'suzdur: store'lu hâlde yalnız `last_update` yazımında
tazeleniyordu ve ping kesilen takım sonsuza dek "Online" kalıyordu.

`team.location.history` liste kolonları: `timestamp`, `latitude`, `longitude`, `accuracy`,
`battery_level`. `maps.website` liste kolonları: `sequence` (handle), `name`,
`provider_type`, `website_url`, `requires_api_key`, `active`.

## 7. Arama Filtreleri

- Modül yeni arama görünümü/facet tanımlamaz; `maps.website` aksiyonu
  `context={'search_default_active': 1}` ile arşivlenmişleri gizler, liste varsayılan sırası
  `sequence, id`'dir. Operasyon ve takım görünümleri çekirdek arama görünümlerini kullanır.

## 8. Uç Nokta Doğrulamaları ve Cron

- `/field_team/update_gps`: `team_id`, `latitude`, `longitude` zorunlu; enlem `[-90, 90]`,
  boylam `[-180, 180]` aralığında doğrulanır; `battery_level` `0..100` aralığına sıkıştırılır;
  bilinmeyen `status`/`signal_strength` değerleri düşürülür (tüm isteği başarısız etmez).
- Geçmiş kaydı: en fazla 5 dakikada bir (`HISTORY_MIN_INTERVAL_SECONDS = 300`).
- `ir.cron` (günlük şirket konumlandırma) modül kurulumunda **kapalı** yüklenir (bkz. §4);
  konumlandırılamayan cariler `geo_localize_attempted` ile işaretlenip **30 gün** sonra yeniden
  denenir ve Nominatim çağrıları arasında `1.1 sn` beklenir.

## 9. Test Kapsamı

Dört dosya, toplam **33 test** (hepsi `@tagged('post_install','-at_install')`):

- `tests/test_gps_tracking.py` — `TestGpsTrackingEndpoints` (`HttpCase`, uç sözleşmesi) +
  `TestGpsTrackingModels` (`TransactionCase`, model/güvenlik/cron) — **16 test**.
- `tests/test_field_operation_forms_map.py` (`TransactionCase`) — servis formundaki
  harita/konumlandırma kısayolları — **10 test**.
- `tests/test_geolocation_views.py` (`TransactionCase`) — görünüm/widget sözleşmesi
  (`boolean_button` yasağı, arşiv toggle'ı, Geolocate butonu) — **3 test**.
- `tests/test_team_map_actions.py` (`TransactionCase`) — takım tarafındaki iki harita
  aksiyonu ve koordinat kuralı (`lat=0.0` kabul, çift sıfır `UserError`) — **4 test**.

- **Servis formu kısayolları (10 test):** harita URL'inde kaydın koordinatları ve hiç yer tutucu
  kalmaması; `requires_api_key=False` iken URL'de `key=` bulunmaması; **çift sıfırın "koordinat yok"
  sayılması** ve `lat=0.0` (ekvator) kabul edilmesi; harita sağlayıcı seçilmemişse `UserError`;
  koordinatların adres değişimini izlemesi; adres yokken konumlandırma `UserError`'ı; eşleşme
  bulunamazsa **warning**, bulunursa **success** (geokodlayıcı `_geo_localize` mock'lanır);
  liste/form butonlarının çözülen arch'ta bulunması.

- **Uç noktalar:** `get_my_team` kullanıcının kendi takımını döndürür; `update_gps` başka takıma
  yazmayı reddeder, kendi takımına yazmayı kabul eder; geçersiz `status` (`started`) tüm isteği
  düşürmez; enlem `91.0` ve boylam `181.0` reddedilir; `(0.0, 0.0)` geçerli koordinat sayılır.
  (Ölü `get_positions` / `get_team_positions` uçları 2026-10-15'te silindi — hiçbir çağıranı yoktu.)
- **Model/güvenlik:** `maps.website.api_key` `password=True` (maskeli); ofis kullanıcısı
  `maps.website` üzerinde salt-okunur, yönetici yazabilir; `team.location.history` kayıt kuralı
  kullanıcıyı kendi takımıyla sınırlar; günlük cron **pasif** (`active=False`) yüklenir ve
  `res.partner`'ı hedefler; cron yöntemi iş çıkmadığında temiz döner; rota geçmişi 50 nokta
  sınırında en yeni noktaları korur; **`is_online` store'suzdur ve yeni takım Online başlamaz**,
  bayrak `last_update` penceresini izler; operation formunda **Geolocate butonu** çözülen arch'ta
  bulunur.

## 10. Geliştirici Notları

- **Ortak mantık neden mixin değil:** İki model (`field.operation`, `field.operation.forms`) aynı
  davranışı paylaşır ama bu bir `AbstractModel` mixin'i ile yapılamaz: alanı olmayan soyut mixin
  `models_to_check` refleksiyonuna girmez, onu miras alan modeller ise girer; `_reflect_inherits`
  bu yüzden `parent_id` NULL olan bir `ir_model_inherit` satırı yazmaya çalışır ve kayıt defteri
  **yüklenmez** (`NotNullViolation`, ölçüldü — `-u` ile de tetiklenir). Düz Python mixin sınıfı da
  çalışmaz: Odoo 19 `_prepare_setup` içinde `Model.__bases__`'i `_base_classes__` ile değiştirir ve
  `TypeError: __bases__ assignment ... object layout differs` verir. Çözüm: `models/geo_helpers.py`
  içinde düz fonksiyonlar + `maps.website._get_lat_lon_url()` + `res.users._get_map_provider()`;
  modellerde yalnız 2-3 satırlık sarmalayıcı aksiyonlar kalır.
- **Float tuzağı:** ORM, veritabanı NULL'ını `0.0` olarak döndürür; `is None` kontrolü bu yüzden
  ölü koddur (eski hâliyle bu modülde vardı). Kural tek yerde: `geo_helpers.has_point`
  (kayıt üzerinden `has_coordinates`); `field.operation.team` kendi `latitude`/`longitude`
  çiftini aynı fonksiyonla kontrol eder.
- Migration yok (`migrations/` bulunmuyor); çeviri dosyaları
  `i18n/field_operation_geolocation.pot` ve `i18n/tr.po` (**131 `msgid`**, iki dosyada
  `msgid` kümesi birebir aynı). `tr.mo` repoda **tutulmaz**; Odoo kurulumda `.po`'dan derler.
- Varlık: `web.assets_backend` paketine `static/src/js/gps_tracking.js`; `icon.png` + `icon.svg`
  var, manifest `images` yalnızca `icon.png`'i gösterir.
- Satır sonları dosya bazında karışıktır: birçok dosya CRLF (`models/field_operation.py`,
  `models/field_operation_team.py`, `models/res_partner_geo_cron.py`,
  `models/team_location_history.py`, `views/*` ve `data/*` XML'lerinin bir kısmı,
  `static/src/js/gps_tracking.js`), bazıları LF (`models/maps_website.py`,
  `models/res_users.py`, `hooks.py` — CRLF/LF karışık, `__manifest__.py`, `README.md`, `i18n/*`).
- `__pycache__/` ve `.pyc` dosyaları diskte var, `.gitignore` kapsamındadır.

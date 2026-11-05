# Field Operation WhatsApp

> Saha operasyonundan müşteriye WhatsApp mesajı açan sihirbaz + mesaj şablonları + gönderim günlüğü.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `apps/saha/field_operation_whatsapp` · 22 dosya · 3 model (`field.whatsapp.template`, `field.whatsapp.log`, `field.whatsapp.message`)

Bu doküman modül kodundan üretilmiştir (manifest + modeller + wizard + view XML + data + ACL/rule + testler).
Kodda kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

Saha operasyonundan müşteriye WhatsApp mesajı **açan** akışı kurar. **Gerçek bir API entegrasyonu
YOKTUR**: gönderim, tarayıcıyı WhatsApp deep-link'ine yönlendirir, mesajı kullanıcı kendi WhatsApp
oturumunda gönderir (`wizard/field_whatsapp_message.py:224-241`).

- **Şablon yönetimi:** `field.whatsapp.template`; `{alan}` yer tutucuları, kategori, kullanım sayacı;
  6 hazır şablon (`data/field_whatsapp_template_data.xml`, `noupdate="1"`).
- **Gönderim sihirbazı:** `field.operation` formundaki **Whatsapp** butonu → `field.whatsapp.message`
  (buton `field_operation.service_group_user` grubuyla kapılıdır; aksiyon sihirbazın kendisinde tek
  kaynaktır: `field.whatsapp.message._open_action_for`). Servis formunda (`field.operation.forms`)
  buton **yoktur**; modül o modele bağımlı değildir.
- **Mesaj günlüğü:** her açılışta `field.whatsapp.log` kaydı düşer, şablonun `usage_count`'u artar.
- **Opsiyonel servis raporu linki:** "Include Service Report PDF" → `field.operation` servis PDF'i
  üretilir, ek `access_token`'lı olarak kaydedilir ve mesaja **müşterinin açabileceği** link eklenir.
- **Menüler:** şablonlar ve günlükler `field_operation.menu_field_operation_config` altına eklenir.

<!-- DOLDURULACAK: Gerçek WhatsApp Business Cloud API (Meta) entegrasyonu planlanıyor mu, yoksa deep-link akışı kalıcı çözüm mü? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli ve form görünümü, `menu_field_operation_config` menüsü, `contact_mobile` / `address_id` / `partner_id` alanları, `service_group_user` / `service_group_manager` grupları, `field_operation.field_operation_action_pdf` raporu (xmlid) |
Manifest'te `mail` / `report` bağımlılığı **yoktur**; modül `message_post`, `ir.attachment` ve
`ir.actions.report` kullanır ve bunları `field_operation` üzerinden dolaylı alır.

`field_operation_forms` bağımlılığı **kaldırıldı**: buton yalnız `field.operation` formunda. Böylece
modül servis formu kurulu olmayan veritabanlarında da kurulabilir (`field_operation` o modüle bağımlı
değildir; temiz DB'de kurulumla doğrulandı).

## 3. Ana Modeller

| Model | Tür | Özet | Dosya |
|---|---|---|---|
| `field.whatsapp.template` | `_name` | `name`, `template_content` (zorunlu), `active`, `available_fields` (referans metni), `template_category`, `usage_count`; `FIELD_MAPPING`, `replace_template_fields()`, `_get_field_value()`, `action_view_usage()`; **yer tutucu doğrulaması** | `models/field_whatsapp_template.py:9-125` |
| `field.whatsapp.log` | `_name` | `template_id`, `res_model`, `res_id`, `res_name` (compute, store), `contact_mobile` (**temizlenmiş** numara), `message_sent`, `company_id` (zorunlu, şirket kuralının dayanağı), `create_date` ("Opened On") | `models/field_whatsapp_template.py:128-165` |
| `field.whatsapp.message` | `_name` (TransientModel) | `res_model`, `res_id`, `res_name`, `partner_name`, `contact_name`, `contact_mobile`, `message`, `template_id`, `include_report`; `default_get()`, `action_use_template()`, `action_send_whatsapp()`, `_generate_report_link()` | `wizard/field_whatsapp_message.py:20-270` |
| `field.operation` | `_inherit` | `action_message_send()` → sihirbazı `active_model/active_id` ile açar | `models/field_operation.py` |

Yer tutucu eşlemesi (`FIELD_MAPPING`, `models/field_whatsapp_template.py:30-43`):
`partner_name→partner_id.name`, `contact_name→contact_id.name`, `operation_date→start_date`, `subject`,
`description`, `solution`, `name`, `address→address_id.display_name`, `phone→partner_id.phone`,
`sender_company→company_id.name`, `sender_phone→company_id.phone`, `sender_user→user_id.name`.
Bilinmeyen bir `{alan}` **kayıtta reddedilir** (`@api.constrains`, `models/field_whatsapp_template.py:78-97`):
Odoo dolduramadığı yer tutucuyu olduğu gibi müşteriye gönderiyordu.

## 4. Roller ve Güvenlik

| Kayıt | Model | Grup | R/W/C/U |
|---|---|---|---|
| `access_field_whatsapp_message_user` | `field.whatsapp.message` | `field_operation.service_group_user` | 1/1/1/1 |
| `access_field_whatsapp_template_user` | `field.whatsapp.template` | `field_operation.service_group_user` | 1/0/0/0 |
| `access_field_whatsapp_template_manager` | `field.whatsapp.template` | `field_operation.service_group_manager` | 1/1/1/1 |
| `access_field_whatsapp_log_user` | `field.whatsapp.log` | `field_operation.service_group_user` | 1/1/1/**0** |
| `access_field_whatsapp_log_manager` | `field.whatsapp.log` | `field_operation.service_group_manager` | 1/1/1/1 |

*Kanıt:* `security/ir.model.access.csv:2-5`.

- **Çok şirket kuralı (global):** `field.whatsapp.log` kişisel veri (müşteri telefonu + mesaj metni)
  taşıdığı için `[('company_id', 'in', company_ids)]` kuralı vardır; kullanıcı yalnız kendi
  şirketlerinin mesajlarını okur. Kural global olduğu için başka grup kurallarıyla gevşetilemez
  (`security/ir_rule.xml:1-17`). Günlük **silme** yalnız yöneticide.
- **Buton kapısı:** "Whatsapp" butonu `groups="field_operation.service_group_user"` ile yalnız
  sihirbazı açma yetkisi olanlara görünür (`views/field_operation_view.xml:12-16`). Grup olmadan
  formu görebilen kullanıcı tıklayıp `AccessError` alırdı (ölçüldü).
- **Şablonlar içeriktir:** saha kullanıcısı şablonları yalnız okur (1/0/0/0), düzenleme/silme
  yöneticide (1/1/1/1). Sayaç artışı `sudo()` ile yapıldığı için okuma yetkisi akışı bozmaz
  (`security/ir.model.access.csv:3-4`).
- **Yetki yükseltme yok:** üretim/okuma çağıranın yetkisiyle yapılır; tek `sudo()` şablon sayacı
  artışındadır (`wizard/field_whatsapp_message.py:245-247`, gerekçesi yorumda).
- **Kimlik bilgisi yok:** gerçek API olmadığı için token/secret saklanmaz.

## 5. Ana Akış

| Adım | Detay | Kanıt |
|---|---|---|
| 1 | `field.operation` formu → **Whatsapp** → `action_message_send` (context: `default_res_model`, `default_res_id`, `active_model`, `active_id`) | `views/field_operation_view.xml:11-16`, `models/field_operation.py` |
| 2 | Sihirbaz açılır; `default_get` telefonu sırayla alır: `contact_mobile` → `address_id.phone` → `partner_id.phone` | `wizard/field_whatsapp_message.py:111-141` |
| 3 | Şablon seçimi mesajı doldurur (`_onchange_template_id`), alternatif **Use Template** butonu | `:88-108` |
| 4 | **Send WhatsApp Message** (onay diyaloglu): telefon boş/mesaj boş kontrolü, numara **uluslararası forma** çevrilir — `0...` ile saklanan numaraya **kaydın kendi ülkesinin** kodu eklenir (`partner_id` → `customer_id` → `contact_id` → `address_id`, sonra şirket ülkesi; `0530 515 81 42` → `905305158142`), `00...`/`+90...` olduğu gibi bırakılır, **ülke bilinmiyorsa numara hiç değiştirilmez** | `:196-220`, `wizard/field_whatsapp_message.xml:36-40` |
| 5 | `include_report` ise servis PDF'i üretilir, `access_token`'lı ek oluşturulur, link mesaja eklenir | `:150-193` |
| 6 | `field.whatsapp.log` yazılır (temizlenmiş telefon, mesaj metni, şirket), şablon sayacı artar | `:224-247` |
| 7 | Kaynak kayda chatter notu: **"WhatsApp opened for …"** | `:249-256` |
| 8 | Kullanıcı WhatsApp'a yönlendirilir (`act_url`); mobil UA `api.whatsapp.com`, masaüstü `web.whatsapp.com` | `:212-241` |

**Dönüş değerleri:** gönderim her zaman `ir.actions.act_url` (WhatsApp penceresi); rapor dalında
`UserError` yükseltilir (rapor bulunamaz / başka model).

## 6. Alan Eşlemeleri / Liste Kolonları

| Görünüm | İçerik | Kanıt |
|---|---|---|
| Şablon listesi | `name`, `template_category`, `usage_count` (number), `active` (**`boolean_toggle`**) | `views/field_whatsapp_template_view.xml:7-13` |
| Şablon formu | header: Usage (`usage_count != 0`) + `active` toggle; `template_category`, `available_fields`, `usage_count` (readonly), `template_content` | `:16-101` |
| Günlük listesi | `create_date`, `res_name`, `template_id`, `contact_mobile`, `company_id` (çok şirket), `message_sent` | `:124-138` |
| Günlük formu | `res_name`, `template_id`, `contact_mobile`, `create_date`, `res_model`, `res_id`, `company_id`, `message_sent` | `:160-190` |
| Günlük arama | `res_name`, `contact_mobile`, `template_id`, "Field Operations" filtresi, Template/Company gruplama | `:140-158` |
| Sihirbaz formu | To (`partner_name`), `contact_name`, `contact_mobile` (phone), `template_id` + Use Template, `message`, `include_report` | `wizard/field_whatsapp_message.xml:7-45` |

Mesaj gövdesi: HTML alanları (`description`, `solution`) `html2plaintext` ile düz metne çevrilir
(`**kalın**` WhatsApp sözdizimine uyar), kalan değerler `str()` ile yazılır
(`models/field_whatsapp_template.py:99-130`).

## 7. Test Kapsamı

`tests/` — **23 test** (`post_install`):

| Test | Neyi sabitler |
|---|---|
| `test_the_placeholders_are_filled_from_the_record` | `{name}`/`{partner_name}`/`{description}` dolar, HTML düz metne çevrilir |
| `test_an_unknown_placeholder_is_refused_on_save` | Bilinmeyen `{xy}` → `ValidationError` |
| `test_the_shipped_templates_pass_the_validation` | Hazır 6 şablon yeni kuralı geçer |
| `test_the_empty_record_gives_empty_values` | Boş kayıtta çökmez |
| `test_the_form_uses_a_boolean_widget_this_version_has` | `boolean_toggle` var, `boolean_button` **yok** (v19'da ikincisi mevcut değil) |
| `test_the_default_get_prefers_the_operation_contact` | Telefon önceliği + `res_name`/`partner_name` |
| `test_the_phone_falls_back_to_the_service_address` | `address_id` doluysa onun telefonu (`0212 111 22 33`) |
| `test_the_phone_falls_back_to_the_partner` | Kontak ve adres yoksa müşterinin kendi telefonu |
| `test_the_message_is_opened_in_the_mobile_and_desktop_urls` | `api.whatsapp.com` vs `web.whatsapp.com` + `905334445566` |
| `test_a_local_number_gets_the_country_code` | `0530 515 81 42` → link ve günlükte `905305158142` (canlı verinin ~%47'si bu formatta) |
| `test_a_number_with_its_own_code_is_left_alone` | `+90…`, `0090…`, `90…` olduğu gibi kalır (çift kod eklenmez) |
| `test_the_country_comes_from_the_record` | Ülke kaydın kendisinden: Almanya müşterisi + `030…` → `phone=493012345678` (şirket TR olsa da) |
| `test_the_log_keeps_the_cleaned_number_and_the_message` | Günlükte temiz numara, mesaj, şirket, şablon |
| `test_the_chatter_note_says_the_window_was_opened` | Not "WhatsApp opened" der (gönderildi demez) |
| `test_the_template_counter_is_incremented` | `usage_count` +1 |
| `test_an_empty_phone_or_message_is_refused` | Telefon/mesaj boş → `UserError` |
| `test_the_report_link_points_to_the_service_report_with_a_token` | Rapor gerçekten üretilir, ek `public=False` + `access_token`, link tokunlu |
| `test_the_report_link_is_refused_for_another_model` | `field.operation` dışı modelde rapor dalı reddedilir |
| `test_the_log_is_scoped_to_the_company_of_the_record` | Şirket kuralı (superuser olmayan kullanıcıyla ölçülür) |
| `test_the_templates_are_read_only_for_field_users` | Şablon ACL'i: kullanıcı 1/0/0/0, yönetici 1/1/1/1 (6 hazır şablon silinemez) |
| `test_the_report_checkbox_is_hidden_outside_the_operation` | `include_report` yalnız `field.operation`'da görünür (başka modelde rapor üretilemiyor) |
| `test_the_log_unlink_is_manager_only` | ACL: kullanıcı 1/1/1/0, yönetici 1/1/1/1 |
| `test_the_operation_button_is_not_wrapped_in_a_second_button_box` | Buton iç içe ikinci `button_box` açmaz ve `groups="field_operation.service_group_user"` taşır (kapı görünümün ham arch'ından okunur) |

## 8. Geliştirici Notları

- Migration yok; veri `data/field_whatsapp_template_data.xml` (`noupdate="1"`).
- Çeviri: `i18n/field_operation_whatsapp.pot` + `i18n/tr.po` (92 `msgid`, setler aynı). **`.mo` yoktur**
  (Odoo kurulumda `.po`'dan üretir).
- Görsel: `static/description/icon.png` (256×256) + `icon.svg` + `index.html`.
- **Gönderim dürüstlüğü:** Odoo mesajın gittiğini bilmez; günlük ve chatter "pencere açıldı" der.
  Kullanıcı vazgeçerse kayıt yine düşer. Gerçek teslim takibi ancak Cloud API + webhook ile mümkündür.
- **Rapor linki neden token'lı:** ek `public=True` yapılsaydı sıralı id ile numaralandırılıp
  başkalarınca açılabilirdi; `access_token` yalnız linki bilene okuma hakkı verir
  (`wizard/field_whatsapp_message.py:150-177`; core: `ir_binary._find_record`, `ir_attachment._can_return_content`).
- **Servis formu kapsam dışı:** buton yalnız `field.operation` formunda; `field_operation_forms`
  bağımlılığı kaldırıldı, form modeli ne inherited ne de buton hedefi. `field_operation_forms_ext`
  de bu görünüme ikinci bir kopya eklemez (kendi testi bunu doğrular).
  Wizard alan adları (`contact_mobile`, `message`, `template_id`) kırılmamalıdır: `default_get`
  telefonu `contact_mobile` → `address_id.phone` → `partner_id.phone` sırasıyla arar.
- Gerçek API entegrasyonu yapılacaksa: token `ir.config_parameter`'da tutulmalı, webhook'a imza
  doğrulaması eklenmeli, `controllers/__init__.py` + kök `__init__.py` güncellenmelidir.

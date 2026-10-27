# Field Operation Disinfect Form

> Saha servis formları için dezenfeksiyon / biyosidal uygulama kayıtları — tank ve dozaj
> ünitesi satırları, PH/CL ölçümleri, imzalı PDF raporu ve e-posta şablonu.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.1`
> Modül: `apps/saha/field_operation_disinfect` · 21 dosya · 2 yeni model içerir

Bu doküman modül kodundan üretilmiştir (manifest + models + views + security + pdf + i18n).
Kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

`field.operation.forms` (servis formu) kaydına dezenfeksiyon boyutu ekler: form başına PH/CL
ölçüm alanları, satır bazlı tank/dispenser tablosu ve imza alanlı QWeb PDF raporu.

- `field.disinfect.product` — dezenfeksiyon ürün/stok kataloğu (Dispenser / Tank)
- `field.operation.disinfect` — form satırı: temizlik, dezenfeksiyon, ozon, filtre değişimi
- `field.operation.forms` üzerine `disinfect_ids` tablosu + 4 PH/CL alanı
- `field.operation.type` seçimine `disinfect` değeri; form alanları yalnız bu tip seçilince görünür
- `res.company` üzerine **Disinfection Certificate** alanı + QWeb PDF raporu ve e-posta şablonu

Kapsam dışı: cron kurmaz, portal denetleyicisi tanımlamaz, satır modeli için liste/kanban görünümü
sağlamaz.

<!-- DOLDURULACAK: PH ve CL ölçümleri hangi limit/yönetmelik değerlerine göre değerlendiriliyor? -->
<!-- DOLDURULACAK: "Disinfection Certificate" alanına girilen belge numarası PDF'e neden basılmıyor? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation.type` modeli (üzerine `disinfect` seçimi eklenir) |
| `field_operation_forms` | `field.operation.forms` modeli, `forms_user`/`forms_manager` grupları, inherit edilen `field_operation_forms_form_view`, PDF iskeleti `external_forms` şablonu |

## 3. Ana Modeller

| Model | Tür | Ana İçerik |
|---|---|---|
| `field.operation.disinfect` | **Yeni**, `_order = "create_date desc"` | `forms_id`, `product_id`, `cleaning`, `disinfection`, `ozone`, `filter_change`, `tank_dimensions`; `user_id`/`customer_id`/`company_id` → `forms_id` üzerinden `related`; `status` → `forms_id.status` (related, stored, precompute) |
| `field.disinfect.product` | **Yeni** | `name`, `type` (`dispenser`/`tank`), `sequence`, `priority` (`0` Low / `1` High), `active` |
| `field.operation.forms` | `_inherit` | `disinfect_ids` (One2many), `before_ph`, `after_ph`, `before_cl`, `after_cl` (`Char`) |
| `field.operation.type` | `_inherit` | `type` seçimine `("disinfect", "Disinfect")` eklenir |
| `res.company` | `_inherit` | `disinfection_certificate` (`Char`) |

Numara üretimi: `field.operation.disinfect.create()` içinde `ir.sequence` kodu `field.disinfect` çağrılır.
Seri kaydı `data/ir_sequence_data.xml` içinde tanımlıdır (`DIS-` öneki, 5 hane padding, `company_id` boş →
şirketler arası paylaşımlı). `create()` boş / `"/"` / `"New"` gelen adları seri numarasıyla doldurur;
seri kaydı bulunamazsa `_("New")` yazılır.

## 4. Roller ve Güvenlik

Kendi grubunu tanımlamaz; `field_operation_forms` modülünden gelen `forms_user` (Field User) ve
`forms_manager` (Field Manager) gruplarına dayanır.

| ACL — Model | Grup | R/W/C/U |
|---|---|---|
| `field.operation.disinfect` | `field_operation_forms.forms_user` | 1/1/1/0 |
| `field.operation.disinfect` | `field_operation_forms.forms_manager` | 1/1/1/1 |
| `field.disinfect.product` | `field_operation_forms.forms_user` | 1/1/1/0 |
| `field.disinfect.product` | `field_operation_forms.forms_manager` | 1/1/1/1 |

| Kayıt kuralı | Grup | Domain / etki |
|---|---|---|
| `disinfect_user_rule` ("Disinfect: Personal Data") | `forms_user` | `['\|', ('forms_id.team_leader_id','=',user.id), ('forms_id.team_leader_id','=',False)]`; `perm_create=False`, `perm_unlink=False` |
| `disinfect_manager_rule` ("Disinfect: Manager") | `forms_manager` | `[(1,'=',1)]` — tüm veri |
| `disinfect_company_rule` ("Disinfect: Multi-Company") | **grup yok (global)** | `[('forms_id.company_id','in',company_ids)]` |

## 5. Ana Akış

Menüye yeni giriş eklemez; tüm giriş noktaları form içindedir.

| Adım | Kayıt / Metod | Detay |
|---|---|---|
| Servis tipi | `field.operation.type` | `type = 'disinfect'` seçilir |
| PH/CL grubu | `field_operation_forms_disinfect_view` (`//notebook` öncesi) | `service_type != 'disinfect'` iken gizli; "Before Cleaning" ve "After Cleaning" grupları |
| Dezenfeksiyon sekmesi | aynı view (`//notebook` içi) | `<page string="Disinfect" name="disinfect">`, `section_and_note_one2many` widget'ı |
| Satır tablosu | `disinfect_ids` listesi | Ürün, tank ölçüsü ve 4 `boolean_toggle` bayrağı |
| Ürün kataloğu | `action_field_disinfect_product` | **Configuration → Disinfect Product** (sequence 7) |
| PDF | `action_field_disinfect_pdf` | `field.operation.forms` formunda rapor bağlaması (`binding_type=report`) |
| E-posta | `email_field_operation_form_biocidal` | Konu "EK-1 Biyosidal Uygulama Formu", alıcı `object.customer_id.email`, rapor eklenir |

PDF şablonu `field_operation_forms.external_forms` (dış başlık/altlık) şablonunu çağırır, dil
müşteri diline (`doc.customer_id.lang`) sabitlenir.

## 6. Alan Eşlemeleri / Liste Kolonları

Dezenfeksiyon sekmesi satır kolonları (`views/field_operation_forms_view.xml`):

| Kolon | Alan | Not |
|---|---|---|
| Ürün | `product_id` | `no_create` — katalogdan seçilir |
| Tank Ölçüsü | `tank_dimensions` | Serbest metin |
| Disinfection / Cleaning / Ozone / Filter Change | `disinfection`, `cleaning`, `ozone`, `filter_change` | `boolean_toggle` |

PDF tablo kolonları (`pdf/field_disinfect_pdf.xml`): Tank/Dispenser, Dimensions, Disinfection,
Cleaning, Ozone, Filter Change — bayraklar `fa-check-square-o` / `fa-square-o` ikonuyla basılır.
PDF ayrıca `doc.name` (Form No), `doc.start_date`, `doc.customer_id` adı+adresi, `doc.solution` ve
iki imza bloğunu (`staff_signature`/`staff_signed_by`, `customer_signature`/`customer_signed_by`)
yazdırır. Ürün listesi kolonları: `priority` (widget priority), `name`, `type`, `sequence`.

## 7. Arama Filtreleri

| Görünüm | Filtre / Arama |
|---|---|
| `field.disinfect.product.search` | Alanlar: `name`, `type`. Filtre veya gruplama yok. |
| `field.operation.disinfect` | Arama görünümü **tanımlı değil**; satırlar yalnız servis formu içinden yönetilir. |

Ürün seçiminde `no_create`/`no_create_edit` ile yerinde oluşturma kapatılmıştır; satır modeli için
özel domain kısıtı yoktur.

## 8. Test Kapsamı

Test yok: `tests/` dizini bulunmuyor. Öneri iki `TransactionCase`: (1) `field.operation.forms`
üzerinde `disinfect_ids` satırları oluşturup PH/CL alanlarının doğru modelden okunduğunu
doğrulamak; (2) `forms_user` grubundaki kullanıcının `field.operation.disinfect` satırı oluşturma
denemesinin `disinfect_user_rule` nedeniyle `AccessError` verdiğini doğrulamak.

## 9. Geliştirici Notları

- `migrations/`, `tests/`, `controllers/` dizinleri yok; `__init__.py` içindeki `# from . import controllers` satırı yorumda durur.
- `models/__init__.py` beş modülü sırayla yükler: `field_operation_disinfect`, `field_disinfect_product`, `field_operation_form`, `field_operation_type`, `res_company`.
- Manifest yükleme sırası kritiktir ve yorumla belgelenmiştir: `pdf/field_disinfect_pdf.xml`, e-posta şablonundan **önce** yüklenir çünkü şablon `report_template_ids` üzerinden `field_operation_disinfect.action_field_disinfect_pdf` kaydına referans verir. *Kanıt:* `__manifest__.py` satır 36–38.
- Menü kaydı `field_operation_forms.menu_field_operation_forms_config` altına `sequence=7` ile eklenir; kendi kök menüsü yoktur.
- Görseller: `static/description/icon.png`, `icon.svg`, `portal.png`; manifest `images` yalnız `icon.png` gösterir.
- PDF şablonu `field_operation_forms` modülündeki `external_forms` iskeletini kullanır; başlık/altlık düzeni orada tanımlıdır, bu modülde tekrar tanımlanmaz.
- `res.company` görünümünde `responsible_manager` ve `biocidal_certificate` alanları yorumda durur; yalnız `disinfection_certificate` forma basılır. *Kanıt:* `views/res_company_view.xml` satır 10–11.

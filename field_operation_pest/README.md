# Field Operation Pest Form

> Field service operation pest control forms
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.2`
> Modül: `apps/saha/field_operation_pest` · 28 dosya · 2 yeni model + 1 yüklenmeyen model + 7 model genişletmesi

Bu doküman modül kodundan üretilmiştir (manifest + models + views + data + pdf + security).
Kodda kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

Saha servis formlarına (`field.operation.forms`) pestisit/biyosidal uygulama alanlarını, pestisit satırlarını
ve zararlı türü sözlüğünü ekler; pestisit kullanımından stok çıkışı üretir ve "Pest Kontrol Formu" PDF'ini tanımlar.

- Biyosidal uygulama başlıkları: hijyen, istila, izolasyon, depolama, EFK-İFT, monitör, diğer
- Pestisit satırları (`field.operation.pesticide`): ürün, miktar, kullanılan ekipman, otomatik ölçü birimi
- Zararlı türü sözlüğü (`field.operation.pest.type`) + `field.operation` ve form üzerinde etiket alanı
- `field.operation.type` seçimine `pest` değeri eklenir; form grupları bu değere göre gizlenir
- `action_transfer`: pestisit satırlarından `stock.picking` + hareketler üretir, kaynağı müşteri çıkış lokasyonudur
- PDF: `field.operation.forms` modeline bağlı "Pest" raporu (qweb-pdf) — **manifest'te kayıtlı olmadığı için yüklenmez**
- `res.company` üzerine biyosidal yetki belgesi ve mesul müdür alanları

Kapsam dışı: rapor/sablon dosyaları data listesinde olmadığı için kurulumda oluşmaz, ABD/AB biyosidal raporlama
entegrasyonu yoktur, portal arayüzü yoktur.

<!-- DOLDURULACAK: Biyosidal ürünler için hangi stok lokasyonu ve çıkış tipi standart (source/destination)? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli, `field.operation.type` (selection genişletmesi), `service_group_user` grubu, `menu_field_operation_config` menüsü |
| `field_operation_forms` | `field.operation.forms` modeli, `forms_user/forms_all/forms_manager` grupları, `external_forms` PDF şablonu |
| `stock` | `stock.picking`, `stock.move`, `stock.location`, `uom.uom` |

## 3. Ana Modeller

| Model | Dosya | Not |
|---|---|---|
| `field.operation.pest.type` | `models/field_operation_pest_type.py:10` | `name` zorunlu, `unique(name)` kısıtı (`_name_uniq`) |
| `field.operation.pesticide` | `models/field_operation_pesticide.py:4` | Şirket formundan related alanlar, `compute_product_uom` |
| `field.biocidal.equipment` | `models/field_pest_equipment.py:4` | **`models/__init__.py` bu dosyayı import etmez** → model yüklenmez |
| `field.operation` (genişletme) | `models/field_operation.py:5` | `pest_type_ids` (Many2many) |
| `field.operation.forms` (genişletme) | `models/field_operation_forms.py:6` | 9 biyosidal alan, `pesticide_ids`, `pest_type_ids`, `service_type_id`, stok lokasyonları, `action_transfer`, `action_send_mail` |
| `field.operation.type` (genişletme) | `models/field_operation_type.py:4` | `selection_add=[("pest", "Pest")]` |
| `product.template` (genişletme) | `models/product_template.py:7` | `active_ingredient`, `package`, `antidote`, `vendor` |
| `res.company` (genişletme) | `models/res_company.py:4` | `biocidal_certificate`, `responsible_manager` |
| `stock.move` / `stock.picking` (genişletme) | `models/stock.py:5,15` | `field_operation_form_id` bağı |

## 4. Roller ve Güvenlik

`security/ir.model.access.csv` (4 satır):

| Grup | field.operation.pesticide | field.operation.pest.type |
|---|---|---|
| `field_operation_forms.forms_user` | 1,1,1,0 | 1,1,1,1 |
| `field_operation_forms.forms_manager` | 1,1,1,1 | — |
| `field_operation.service_group_user` | — | 1,0,0,0 |

- `forms_user` → `base.group_user` miraslıdır, `forms_manager` → `forms_all` → `forms_user` zinciri ve
  `base.user_root`/`base.user_admin` üyeliği (`field_operation_forms/security/security.xml:13-40`).
- `field.biocidal.equipment` modeli hiç yüklenmediği için ACL satırı da yoktur.
- Kayıt kuralı (ir.rule) bu modülde tanımlanmaz; kısıtlama `field_operation` kurallarından gelir.

## 5. Ana Akış

| Akış | Girdi | Sonuç |
|---|---|---|
| Pestisit sevkiyatı | Form üzerinde `source_location_id` + `destination_location_id` + `pestisit satırları` | Aynı lokasyon uyarısı (`UserError`) → `stock.picking` (`sudo()`) + `stock.move` satırları → `action_confirm()` → `stock_picking_id` forma yazılır |
| Biyosidal e-posta | `action_send_mail` | `service_type == "biocidal"` ise `email_field_operation_form_pest` şablonu ile `send_mail` |
| Form görünümü | Formun `service_type` değeri | `pest` ise biyosidal grup ve **Pesticide** sekmesi görünür |

Varsayılanlar (`@api.model`): çıkış tipi (`code='outgoing'`), kaynak lokasyon (`warehouse.lot_stock_id`),
hedef lokasyon (`usage='customer'`).

## 6. Alan Eşlemeleri / Liste Kolonları

`field.operation.forms` üzerine eklenen alanlar: `hygiene`, `infestation`, `insulation`, `storage`, `efk_ift`,
`monitors`, `others`, `residence`, `place`, `application_method`, `security_precautions` (Html),
`responsible_manager_id` (hr.employee), `application_place` (house/workplace/other), `pesticide_ids`,
`pest_type_ids`, `service_type_id`, `service_type` (related, store, readonly=False), `stock_picking_id`,
`picking_type_id` (zorunlu, `check_company`), `source_location_id`, `destination_location_id`.

`field.operation.pesticide` satır kolonları (form sekmesi, `section_and_note_one2many`):
`product_id` (domain `type = 'consu'`), `product_uom`, `product_qty` (zorunlu).
PDF tablo kolonları: Tedarikçi (`product_id.vendor`), Ürün, Aktif Maddesi, Ambalaj, Antidot, Ölçü Birimi, Miktar.

## 7. Arama Filtreleri

Bu modül kendi listesini eklemez; `field.operation.forms` ve `field.operation` üzerinde görünüm genişletmeleri
yapar. Arama tarafında eklenen filtre yoktur. Zararlı türü sözlüğü görünümü (list/form/search) ve
**Ayarlar → Field Operation → Pest Type** (sequence 5) menüsü bu modülle gelir.

## 8. Test Kapsamı

Test yoktur (`tests/` bulunmaz). Öneri: (a) `pest_type_ids` kopya ad kısıtının doğrulanması, (b) `action_transfer`
sonrası `stock_picking_id` ve hareket satır sayısının kontrolü, (c) kaynak/hedef lokasyon aynıyken `UserError`
beklentisi, (d) `compute_product_uom` davranışı — `TransactionCase` (`@tagged('post_install', '-at_install')`).

## 9. Geliştirici Notları

- Migration dizini yok. Veri dosyaları: `data/uom_uom_data.xml` (4 UoM), `data/email_template.xml` (manifest dışı).
- PDF: `pdf/field_pest_pdf.xml` — `pdf_field_pest` şablonu `field_operation_forms.external_forms` başlık/altlık
  şablonunu çağırır, gövde `field_pest_layout` içindedir. Rapor içeriği (Türkçe etiketlerle, kanıtlı satırlar):
  başlık "Pest Kontrol Formu", "Yetki Belge No" (`company_id.biocidal_certificate`), "Müşteri", "Adres"
  (contact widget: address/phone/email), "Form No" (`name`), "Mesul Müdür" (`company_id.responsible_manager`),
  "Başlama/Bitiş Tarihi" (`dd/MM/YYYY - hh:mm`), "Uygulama Yeri", "Mesken ise Daire Sayısı", "Yapılan Yerin Alanı",
  "Zararlı Türü" (`pest_type_ids`), "Uygulayıcılar" (`person_ids`), pestisit tablosu, "Alınan güvenlik önlemleri…"
  (`security_precautions`), "Ekip Sorumlusu" ve "Müşteri" imza blokları
  (`staff_signature`/`staff_signed_by`, `customer_signature`/`customer_signed_by`).
- Rapor aksiyonu: `action_field_pest_pdf` (qweb-pdf, `field.operation.forms`, `binding_type=report`).
- E-posta şablonu: `email_field_operation_form_pest` (konu "EK-1 Biyosidal Uygulama Formu", gövde metni jenerik
  "Purchase Request ... for approval" şablonundan kopyalanmış görünür, `report_template_ids` ile raporu ekler).
- Görsel: `static/description/` altında `icon.png`, `icon.svg`, `portal.png`, `index.html`; manifest `images` yalnız `icon.png`.
- Zararlı türleri `field.operation` formunda `many2many_tags` + `no_create` ile bağlanır; sözlük yalnız
  Ayarlar menüsünden büyütülür.

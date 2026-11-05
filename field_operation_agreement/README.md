# Field Operation Agreement

> Saha servis işlerine bağlı sözleşme yönetimi — sözleşme kaydı, süre/statü takibi,
> şablon tabanlı metin üretimi ve PDF çıktısı.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`
> Modül: `apps/saha/field_operation_agreement` · 21 dosya · 4 Python sınıfı (3 yeni model + 1 inherit)

Bu doküman modül kodundan üretilmiştir (manifest + models + security + views + pdf + data).
Kodda kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

`field.operation` kayıtlarını bir sözleşmeye (`field.operation.agreement`) bağlar ve
sözleşme metnini şablondan üretir.

- **Sözleşme kaydı:** referans (`AGR/` sequence), ad, tip (maintenance / service / pest_control / other),
  tarih aralığı, tutar, para birimi, müşteri + irtibat kişisi.
- **Statü akışı:** `draft → active → expired / cancelled` ve `action_draft` ile geri dönüş;
  `action_activate` geçmiş bitiş tarihli sözleşmeyi aktive etmeyi reddeder.
- **İş bağlantısı:** `field.operation.agreement_id` alanı iş formuna, listesine ve aramasına eklenir;
  `action_open_operations` ile bağlı işler açılır (`operation_count` akıllı butonu).
- **Şablon motoru:** `field.operation.agreement.template` + `...template.variable`; `{{1}}`,
  `{{2}}` … yer tutucuları onchange ile otomatik tespit edilir (`_onchange_content`),
  değişkenler serbest metin veya nokta notasyonlu alan yolu (`partner_id.name`) olarak çözülür
  (`_render_content`, `_get_field_value`). `action_load_template` sonucu `description` alanına yazar.
- **PDF:** `agreement_pdf` QWeb template'i ve `agreement_action_pdf` rapor kaydı (print menüsüne bağlı).

Kapsam dışı: yenileme/otomasyon (cron yok), sözleşmeye bağlı faturalama, imza toplama akışı
(portal yok — imza alanları yalnız backend formda).

<!-- DOLDURULACAK: Sözleşme tutarı (total_amount) hangi iş kuralına göre belirleniyor (yıllık bedel / iş başı)? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli, `field_operation.service_group_*` grupları, `menu_field_operation_root` / `menu_field_operation_config` menüleri, `view_field_operation_form|list|filter` view'leri |

## 3. Ana Modeller

| Model | `_description` | Dosya |
|---|---|---|
| `field.operation.agreement` | Field Operation Agreement | `models/field_operation_agreement.py` |
| `field.operation.agreement.template` | Field Operation Agreement Template | `models/field_operation_agreement_template.py` |
| `field.operation.agreement.template.variable` | Agreement Template Variable | `models/field_operation_agreement_template.py` |
| `field.operation` (inherit) | — | `models/field_operation.py` (`agreement_id`) |

`field.operation.agreement`: `_inherit = ['mail.thread','mail.activity.mixin']`,
`_order = "create_date desc"`, `_rec_name = "reference"`.
`template.variable` → `template_id` `ondelete='cascade'`.

## 4. Roller ve Güvenlik

`field_operation` modülünün grupları kullanılır; yeni grup tanımlanmaz. `total_amount`
alanı `groups="field_operation.service_group_user"` taşır: saha personeli sözleşme
tutarını okuyamaz (doğrudan RPC okuması `AccessError` alır). ACL
(`security/ir.model.access.csv`, 12 satır):

| Model | Field Worker | Office User | Head Office | Admin |
|---|---|---|---|---|
| `field.operation.agreement` | 1,0,0,0 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 |
| `...agreement.template` | 1,0,0,0 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 |
| `...agreement.template.variable` | 1,0,0,0 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 |

- **Record rule yok:** modülde `ir.rule` tanımı bulunmuyor; `field.operation` üzerindeki
  kurallar devralınır ama sözleşme kayıtları için şirket/kullanıcı bazlı kısıt yoktur —
  `service_group_user` ACL'ine sahip herkes tüm sözleşmeleri görür.
- Menü görünürlüğü: **Agreements** → `service_group_user`;
  **Configuration → Agreement Templates** → `service_group_manager`.

## 5. Ana Akış

Menü yolu: **Field Operation → Agreements** (sequence 8) ve
**Field Operation → Configuration → Agreement Templates** (sequence 5).

| Aksiyon kaydı | Ad | `res_model` | Görünümler |
|---|---|---|---|
| `action_agreement` | Agreements | `field.operation.agreement` | list, form |
| `action_agreement_template` | Agreement Templates | `field.operation.agreement.template` | list, form |

Form başlığı butonları:

| Buton | Metod | Görünürlük |
|---|---|---|
| Activate | `action_activate` | `status in ('draft','expired')` |
| Expire | `action_expire` | `status == 'active'` |
| Cancel | `action_cancel` | `status not in ('cancelled','expired')` |
| Reset to Draft | `action_draft` | `status != 'draft'` |
| Load Template | `action_load_template` | `template_id` doluysa (Terms sekmesi) |

Durum çubuğu: `statusbar_visible="draft,active,expired,cancelled"`.
Sekmeler: Terms & Conditions (şablon seçimi + `description`), Operations (bağlı işler, `editable="bottom"`),
Signature (`signed`, `signed_on`, `signed_by`, `signature` widget). Buton kutusunda `operation_count`
akıllı butonu ve `web_ribbon` (Archived) var; chatter ekli.

`field.operation` tarafına eklenen görünümler: formda `partner_id`'den sonra `agreement_id`
(domain `partner_id` eşleşmesi), listede `partner_id`'den sonra `agreement_id` (`optional="show"`),
aramada `agreement_id` alanı.

## 6. Alan Eşlemeleri / Liste Kolonları

Liste (`view_agreement_tree`): `reference`, `name`, `partner_id`, `agreement_type`, `start_date`,
`end_date`, `status` (badge), `total_amount` (monetary, `sum="Total"`), `operation_count`,
`company_id` (gizli). Dekorasyonlar: `expired`→danger, `cancelled`→muted, `draft`→info.

Şablon listesi: `name`, `agreement_type`, `description`, `active` (gizli).
Değişken listesi (`editable="bottom"`): `name`, `variable_type` (radio), `free_text_value`,
`field_path`, `sample_value`.

Şablon içeriğinde `content` alanı `sanitize=False` ve çeviri kapalı (`translate=False`).

## 7. Arama Filtreleri

| Model | Filtreler |
|---|---|
| Sözleşme | Draft / Active / Expired / Cancelled; Maintenance / Service / Pest Control; My Agreements (`user_id = uid`); Grupla: Status, Type, Customer |
| Şablon | Maintenance / Service / Pest Control; Grupla: Type |

## 8. Test Kapsamı

Test yok: `tests/` dizini bulunmuyor. Öneri: (1) `action_activate` süresi geçmiş sözleşmeyi
reddetmeli, (2) `_render_content` şablondaki `{{N}}` yer tutucularını alan değerleriyle
değiştirmeli, (3) aynı `agreement_type` için iki şablon yüklendiğinde xmlid çakışması olmaması
(veri dosyası tekilliği) — `TransactionCase`, `@tagged('post_install','-at_install')`.

## 9. Geliştirici Notları

- **Migration yok:** `migrations/` dizini bulunmuyor.
- **Sequence:** `field.operation.agreement`, prefix `AGR/`, padding 5, `company_id=False`;
  veri dosyası `noupdate="1"`.
- **Şablon verisi (demo):** `demo/sample_agreement_template.xml` örnek bir CNC bakım sözleşmesi şablonu — yalnız demo kurulumunda yüklenir
  (`{{1}}`-`{{9}}`) ve 9 değişken kaydı oluşturur; gerçek müşteri verisi içermemesi için anonimleştirilmiştir.
- **PDF:** `pdf/agreement_pdf.xml` → `agreement_document` (yardımcı) ve `agreement_pdf` template'leri;
  rapor kaydı `agreement_action_pdf` (`print_report_name`: `Agreement - <reference>`,
  `binding_model_id=model_field_operation_agreement`) — paperformat atanmamış (global varsayılan kullanılır).
- **Cron:** bu modülde `ir.cron` yok.
- **i18n:** `i18n/field_operation_agreement.pot` + `i18n/tr.po` (+ derlenmiş `tr.mo`).
- Görsel: `static/description/` altında `icon.png`, `icon.svg`, `index.html`.

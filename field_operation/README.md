# Field Operation

> Saha servis operasyonunun çekirdeği — iş kaydı, ekip/bölge planlama, durum takibi,
> portal erişimi ve PDF servis teslim formu.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.2.4.0` (tek kaynak: `__manifest__.py`)
> Modül: `field_operation` · 49 dosya · 9 Python sınıfı (6 yeni model + 3 inherit) + portal controller

Doküman modül kodundan üretilmiştir; kanıtsız iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

Suite'in taban modülü: saha servis işini (`field.operation`) kaydeder, planlar ve izler; diğer
`field_operation_*` modülleri bunu `_inherit` eder.

- **Durum makinesi:** `draft → planned → progress → done` (+ `cancel`) ve form başlığındaki
  `action_planned` / `action_progress` / `action_done` / `action_cancel` / `action_draft` butonları.
- **Planlama/atama:** ekip seçilince `_get_team_members` onchange'i ekip üyelerini, ekip liderini
  ve ekip şefini kayda kopyalar.
- **Çakışma/izin kontrolü:** `_check_team_integrity` atanan personelin onaylı iznini (`hr.leave`,
  `state='validate'`) ve aynı zaman aralığındaki başka planned/progress işini engeller.
- **Ana veri:** ekip, bölge, servis tipi, etiket (Configuration menüsü).
- **Portal:** müşteri `/my/list_operations` üzerinden kendi işlerini görür, detayda imza atar,
  PDF indirir; biten işte `service_customer_delivery_mail` ile rapor e-postası gider.
- **Tekrarlı servis:** `service.repeat.wizard` (`dateutil.rrule`) toplu iş üretir; üst sınır 500
  kayıt (`max_recurring_operations` context anahtarı).

Kapsam dışı: sözleşme, taşeron, fatura, stok ve konum toplama ayrı modüllerde.

Servis fiyatı politikası (2026-10-15 kararı): backend'de `service_price` yalnız Head Office grubuna
açık (`views/field_operation_view.xml`); portal'da ise müşteriye **bilinçli olarak** gösterilir
(liste "Fee" kolonu ve detay "Price" alanı). İki görünürlük farkı kasıtlıdır, hata değildir.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `base` | `ir.sequence`, `res.partner/users/company`, `ir.rule` |
| `base_geolocalize` | `partner_latitude/longitude` ve `date_localization` |
| `hr` | `hr.employee` — `person_ids`, `team_head`, ekip üyeleri |
| `hr_holidays` | `hr.leave` — izin çakışması kontrolü |
| `portal` | `portal.mixin`, `CustomerPortal`, portal şablonları |

## 3. Ana Modeller

| Model | `_description` | Dosya |
|---|---|---|
| `field.operation` | Field Operation | `models/field_operation.py` |
| `field.operation.team` | Field Operation Team | `models/field_operation_team.py` |
| `field.operation.region` | Field Operation Region | `models/field_operation_region.py` |
| `field.operation.type` | Field Operation Type | `models/field_operation_type.py` |
| `field.operation.tags` | Service Tags | `models/field_operation_tags.py` |
| `service.repeat.wizard` | Service Repeat Wizard | `wizard/service_repeat_wizard.py` |
| `res.partner` (inherit) | — | `models/res_partner.py` (`field_operation_ids`, `field_operation_count`) |
| `res.users` (inherit) | — | `models/res_users.py` (`field_team_ids`) |
| `res.config.settings` (inherit) | — | `models/res_config_settings.py` (2 grup anahtarı) |
| `FieldOperationPortal` (controller) | — | `controllers/portal.py` (`CustomerPortal` alt sınıfı) |

`field.operation` mixin'leri: `mail.thread`, `mail.activity.mixin`, `portal.mixin`; sıralama
`_order = "create_date desc"`. Etiket ve tip modelleri `models.Constraint("unique (name)")` zorlar.

## 4. Roller ve Güvenlik

Ayrıcalık: **Field Operation** (`res.groups.privilege`, sequence 23).

| Grup | Ad | `implied_ids` | Kapsam |
|---|---|---|---|
| `service_group_worker` | Field Worker | `base.group_user` | Atandığı planned/progress işler |
| `service_group_user` | Office User | Field Worker | Kendi/ofis kayıtları |
| `service_group_all` | Head Office | Office User | Tüm kayıtlar |
| `service_group_manager` | Admin | Head Office | Yapılandırma + `user_root`/`user_admin` |

Gizli teknik gruplar (`field_operation_hidden_privilege`): `group_field_operation_recurring`
(tekrarlı servis) ve `group_field_operation_signature` (dijital imza) — Ayarlar → Field Operation
ekranından açılır (`res.config.settings`).

ACL (`security/ir.model.access.csv`, 15 satır): iş kaydı için Field Worker `1,1,0,0` (create/unlink
yok), Office User / Head Office / Admin `1,1,1,1`, `base.group_portal` `1,0,0,0`; etiket, bölge,
ekip, tip ve sihirbazda Field Worker okuma / Office User ve üstü tam yetki (sihirbaz yalnız Office User).

Record rule (`security/ir_rule.xml`, 5 kural): Field Worker → `person_ids.user_id = user` **ve**
`status in ('planned','progress')`; Office User → `user_id = user` veya boş; Head Office → `(1,'=',1)`;
Portal → `partner_id`/`message_partner_ids` üzerinden `commercial_partner_id`; global multi-company
kuralı `company_id in company_ids`. `service_price`, `region_id`, `create_date` alanları view'lerde
`groups="field_operation.service_group_all"` ile kısıtlıdır.

## 5. Ana Akış

Menü: **Field Operation** (kök, sequence 36, `web_icon` ikonu) → **Services** `action_field_operation`
(worker, seq 3), **Teams** (all, 5), **Customers** `field_operation_partner_action` (all, 8),
**Reporting** (all, 57), **Configuration → Regions / Tags / Type** (manager, seq 3/9/12).
`action_field_operation` görünüm sırası: list (0) → kanban (1) → form (2) → calendar (3) →
graph (4) → pivot (5); `view_mode` ayrıca `activity` içerir (list/kanban/form/calendar/graph/pivot).

| Buton | Metod | Görünürlük / kısıt |
|---|---|---|
| Planned | `action_planned` | `status not in ('progress','cancel','planned','done')` |
| Service | `action_progress` | `status not in ('draft','progress','done','cancel')` |
| Done | `action_done` | `status not in ('draft','planned','done','cancel')`; yazımdan sonra listeye döner |
| Cancel | `action_cancel` | `status not in ('cancel','draft')`, grup `service_group_user` |
| Draft | `action_draft` | `status not in ('draft','planned','done')`, grup `service_group_user` |
| Send Report | `action_send_report_mail` | yalnız `done`; `mail.compose.message` açar |
| Portal | `action_portal_operation` | buton kutusu — `get_portal_url()` |
| Repeat Service | `action_service_repeat_wizard` | grup `group_field_operation_recurring`, `status != 'cancel'` |

Durum çubuğu `statusbar_visible="draft,planned,progress,done,cancel"`, `readonly="1"`; sekmeler
Description, Solution, Signature (grup `group_field_operation_signature`); `web_ribbon` + chatter.

Portal rotaları (`controllers/portal.py`):

| Rota | Tip / auth | İşlev |
|---|---|---|
| `/my/list_operations[/page/<int:page>]` | `http`, `user` | Arama, durum/tarih filtresi, sıralama, pager |
| `/my/operation_detail/<id>` | `http`, `public` | Detay; `_document_check_access` token kontrolü |
| `/my/operation_detail/<id>/operation_sign` | `jsonrpc`, `public` | Yalnız `status == 'done'` kayıt imzalanır |
| `/my/operation_detail/<id>/download_pdf` | `http`, `public` | `field_operation_action_pdf` indirir |

## 6. Liste Görünümü Alanları

Liste (`multi_edit="1" duplicate="false" sample="1"`, `default_order="priority desc, id desc"`):
görünür → `name`, `subject`, `partner_id` (readonly), `contact_mobile`, `team_id`, `start_date`,
`total_work` (float_time), `activity_exception_decoration`, `status` (badge); gizli → `priority`,
`user_id`, `contact_id`, `address_id`, `region_id`, `team_leader_id`, `person_ids`, `id`,
`service_type_id`, `end_date`, `service_price` (grup), `company_id`.
Satır renkleri: `draft`→primary, `planned`→info, `progress`→danger, `done`→success. Kanban:
`default_group_by="status"`, `quick_create="0"`; kartta subject/name/priority/partner/start_date/
tag/status/activity. Ana veri listeleri: Region (`name`, `code`, `manager_id`), Type (`priority`,
`name`, `type`), Tags (yalnız `name`), Team (`sequence` handle, `priority`, `name`,
`team_leader_id`, `region_id`, `team_members_ids`, `company_id`).

## 7. Arama Filtreleri

| Grup | Filtreler |
|---|---|
| Hızlı | My Tasks (`user_id = uid`), Draft, Planned, Progress, Done |
| Tarih | Yesterday, Today, Tomorrow, In Next 7/30 Days, This Week, Last Week, This Month, Last Month (`start_date`), Create Date |
| Grupla | Customer, Service Type, Team, Date (`start_date`) |
| Searchpanel | `status` (çoklu seçim), `service_type_id`, `team_id` |

Arşivli takımlar searchpanel'in `team_id` kategorisinde **görünmez**:
`field.operation.search_panel_select_range` bu alan için
`comodel_domain=[('active', '=', True)]` geçirir. Panel, işleri `team_id`'ye göre gruplayıp
bulduğu değeri gösterdiği için arşivli bir takıma bağlı tek bir iş o takımı panelde
tutabiliyordu; comodel domain'i paneli takımların kendisini okumaya zorlar.

Alan aramaları: `name` ("No", ilike), `partner_id` (`child_of`), `subject` (ilike), `team_id`.
Ek: `res.partner`'da "Services" filtresi (`field_operation_count > 0`) ve kişi listesindeki "Stats"
hücresinde servis sayacı rozeti (`_compute_application_statistics_hook`, `fa-tasks`);
`field.operation.team` aramasında My Teams / Archived / Region / Priority.

## 8. Test Kapsamı

Suite toplam **16 test** (`post_install`, `-at_install`; etiket `field_operation`):

`tests/test_field_operation.py` — `TestFieldOperation(TransactionCase)`, **12 test**: ekip kanban
sayacı `draft` dahil tüm status'leri sayar, izin çakışması `ValidationError` yükseltir, alt kişi
kayıtlarında `field_operation_count` invalidasyonu, partner aksiyon domain'i ile sayacın aynı olması,
portal PDF rapor xml:id'inin varlığı, This Week/Last Week filtrelerinin gerçek pazartesiyi
kullanması, `date_localization`'ın compute ile ezilmemesi, ekip `service_count` takibi, ekip kanban
verisinin tek sorguda toplanması (N+1), tekrarlayan servis sihirbazının UTC saklaması ve kişi
listesindeki "Stats" hücresinin servis rozetini (`application_statistics`) yayması.

`tests/test_search_panel.py` — `TestSearchPanelTeams(TransactionCase)`, **1 test**: arşivli
takım searchpanel'de görünmez, aktif takım görünür.

`tests/test_service_repeat_wizard.py` — `TestServiceRepeatWizard(TransactionCase)`, **3 test**:
aylık "Day of Month" alanının başlangıç tarihini izlemesi ve düzenlenebilir kalması, 500 kayıt
üst sınırının tarihler üretilmeden ÖNCE (islice) uygulanması (`rrule_count=10_000_000` 5 sn altında
reddedilir).

```bash
odoo-bin -c <odoo.conf> -d <test_db> -u field_operation \
  --stop-after-init --test-tags /field_operation
```

## 9. Geliştirici Notları

- **Migration yok**, **cron yok**.
- **Sequence:** kod `field.operation`, prefix `FO/`, padding 5, `company_id=False` (global).
- **Veri dosyaları:** `customer_service_mail.xml` (`mail.template`, `report_template_ids` ile PDF
  ekler), `paper_formats.xml`, `res_groups_privilege.xml` (privilege, `noupdate=1`).
- **PDF:** `pdf/service_work_delivery.xml` → `field_work_delivery_pdf`; rapor kaydı
  `field_operation_action_pdf` (`report_name=field_operation.field_work_delivery_pdf`,
  `binding_model_id=model_field_operation`).
- **Dış Python bağımlılığı:** `dateutil.rrule` (sihirbaz); `external_dependencies` boş — dateutil
  Odoo ile gelir. `xlsxwriter` bu modülde kullanılmaz.
- **i18n:** `i18n/field_operation.pot` + `i18n/tr.po` (derlenmiş `.mo` repoya girmez; Odoo `.po`'yu
  kurulumda derler).
- **Statik:** `static/description/` altında `icon.png`, `icon.svg`, `portal.png`, `index.html`; portal ekran görüntüleri,
   `frontend.scss` / `portal_dashboard.scss` (`web.assets_frontend`).

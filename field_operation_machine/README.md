# Field Operation Machine

> Field service operation machine management
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `field_operation_machine` · 22 dosya · 7 yeni model + 1 model genişletme

Bu doküman modül kodundan üretilmiştir (manifest + models + views + data + security + tests).
Kodda kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

Servis operasyonlarına makine (varlık) kaydı kazandırır: makine kartı, garanti/sigorta takibi,
periyodik bakım planı, yedek parça kullanımı ve QR kod üretimi.

- `field.operation` kaydına `machine_id` ile makine bağlanır; makine künyesi related alanlarla taşınır
- Garanti ve sigorta bitiş tarihinden durum (`active`/`expired`/`none`) + kalan gün hesabı
- QR kod: `MACHINE:{id}|SN:{serial}|BC:{barcode}|NAME:{name}` metninden Python `qrcode` ile üretilir
- Bakım kaydı `MNT/YYYY/00001`, yedek parça kaydı `SPR/YYYY/00001` seri numarası alır
- 4 günlük cron: garanti bildirimi, sigorta bildirimi, yaklaşan bakım bildirimi, periyodik bakım üretimi
- Kaynak tipi "stok" olan yedek parça gerçek bir `stock.move` üretir ve tamamlandığında stoktan düşer

Kapsam dışı: satış/fatura/muhasebe entegrasyonu yok, portal arayüzü yok, rapor tanımı yoktur.

<!-- DOLDURULACAK: Makine marka/model sözlüğü serbest metin kalacak mı, yoksa ürün kartına mı bağlanacak? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli, `service_group_worker/user/all/manager` grupları, `menu_field_operation_root` ve `menu_field_operation_config` menüleri |
| `stock` | `stock.move`, `stock.location` (yedek parça sarfı ve stok hareketi) |
| `product` | `product.template` / `product.product` (makine ürünü, parça ürünü) |
| `hr` | `machine.maintenance.technician_id` doğrudan `hr.employee` kullanır; önceden yalnızca transitive geliyordu |
| Python `qrcode` | `external_dependencies.python` (manifest) — `models/machine_master.py` import eder |

## 3. Ana Modeller

| Model | Dosya | Not |
|---|---|---|
| `machine.master` | `models/machine_master.py` | `mail.thread` + `mail.activity.mixin`, `_order = "name desc"` |
| `machine.document` | `models/machine_master.py` | Makine dosyaları (manuel, teknik çizim, sertifika) |
| `machine.maintenance` | `models/machine_maintenance.py` | `mail.thread` + `activity.mixin`, `_order = "date desc"` |
| `machine.maintenance.schedule` | `models/machine_maintenance.py` | Periyodik bakım planı (gün/hafta/ay/yıl, takvim farkındalıklı `relativedelta`) |
| `machine.spare.part` | `models/machine_spare_part.py` | Yedek parça kullanımı + `stock.move` bağı |
| `machine.spare.part.wizard` (+`.line`) | `models/machine_spare_part.py` | TransientModel, toplu parça ekleme |
| `field.operation` (genişletme) | `models/field_operation.py` | `_inherit`, 18 alan ve 3 aksiyon ekler |

> `machine.maintenance.line` modeli kaldırılmıştır. Kullanılan parçaların tek kaynağı
> `machine.spare.part` (`maintenance_id` ters ilişkisi) üzerinden `machine.maintenance.spare_part_ids`'tir.

## 4. Roller ve Güvenlik

Bakım maliyetleri (`labor_cost`, `parts_cost`, `total_cost`) ve yedek parça fiyatları
(`unit_price`, `subtotal`) `groups="field_operation.service_group_user"` taşır; saha
personeli bu alanları okuyamaz.

`security/ir.model.access.csv` (18 satır) — her model için worker / user / manager satırları:

| Grup | machine.master | document | maintenance | schedule | spare.part | wizard(+line) |
|---|---|---|---|---|---|---|
| `field_operation.service_group_worker` | 1,0,0,0 | 1,0,0,0 | 1,0,0,0 | **satır yok** | 1,0,0,0 | **satır yok** |
| `field_operation.service_group_user` | 1,1,1,1 | 1,1,1,0 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 |
| `field_operation.service_group_manager` | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 |

`security/ir_rule.xml` — `company_id` taşıyan `machine.master`, `machine.document`,
`machine.maintenance`, `machine.maintenance.schedule` ve `machine.spare.part` modelleri için
**global** çok şirket kuralı: `[('company_id', 'in', company_ids)]`. Kural global olduğu için
servis grubundan bağımsız uygulanır ve bir kullanıcı yalnızca erişebildiği şirketlerin kayıtlarını görür.

## 5. Ana Akış

Menü yolu: **Field Operation → Machines** (seq 10) → Machines (10) / Maintenance (20) / Spare Parts (30);
**Field Operation → Configuration → Maintenance Schedules** (seq 10, `field_operation.menu_field_operation_config`).

| Akış | Durumlar | Butonlar |
|---|---|---|
| Makine | `draft → active → maintenance → inactive → scrapped` | Activate (draft), Set to Maintenance (active/inactive), Deactivate (active/maintenance), Scrap (`confirm` diyaloglu, active=False) |
| Bakım | `draft → scheduled → in_progress → done / cancelled` | Schedule, Start, Complete, Cancel — hepsi sunucu tarafı grup (`service_group_user`) ve kaynak-durum guard'ından geçer |
| Yedek parça | `draft → confirmed → done / cancelled` | Confirm (stok ise `stock.move` üretir + rezerve eder), Done (hareketi doğrular → stok düşer), Cancel (taslak/onaylı hareketi iptal eder; tamamlanmışsa ters hareket üretir) |

- **Stok akışı düzeltmesi:** `_create_stock_move` hareketi oluşturup `_action_confirm()` eder;
  `_validate_stock_move` önce `_action_assign()` ile rezerve eder, rezerve miktar talep karşılanmazsa
  `UserError` yükseltir, yeterliyse `picked = True` işaretleyip `_action_done()` çağırır. Odoo 19 çekirdeği
  `_action_done` yalnızca `picked` hareketleri işlediği için bu adım olmadan stok hiç düşmüyordu.
- Yedek parça tamamlandıktan sonra `action_cancel()` ters (`origin_returned_move_id`) hareket doğrular ve
  stok geri gelir; `unlink()` tamamlanmış stok hareketi olan kaydı silmez (`UserError`).
- Sihirbaz (`machine.spare.part.wizard`): satırları taslak kayda çevirir, `action_confirm()` çağırır
  (böylece stok hareketleri de oluşur) ve tekrar çalıştırılmaya karşı korumalıdır (mükerrer kayıt üretmez).
- `action_done` (bakım): tip `preventive`/`periodic` ve `next_maintenance_date` boşsa bugün + 90 gün atanır.
- Cron'lar `data/sequence_data.xml`'de (hepsi 1 günlük): garanti, sigorta, yaklaşan bakım, plan üretimi; üçü
  `mail.mail_activity_data_todo` aktivitesi açar (kullanıcı `partner_id.user_id` yoksa `env.user`).
  Seri kodları: `machine.maintenance` (MNT/%(year)s/, padding 5) ve `machine.spare.part` (SPR/%(year)s/, padding 5).
- Bakım maliyeti: `parts_cost` kullanılan yedek parçaların `subtotal` toplamından (depends `spare_part_ids.subtotal`),
  `total_cost = labor_cost + parts_cost` olarak hesaplanır; parça satırı değiştiğinde bayat kalmaz.

## 6. Alan Eşlemeleri / Liste Kolonları

`field.operation` üzerine eklenen alanlar (`models/field_operation.py`):

| Alan | Kaynak / Not |
|---|---|
| `machine_id` | Makine seçimi, `tracking=True` |
| `machine_display_name`, `machine_product`, `machine_option`, `machine_control_unit`, `control_unit_serial`, `machine_year`, `machine_serial` | `machine_id.*` related + store |
| `alarm_number`, `machine_fault` | Operasyona özel arıza bilgisi |
| `start_warranty_date`, `end_warranty_date`, `warranty_status` | `machine_id.*` related + store |
| `machine_warranty`, `machine_insurance` | Yes/No bayrak, compute + store |
| `spare_part_ids`, `spare_part_count`, `spare_part_total` | `machine.spare.part` ters ilişki + sayı/tutar |

Liste kolonları:
- `machine.master.list`: `name`, `display_name`, `machine_brand`, `machine_model`, `serial_number`, `partner_id`, `warranty_status` (badge), `insurance_status` (badge), `state` (badge); satır kırmızı: `warranty_status == 'expired'`
- `machine.maintenance.list`: `name`, `machine_id`, `partner_id`, `date`, `maintenance_type` (badge), `priority` (widget), `technician_id`, `total_cost`, `state` (badge, 4 renk dekore); `next_maintenance_date` gizli
- `machine.spare.part.list`: `name`, `date`, `machine_id`, `partner_id`, `product_id`, `product_code`, `quantity`, `unit_price`, `subtotal`, `source_type` (badge), `state` (badge)
- `field.operation` listesine `machine_id` (optional="show"), `machine_display_name`, `machine_serial` (optional="hide") eklenir

Form: `field.operation` formuna **Machine** sekmesi (makine künyesi, garanti/sigorta badge'leri, arıza bilgisi,
kullanılan parçalar ve tutar) + taban formun `button_box`'una (xpath `//div[@name='button_box']`) Machine ve
Spare Parts stat butonları eklenir.

## 7. Arama Filtreleri

| Model | Filtreler |
|---|---|
| `machine.master` | Under Maintenance, Warranty Active, Warranty Expired, Insurance Active; grupla: Customer, Warranty Status, State |
| `machine.maintenance` | My Maintenance (`technician_user_id = uid`), Scheduled, In Progress, Completed, Due This Week (7 gün); grupla: Machine, Type, State, Technician, Date |
| `machine.spare.part` | From Stock, Purchased, Warranty, This Month; grupla: Machine, Product, Source Type, Date |
| `field.operation` (devralınan) | `machine_id`, `machine_serial`, Under Warranty, With Machine; grupla: Machine |

Bakım aksiyonu varsayılan filtreleri: `search_default_scheduled` + `search_default_in_progress`.
Makine aksiyonu `search_default_active` gönderir ama arama görünümünde `active` adlı filtre **yoktur** (etkisiz).

## 8. Test Kapsamı

`tests/test_field_operation_machine.py` — `TransactionCase`, `@tagged('post_install', '-at_install')`,
13 test (kurulum sırasında çalışır):

| Test | Doğrular |
|---|---|
| `..._consumption_reduces_stock` | Confirm→Done sonrası `stock_move_id.state == 'done'` ve stok gerçekten azalır |
| `..._insufficient_stock_raises` | Yetersiz stokta `UserError` |
| `...wizard_creates_spare_parts_with_stock_moves` | Sihirbaz kayıtları stok hareketi taşır ve Done stoğu düşürür |
| `...wizard_is_idempotent` | Sihirbaz iki kez çalıştırılınca mükerrer kayıt oluşmaz |
| `...cancel_restores_stock` | İptal, ters hareketle stoğu geri getirir |
| `...unlink_completed_spare_part_is_blocked` | Done hareketli kayıt `unlink` edilemez (`UserError`) |
| `...cron_upcoming_maintenance_schedules_activity` | Yaklaşan bakım cron'u gerçekten aktivite açar |
| `...cron_upcoming_maintenance_with_no_data_does_not_crash` | Boş veride cron çökmez |
| `...parts_cost_recomputes_when_spare_part_changes` | `parts_cost`/`total_cost` bayat kalmaz |
| `...multi_company_isolation` | A şirketi kullanıcısı B şirketinin makinesini görmez |
| `...maintenance_wrong_state_transition_raises` | Yanlış durum geçişi `UserError` |
| `...maintenance_action_requires_service_user` | Yetkisiz kullanıcı `AccessError` |
| `...maintenance_line_model_is_removed` | `machine.maintenance.line` registry'de yok |

## 9. Geliştirici Notları

- Migration dizini yok; veri dosyası `data/sequence_data.xml` (`noupdate="1"`, 2 seri + 4 cron).
- Çeviri: `i18n/field_operation_machine.pot`, `i18n/tr.po` (Odoo 19 başlığı, msgid kümeleri birebir aynı, boş çeviri yok).
- Görsel: `static/description/` altında `icon.png`, `icon.svg`, `index.html`; manifest `images` yalnız `icon.png` gösterir.
  (Referanssız ve modülde portal olmadığı için `portal.png` kaldırılmıştır.)
- `models/__init__.py` sırası: `machine_master → machine_maintenance → machine_spare_part → field_operation`.
- `machine.spare.part._validate_stock_move` içinde `stock.move._action_done()` çağrılır; `stock` modülünde bu metot
  `odoo/addons/stock/models/stock_move.py:2253`'te mevcuttur.

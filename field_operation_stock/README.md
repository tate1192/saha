# Field Operation Stock

> Stock consumption tracking for field operations
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`
> Modül: `field_operation_stock` (saha repo kökü; `addons_path`'te `apps/saha` symlink'i ile) · 14 dosya · 1 yeni model (`field.operation.stock.line`) + `field.operation` genişletmesi

Bu doküman modül kodundan üretilmiştir (manifest + modeller + view XML + sequence data + tests). Kodda
kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

Saha servisinde kullanılan malzemelerin (sarf) kaydını ve stok çıkışını yönetir:

- **Sarf satırları:** `field.operation` formunda "Sarf Malzemeleri" sekmesi; ürün, miktar, birim fiyat, ara toplam ve tüketim tipi girilir. `views/field_operation_view.xml:40-75`
- **İki tüketim tipi:** `serviced` ("Servise Dahil") ve `warranty` ("Garanti / Ücretsiz"). `models/field_operation_stock_line.py:70-79`
- **Maliyet özeti:** servis / garanti / toplam stok maliyeti `field.operation` üzerinde parasal alan olarak hesaplanır. `models/field_operation.py:21-66`
- **Stok çıkışı:** "Sarfı Onayla" butonu draft satırlardan tek bir `stock.picking` (outgoing) üretir, onaylar, atama yapar ve doğrular. `models/field_operation.py:68-75`, `models/field_operation_stock_line.py:180-290`
- **Referans numarası:** `SL` önekli, 5 hane padding'li dizi. `data/sequence_data.xml:4-10`

Kapsam dışı: iade (reverse move) ve tedarik (incoming) otomasyonu, maliyetin faturaya/satış siparişine yansıtılması yok.

<!-- DOLDURULACAK: Sarf malzemesi tek merkez depodan mı düşülür, ekip/araç stok lokasyonu kullanılacak mı? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli + form görünümü (`view_field_operation_form`) ve `service_group_*` grupları |
| `stock` | `stock.picking`, `stock.move`, `stock.picking.type`, `stock.stock_location_stock`, `stock.stock_location_customers` |
| `product` | `product.product` (`default_code`, `uom_id`, `standard_price`, `type`) |
| `uom` (dolaylı) | görünümlerde `uom.group_uom` grubu (`views/field_operation_stock_line_view.xml:16`) |
| `mail` (dolaylı) | `_inherit = "mail.thread"` → chatter (`models/field_operation_stock_line.py:11`) |

## 3. Ana Modeller

| Model | Tür | Özet | Dosya |
|---|---|---|---|
| `field.operation.stock.line` | `_name` (+ `mail.thread`) | Sarf satırı: `name` (SL dizi), `operation_id`, `partner_id` (related, store), `product_id`, `product_code` (related), `product_uom_id`, `quantity`, `unit_price`, `subtotal` (compute, store), `currency_id`, `consumption_type`, `stock_move_id`, `stock_picking_id`, `state`, `notes`, `company_id` | `models/field_operation_stock_line.py` |
| `field.operation` | `_inherit` | `stock_line_ids` (O2m, `:12-16`), `stock_line_count` (`:17-20`), `total_stock_cost` / `total_warranty_cost` / `total_stock_all` (`:21-38`); `action_confirm_stock()`, `action_view_stock_lines()`, `action_view_stock_pickings()` | `models/field_operation.py` |

| Alan | Hesap/kural | Kanıt |
|---|---|---|
| `subtotal` | `quantity * unit_price` (`@api.depends`, store) | `models/field_operation_stock_line.py:60-64,110-113` |
| `unit_price` | Ürün seçilince `standard_price` ile doldurulur (`@api.onchange`) | `models/field_operation_stock_line.py:56-59,115-121` |
| `name` | `create()` içinde `ir.sequence` kodu `field.operation.stock.line` | `models/field_operation_stock_line.py:128-137` |
| `quantity` | `> 0` zorunlu (`@api.constrains`) | `models/field_operation_stock_line.py:122-127` |
| `state` | `draft → confirmed → done` / `cancelled` | `models/field_operation_stock_line.py:92-102,138-169` |
| `total_stock_cost` / `total_warranty_cost` / `total_stock_all` | `state in ('confirmed','done')` satırların `subtotal` toplamı, tüketim tipine göre; toplam = ikisinin toplamı (store) | `models/field_operation.py:45-66` |

<!-- DOLDURULACAK: Maliyet hesabında draft satırlar neden hariç, "confirmed" satırlar neden dahil — iş kuralı bu mu? -->

## 4. Roller ve Güvenlik

| Kayıt | Grup | İzin (R/W/C/U) | Kanıt |
|---|---|---|---|
| `access_field_operation_stock_line_worker` | `field_operation.service_group_worker` | 1/0/0/0 | `security/ir.model.access.csv:2` |
| `access_field_operation_stock_line_user` | `field_operation.service_group_user` | 1/1/1/1 | `security/ir.model.access.csv:3` |
| `access_field_operation_stock_line_manager` | `field_operation.service_group_manager` | 1/1/1/1 | `security/ir.model.access.csv:4` |

- `security/ir_rule.xml` **tek bir global çok şirket kuralı** tanımlar: `field.operation.stock.line` kayıtları `company_ids` listesindeki şirketlerle sınırlanır (`security/ir_rule.xml:12-17`); kural `global=True` olduğu için hiçbir grubun kuralıyla gevşetilemez (machine modülündeki desenin aynısı).
- Modül yeni `res.groups` tanımlamaz; mevcut `field_operation.service_group_*` gruplarını kullanır.
- Akıllı buton, sekme ve "Sarfı Onayla" butonunda grup kısıtı yok (`views/field_operation_view.xml:12-48`); saha çalışanı (worker) satırı **görür** ama ACL gereği yazamaz, buton tıklanırsa `AccessError` beklenir.
- **Para alanları saha personeline kapalıdır:** `field.operation` üzerindeki `total_stock_cost`, `total_warranty_cost`, `total_stock_all` ile sarf satırındaki `unit_price`/`subtotal` alanları `groups="field_operation.service_group_user"` taşır. Worker bu alanları `fields_get`'te görmez, doğrudan okuma `AccessError` alır.
- Maliyet alanları `groups="field_operation.service_group_all"` ile sınırlıdır (`views/field_operation_view.xml:30-35`).

## 5. Ana Akış

**Sarf girişi → onay → stok çıkışı → maliyet**

| Adım | Detay | Kanıt |
|---|---|---|
| 1 | `field.operation` formu → "Sarf Malzemeleri" sekmesi → `stock_line_ids` inline liste (`editable="bottom"`), context `default_operation_id` / `default_company_id` | `views/field_operation_view.xml:49-74` |
| 2 | Ürün seçimi `uom_id` + `standard_price` + görünen adı doldurur; `product_id` domain `type in ('consu','product')` | `models/field_operation_stock_line.py:33-38,115-121` |
| 3 | Kayıt `SL00001…` referansı alır | `models/field_operation_stock_line.py:128-137`, `data/sequence_data.xml:4-10` |
| 4 | "Sarfı Onayla" (`action_confirm_stock`, `invisible="status in ('cancel','done')"`, onay diyaloglu) | `views/field_operation_view.xml:42-47` |
| 5 | Draft satır yoksa `UserError("There are no draft stock lines to confirm.")` | `models/field_operation.py:71-74` |
| 6 | `_create_stock_picking(draft_lines)`: kaynak `stock.stock_location_stock`, hedef `stock.stock_location_customers`, picking type `code='outgoing'` ve servis şirketine ait | `models/field_operation_stock_line.py:190-222` |
| 7 | Picking oluşturulur, `action_confirm()`, `action_assign()`; atanamayan move varsa `UserError("Insufficient stock for: …")` | `models/field_operation_stock_line.py:236-254` |
| 8 | Atanan move'larda `quantity = product_uom_qty` **ve `picked = True`**, sonra `_action_done()`; doğrulama hatası `UserError("Stock picking could not be validated…")` | `models/field_operation_stock_line.py:256-273` |
| 9 | Satırlar `state = 'done'` + `stock_move_id` ile güncellenir; `total_stock_*` yeniden hesaplanır | `models/field_operation_stock_line.py:275-285`, `models/field_operation.py:50-66` |

Yan akışlar: `action_view_stock_lines()` servisin sarf satırlarını açar (`models/field_operation.py:77-88`); `action_view_stock_pickings()` tek picking varsa form, çoksa liste döner (`models/field_operation.py:90-107`). Satır formundaki **Confirm** butonu **kaldırıldı** (2026-10-11 kararı): yalnız durum değiştirip stok hareketi üretmediği için satırı "confirmed" durumunda bırakıyordu ve operation akışı yalnız `draft` satırları aldığından o satır bir daha stoğa gidemiyordu (buna rağmen maliyete giriyordu). Tek akış: operation formu → "Sarfı Onayla". `action_confirm` metodu yalnız RPC düzeyinde durum geçişi olarak duruyor (`models/field_operation_stock_line.py:138-150`).
- `done` satır **silinemez** (`unlink` override, `models/field_operation_stock_line.py:152-168`) — doğrulanmış stok hareketinin tek izi o satırdır; draft satırlar serbestçe silinebilir.

### 5.1 Odoo 19 stok API notları (P0 düzeltmesi — 2026-10-11)

Akış v19'da iki noktadan kırılıyordu; modül **kurulabiliyor ama hiçbir iş yapamıyordu**. İnceleme raporu:
`field_operation_stock_inceleme_2026-10-11.md`.

1. **`stock.move` üzerinde `name` alanı v19'da yoktur** (v18'de vardı) → picking oluşturma
   `ValueError: Invalid field 'name' on model 'stock.move'` ile düşüyordu; `name` anahtarı kaldırıldı.
2. **Ölçü birimi alanı `stock.move`'da `product_uom`'dur** (`product_uom_id` değil; o ad
   `stock.move.line`'a aittir) → `ValueError: Invalid field 'product_uom_id'` düzeltildi.
3. **`picked` olmadan doğrulama yoktur:** `stock.move._action_done` yalnız `picked = True` move'ları
   doğrular (`odoo/addons/stock/models/stock_move.py:2282-2286` — bu kural **18.0'da da aynıydı**,
   v19 yeniliği değil: `v18/odoo/addons/stock/models/stock_move.py:2091` birebir aynı filtre); sadece
   `quantity` yazıldığında transfer `assigned` kalıyor, **stok çıkmıyor**, ama sarf satırı `done`
   işaretleniyordu (sessiz veri bozulması). `move.picked = True` eklendi (`models/field_operation_stock_line.py:262`).

## 6. Alan Eşlemeleri / Liste Kolonları

`field.operation` formu:

| Konum | Alanlar | Kanıt |
|---|---|---|
| Akıllı buton | `action_view_stock_lines` → `stock_line_count` / "Sarf" | `views/field_operation_view.xml:12-24` |
| Sağ grup (`total_work` sonrası) | `total_stock_cost`, `total_warranty_cost`, `total_stock_all` (monetary) | `views/field_operation_view.xml:29-36` |
| Sekme (signature sonrası) | `stock_line_ids`: `product_id`, `product_uom_id`, `quantity`, `unit_price`, `subtotal`, `consumption_type` (badge), `stock_picking_id`, `state` (badge), `notes` (optional hide), `company_id` (gizli) | `views/field_operation_view.xml:54-73` |

Sarf satırı listesi (`views/field_operation_stock_line_view.xml:9-29`): satır renkleri `state == 'done'` yeşil, `'confirmed'` sarı, `'cancelled'` soluk; `consumption_type` badge'inde `serviced` mavi, `warranty` yeşil.

Sarf satırı formu (`views/field_operation_stock_line_view.xml:38-74`): header'da Confirm / Cancel + `statusbar_visible="draft,confirmed,done"`; `operation_id` yalnız context'te `default_operation_id` varsa gizlenir; `currency_id`, `stock_move_id`, `company_id` gizli; `chatter` var.

## 7. Arama Filtreleri

`field.operation.stock.line` arama görünümü (`views/field_operation_stock_line_view.xml:85-102`):

| Tür | Öğeler |
|---|---|
| Arama alanları | `name`, `product_id`, `operation_id`, `partner_id` |
| Durum filtreleri | Draft `state='draft'`, Confirmed `state='confirmed'`, Done `state='done'` |
| Tüketim tipi filtreleri | "Servise Dahil" `consumption_type='serviced'`, "Garanti / Ücretsiz" `consumption_type='warranty'` |
| Gruplama | Consumption Type, State, Product, Operation |

`field.operation` tarafına ek filtre eklenmez. `action_field_operation_stock_line` ("Stock Consumption", `list,form`) aksiyonu tanımlı ancak **menü kaydı yoktur**; erişim yalnız servis formundaki akıllı buton üzerindendir.

## 8. Test Kapsamı

`tests/test_field_operation_stock.py` (`post_install`, `TransactionCase`, **13 test — YEŞİL**):

| Test | Neyi korur |
|---|---|
| `test_confirm_consumes_stock` | **P0 regresyonu:** onaydan sonra move `done` + `picked`, picking `done`, satır `done`; kaynak stok 3 birim azalır, hedef (müşteri) konumda 3 birim görünür |
| `test_confirm_uses_the_current_stock_move_field_names` | `stock.move`'da `name` **yok**, `product_uom` **var**; picking bu adlarla kurulabiliyor |
| `test_confirm_without_stock_leaves_nothing_behind` | Yetersiz stokta `UserError` + savepoint geri dönüşü: satır `draft` kalır, picking/move kalmaz, stok değişmez |
| `test_confirm_requires_a_draft_line` | İkinci onay denemesi `UserError` |
| `test_two_lines_of_the_same_product_move_the_total` | Aynı üründen iki satır tek (birleşmiş) move'da toplanır, toplam miktar çıkar |
| `test_reference_is_taken_from_the_sequence` | `SL\d{5}` referansı ve tekilliği |
| `test_quantity_must_be_positive` | `quantity > 0` kısıtı |
| `test_subtotal_and_operation_costs_are_split_by_consumption_type` | Draft satırlar toplama **girmez**; onaydan sonra servis/garanti/toplam ayrışır |
| `test_a_completed_line_cannot_be_cancelled` | `done` satır iptal edilemez → maliyet toplamı korunur |
| `test_a_completed_line_cannot_be_deleted` | `done` satır `unlink` edilemez; satır ve move durur, maliyet korunur |
| `test_a_draft_line_can_be_deleted` | Draft satır serbestçe silinebilir (guard fazla geniş değil) |
| `test_the_line_form_has_no_manual_confirm_button` | Satır formundaki elle `Confirm` kaldırıldı → tek akış operation butonu |
| `test_multi_company_isolation` | Çok şirket kuralı: A şirketi kullanıcısı B'nin sarf satırını görmez |

## 9. Geliştirici Notları

- Migration yok (`migrations/` bulunmuyor); veri: `data/sequence_data.xml` (`noupdate="1"`).
- Çeviri: `i18n/field_operation_stock.pot` + `i18n/tr.po` üretildi (`odoo-bin i18n export`, 76 msgid; iki
  dosyanın msgid seti birebir aynı). **Karar gereği metinler değiştirilmedi**: seçenek/sekme/buton
  metinleri Türkçe, geri kalanı İngilizce kalıyor; `tr.po` şu an yalnız iskelet (74/76 msgstr boş) —
  İngilizce metinler Türkçeye çevrilmek istenirse dosya hazır.
- Görsel: `static/description/icon.png` (256×256, suite ikonunun aynısı — md5 `8a1c447c…`) ve `index.html`.
- View çapaları isim tabanlıdır: akıllı buton `//div[@name='button_box']`, maliyet alanları
  `//field[@name='total_work']` (form içinde tek geçiyor), sekme `//notebook/page[@name='signature']`.
- Modül dışı tüketici yok: `field.operation.stock.line` ve `total_stock_*` alanlarını `apps/` + `custom/` içinde başka modül kullanmıyor (grep ile doğrulandı), ancak `field_operation_forms` form görünümünü miras aldığı (`field_operation_forms/views/field_operation_view.xml:20`) için xpath hedefleri kontrol edilmeli.
- Onay akışında stok yetersizliği tüm transaction'ı geri alır (`UserError`); kısmi picking bırakmaz (testle doğrulandı).

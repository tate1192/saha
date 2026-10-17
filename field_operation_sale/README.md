# Field Operation Sale

> Field Operation Sale integration
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.3`
> Modül: `apps/saha_legacy/field_operation_sale` · 30 dosya · 1 yeni model (`field.operation.create.sale.wizard`) + 5 `_inherit`

Bu doküman modül kodundan üretilmiştir (manifest + modeller + view XML + i18n). Kodda kanıtı
olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

Saha servisi (`field.operation`) ile satış/fatura tarafı arasında **iki yönlü** köprü kurar:

- **Servis → Satış:** tamamlanmış (`status = 'done'`) saha işinden tek butonla satış siparişi üretimi (wizard). `wizard/create_sale_wizard.py:36-70`
- **Satış → Servis:** `sale.order` üzerindeki **Service** butonu ile her ürün satırına karşılık ayrı `field.operation` kaydı üretimi. `models/sale_order.py:49-80`
- **Fatura bağı:** satıştan doğan faturaya servis referansını taşır, fatura formuna "Services" akıllı butonu ekler. `models/sale_order.py:42-47`, `models/account_move.py:7-24`
- **Ürün eşlemesi:** ürün kartında `service_type_id` ile ürün → servis tipi bağlantısı. `models/product_template.py:7`
- **Ayarlar:** grup bazlı özellik anahtarı + varsayılan satış ürünü parametresi. `models/res_config_settings.py:7-19`

Kapsam dışı: fiyat listesi/kampanya hesabı ve otomatik fatura/sipariş onayı yok — siparişler `draft` açılır (`wizard/create_sale_wizard.py:45-58`).

<!-- DOLDURULACAK: Servis → satış dönüşümünde ticari kural ne (her zaman yeni sipariş mi, mevcut siparişe ekleme mi)? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation`, `field.operation.type`, `service_group_all` / `service_group_user` / `service_group_manager` grupları, `view_field_operation_list` / `view_field_operation_form`, wizard aksiyonunun `binding_model_id` hedefi |
| `sale` | `sale.order`, `sale.order.line`, `sale.view_order_form`, `_prepare_invoice` |
| `account` (dolaylı) | `views/account_move_view.xml:6` → `account.view_move_form` mirası; `account` doğrudan `depends`'te değil, `sale` üzerinden gelir |
| `product` (dolaylı) | `views/product_template_view.xml:6` → `product.product_template_form_view` |

## 3. Ana Modeller

| Model | Tür | Eklenenler / davranış | Dosya |
|---|---|---|---|
| `field.operation` | `_inherit` | `sale_id` (M2o `sale.order`), `sale_count`, `action_view_sale()` | `models/field_operation.py` |
| `sale.order` | `_inherit` | `field_operation_ids` (O2m `sale_id`), `field_operation_count`, `order_types` (Selection `service`/`stock`), `show_field_operation()`, `_prepare_invoice()`, `create_sale_service()` | `models/sale_order.py` |
| `account.move` | `_inherit` | `field_operation_count`, `field_operation_id`, `show_field_operation()` | `models/account_move.py` |
| `product.template` | `_inherit` | `service_type_id` (M2o `field.operation.type`) | `models/product_template.py` |
| `res.config.settings` | `_inherit` | `group_field_operation_sale_enabled`, `field_operation_sale_default_product_id` | `models/res_config_settings.py` |
| `field.operation.create.sale.wizard` | `_name` (TransientModel) | `operation_ids`, `product_id`, `default_get()`, `action_create_sale()` | `wizard/create_sale_wizard.py` |

## 4. Roller ve Güvenlik

- **Grup:** `group_field_operation_sale_enabled` ("Field Operation Create Sale"), gizli privilege kategorisinde tanımlı (`security/security.xml:3-12`); kullanıcı grubu Settings anahtarı üzerinden alır (`models/res_config_settings.py:7-11` → `implied_group`).
- **Wizard ACL:** `access_field_operation_create_sale_wizard` → `field_operation.service_group_user`, tam yetki (R/W/C/U). `security/ir.model.access.csv:2`
- **Buton görünürlüğü:** "Create Sale" → `group_field_operation_sale_enabled` + `invisible="status not in ('done',)"` (`views/field_operation_view.xml:31-36`); "Sale" akıllı butonu ve `sale_id` alanı → `field_operation.service_group_all` (`views/field_operation_view.xml:26,39`); Settings bloğu → `field_operation.service_group_manager` (base: `field_operation/views/res_config_settings_view.xml:12`).
- **Kayıt kuralı:** modül kendi `ir.rule` kaydını tanımlamaz; erişim `field_operation` kural setine ve `field.operation` / `sale.order` ACL'lerine bağlıdır.
- **Sunucu tarafı kontrol (2026-10-09):** grup yalnız UI'da değil, modelde de uygulanıyor: `action_create_sale` ve `create_sale_service`, `group_field_operation_sale_enabled` yoksa `AccessError` yükseltir.

<!-- DOLDURULACAK: Servis → satış dönüşümünü yalnız yönetici mi yapabilmeli, saha kullanıcısı da yetkili mi? -->

## 5. Ana Akış

### Akış A — Servisten satış üretimi (wizard)

| Adım | Detay | Kanıt |
|---|---|---|
| 1 | `status = 'done'` kayıtta **Create Sale** butonu | `views/field_operation_view.xml:31-36` |
| 2 | Wizard açılır; `active_ids` → `operation_ids` | `wizard/create_sale_wizard.py:26-28` |
| 3 | Varsayılan ürün `ir.config_parameter` `field_operation_sale.default_product_id`'den okunur | `wizard/create_sale_wizard.py:29-33` |
| 4 | `action_create_sale`: her servis için 1 `sale.order` (`partner_id`, `order_types='service'`, `note ← description`); bağ ters yönden (`operation.sale_id`) kurulur | `wizard/create_sale_wizard.py:159-185` |
| 5 | Her siparişe 1 satır: `name ← subject`, `price_unit ← service_price`, `product_uom_qty = 1` | `wizard/create_sale_wizard.py:52-58` |
| 6 | `operation.sale_id = sale.id`; dönüş domain'i `[('id','in',created_sales.ids)]` | `wizard/create_sale_wizard.py:60-70` |

Servis seçilmezse `UserError('Please select at least one field operation.')` (`wizard/create_sale_wizard.py:39-40`).

### Akış B — Siparişten servis üretimi

| Adım | Detay | Kanıt |
|---|---|---|
| 1 | `sale.order` header'ında **Service**; `order_types = 'service'` ve `field_operation_count == 0` ise görünür | `views/sale_order_view.xml:9-14` |
| 2 | `create_sale_service()` her ürün satırı için ayrı `field.operation` yaratır | `models/sale_order.py:59-75` |
| 3 | Aktarım: `partner_id`, `sale_id`, `subject = "{ürün adı} {satır adı}"`, `start_date = bugün`, `description ← order.note`, `service_type_id ← line.product_id.service_type_id`, `service_price ← line.price_subtotal` | `models/sale_order.py:63-74` |
| 4 | Ürün satırı yoksa `UserError('There are no product lines to create service operations.')` | `models/sale_order.py:77-78` |

### Akış C — Fatura bağı

`_prepare_invoice()` servis referansını faturaya taşır (`models/sale_order.py:35-46`); `account.move` formunda `field_operation_count == 0` değilse **Services** butonu görünür (`views/account_move_view.xml:8-13`) ve `show_field_operation()` ilgili servisleri listeler (`models/account_move.py:16-24`).

<!-- DOLDURULACAK: `service_price` ile ürünün satış fiyatı çelişirse hangisi esas alınmalı? -->

## 6. Alan Eşlemeleri / Liste Kolonları

| Kaynak | Hedef | Not |
|---|---|---|
| `field.operation.partner_id` | `sale.order.partner_id` | wizard |
| `field.operation.description` | `sale.order.note` | wizard (`or ''`) |
| `field.operation.subject` | `sale.order.line.name` | wizard |
| `field.operation.service_price` | `sale.order.line.price_unit` | `or 0.0` |
| `sale.order.line.price_subtotal` | `field.operation.service_price` | ters akış |
| `product.template.service_type_id` | `field.operation.service_type_id` | ters akış |

| Görünüm | Eklenen | Kanıt |
|---|---|---|
| `field.operation` listesi | `sale_id` (`optional="hide"`, `name` sonrası) | `views/field_operation_view.xml:4-13` |
| `field.operation` formu | "Sale" akıllı butonu, header'da "Create Sale", `create_date` sonrası `sale_id` (`no_create`) | `views/field_operation_view.xml:15-42` |
| `sale.order` formu | `order_types`, "Services" akıllı butonu | `views/sale_order_view.xml:16-22` |
| `product.template` formu | `service_type_id` (`type == 'service'` ise zorunlu) | `views/product_template_view.xml:8-12` |
| `res.config.settings` | "Create Sale Feature" + "Default Sale Product" | `views/res_config_settings_view.xml:11-21` |

## 7. Arama Filtreleri

Bu modül yeni arama görünümü/filtre eklemez (kanıt: `views/` altında `search` tanımı ve mevcut arama görünümlerine xpath eklemesi yok). Tek domain, wizard dönüşündeki `[('id','in',created_sales.ids)]` filtresidir (`wizard/create_sale_wizard.py:69`); `order_types` için hazır filtre yoktur.

## 8. Test Kapsamı

`tests/test_field_operation_sale.py` — 6 test, `@tagged("field_operation_sale", "post_install", "-at_install")`:

1. Wizard servisi taslak siparişe çeviriyor; müşteri, fiyat, satır adı ve iki yönlü bağ + sayaçlar doğrulanır.
2. Müşterisiz servis için `UserError` (ham ORM hatası yerine).
3. Modül grubu olmayan kullanıcı wizard'ı çağırınca `AccessError`.
4. `_prepare_invoice()` her iki bağ yönünde de servis referansını taşır.
5. `create_sale_service` satır başına bir servis üretir, fiyat `price_subtotal`'dan gelir, `start_date` gerçek zaman damgasıdır; ikinci çağrı `UserError`.
6. Satış yetkisi olan ama modül grubu olmayan kullanıcı `create_sale_service` çağırınca `AccessError`.

    odoo-bin -c <odoo.conf> -d <test_db> -u field_operation_sale \
        --stop-after-init --test-tags /field_operation_sale

## 9. Geliştirici Notları

- Migration yok (`migrations/` bulunmuyor).
- Çeviri: `i18n/field_operation_sale.pot`, `i18n/tr.po` (33 `msgid`).
- Görsel: `static/description/` altında `icon.png`, `icon.svg`, `index.html`.
- Wizard `binding_model_id` ile `field.operation` Action menüsüne bağlanır; grup kısıtı `group_ids` ile verilir (`wizard/create_sale_wizard_view.xml:29-37`).
- `order_types` alanına yeni değer eklerken `field_operation_contract` (`models/sale_order.py:10`, `models/field_operation_contract.py:311,407`) ile uyum kontrol edilmeli.

## 10. Değişiklik kaydı — 2026-10-09 (inceleme sonrası, sürüm 19.0.1.0.1)

İnceleme raporu: `field_operation_sale_inceleme_2026-10-09.md` (saha_legacy kökünde).

- **Eksik/yanlış bağımlılıklar:** `sale.order.field_operation_count` artık `field_operation_ids` one2many
  üzerinden hesaplanıyor (dekoratör daha önce yorum satırındaydı → sayaç hiç tetiklenmiyordu);
  `field.operation.sale_count` `sale_id`'ye bağlandı; `account.move.field_operation_count` kayıt bazlı
  hesaplanıyor ve `@api.depends("line_ids.sale_line_ids.order_id")` aldı (önce tüm kayıtlara tek değer yazıyordu).
- **`sale_count` anlamı:** artık `sale_id` dolu ise 1. Önce boş kalan `sale.order.field_operation_id` sayılıyordu,
  bu yüzden "Sale" butonu 12.032 bağlı kayıtta görünmüyordu — düzeldi.
- **Fatura referansı:** `_prepare_invoice()` artık `field_operation_id` boşsa ters bağa (`sale_id`) bakıyor;
  mevcut siparişlerde fatura servis referansını alıyor.
- **`date` → `Datetime`:** `create_sale_service` `fields.Date.today()` yerine `fields.Datetime.now()` yazıyor
  (ORM date'i UTC gece yarısına çevirdiği için servis "bugün 03:00" görünüyordu).
- **Wizard:** `self._context` → `self.env.context` (19.0'da deprecated); varsayılan ürün `ir.config_parameter`'dan
  okunurken doğrulanıyor (bozuk değerde `ValueError` ile açılmıyordu); müşterisiz servis için okunur `UserError`.
- **Yetki:** iki giriş noktası da (`action_create_sale`, `create_sale_service`) modül grubunu sunucuda uyguluyor;
  "Service" butonuna `groups=` eklendi.
- **Çift kayıt koruması:** `create_sale_service` siparişin servisi varsa `UserError` yükseltir.
- **İki yönlü bağ:** iki alan korundu (tek alana indirmek mevcut 12.032 kaydı ve diğer modülleri etkilerdi);
  `_prepare_invoice` ikisini de okur, `create_sale_service` yalnız `sale_id` yazar (n servis tek alana sığmaz).
- **Standart:** manifest gömülü `description` kaldırıldı, boş `demo`/`assets`/`external_dependencies` silindi,
  `order_types` view'da artık zorunlu değil (DB'de 2 boş kayıt vardı), 6 dosya CRLF→LF, Türkçe docstring'ler
  İngilizce, ruff temiz, `tests/` eklendi.

## 11. Değişiklik kaydı — 2026-10-17 (sürüm 19.0.1.0.3)

- **`sale.order.field_operation_id` kaldırıldı.** Sipariş ↔ servis bağının tek sahibi artık
  `field.operation.sale_id`. Kaldırma öncesi canlı kopyada (`uzman_fix_check`) ölçüldü: m2o
  **0 kayıtta** dolu, 12.090 servisin tamamı `sale_id` üzerinden bağlı → veri kaybı yok. Bir servis
  birden fazla olabildiği için m2o zaten n servisi temsil edemiyordu.
- **Davranış korundu:** "Service" butonu `field_operation_count == 0` iken görünür; akıllı buton tek
  servis varsa formu, birden fazlaysa listeyi açar; `_prepare_invoice()` ilk servisi faturaya yazar.
- **Şema notu:** `-u` sırasında Odoo 19 `ir_model_fields` kaydını temizleyip
  `sale_order.field_operation_id` kolonunu da düşürür (canlı kopyada doğrulandı). Yani geri dönüş
  gerekirse alan + veri yeniden kurulmalı; kolon boş olduğu için kayıp yok.
- **i18n:** `pot` yeniden üretildi (47 giriş, 19.0), `tr.po` 47/47 dolu (0 boş, yer tutucular
  korunuyor). Yeni hata mesajları, `Sale`, `Sales Order Line` ve `Service Count` çevrildi;
  `Service Count` eski yanlış karşılığı (`Servisler`) `Servis Sayısı` oldu.

# Field Operation Forms Pest

> `field_operation_forms` için bağımsız pest sekmesi ve stok teslimat akışı.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.4.0`

## Kapsam

- `field.operation.forms.pest` form satırları ve `BIO-F-` sequence'i
- Form üzerinde saklanan biyosidal başlıklar ve zararlı türleri
- Stok teslimat alanları, `action_transfer` ve teslimat smart button'ı
- Forms grupları için ACL, atama ve multi-company record rule'ları
- `stock.move` / `stock.picking` üzerindeki form bağlantıları

Form akışı operation oluşturmaz veya operation verisini değiştirmez. Form
silindiğinde form satırları cascade silinir.

## Bağımlılıklar

- `field_operation_forms`
- `field_operation_pest_common`
- `stock`

`field_operation_pest` bağımlılığı yoktur. Ortak katalog ve ürün/şirket
metadata'sı common modülde kaldığı için operation modülü kaldırıldığında forms
akışı ve mevcut veriler korunur. Modül `auto_install=False` olarak kurulur.

## Veri Geçişi

`post_init_hook` ve `19.0.1.3.0` migration'ı legacy form satırlarını, biyosidal
başlıkları, zararlı türü ilişkilerini ve stok bağlantılarını forma taşır.
`19.0.1.4.0` ortak varlıkları `field_operation_pest_common` sahipliğine ayırır.

Uzman veritabanında ayrıca `saha_uzman_migration` snapshot ve doğrulama paketi
kullanılır. Eski operation modülü ancak sayımlar ve forms testleri doğrulandıktan
sonra kaldırılır.

## Testler

```bash
odoo-bin -c conf -d <test_db> -i field_operation_forms_pest \
  --test-enable --stop-after-init
```

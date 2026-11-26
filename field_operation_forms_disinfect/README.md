# Field Operation Forms Disinfect

> `field_operation_forms` için bağımsız dezenfeksiyon sekmesi, PDF ve e-posta.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.4.0`

## Kapsam

- `field.operation.forms.disinfect` form satırları ve `DIS-F-` sequence'i
- Form üzerinde saklanan PH/CL ölçümleri
- İmzalı form PDF'i ve form e-posta şablonu
- Forms grupları için ACL, atama ve multi-company record rule'ları

Form akışı operation oluşturmaz veya operation verisini değiştirmez. Form
silindiğinde form satırları cascade silinir.

## Bağımlılıklar

- `field_operation_forms`
- `field_operation_disinfect_common`

`field_operation_disinfect` bağımlılığı yoktur. Ürün kataloğu ve şirket
sertifika alanı common modülde kaldığı için operation modülü kaldırıldığında
forms akışı ve mevcut veriler korunur. Modül `auto_install=False` olarak kurulur.

## Veri Geçişi

`post_init_hook` ve `19.0.1.3.0` migration'ı legacy satırları ve PH/CL
değerlerini forma taşır. `19.0.1.4.0` ortak varlıkları
`field_operation_disinfect_common` sahipliğine ayırır.

Uzman veritabanında ayrıca `saha_uzman_migration` snapshot ve doğrulama paketi
kullanılır. Eski operation modülü ancak sayımlar ve forms testleri doğrulandıktan
sonra kaldırılır.

## Testler

```bash
odoo-bin -c conf -d <test_db> -i field_operation_forms_disinfect \
  --test-enable --stop-after-init
```

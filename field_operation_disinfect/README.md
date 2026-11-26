# Field Operation Disinfect

> Operation merkezli dezenfeksiyon satırları ve PH/CL ölçümleri.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.3.0`

## Kapsam

- `field.operation.disinfect` satırları ve `DIS-` sequence'i
- `field.operation` üzerinde `before_ph`, `after_ph`, `before_cl`, `after_cl`
- Operation servis PDF'inde dezenfeksiyon satırları ve ölçümler
- Operation ataması ve şirket bazlı ACL/record rule'lar

## Bağımlılıklar

`field_operation_disinfect_common`; dezenfeksiyon ürün kataloğu, `disinfect`
servis tipi ve şirket sertifika alanını sağlar.

`field_operation_forms` ve `field_operation_forms_disinfect` bu modülün
bağımlılığı değildir. Forms akışı ayrı kurulur ve kendi
`field.operation.forms.disinfect` satırlarını kullanır.

## Veri Geçişi

`19.0.1.3.0` ile ortak katalog ve metadata `field_operation_disinfect_common`
modülüne taşınır. Common modülün `pre_init_hook` mevcut XMLID'leri yeni sahibine
aktarır; ürün ID'leri ve ilişkiler korunur. Legacy form verisinin operation'a
alınması `19.0.1.2.0` migration'ında yapılır.

## Testler

```bash
odoo-bin -c conf -d <test_db> -i field_operation_disinfect \
  --test-enable --stop-after-init
```

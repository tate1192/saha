# Field Operation Pest

> Operation merkezli pest kontrol / biyosidal uygulama kayıtları.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.3.0`

## Kapsam

- `field.operation` üzerinde biyosidal başlıklar ve zararlı türleri
- `field.operation.pesticide` satırları ve `BIO-` sequence'i
- Operation servis PDF'inde pest bölümü
- Operation ataması ve şirket bazlı ACL/record rule'lar

## Bağımlılıklar

`field_operation_pest_common`; operation, pest kataloğu, `pest` servis tipi,
biyosidal ürün alanları ve şirket sertifika alanlarını sağlar.

`field_operation_forms` ve `field_operation_forms_pest` bu modülün bağımlılığı
değildir. Forms akışı ayrı kurulur ve kendi `field.operation.forms.pest`
satırlarını kullanır; iki akış birbirine veri yazmaz.

## Veri Geçişi

`19.0.1.3.0` ile ortak katalog ve metadata `field_operation_pest_common`
modülüne taşınır. Common modülün `pre_init_hook` mevcut XMLID'leri yeni sahibine
aktarır; kayıt ID'leri ve tablolar korunur. Eski form satırlarının operation'a
alınması `19.0.1.2.0` migration'ında yapılır.

## Testler

```bash
odoo-bin -c conf -d <test_db> -i field_operation_pest \
  --test-enable --stop-after-init
```

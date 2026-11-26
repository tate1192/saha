# Field Operation Cost

> Servis başına işçilik, malzeme, taşeron/araç ve diğer maliyetleri toplar; servisin
> cirosunu ve kâr marjını tek ekranda gösterir.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`
> Modül: `field_operation_cost/` · iki model: `field.operation` (inherit) + `field.operation.cost.line`

## 1. Genel Bakış

Saha operasyonuna **maliyet satırları** ekler. Satırlar iki kaynaktan gelir:

- **Elle girilen** satırlar: ofisin yazdığı park/konaklama/ek malzeme gibi kalemler.
- **Otomatik (`auto`) satırlar**: atanan personel + `hourly_cost` üzerinden işçilik,
  stok/makine katmanlarının toplamı üzerinden malzeme, `contractor_cost` /
  `vehicle_cost` alanlarından taşeron ve araç satırları.

Otomatik satırlar **silinip yeniden üretilir**; elle girilen satırlara dokunulmaz.
Servis `done` durumuna geçtiğinde yenileme kendiliğinden çalışır, ayrıca formdaki
**Refresh Costs** butonuyla elle tetiklenebilir.

Ciro = servisteki `service_price`; fiyat boşsa ve `field_operation_contract`
kuruluysa bağlı sözleşme satırının `price_subtotal` değeri. Kâr = ciro − toplam
maliyet, marj = kâr / ciro × 100.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` kaydı, `person_ids`, `total_work`, `service_price`, `currency_id`, ofis grubu kontrolü (`_check_office_group`) |
| `hr_hourly_cost` | `hr.employee.hourly_cost` — işçilik satırının birim maliyeti |

İsteğe bağlı (bağımlılık değil, alan varlığına göre çalışır):
`field_operation_stock` (`total_stock_all`), `field_operation_machine`
(`spare_part_total`), `field_operation_contract` (`contract_line_id`).

## 3. Nasıl Çalışır

1. **Satır üretimi** — `_prepare_auto_cost_vals()` her personel için
   `quantity = total_work`, `unit_cost = hourly_cost` satırı üretir; malzeme
   toplamı varsa tek satır, taşeron/araç tutarları varsa birer satır eklenir.
2. **Yenileme** — `_refresh_auto_cost_lines()` önce `auto=True` satırları siler,
   sonra yukarıdaki listeyi yeniden yaratır. İki kez basmak maliyeti ikiye katlamaz.
3. **Kapanışta yenileme** — `field.operation.write()` içinde `status == "done"`
   görülürse yenileme çalışır. Saha personeli işi kapatabildiği için bu yol
   `sudo()` ile okur: personelin para alanlarını görme yetkisi yoktur, satırlar
   görünmezse yenileme eskisini silmek yerine ikinci bir takım ekler.
4. **Toplamlar** — `_compute_cost_totals()` satırları tipe göre toplar
   (`personnel`, `material`, `subcontractor` + `vehicle` → `external_cost`,
   `other`); `cost_hours` personel satırlarının saat toplamıdır.
5. **Kârlılık** — `_compute_profitability()` ciro, kâr ve marjı hesaplar.

## 4. Alanlar

`field.operation` üzerinde (hepsi `field_operation.service_group_all` grubuna açık):

| Alan | Tip | Açıklama |
|---|---|---|
| `cost_line_ids` | One2many | Servisin maliyet satırları |
| `total_cost` | Monetary (stored) | Tüm satırların toplamı |
| `personnel_cost` / `material_cost` / `external_cost` / `other_cost` | Monetary (stored) | Tip bazlı toplamlar |
| `cost_hours` | Float (stored) | Personel satırlarındaki saat toplamı |
| `revenue_amount` | Monetary (stored) | `service_price` veya sözleşme satırı fiyatı |
| `profit_amount` | Monetary (stored) | Ciro − toplam maliyet |
| `profit_percent` | Float (stored) | Kâr / ciro × 100 (ciro 0 ise 0) |
| `contractor_cost` | Monetary | Taşerona ödenen tutar (elle) |
| `vehicle_cost` | Monetary | Araç/yakıt tutarı (elle) |

`field.operation.cost.line`:

| Alan | Tip | Açıklama |
|---|---|---|
| `operation_id` | Many2one | Servis (cascade silme, `check_company`) |
| `name` | Char | Açıklama |
| `line_type` | Selection | `personnel`, `material`, `subcontractor`, `vehicle`, `other` |
| `employee_id` | Many2one | İşçilik satırının personeli |
| `date` | Date | Satır tarihi (varsayılan bugün) |
| `quantity` / `unit_cost` | Float / Monetary | İşçilikte saat, diğerlerinde adet |
| `amount` | Monetary (stored) | `quantity × unit_cost` |
| `auto` | Boolean | Otomatik üretilen satır işareti (readonly) |
| `currency_id` / `company_id` | related | Servisten gelir |

## 5. Görünümler ve Menü

- Servis formunda **Costs** sekmesi (`groups=service_group_all`): kârlılık özeti,
  taşeron/araç tutarları, düzenlenebilir satır listesi ve **Refresh Costs** butonu.
- Servis listesinde `Total Cost` ve `Profit` kolonları (varsayılan gizli).
- **Cost Analysis** aksiyonu: list / pivot / graph + arama filtreleri
  (tip, otomatik, bu ay, servis/personel/ay grupları).
- Menü: *Field Operations → Raporlar → Cost Analysis* (`service_group_all`).

## 6. Güvenlik

- `field.operation` üzerindeki tüm maliyet alanları `service_group_all` grubuna
  kapalıdır; saha personeli bu alanları RPC ile bile okuyamaz (çekirdekteki
  `service_price` ile aynı yaklaşım).
- `field.operation.cost.line` için ACL yalnız `service_group_all` ve
  `service_group_manager` gruplarına tam yetki verir; saha personeli ve ofis
  kullanıcısı satır görmez.
- Çok şirket kuralı (`rule_cost_line_company`) global olarak `company_id in company_ids`.
- **Refresh Costs** `service_group_all` ile korunur (ofis grubu yetmez: satırları
  göremeyen kullanıcı onları RPC ile de yeniden yazamaz); butonu gizlemek yetmez,
  çağrı `AccessError` ile reddedilir.
- Kapanışta çalışan otomatik yenileme `sudo()` ile okur, çünkü işi kapatan saha
  personelinin maliyet satırlarını görme yetkisi yoktur.

## 7. Kapsam Dışı

- Fatura/muhasebe kaydı üretmez (`field_operation_invoice` işi).
- Saatleri puantajla karşılaştırmaz — saat tutarları `field_operation_timesheet`
  modülünün konusudur.
- Kur/çoklu para birimi dönüşümü yapmaz: personelin `hourly_cost` değeri kendi
  para birimindedir, satırlar servisin `currency_id` değerini taşır.
- Sözleşme katmanı kurulu değilse ciro yalnız `service_price` alanından gelir.

## 8. Test

```bash
bash odoo19-test-modules.sh <db> <addons_dir> field_operation_cost
```

Testler (`tests/test_field_operation_cost.py`, 9 test) şunları sabitler: bileşen
başına tek satır, yenilemenin satırları çoğaltmaması, elle girilen satırın
korunması, fiyatsız serviste marjın 0 kalması, **saha personelinin kapatmasında
satırların ikilenmemesi**, para alanlarının personelden gizli kalması, negatif
tutar reddi ve `amount` hesabı.

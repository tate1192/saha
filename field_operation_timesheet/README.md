# Field Operation Timesheet

> Servis başına personel bazlı **zaman satırları**: planlamadan öneri, ofis onayı,
> onaylı saatin kilitlenmesi ve ay sonunda puantajla karşılaştırma.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`
> Modül: `field_operation_timesheet/` · iki model: `field.operation` (inherit) + `field.operation.time.line`, iki transient sihirbaz

## 1. Genel Bakış

`field.operation` kaydına personel başına harcanan saati ekler. Her satır bir
personel + tarih + süre taşır ve `draft` / `approved` durumundadır:

- **Draft**: ofis (ve personelin kendisi) düzenleyebilir.
- **Approved**: satır kilitlenir — süre değiştirilemez, satır silinemez. Kilit
  ancak ofisin **Reset To Draft** aksiyonuyla açılır.

Servis, `time_draft` / `time_approved` / `time_expected` / `time_difference`
alanlarıyla planlanan saat ile onaylanan saati yan yana gösterir; fark, servis
faturalanmadan önce ofisin açıklaması gereken boşluktur.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation`, `person_ids`, `total_work`, durum akışı, `_check_office_group` |

İsteğe bağlı: `hr_attendance` — kuruluysa **Time vs Attendance** raporu çalışır,
kurulu değilse sihirbaz bunu açık bir `UserError` ile söyler.

## 3. Nasıl Çalışır

1. **Propose From Planning** (`action_generate_time_lines()`): servisin
   `total_work` süresi ve `start_date` günü ile atanan her personel için bir
   `draft` satır üretir. Aynı gün için zaten satırı olan personel atlanır; başka
   güne planlama yapıldığında o gün için yeni satırlar üretilir.
2. **Approve All** (`action_approve_time_lines()`): servisin `draft` satırlarını
   onaylar (`approved_by`, `approved_on` doldurulur).
3. **Reset To Draft** (`action_reset_time_lines()`): onaylı satırları kilit
   bağlamıyla (`field_operation_time_unlock`) geri açar.
4. **Toplamlar** (`_compute_time_totals()`): `time_draft` ve `time_approved`
   satır durumlarına göre toplanır; `time_expected = total_work × personel sayısı`;
   `time_difference = time_approved − time_expected`.
5. **Time vs Attendance** (`field.operation.timesheet.reconciliation`): seçilen
   dönem için personel başına onaylı saat, draft saat, `hr.attendance` çalışma
   saati ve farkı hesaplar. Personel seçilmezse dönemde saha saati veya puantajı
   olan herkes listelenir.

> Kilit kuralı `write()` ve `unlink()` içinde uygulanır: onaylı satırı
> değiştirmeye çalışan her yol (form, liste, RPC, import) aynı `UserError` ile
> durur.

## 4. Alanlar

`field.operation` üzerinde:

| Alan | Tip | Açıklama |
|---|---|---|
| `time_line_ids` | One2many | Servisin zaman satırları |
| `time_draft` | Float (stored) | Onay bekleyen saat |
| `time_approved` | Float (stored) | Onaylı saat |
| `time_expected` | Float (stored) | Planlanan süre × personel sayısı |
| `time_difference` | Float (stored) | Onaylı − beklenen |

`field.operation.time.line`:

| Alan | Tip | Açıklama |
|---|---|---|
| `operation_id` | Many2one | Servis (cascade silme, `check_company`) |
| `employee_id` | Many2one | Personel — servise atanmış olmak zorunda (`ValidationError`) |
| `date` | Date | Çalışma günü (varsayılan bugün) |
| `duration` | Float | Saat; 0'dan büyük olmalı |
| `state` | Selection | `draft` / `approved` |
| `approved_by` / `approved_on` | Many2one / Datetime | Onay izi (readonly) |
| `note` | Char | Not |
| `company_id` | related (stored) | Servisten gelir |

## 5. Görünümler ve Menü

- Servis formunda **Time Tracking** sekmesi: toplam saatler, üç aksiyon butonu ve
  düzenlenebilir satır listesi (onaylı satırlar soluk, satır üstü onay/geri al
  ikonları `service_group_user`'a açık).
- Servis listesinde `Approved` ve `Difference` kolonları (varsayılan gizli).
- **Time Lines** aksiyonu (draft filtresiyle açılır) ve **Time vs Attendance**
  sihirbazı; ikisi de *Field Operations → Raporlar* menüsü altında.

## 6. Güvenlik

- Alan başına görünürlük çekirdeğin katmanlarını izler:
  - `service_group_worker`: yalnız **kendi** (`employee_id.user_id = user`) satırını görür.
  - `service_group_user`: kendi planladığı, sahibi olmayan (draft) veya ekip
    lideri olduğu servislerin satırlarını görür — çekirdekteki ofis kuralının
    aynısı, `team_leader_id` ile genişletilmiş.
  - `service_group_all`: hepsini görür.
- Onaylama, geri alma ve öneri üretme `_check_office_group` ile korunur:
  `AccessError` — butonu gizlemek yetmez, RPC de reddedilir.
- **Time vs Attendance** sihirbazı ofis işidir: ACL `service_group_user`'a
  kapatıldı ve `action_compute()` grubu ayrıca doğrular (aksi halde saha
  personeli RPC ile tüm personelin puantajını okuyabilirdi).

## 7. Kapsam Dışı

- Puantaj kaydı (`hr.attendance`) **yaratmaz**; yalnız okur ve karşılaştırır.
- Ücret/maliyet hesabı yapmaz — işçilik maliyeti `field_operation_cost` modülünde,
  `hr.employee.hourly_cost` üzerinden.
- Fazla mesai / izin bakiyesi hesabı içermez.
- Mobil uygulama için ayrı bir sayaç yoktur; süre elle veya öneriyle girilir.

## 8. Test

```bash
bash odoo19-test-modules.sh <db> <addons_dir> field_operation_timesheet
```

Testler (`tests/test_field_operation_timesheet.py`, 12 test) şunları sabitler:
öneri satırları, aynı gün tekrar önerinin çoğaltmaması, **başka güne önerinin yeni
satır eklemesi**, onay kilidi ve geri alma, toplamların draft/approved ayrımı,
atanmamış personel ve sıfır süre reddi, saha personelinin onaylayamaması ve yalnız
kendi saatini görmesi, puantaj karşılaştırması ve personelin raporu çalıştıramaması.

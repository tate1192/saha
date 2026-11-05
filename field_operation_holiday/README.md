# Field Operation Time Off

> Onaylı personel izinlerini saha planına yansıtır: izinli olunan **her gün için**
> saha operasyonunda "X izinli" görevi oluşturur, izin iptal/silinince görevi kaldırır.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `apps/saha/field_operation_holiday` · yeni model içermez

## 1. Genel Bakış

`hr.leave` (İzin) kaydı `validate` durumuna geçtiğinde, iznin kapsadığı her takvim günü
için bir `field.operation` görevi üretir. Görev, personeli (`person_ids`), izin türünü ve
izin kaydını (`leave_id`) taşır; böylece planlamada o gün personelin izinli olduğu görünür.

- İzin onaylandığında: gün sayısı kadar görev oluşturulur
- İzin iptal/reddedilirse veya onaydan geri alınırsa: görevler silinir
- İzin tarihleri değişip yeniden onaylanırsa: görevler yeniden üretilir
- İzin kaydı silinirse: görevler de silinir (`leave_id` üzerinde `ondelete="cascade"`)

Kapsam dışı: cron kurmaz, izin bakiyesi/hakediş hesabı yapmaz, izin talebi oluşturmaz,
başka modüllerin izin kurallarını değiştirmez.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` görevi, `field.operation.type` modeli, `_check_leave_conflicts` kancası |
| `hr_holidays` | `hr.leave` kaydı ve izin türü |

## 3. Nasıl Çalışır

1. `hr.leave.create` / `hr.leave.write` → izin `validate` mı, tarih/personel değişti mi bakılır
2. `_sync_leave_operations()`: iznin eski görevlerini siler, gün varsa yeniden üretir
3. Her gün için bir görev: kesim **yerel gece yarısı** sınırlarıyla yapılır (`leave.tz`). `date_from/date_to`
   UTC olduğu için doğrudan UTC gününe bölmek ara günleri 24 saatlik UTC bloklarına çevirir (İstanbul'da
   03:00 → ertesi gün 02:59) ve ilk günün sabahını boşta bırakır. Örnek: 10.11 08:00 → 12.11 17:00 izni
   yerelde 10.11 08:00-24:00, 11.11 00:00-24:00, 12.11 00:00-17:00 olarak üç göreve ayrılır
4. Görev alanları: `subject` = "İzinli: PERSONEL (İZİN TÜRÜ)", `description` = izin aralığı,
   `service_type_id` = **Personel İzni**, `person_ids` = personel, `status` = `planned`,
   `leave_id` = izin kaydı

> Görevler `sudo()` ile oluşturulur: izni onaylayan kullanıcının (İK) `field.operation`
> üzerinde yazma yetkisi olmasa da akış çalışır. `field_operation` modülünde saha personeli
> yalnız okuma yetkisine sahiptir (`access_field_operation_field_worker`).

## 4. İzin Çakışma Kontrolü

İzin kontrolü **bu modülde** yaşar: `field_operation` çekirdeği artık `hr_holidays`'e bağımlı
değildir, `_check_team_integrity` içinden `_check_leave_conflicts` kancasını çağırır (çekirdekteki
tanım boş). Kanca burada onaylı (`state='validate'`) izinleri tek sorguda okur, kayıt tarihleriyle
kesiştirir ve çakışmada `ValidationError` fırlatır (`models/field_operation.py`).

Kontrol, bu modülün ürettiği izin görevlerini denetim dışı bırakır: `_check_team_integrity`
override'ı `service_type_id.type == 'leave'` kayıtlarını atlar, çünkü görev zaten personelin
izinli olduğunu anlatır ve kendini reddedemez. Gerçek servislerde kontrol aynen çalışır
(`test_05`, `test_08`).

## 5. Alanlar

| Model | Alan | Açıklama |
|---|---|---|
| `field.operation` | `leave_id` | Görevin üretildiği izin kaydı (cascade silme) |
| `field.operation` | `is_leave_marker` | İzin görevi işareti (compute, stored; aramada "Leaves" filtresi) |
| `hr.leave` | `operation_ids` | İznin ürettiği görevler |
| `field.operation.type` | `type` seçimi | `leave` değeri eklendi ("Personel İzni") |

Veri: `field_operation_holiday.operation_type_leave` — "Employee Leave" / "Personel İzni"
(`type=leave`, global şirket).

## 6. Görünüm Değişiklikleri

- `field.operation` arama görünümüne **Leaves** filtresi (`is_leave_marker = True`)
- `field.operation` formunda `leave_id` alanı (sadece ofis grubuna görünür)
- İzin görevlerinde `partner_id` ve `team_id` zorunluluğu kaldırılır (izinde müşteri/ekip yok)

## 7. Testler

`tests/test_field_operation_holiday.py`, `post_install` etiketli, 8 test:

1. Onaylı 3 günlük izin → 3 görev, doğru günler, `planned`, personel ve izin bağlantısı; kesim yerel saatle
   doğrulanır (personel takvimi Europe/Istanbul; hiçbir görev yerel gece yarısını geçmez)
2. Tarih değiştirilip yeniden onaylanınca görevler yeniden üretilir (önce 2, sonra 4)
3. İptal edilen izin görevlerini siler
4. Silinen izin görevlerini de siler
5. İzinli personel için gerçek servis açılmaya çalışılınca mevcut `ValidationError` hâlâ fırlar
6. Görevler izin servis tipini taşır
7. Servis tipi/yetkisi olmayan Time Off memuru senkronu çalıştırabilir (sudo yolu)
8. İzin kontrolü toplu yapılır: batch başına tek `hr.leave.search`, çakışmada `ValidationError`

```
odoo-bin -c <conf> -d <db> -u field_operation_holiday --test-tags /field_operation_holiday --stop-after-init
```

## 8. Çeviri

`i18n/tr.po` ve `i18n/field_operation_holiday.pot` dahildir: görev başlığı/açıklaması,
"Leaves" filtresi, izin tipi adı Türkçeleştirilmiştir.

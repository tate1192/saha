# Field Operation Report

Saha operasyonu (`field_operation`) uzerine salt-okunur raporlama katmani.

## Ne ekler

- `field.operation` uzerinde rapor alanlari: `report_date` (gruplama tarihi),
  `person_count`, `duration_per_person`.
- Saha Hizmet Analizi: `field_operation`'in **mevcut** pivot/graph ekranlarina
  rapor alanlarini ekler (ayri kopya view yok), menuden dogrudan acilir.
- Veri Kalitesi listesi: bitis tarihi / personel / tutar eksik isler.
- Takim Raporu (PDF): secilen donem ve takimlar icin takim bazli ozet.
- Saha Hizmet Dokumu (PDF): listede secilen islerin dokumu (Print menusunde).

## Notlar

- Hicbir sey yazmaz; is akisini degistirmez. Metrikler mevcut alanlardan turetilir.
- **Sure tek kaynaktan gelir: cekirdek `total_work` alani** (`start_date` ve
  `end_date` doluysa fark, degilse 0). Modul kendi "saat" alanini tanimlamaz;
  aksi halde ayni is icin iki farkli sure rakami cikiyordu.
- `duration_per_person` = `total_work` / atanan personel sayisi.
- `report_date` **sirket saat diliminde** kesilir (`res.company.partner_id.tz`),
  UTC'de degil: 01:00 Istanbul'da baslayan is bir onceki gune dusmez. Stored
  compute oldugu icin kullanici tz'sine baglanmaz.
- Toplamlar sirket para biriminde, **kur cevrimi yapilmadan** toplanir; donemde
  birden fazla para birimi varsa PDF'te uyari cikar (`multi_currency`).

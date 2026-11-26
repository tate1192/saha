# Field Operation Pest Common

`field_operation_pest` ve `field_operation_forms_pest` modüllerinin ortak
katalog ve metadata sahibidir. İki modül birbirine bağımlı olmadan aynı zararlı
türü kataloğunu, `pest` servis tipini, biyosidal ürün alanlarını ve şirket
sertifika alanlarını kullanır.

Bu modül forms'a bağımlı değildir. Operation veya forms modüllerinden biri
kaldırıldığında ortak kayıtlar diğer modül için korunur.

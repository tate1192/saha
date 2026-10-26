# Changelog — saha (field_operation suite)

Bu dosya repodaki modül suite'inin değişim kaydıdır. Sürüm numaraları her modülün
kendi `__manifest__.py` dosyasında tutulur; aşağıdaki tablo güncel durumu gösterir.

Biçim: [tutulan sürüm] — tarih — commit — açıklama

## [field_operation_report: 19.0.1.1.0 · field_operation: 19.0.2.5.0] — 2026-10-24

### Saha raporlama katmanı ve merge sonrası sayaç tazeleme

- **Yeni modül `field_operation_report`** (salt-okunur): `field.operation` üzerinde
  `report_date`, `person_count`, `duration_per_person`; Saha Hizmet Analizi
  (pivot/graph), Takım Raporu (PDF), Saha Hizmet Dökümü (PDF, Print menüsünde) ve
  Veri Kalitesi listesi + filtreleri.
- **Süre tek kaynaktan:** çekirdek `total_work` kullanılıyor. Modülün ilk taslağındaki
  `duration_hours` alanı kaldırıldı — `close_date` yedeği ve negatif kırpma yüzünden
  aynı hizmet için iki farklı süre üretiyordu (`total_work` ile çelişki).
- **`report_date` şirket saat diliminde** kesilir (`res.company.partner_id.tz`);
  UTC'de kesildiğinde 01:00 İstanbul'da başlayan hizmet bir önceki güne düşüyordu.
  Stored compute olduğu için kullanıcı tz'sine bağlanmaz; bilinmeyen tz'de UTC'ye düşer.
- **Analiz ekranı çoğaltılmadı:** modülün kendi pivot/graph kopyaları yerine çekirdek
  `view_field_operation_pivot` / `view_field_operation_graph` inherit edilip rapor
  alanları eklendi; menü `act_window.view` ile aynı analizi açıyor.
- **Para birimi:** toplamlar şirket para biriminde, kur çevrimi yapılmadan; dönemde
  birden fazla para birimi varsa wizard `multi_currency` bayrağıyla PDF'te uyarı basar.
- **`field_operation` — merge sayacı:** `base_partner_merge._merge` sonrası stored
  `field_operation_count` bayat kalıyordu (sihirbaz FK'leri düz SQL ile taşıyor, ORM
  görmüyor). Merge **öncesi** toplanan tüm atalar (kaynak + hedef taraf) tazeleniyor:
  yalnız `parent_id` yetmiyor (şirket > şube > kontak) ve kaynağın eski ebeveyni
  hizmeti kaybediyor. v19'da `res.partner`'da `parent_path`/`_parent_store` yok,
  `parent_id` zinciri döngü korumasıyla elle yürünüyor. Tazeleme varsayılan context'te
  yapılır: ata yürüyüşü için açılan `active_test=False` context'i sayaca sızarsa
  arşivlenmiş hizmetler de sayılıyor ve akıllı butonla uyuşmuyordu.
- Testler: **9 yeni** (7 raporlama + 2 merge). İzole temiz kurulumda `25 test,
  0 failed, 0 error`, 0 skipped. Düzeltmeler geri alındığında merge ve tz testleri
  kırılıyor (koruma kanıtı); arşiv context'i düzeltmesi geri alındığında yeni merge
  testi `3 != 2` ile düşüyor.
- i18n: `.pot` Odoo `i18n export` ile yeniden üretildi; `tr.po` 71/71 senkron
  (3 bilinen untranslated: iki `print_report_name` ifadesi ve `"on"`).

## [field_operation_geolocation: 19.0.1.6.1] — 2026-10-20

### Erişim hatası: `home_location_id` genel profilde yoktu

- HR yetkisi olmayan bir kullanıcı çalışan kaydını okuduğunda Odoo genel profile
  (`hr.employee.public`) düşüyor; `home_location_id` orada tanımlı olmadığı için
  `Erişim Hatası: "home_location_id" ... çalışanların genel profilleri için
  kullanılamaz` veriyordu (takım formundan çalışan kartı açmak, liste export'u,
  kayıtlı filtre vb.).
- Alan `hr.employee.public` üzerine **stored olmayan related** alan olarak eklendi
  (`models/hr_employee_public.py`): okuma başarılı olur, değer çalışanın kendi
  kaydında kalır, kolon çoğaltılmaz.
- Görünürlük notu: ev adresi artık genel profil üzerinden de okunabilir; KVKK
  başlığındaki "kimler görür" maddesi bu gerçeğe göre değerlendirilmeli.

## [field_operation_geolocation: 19.0.1.6.0] — 2026-10-19

### GPS geçmişi saklama ve chatter gürültüsü

- `team.location.history` için günlük **GPS History Cleanup** cron'u eklendi
  (`ir_cron_cleanup_team_location_history`): `timestamp`'i 60 günden eski kayıtları siler.
  Süre `field_operation_geolocation.location_history_retention_days` sistem parametresiyle
  değiştirilir; geçersiz değerde varsayılan 60 güne döner. Cron aktiftir; ilk çalışmada
  mevcut eski kayıtları da temizler.
- GPS telemetri alanlarındaki (`accuracy`, `device_id`, `status`, `signal_strength`)
  `tracking=True` kaldırıldı; controller artık `tracking_disable=True` ile yazıyor. Böylece
  her ping takım chatter'ına tracking mesajı bırakmıyor.
- **Yükseltme:** `migrations/19.0.1.6.0/post-migration.py` mevcut takımları (arşivliler
  dahil) `company` moduna alır; yeni takımlar `home` başlar. Ev adresi hiç tanımlı değilse
  plan artık uyarı basmaz; uyarı yalnız ev tanımlı ama koordinatsızsa gösterilir.
- Testler: 50 → **53** post-test; `test_location_history_cleanup_drops_rows_older_than_the_window`,
  `test_location_history_cleanup_reads_the_retention_parameter` ve
  `test_a_team_without_a_home_starts_at_the_company_silently` eklendi.
- Yeni alan yok; saklama penceresi sistem parametresinden okunur. 1.5.0'ın yeni alanları
  için migration gerekmez.

## [field_operation_geolocation: 19.0.1.5.0] — 2026-10-19

### Rota evden/firmadan başlar ve aynı noktada biter

- **Kapalı döngü:** `total_km` artık `başlangıç → duraklar → başlangıç` toplamı;
  dönüş bacağı ayrıca `return_km` alanında gösterilir. `leg_km` satırlarının
  toplamı gidiş bacağını verir.
- **Başlangıç noktası seçimi:** `field.operation.team.route_start_mode`
  (`home` / `company`, varsayılan `home`). `home`, takım şefinin
  `hr.employee.home_location_id` adresini kullanır; adres yoksa veya koordinatı
  yoksa firmaya (`base_location_id` → şirket adresi) düşer ve plan ekranı bunu
  uyarı olarak yazar.
- **Yeni alanlar:** `hr.employee.home_location_id` (personel formunda **Ev
  Adresi**), `field.operation.team.home_location_id` (related, takım formunda
  düzenlenebilir), plan sihirbazında `route_start_mode`, `start_location_id`,
  `return_km`.
- **Öneri:** nearest-neighbour + 2-opt artık dönüş bacağını maliyete katar
  (`geo_helpers.suggest_route_order(..., end=)`); aksi hâlde eve en yakın durak
  günün sonuna bırakılabiliyordu.
- **Harita:** çok noktalı sağlayıcılarda rota başlangıç noktasında kapanır;
  yalnız başlangıç+varış destekleyen şablon sağlayıcılarda son müşteri varış
  kalır (X→X üretilmez).
- **Testler:** `uzman_v19_test -u field_operation_geolocation --test-enable
  --test-tags /field_operation_geolocation` → 0 failed, 50 post-test; rota
  planlama dosyası 21 → **27 test**.
- Bu sürümde migration yok; yeni alanlar boş, `route_start_mode` varsayılanı `home`.
  Mevcut takımların `company` moduna alınması 19.0.1.6.0 migration'ında yapılır.

## [field_operation_geolocation: 19.0.1.4.0] — 2026-10-19

### Form ve liste görünümünde alan yerleşimi

- **Form görünümü:** `service_latitude`, `service_longitude` ve `date_localization` alanları
  `create_date` sonrasından `person_ids` bloğunun altına taşındı; konum bilgisi artık ekip/kişi
  bloğunun hemen altında görünüyor. Devralma konumu (`person_ids`) `field.operation` form
  görünümünde mevcut.
- **Liste görünümü:** `is_located` kolonu `optional="show"` → `optional="hide"`. Varsayılan
  olarak gizli, kullanıcı kolon seçicisinden açabilir; `No Coordinates` filtresi ve
  `is_located` üzerine kurulu domain'ler değişmedi.
- **Doğrulama:** `fo_check -u field_operation_geolocation` → hatasız yüklendi (view devralma
  hatası yok). Kod/test değişikliği yok, migration gerekmez.

## [field_operation_gantt: 19.0.1.1.0] — 2026-10-18

### `label` niteliği kaldırıldı: çevrilebilir alan adı riski

- View `label="team_id"` kullanıyordu. Gruplu görünümde satır etiketi zaten `group_by="team_id"`dan
  geliyordu; `label` bu view'da görünür bir etki yapmıyordu.
- Daha önemlisi Odoo `label` niteliğini çevrilebilir metin olarak POT'a alıyor. `tr.po`da bu terim
  çevrilirse arch `label="Ekip"` olur ve `soft_gantt` bir alan adı beklediği için view kırılır.
  `label` kaldırıldı; `team_id` terimi POT/PO'dan çıkarıldı.
- `tr.po`daki eksik çeviriler tamamlandı (Gantt Rengi, İlerleme (%), Plan, iki help metni).
- README'deki tarih/saat ifadesi (UTC saklanır, kullanıcının saat diliminde çizilir), `label`
  satırı ve soft_gantt test sayıları güncellendi.
- **Testler:** 10 → **11** (`test_the_view_has_no_translatable_field_name`); scratch
  `soft_gantt_check`, `-i field_operation_gantt --test-enable --test-tags /field_operation_gantt`
  → 0 failed, 11 test.

## [field_operation: 19.0.2.4.0] — 2026-10-18

### Arşivli takımlar arama panelinden çıkarıldı

- `field.operation.search_panel_select_range`, `team_id` için
  `comodel_domain=[('active', '=', True)]` geçiriyor. Panel, işleri `team_id`'ye göre gruplayıp
  bulduğu her değeri listelediği için arşivli bir takıma bağlı tek bir iş o takımı panelde
  tutabiliyordu; comodel domain'i paneli takımların kendisini okumaya zorlar, tek seçimli
  kategori davranışı korunur (view'da `domain` yalnız `select="multi"` ile kullanılabiliyor).
- Bu kural önce geolocation modülünde yazılmıştı; arama görünümü bu modülde olduğu için
  buraya taşındı.
- **Testler:** 15 → **16** (`tests/test_search_panel.py`: arşivli görünmez, aktif görünür).

## [field_operation_forms_ext: 19.0.1.1.0] — 2026-10-18

### Modül repoya geri geldi: servis formu harita/konum kısayolları (WhatsApp'sız)

- `field.operation.forms` üzerinde **Map** (harita) ve **Geolocate** (konumlandırma) butonları,
  listede **Open Maps**; eylemler `field_operation_geolocation`'ın `geo_helpers`'ını kullanır
  (eski kopyadaki 0.0 koordinat tuzağı ve eşleşme yokken "success" bildirimi gitti).
- `field_operation_whatsapp` bağımlılığı, `action_message_send` ve WhatsApp butonu kaldırıldı
  (modül hazır olunca geri eklenecek).
- `service_latitude` / `service_longitude` (related, stored) + `display_address` compute korunur.
- **Testler:** 5 test (arch'ta Map/Geolocate/Open Maps, harita URL'i, çift sıfır reddi,
  geolocation warning/success, WhatsApp butonunun yokluğu); `fo_check`
  `-i field_operation_forms_ext --test-enable --test-tags /field_operation_forms_ext` →
  0 failed, 5 test.

## [field_operation_contract: 19.0.1.1.0] — 2026-10-18

### Gereksiz arama paneli kaydı kaldırıldı

- `contract_field_operation_filter_view` silindi: `field.operation` arama görünümüne
  `contract_id` alanını ve `<searchpanel>` içine sayaçlı bir `contract_id` kategorisi ekliyordu;
  kullanılmayan bir panel kalabalığıydı. Contract'ın form ve liste görünümleri yerinde.
- **Güncelleme notu:** `-u field_operation_contract` ilk denemede DB'deki eski
  `field_operation_sale_order_form_view` yüzünden `ParseError` verdi (`sale.order.field_operation_id`
  alanı kodda yok). Önce `-u field_operation_sale` çalıştırılınca view yenilendi ve contract
  güncellemesi geçti. Sıra: **önce `field_operation_sale`, sonra `field_operation_contract`**.

## [field_operation_geolocation: 19.0.1.3.0] — 2026-10-18

### Ofis/dispeçer için günlük rota planlama

- **Neden:** modülün asıl kullanıcısı ofiste servis oluşturan planlamacı: müşteri konumları
  üzerinde günün rotasını görmek, işi başlama saatine göre (bugün/yarın) filtrelemek ve
  kayıtları servis ekibine göre görmek istiyor. Öncesinde rota yalnız elle seçilen kayıtlardan
  açılabiliyordu, sıra recordset sırasıydı ve tek konumsuz iş tüm rotayı düşürüyordu.
- **Gün filtreleri (`field.operation` arama görünümü):** *Today (running)* / *Tomorrow (running)*
  `start_date < gün_sonu` ve (`start_date >= gün_başı` veya `end_date >= gün_başı` veya dün
  başlamış açık uçlu iş) kesişimi: dün başlayıp kapatılmamış iş bugünde görünür (canlı veride
  açık işlerin çoğunda `end_date` boş), aylardır kapatılmamış işler plana dolmaz; gün sınırı
  kullanıcı saat diliminde (test: `test_the_day_boundary_uses_the_user_timezone`).
  *No Coordinates* filtresi (`is_located = False`) rotaya giremeyecek işleri önceden gösterir.
- **Rota planı sihirbazı** (`field.operation.route.plan` + `.line`, geçici): takım/gün ön
  seçili gelir (`_default_team_id`: lider → çalışanın takımı → tek takım), duraklar planlanan
  başlama saati sırasıyla listelenir; bacak bacak haversine km (`leg_km` satırın kendi compute
  alanı), nearest-neighbour + 2-opt önerisi, kazanç **≥ %15 ve ≥ 5 km** ise "tutarsız" uyarısı
  (ör. 12:00 Tuzla → Beykoz → Pendik 69,6 km yerine Tuzla → Pendik → Beykoz 39,3 km).
  *Suggest Order*, sürükle-bırak, *Save Order* → `route_sequence`, isteğe bağlı saat kaydırma
  (yalnız plan günü başlayan duraklar), *Durakları Konumlandır* ve *Open Map*.
  Giriş noktaları: iş formundaki **Route Plan** butonu, *Saha Servisi* listesinde
  ⚙ Actions > **Route Plan** ve takım formundaki **Today's / Tomorrow's Route** butonları;
  gün filtresi listede *Today (running)* / *Tomorrow (running)* olarak durur (ayrı menü/
  act_window yok — menüler bu turda kaldırıldı).
- **Liste rota aksiyonu:** `action_show_selected_routes` sırayı `route_sequence`, sonra
  `start_date` ile kurar (`_sorted_for_route`); konumsuz durakları atlar ve bus bildirimiyle
  bildirir; seçim tek takımdansa depodan başlar. Sihirbazın coğrafi kontrolü harici
  servis/anahtar kullanmaz (haversine + nearest-neighbour + 2-opt).
- **Rota başlangıcı:** takıma `base_location_id` (depo) eklendi; boşsa şirket adresi, o da
  konumsuzsa günün ilk müşterisi.
- **Toplu konumlandırma:** *Konumlandır (seçili)* aksiyonu (`action_geolocate_selected`) sonucu
  bulunan/bulunamayan olarak raporlar.
- **Sağlayıcı tarafı:** `route_lat_lon_url` artık gerçekten kullanılıyor (`here`, `other`);
  Mapbox için çok duraklı `rtext` biçimi eklendi; OSM/Google/Bing yerleşik biçimleri korunur.
  Rotanın başlangıcı `lat=0.0` (ekvator) artık düşmüyor — kural `geo_helpers.has_point`.
- **Office User'ın planı boş kalıyordu:** `field_operation`'ın "Office: Own Documents" kuralı
  yalnız kullanıcının kendi + sahipsiz işlerini gösterdiği için, servisleri başka ofis
  kullanıcıları oluşturduğunda plan boş geliyordu. `Office: My Team's Documents` kuralı
  eklendi: ofis kullanıcısı lider/baş/üye olduğu takımların işlerini görür (başka takımı görmez;
  yönetici kuralları zaten tümünü görür).
- **Şema:** `field.operation.route_sequence` (Integer, default 0), `field.operation.is_located`
  (Boolean, stored compute), `field.operation.team.base_location_id` (m2o → res.partner);
  sürüm 19.0.1.2.0 → **19.0.1.3.0**. Migration yok.
- **`field_operation_forms` bağımlılığı kaldırıldı:** servis formu kısayolları artık
  `field_operation_forms_ext` modülünün işi. Bu modülden `models/field_operation_forms.py`,
  `views/field_operation_forms_view.xml`, `tests/test_field_operation_forms_map.py` ve manifest
  bağımlılığı kaldırıldı.
- **Testler:** 33 → **44** (`tests/test_route_planning.py`, 21 test). Doğrulama: `fo_check`
  `-u field_operation_geolocation --test-enable --test-tags /field_operation_geolocation` →
  EXIT=0, **0 failed, 0 error(s) of 44 tests**; ruff/ruff-format temiz.
- **i18n:** pot/po koddan yeniden üretildi; **185 msgid**, tr.po'da boş çeviri yok.
- **Kararlar:** depo = takım `base_location_id` → şirket adresi → ilk müşteri; plan bir
  sihirbaz (geçici model), kalıcı olarak işlere yalnız `route_sequence` (ve istenirse saatler)
  yazılır; rota kontrolü harici servis/anahtar kullanmaz (haversine + 2-opt). Canlıda `-u`
  kullanıcının adımı.

### PR #7 inceleme düzeltmeleri (2026-10-18)

- **Doküman/kod uyumu:** README ve CHANGELOG, "plan bir liste, sihirbaz kaldırıldı" diyordu;
  kod ise sihirbazı gönderiyordu. İkisi de sihirbaz tasarımına göre yeniden yazıldı.
- **`_plan_day_domain`:** `end_date` boş işler gün planından düşüyordu. Açık uçlu iş artık
  **bir önceki günden itibaren** plana giriyor; aylardır kapatılmamış işlerin her günü
  doldurmasını engellemek için pencere bilinçli olarak bir gün (canlı veride açık işlerin
  426/438'inde `end_date` boş). İki test: dün açık → girer, 30 gün önce açık → girmez.
- **`_shift_start_times`:** saat havuzu önceki günün işini de içeriyordu ve saatler günler
  arasında taşınıyordu. Artık yalnız **plan gününde başlayan** durakların saatleri dağıtılır;
  günler arası işin saati korunur. Regresyon testi eklendi.
- **`_notify_missing_stops`:** `missing._notify_missing_stops(missing)` gereksiz parametresi
  kaldırıldı; metot `self` üzerinden çalışır.
- **`leg_km`:** plan compute'u başka modelin alanını yazıyordu; `leg_km` artık satır modelinin
  kendi compute alanı (`@api.depends("plan_id.line_ids.sequence", ...)`), plan compute'u
  yalnız toplamı hesaplar. Bacak km'si için test eklendi.
- **Servis formu kısayolları testleri:** `field_operation_forms_ext`'e 5 test eklendi
  (arch'ta Map/Geolocate/Open Maps, harita URL'i, çift sıfır reddi, geolocation warning/success,
  WhatsApp butonunun yokluğu).
- **Test sayısı:** CHANGELOG'daki 42 → **44** (gerçek koşu; arşivli takım testi
  `field_operation` modülüne taşındı, orada 16 test). `field_operation_forms_ext` 5 test.

## [field_operation_sale: 19.0.1.0.3] — 2026-10-16

### Düzeltme: "Create Sale" butonu satılmış serviste de görünüyordu (mükerrer sipariş üretimi)

- **Buton koşulu eksikti:** `views/field_operation_view.xml` (header butonu) yalnız
  `status not in ('done',)` bakıyordu; `sale_id` dolu servislerde de görünüyordu. Canlı veride
  `status='done'` olan 12879 servisin **11656'sı zaten satışlı** → buton görünür, tıklayan ikinci
  siparişi yaratıp `field.operation.sale_id`'yi yeni siparişe çeviriyordu: eski siparişin o2m'i
  boşalır (sayacı 0'a düşer, stat butonu kaybolur), `sale.order.field_operation_id` eski siparişte
  kalır → iki kayıt karşılıklı farklı şey söyler. Koşul `status not in ('done',) or sale_id` oldu;
  satış tarafındaki `order_types != 'service' or field_operation_id` koşuluyla simetrik.
- **Sunucu tarafı guard eklendi:** wizard'a yalnız butondan girilmiyor, ⚙ Actions bağlamsal
  aksiyonundan da giriliyor (`binding_model_id=field.operation`, orada sadece grup kısıtı var).
  `action_create_sale` artık `sale_id` dolu servis varsa `UserError` ile duruyor ve hiç sipariş
  üretmiyor — `create_sale_service`'teki simetrik guard'ın aynısı.
- **Testler:** 6 → **8** (satışlı serviste UserError + yeni sipariş oluşmaması; buton arch'ının
  `sale_id` koşulunu taşıması).
- **Şema:** yeni kolon `field.operation.sale_line_id` (m2o → sale.order.line, index, `ondelete=set
  null`, `copy=False`); başka alan/veri değişikliği yok. Sürüm 19.0.1.0.1 → 19.0.1.0.2 (canlı `-u`
  sırasında görünür olsun diye).

### Düzeltme: "satış ↔ servis" kenarının kayıtsız kalan yarısı

- **Satır bağı artık yazılıyor:** `create_sale_service` ve wizard, servisin doğduğu satırı
  `sale_line_id`'ye yazıyor (öncesinde `create_sale_service` docstring'i "No line ↔ service link is
  stored" diyordu). Böylece "fatura satırı → core `sale_line_ids` → sipariş satırı → servis" zinciri
  kurulabiliyor; eşleşme servisin doğduğu anda bilinen tek yer olduğu için bu kenar satış tarafının işi.
- **Para birimi/şirket taşınıyor:** servis `with_company(order.company_id)` bağlamında ve
  `currency_id = order.currency_id` ile yaratılıyor (öncesinde EUR siparişin tutarı şirket para
  birimli servise yazılıyordu — probe ile doğrulanmıştı). Wizard yönünde ters durum sessizce
  geçmiyor: sipariş para birimi servisten farklıysa `UserError`.
- **İptal davranışı:** iptal edilmiş siparişte `create_sale_service` `UserError` ile duruyor; var olan
  bağ koparılmıyor (servis yapılmış olabilir: form, imza, stok) — bu bilinçli davranış olarak
  docstring'e yazıldı.
- **Geri doldurma scripti:** `scripts/backfill_sale_line_id.py` (varsayılan **kuru koşu**). İsim veya
  satır tutarı eşleşmesiyle tek adaya düşen servisleri bağlar, çok adaylı/eşleşmeyeni raporlar.
- **Testler:** 8 → **11** (satır bağı + para birimi, iptal guard'ı ve bağın korunması, wizard para
  birimi reddi).

### Ek tur (2026-10-17): wizard para birimi ve fiyat listesi

- **Sipariş para birimi servisten kopamıyor:** wizard `pricelist_id` hiç yazmıyordu; sipariş şirket
  para birimine düşerken `service_price` dönüştürülmeden `price_unit`'e yazılıyordu (EUR servis TRY
  siparişte TRY tutar gibi görünüyordu). `_order_pricelist()` sırayla müşterinin fiyat listesini
  (para birimi uyuyorsa), servis şirketinde aynı para birimindeki listeyi, sonra şirket-nötr listeyi
  seçiyor.
- **Aynı para biriminde liste zorunlu değil:** servis zaten şirket para birimindeyse `pricelist_id`
  boş bırakılır (sipariş yine o para biriminde doğar). Yabancı para biriminde eşleşen liste yoksa
  `UserError` — tutar dönüştürülmediği için yanlış fiyat yazmaktansa durmak doğru.
- **`with_company` recordset karşılaştırma hatası:** `self._order_pricelist(op) in
  env["product.pricelist"]` Odoo 19'da kayıtları env'iyle karşılaştırdığı için her zaman `False`
  dönüyordu (testlerin 3'ü bu yüzden düşüyordu). Kontrol `not pricelist` oldu; liste sorgusu servis
  başına bir kez, döngüden önce yapılıyor.
- **Wizard `active_ids` sahipliği:** `default_get` yalnız `active_model == 'field.operation'` iken
  `active_ids`'i kullanıyor; başka modelden gelen id'ler servis sanılmıyor.
- **Testler:** 11 → **15** (`test_11` yabancı para biriminde liste yoksa ret, `test_12` şirket para
  biriminde listesiz sipariş, `test_13` yabancı para biriminde uygun listeye düşme, `test_14`
  para birimsiz servis, `test_15` yabancı `active_ids`).

### Alan kaldırıldı: `sale.order.field_operation_id` (2026-10-17)

- **Ölçüm (canlı kopya `uzman_fix_check`):** m2o **0 kayıtta** dolu; 12.090 servisin tamamı
  `field.operation.sale_id` üzerinden bağlı, m2o'su dolu olup `sale_id`'si başka siparişi gösteren
  kayıt **0**. Yani kaldırma veri kaybı yaratmıyor; alan pratikte ölüydü.
- **Kaldırıldı:** model alanı, formdaki gizli `<field>`, wizard'ın `sale.order.create` değeri.
  Bağın tek sahibi `field.operation.sale_id` (bir siparişin n servisi olabildiği için m2o zaten
  doğru temsil değildi).
- **Davranış korundu:** "Service" butonu `field_operation_count == 0` iken görünür; akıllı buton tek
  serviste formu, birden fazla serviste listeyi açar; `_prepare_invoice()` ilk servisi faturaya yazar.
- **Testler:** 15 → **16**; `test_04` iki yönlü bağ varsayımı yerine tek bağı (n servis dahil),
  `test_07`, `test_11`, `test_14` "sipariş sayısı değişmedi" kontrolünü kullanıyor, `test_16` akıllı
  butonun tek serviste formu / çok serviste listeyi açtığını sabitliyor.
- **Sürüm:** 19.0.1.0.2 → **19.0.1.0.3**. Odoo 19 `-u` sırasında alan kaydını ve **kolonu** düşürdü
  (`uzman_fix_check`: `ir_model_fields` kaydı yok, `information_schema`'da kolon yok); kolon 0 dolu
  olduğu için veri kaybı yok, geri dönüş gerekirse alan yeniden kurulmalı.

### i18n (2026-10-17)

- **`pot` yeniden üretildi:** `odoo-bin i18n export -l pot` → 19.0 damgası, **47 giriş** (v18
  kalıntısı 33 girişin yerine; sale_line_id yardımı, para birimi/fiyat listesi hataları dahil).
- **`tr.po` sıfırdan kuruldu:** 47/47 çeviri, **0 boş**, yer tutucular birebir (`%s`,
  `%(service_currency)s`, `%(operation)s`); 14 yeni çeviri (9 hata mesajı + `Sale`, `Sales Order
  Line`, `Service Count` ve iki teknik anahtar). `Service Count` yanlış eski kopyası (`Servisler`)
  `Servis Sayısı` olarak düzeltildi.
- **Kopyaya yazıldı:** `odoo-bin i18n import -l tr_TR -w` → alan etiketleri (`Satış`, `Satış
  Siparişi Satırı`, `Servis Sayısı`) ve görünüm terimleri DB'de güncel. Kod çevirisi tr_TR'de
  probe'la doğrulandı: `FO/12686 servisinin para birimi yok: önce bir para birimi ayarlayın.`
  (yer tutucu korunuyor).
- `.mo` üretilmedi (önceki turdaki karar); sunucu `.po`'yu doğrudan yükler.

**Doğrulama (gerçek koşular):** scratch DB `master_sale_check`: `-u field_operation_sale
--test-enable --test-tags /field_operation_sale` → EXIT=0, **0 failed, 0 error(s) of 16 tests**
(hem para birimi turundan sonra hem alan kaldırıldıktan sonra), log'da 0 ERROR/CRITICAL. Canlı veri
kopyası `uzman_fix_check` (`uzman_v19_20261012`'nin pg_dump kopyası; canlı kopyaya yazılmadı):
`-u field_operation_sale` → EXIT=0, `latest_version=19.0.1.0.3`; `sale_line_id` kolonu geldi (0 dolu
— script çalıştırılmadı), `sale_order.field_operation_id` `ir_model_fields` kaydı ve DB kolonu düştü,
`sale.order` formu `or field_operation_count` taşıyor ve eski gizli alanı içermiyor. Gerçek kayıtlarla
probe (hepsi rollback, veriye yazılmadı): sipariş **S08681** (state `sale`, TRY, 1 ürün satırı) →
`create_sale_service` → 1 servis, `sale_line_id` = siparişin satırı, para birimi TRY, tutar 15000.0;
servis **FO/11022** → wizard → **S08694**, servisin `sale_line_id`'si o satır, para birimleri TRY/TRY,
tutar 2500.0 = satır fiyatı; iptal sipariş **S08659** → `UserError: This sale order is cancelled, no
service is created: S08659`. Geri doldurma kuru koşusu (aynı kopya, gerçek veri): scanned=12090,
**matched=7196**, ambiguous=150, unmatched=4744; iki örnek: FO/12683 → S08692'nin satırı (8000.0),
FO/12682 → S08668'in satırı (4500.0). pre-commit 11/11 Passed (ruff 0 ihlal).
Bilinen artıklar: `scripts/backfill_sale_line_id.py` canlıda `APPLY=True` ile çalıştırılacak
(öncesinde `pg_dump -Fc`); canlı `-u` ve `i18n import -w` kullanıcının kendi sunucusunda.

## [field_operation_geolocation: 19.0.1.2.0] — 2026-10-15

### İnceleme turu: "kim online" dürüstleşti, Geolocate butonu, ölü uçlar silindi (rapor: `field_operation_geolocation_inceleme_2026-10-15.md`)

- **P1 — `is_online` iki yönden güvenilmezdi, düzeltildi:** (1) `store=True` olduğu için
  yeniden hesap yalnız `last_update` yazımında tetikleniyordu → ping kesilen takım sonsuza
  dek "Online" kalıyordu (probe: `last_update` DB'den 2 saat geri çekildi, ORM hâlâ True
  okudu); alan artık **store'suz**. (2) `last_update`/`timestamp` `default=now` yüzünden hiç
  ping atmamış yeni takım 5 dk Online görünüyordu; default'lar kaldırıldı. İki regresyon testi
  eklendi.
- **P2 — `action_geolocate_operation` artık formdan erişilir:** operation formunun button_box'ına
  **Geolocate** butonu eklendi (`base.group_user`); eskiden yalnız RPC'den çağrılabiliyordu,
  onchange ise adres değişmedikçe tetiklenmiyordu. Arch testi eklendi.
- **P2 — ölü uçlar silindi:** `/field_team/get_positions` ve `/field_team/get_team_positions/<id>`
  hiçbir çağıranı yoktu (JS yalnız `get_my_team` + `update_gps` kullanır) ve own-team kısıtıyla
  dispeçere de veri vermiyordu; `_serialize_position` ile birlikte kaldırıldı, testi de düştü.
- **P3:** takım tarafındaki 0.0 falsy kontrolü `geo_helpers` kuralına bağlandı ("çift sıfır =
  koordinat yok", `lat=0.0` geçerli) — `action_show_on_map`, `action_show_team_locations` ·
  `mapbox_map.requires_api_key` False (URL'lerde `{API_KEY}` yok; `noupdate=1`, yalnız taze
  kurulumlara iner) · `tr.po`'daki **9 boş çeviri dolduruldu** (Geolocate→Konumlandır,
  Open Maps→Haritada Aç, 2 hata metni; pot=po=130, 0 boş).
- **README:** yasal dayanak satırı, karar için gereken dört teknik gerçeği listeleyen nota
  dönüştü (otomatik başlatma, ~5 dk ping, sınırsız geçmiş, görünürlük sınırı) + KVKK
  dayanağının **kurulumdan önce** belgelenmesi şartı; §6/§9 bayat noktaları düzeltildi.
- **Testler:** 27 → **29** (ölü uç testi düştü, 2 is_online + 1 arch testi eklendi).

**Doğrulama (gerçek koşular):** `-u field_operation_geolocation --test-enable --test-tags
/field_operation_geolocation -d fo_check` → EXIT=0, **0 failed, 0 error(s) of 29 tests**
(ruff-format sonrası iki kez); pre-commit 9/9 Passed; **canlı kopyada `-i` dry-run** →
EXIT=0, 5 sağlayıcı + cron pasif `1 days` + hook 16 kullanıcı, `latest_version=19.0.1.2.0`.
Aynı log'da geolocation ile İLGİSİZ önceden var olan bir satır: `Model muk_mcp.transfer has
no table.` (muk_mcp modülünün tablosu; canlı -i/-u planlanırsa izlenmeli). Sürüm artırılmadı
(şema/migration yok). Canlı sunucuda kurulum/`-u` kullanıcının adımı.

### PR #4 inceleme düzeltmeleri (2026-10-17)

- **README §Güvenlik silinen uçları anlatmayı bıraktı:** paragraf, kaldırılan
  `/field_team/get_positions` ve `/field_team/get_team_positions/<id>` uçlarını hâlâ "`sudo()` ile
  tüm takımları okumaz" diye tarif ediyordu (§9 güncellenmiş, güvenlik paragrafı kalmıştı). Artık
  geriye kalan iki uç (`get_my_team`, `update_gps`) ve iki ucun **kaldırıldığı** yazıyor.
- **Bayat sayılar:** README "35 dosya" → **37** (yeni test dosyası dahil), `static/description/index.html`
  sürümü `19.0.1.1.0` → **19.0.1.2.0** (manifest ile aynı; bir önceki turda `field_operation`
  için düzeltilen aynı hata sınıfı).
- **Koordinat kuralı gerçekten tek yerde:** `geo_helpers`'a değer alan `has_point(latitude,
  longitude)` eklendi, `has_coordinates()` onu çağırıyor. Önceki turun P3 notu "kurala çekildi"
  diyordu ama takım modelinde kural **satır içi kopyaydı** ve testi yoktu; `has_coordinates()`
  servis modelinin `service_*` alanlarına bağlı olduğu için takım modelinde doğrudan
  kullanılamıyordu. `action_show_on_map` ve `action_show_team_locations` artık `has_point` çağırıyor.
- **Testler:** 29 → **33**. `tests/test_team_map_actions.py` (4 test): `lat=0.0` kabul (ekvator),
  çift sıfır `UserError`, çoklu konum aksiyonunun ekvator takımını filtrelememesi, konumsuz takımda
  `UserError`.

**Doğrulama:** `fo_check` `-u field_operation_geolocation --test-enable --test-tags
/field_operation_geolocation` → EXIT=0, **0 failed, 0 error(s) of 33 tests**; mutasyon koşusu
(kural `or` yerine `and`'e çevrildi) → **tam olarak 2 yeni test** hata verdi
(`test_a_lone_zero_latitude_is_still_a_coordinate`, `test_the_multi_location_action_keeps_the_equator_team`),
diğer 31 test geçti; pre-commit 9/9 Passed (2 hook dosya tipi yok diye atlandı). Sürüm artırılmadı
(şema/migration yok).

## [field_operation: 19.0.2.3.0] — 2026-10-15

### İnceleme turu: `contact_mobile` salt-okunur, i18n tazelendi, doküman + temizlik (rapor: `field_operation_inceleme_2026-10-15.md`)

- **P1 — `contact_mobile` write-through kapatıldı (karar a):** alan `related="contact_id.phone",
  store=True, readonly=False` idi (`models/field_operation.py:78`); iş kartında telefon değiştirmek
  kişi kaydının telefonunu **global ve sessizce** yeniden yazıyordu (probe: `op.write(
  {'contact_mobile': '999'})` → partner phone 222 → 999). Liste `multi_edit` ile toplu yazım da
  açıktı. Artık `readonly=True` + açıklayıcı `help`; şema aynı, sürüm artırılmadı.
- **i18n tazelendi:** pot/po koddan 3 string gerideydi (+1 bayat). Koddan yeniden export (iki koşu,
  msgid seti stabil: 350); `tr.po` 344 çeviriyi korudu + 4 yeni çeviri (`Only office users are
  allowed to %s.`, `Signature is too large.`, `rrule_bymonthday` help'i, `contact_mobile` help'i).
  Eskiden beri boş olanlar aynen duruyor: mail template `body_html`, `team_id`.
- **Doküman:** README §8 test sayısı 11 → **14** (`test_service_repeat_wizard.py` belgelendi),
  bayat `(+ derlenmiş tr.mo)` iddiası ve "48 dosya" sayısı düzeltildi, fiyat politikası notu eklendi
  (karar b: portal **bilinçli** gösteriyor — backend Head Office kısıtıyla fark kasıtlı);
  `index.html` sürümü 19.0.2.2.1 → 19.0.2.3.0.
- **Temizlik:** ölü alias `open_team_tasks` kaldırıldı (`models/field_operation_team.py`); sihirbazın
  no-op `raise ve/ue` blokları sadeleşti, genel `except Exception` artık `_logger.exception` ile
  traceback bırakıyor (`wizard/service_repeat_wizard.py`).
- **Bırakılanlar (karar):** durum geçiş guard'ı (c — kural yeterli), 09 bakiyesi priority/`_order`
  (e — açık). 09 raporu m.6 retraksiyonu raporda: `ir_rule` flag'leri default True
  (`base/models/ir_rule.py:27-30`), worker kuralı yazma dahil 4 işleme uygulanır.

**Doğrulama (gerçek koşular):** `-u field_operation --test-enable --test-tags /field_operation
-d fo_check --stop-after-init` → EXIT=0, **0 failed, 0 error(s) of 14 tests**
(`/tmp/fo_check_update.log:75,101-102`); pre-commit 11/11 Passed; i18n export scratch conf'ta
(kullanıcının log'una dokunulmadı); **`uzman_v19_20261012`'ye yazılmadı** — canlıya alım kullanıcının
kendi sunucusunda `-u field_operation` ile (etiket değişmedi, Apps listesi işaret vermez).

**PR #1 gözden geçirme turu (tate1192):** Talep 1 gereği `test_12_contact_mobile_reads_through_
without_writing_back` eklendi — readonly bayrağı, yazımın partner'a akmaması ve read-through sabitlendi
(forms modülündeki muadil desen); suite **15 test**. Ayrıca `tr.po`'nun düşen 3 satırlık Odoo başlığı
geri eklendi (export churn'ü kalmasın). Doğrulama: aynı koşu → **0 failed, 0 error(s) of 15 tests**.
Talep 2 (main/19.0 ayrışması) aynı daldan `main`'e açılan ikinci PR ile karşılanıyor.

## [field_operation_geolocation: 19.0.1.2.0] — 2026-10-13

### Ölü `boolean_button` widget'ı iki görünümden kaldırıldı

`boolean_button` 19.0 web client'ında **kayıtlı değil** ve bilinmeyen widget adı hata vermez:
`getFieldFromRegistry` (`web/static/src/views/fields/field.js:132-142`) `<jsClass>.<widget>` →
`<viewType>.<widget>` → çıplak ad sırasıyla arar, bulamazsa konsola
`Missing widget: X for field of type Y` yazar ve tipin varsayılan widget'ına düşer. Yani alan
görünmeye devam etti, istenen görünüm hiç gelmedi, log'da iz kalmadı.

- `views/field_operation_team_view.xml`: `is_online` computed + readonly (`models/field_operation_team.py:17`)
  → `widget="boolean_toggle" readonly="1"` (core da böyle kullanıyor: `l10n_ec/views/l10n_ec_sri_payment.xml:30`).
- `views/maps_website_view.xml`: `active` gerçek arşiv bayrağı → `widget="boolean_toggle"`.
  `options='{"terminology": ...}'` bu widget'larda 19.0'da yok, kaldırıldı.
- Aynı kalıp `field_operation_whatsapp`'ta zaten düzeltilmişti (testi de var); bu iki yer kalmıştı.
- Test: `tests/test_geolocation_views.py` (2 test, view kayıtlarının arch'ı üzerinden).

**Doğrulama (gerçek koşular):** `-u field_operation_geolocation --test-enable
--test-tags field_operation_geolocation -d soft_gantt_check --stop-after-init` → EXIT=0,
"0 failed, 0 error(s) of 27 tests" (modül istatistiği: 35 test); pre-commit 11/11 Passed.

**Açık (ayrı onay bekliyor):** yeni kurulan takım `is_online = True` görünüyor — `last_update`
alanının `default=fields.Datetime.now` değeri yüzünden (`models/field_operation_team.py:16` +
compute `:66-73`); hiç ping göndermemiş takım 5 dakika "Online". Ayrıntı: legacy inceleme raporu.

## [field_operation: 19.0.2.3.0] — 2026-10-13

### Action context'indeki `partner_display_name_hide_company` kaldırıldı; sürüm etiketi geri alındı

- **Anahtar ölü değil, core okuyor:** `odoo/addons/base/models/res_partner.py:388`
  (`_get_complete_name()`) — truthy iken kişi adı firma ön eki olmadan gösterilir
  ("Hisar Yapı İlkokulu, Cihan Bey" yerine "Cihan Bey"); core da kullanıyor
  (`crm/views/crm_lead_views.xml:450`). **Action** context'inde durduğu için o action'ın
  bütün görünümlerine (list, kanban, form, calendar, graph, pivot) uygulanıyordu → listede ve
  kanbanda partner etiketleri firma adını kaybediyordu. `action_field_operation` context'inden
  çıkarıldı (`views/field_operation_view.xml:338-344`). Alan seviyesindeki kullanımlar korundu
  (formdaki `address_id`/`contact_id`, calendar'daki iki alan, `field_operation_contract` form +
  wizard): orada anahtar sadece o picker'ı etkiler.
- **Sürüm etiketi `19.0.0.1.0` → `19.0.2.3.0`:** etiket 2026-10-09 23:17'de elle düşürülmüştü
  (`field_operation_inceleme_2026-10-09.md:6`) ama DB'lerin `latest_version`'ı 19.0.2.3.0 kaldı;
  etiket aşağı kalınca modül için ileride yazılacak `migrations/<sürüm>/` klasörleri
  kendiliğinden çalışmaz hale geliyordu. Kod değişmedi, yalnız etiket ve README satırı.

**Doğrulama (gerçek koşular):** XML parse OK; `-u field_operation -d soft_gantt_check
--stop-after-init` → **EXIT=0, 0 ERROR**; `ir_act_window` context'inde anahtar yok;
`ir_module_module.latest_version` = **19.0.2.3.0**.

## [field_operation_geolocation: 19.0.1.2.0 / field_operation_whatsapp: 19.0.1.1.0] — 2026-10-12

### Servis formu kısayolları sahibine taşındı; `field_operation_forms_ext` kaldırıldı

`field_operation_forms_ext` (legacy, hiçbir DB'de kurulu değil) `field.operation.forms` için
`action_open_map`, `action_geolocate_address` ve `action_message_send` kopyalarını taşıyordu ve
Whatsapp butonu **grupsuzdu**: formu görebilen ama `field.whatsapp.message` yetkisi olmayan kullanıcı
butonu görüp tıklayınca `AccessError` alıyordu (ölçüldü: `You are not allowed to create 'Send
WhatsApp Message'`). Karar: özellikler sahibi modüle taşınsın, kopya modül **kaldırılsın**.

- **geolocation (19.0.1.2.0):** `field.operation.forms` üzerinde `service_latitude` /
  `service_longitude` (related, stored), `action_open_map`, `action_geolocate_address`; listeye
  **Open Maps** (`base.group_user`), forma **Map** + **Geolocate** (`base.group_user`) butonları.
  Yeni bağımlılık `field_operation_forms`. Ortak mantık tek kaynakta:
  `models/geo_helpers.py` + `maps.website._get_lat_lon_url()` + `res.users._get_map_provider()`.
- **whatsapp (19.0.1.1.0):** aynı **Whatsapp** butonu servis formu görünümüne `groups` ile eklendi;
  aksiyon sihirbazda tek kaynak (`field.whatsapp.message._open_action_for`). Yeni bağımlılık
  `field_operation_forms`.
- **Düzeltilen mantık hataları:** (1) `(0.0, 0.0)` çifti artık "koordinat yok" sayılıyor; eski
  `is None` kontrolü **ölü koddur** (ORM Float'ta NULL'ı `0.0` döndürür, ölçüldü: kolon NULL,
  okuma `0.0`) ve `lat=0.0` (ekvator) geçerli kabul ediliyor; `action_show_selected_routes`'un
  aynı falsy kontrolü de düzeltildi. (2) `action_geolocate_operation` / `action_geolocate_address`
  artık kör "başarılı" demiyor: `geo_localize()` eşleşme bulamazca hata atmaz, bus bildirimi
  gönderir; koordinat oluşmadıysa **warning** dönüyor.
- **Test:** geolocation 15 → **25 test** (yeni `tests/test_field_operation_forms_map.py`, 10 test),
  whatsapp 17 → **23 test** (yeni `tests/test_field_operation_forms_button.py`, 6 test).
- **Forms_ext silindi:** modül dizini legacy'den kaldırıldı; hiçbir gerçek DB'de kurulu olmadığı
  için migration gerekmedi.

**Doğrulama (gerçek koşular):** `-u field_operation_geolocation,field_operation_whatsapp`
`--test-enable` iki DB'de → **0 failed / 0 error (48 test)**; temiz kurulum `fx_check`
(`-i` ile, 51 modül) hatasız; pre-commit/ruff temiz.

**Açık kalan (ayrı iş):** `action_geolocate_operation` `field.operation` görünümlerinde hâlâ
buton olarak yok (RPC'den çağrılabilir); GPS uçlarının hukuki dayanağı `<!-- DOLDURULACAK -->`.

## [field_operation_whatsapp: 19.0.1.0.0] — 2026-10-11

### Repoya alındı + dört P1 düzeltildi (inceleme: `field_operation_whatsapp_inceleme_2026-10-11.md`)

Modül hiçbir DB'de **kurulu değildi** (canlıda `field_whatsapp_log` tablosu bile yok; temiz kurulum
EXIT=0). Gönderim gerçek API değil **deep-link**: tarayıcı WhatsApp penceresini açar, mesajı kullanıcı
gönderir. Karar (a): toparla ve repoya al (deep-link kalıcı kabul edildi). Düzeltilenler:

- **Rapor linki ölüydü (P1):** kod `report_name='field_operation.field_operation_pdf'` arıyordu; öyle bir
  rapor yok (ölçüm: 0 kayıt; gerçek ad `field_operation.field_work_delivery_pdf`, xmlid
  `field_operation.field_operation_action_pdf`). Kutucuk işaretlenince `UserError` atıyordu. Artık xmlid
  ile `env.ref` + gerçek render (ölçüldü: 17 test, gerçek PDF) ve yalnız `field.operation` için.
- **Link müşteride açılmıyordu (P1):** ek `public=False`/token'sız üretiliyordu; `/web/content` anonim
  kullanıcıda `check_access('read')`e düşüp reddediyordu (`ir_binary._find_record`,
  `ir_attachment._can_return_content`). Artık **`access_token`'lı** link üretiliyor (numaralandırma yok),
  görünürlük kararı (b) bu yönde.
- **Şablon arşiv düğmesi kırıktı (P1):** `widget="boolean_button"` v19'da **yok** (registry: boolean,
  boolean_favorite, boolean_icon, boolean_toggle) → `boolean_toggle`'a çevrildi (karar (d)).
- **Günlük kişisel veri + herkese açıktı (P1):** müşteri telefonu ve mesaj metni tüm ofis grubuna
  açıktı, `ir.rule` yoktu. Karar (c): log modeline `company_id` eklendi, **global şirket kuralı**
  (`security/ir_rule.xml`) ve **silme yalnız yöneticide** (ACL 1/1/1/0 + manager satırı).
- **Dürüstlük (P2):** günlük ve chatter artık "WhatsApp opened for …" diyor, günlüğe **temizlenmiş**
  numara yazılıyor (eskiden "gönderildi" deniyor ve ham numara kaydediliyordu) (karar (e)).
- **Yer tutucu doğrulaması:** bilinmeyen `{alan}` kayıtta `ValidationError` (eskiden müşteriye `{yok}`
  olarak gidiyordu).
- **Temizlik:** `boolean_button` dışında buton artık iç içe ikinci `oe_button_box` açmıyor + `groups`
  taşıyor; günlüğe arama görünümü (aksiyonun `search_default_res_model`'i artık çalışıyor); ölü
  `get_sample_templates()`/`get_available_fields_list()` kaldırıldı; `tr.mo` silindi (Odoo `.po`'dan
  üretir); 5 dosyadaki CRLF → LF; ACL ad yazım hataları; manifest `security/ir_rule.xml` + double-quote
  düzeni; `# +++++++ REPLACE` işaretçisi; `except Exception: pass` daraltıldı; suite başlıkları;
  `i18n/*.pot` + `tr.po` (91 msgid, 80 gerçek çeviri korundu); README koda göre baştan yazıldı.

**Not (inceleme sırasında düzeltilen kendi hatam):** CRLF→LF normalizasyonu ikili dosyayı da
(`static/description/icon.png`) dönüştürdü ve PNG bozuldu; ikon **v18 kopyasından byte-byte geri
yüklendi** (md5 `ffbedd8fbb3c03dc672f9e2f577cf9ef`, 256×256, PIL ile doğrulandı).

### Doğrulama
- `-u field_operation_whatsapp --test-enable --test-tags field_operation_whatsapp` → **0 failed / 0 error (17 test)**
- Modül repodan yükleniyor: `field_operation_whatsapp.__file__` → `/home/tate/dev/saha/field_operation_whatsapp/__init__.py`
- pre-commit 11/11 Passed · ruff 0 bulgu · i18n export kullanıcının canlı log'una dokunmadı
- **`uzman_v19_test`'e yazılmadı** (modül orada kurulu değil; kurmak için `-i field_operation_whatsapp`)

**Açık kalan (ayrı iş):** bağımlı modül `field_operation_forms_ext` (legacy, kurulu değil) aynı sihirbazı
kendi `action_message_send` kopyasıyla açar; karar (g) gereği bu turda dokunulmadı.
_(2026-10-12'de yapıldı: modül kaldırıldı, kısayollar geolocation/whatsapp'a taşındı — bkz. en üstteki girdi.)_

## [field_operation_contract_repeat: 19.0.1.0.0] — 2026-10-11

### Repoya alındı + altı P1 düzeltildi (inceleme: `field_operation_contract_repeat_inceleme_2026-10-11.md`)

Modül hiçbir DB'de **kurulu değildi** (temiz kurulum EXIT=0 ile mümkün: sorun bozukluk değil,
sahiplenilmeme) ve canlıda izi yoktu: `uzman_v19_test` → 13.304 `field.operation`, 534 sözleşmeli,
`subject='Scheduled Service'` olan **0**. Karar (a): toparla ve repoya al. Düzeltilenler:

- **`view_mode` yarışı yok — bu modül aksiyonu yeniden yazmıyor**, üretilen kayıtlar
  `field_operation.action_field_operation` ile açılıyor (ölçüm: `view_mode` = `list,kanban,form,calendar,gantt_soft,graph,pivot,activity,leaflet_map`).
- **Saat dilimi (P1):** `_local_to_utc` (kardeş modülden) — `context.tz` → kullanıcı tz → UTC.
  Ölçüm: `tz=Europe/Istanbul` + `2026-11-01` artık `2026-10-31 21:00:00` yazıyor (eskiden `00:00`, ekranda 03:00).
- **Aylık gün varsayılanı (P1):** `rrule_bymonthday` artık `start_date`'ten türüyor (`compute`, `readonly=False`,
  `precompute=True`). Ölçüm: 1 Kasım'da başlayan aylık kural işleri 11'inde üretiyordu, şimdi 1'inde.
- **Sınır sırası (P1):** `islice` ile en fazla `max_operations + 1` tarih üretiliyor; eskiden liste
  tamamen kurulup sonra kontrol ediliyordu (ölçüm: 100.000 tarih 0,139 sn'de üretilip reddediliyordu).
- **Zorunlu alanlar (P1):** `partner_id`/`user_id`/`company_id`/`subject`/`start_date`/`service_type_id`
  `onchange` yerine `compute`+`precompute` ile doluyor; yalnız `contract_id` ile `create` artık
  `NotNullViolation` vermiyor (ölçüm: `null value in column "partner_id"`).
- **Mükerrer koruması (P1):** aynı sözleşmede aynı tarihte kayıt varsa atlanıyor, kaç kaydın atlandığı
  uyarı olarak bildiriliyor ve `params.next` ile üretilen liste açılıyor.
- **İzin (P1):** buton `groups="field_operation.group_field_operation_recurring"` + `invisible="state == 'cancel'"`
  ve ACL satırı da aynı gruba çevrildi (eskiden butonda grup yoktu, ACL ofis grubundaydı).
- **İçerik (P2):** üretilen kayıt `status='draft'` (sözleşme cron üreticisiyle aynı), `end_date = start + 1 gün`
  (Gantt çubuğu görünür), `service_type_id` boşsa sözleşmenin ilk servis tipi devralınıyor.
- **Buton** `context="{'default_contract_id': id}"` ile açık sözleşmeyi taşıyor (P2).
- Temizlik: Türkçe kod yorumları İngilizce'ye çevrildi, `except ValidationError as ve: raise ve` kaldırıldı,
  hata `from error` ile sarılıyor (`noqa: BLE001` gerekçeli), ruff 27 bulgu → **0**, suite başlıkları,
  `i18n/*.pot` + `tr.po` (84 msgid), README baştan yazıldı.

### Doğrulama
- `-u field_operation_contract_repeat --test-enable --test-tags field_operation_contract_repeat` → **0 failed / 0 error (14 test)**
- Modül repodan yükleniyor: `field_operation_contract_repeat.__file__` → `/home/tate/dev/saha/field_operation_contract_repeat/__init__.py`
- pre-commit 11/11 Passed · ruff 0 bulgu · i18n export kullanıcının canlı log'una dokunmadı (boyut+mtime aynı)
- **`uzman_v19_test`'e hiç yazılmadı** (modül orada zaten kurulu değil; kurmak istersen `-i field_operation_contract_repeat`)

## [field_operation: 19.0.0.1.0] — 2026-10-11

### Düzeltildi — tekrar sihirbazında iki kusur (kardeş modülle aynı desen)

`field_operation_contract_repeat` incelemesinde çıkan iki kusur, aynı mantığın kopyası olan bu
modüldeki `service.repeat.wizard`'da da vardı; karar (d+e) uyarınca ikisi de burada da düzeltildi:

- `rrule_bymonthday` artık `dtstart`'ten türeyen bir `compute` (`store=True, readonly=False, precompute=True`);
  eskiden `today.day` idi → 1 Kasım'da başlayan aylık kural işleri ayın 11'inde üretiyordu.
- `max_recurring_operations` sınırı artık `islice` ile tarihler **üretilirken** uygulanıyor; eskiden
  `list(rrule.rrule(...))` tamamen kurulup sonra kontrol ediliyordu (ölçüm: 100.000 tarih 0,139 sn'de).
- Test: `tests/test_service_repeat_wizard.py` (3 test) — ayın günü başlangıçtan, elle değiştirilebilir,
  sınır 5 sn altında ve kayıt üretmeden hata veriyor. Modül suite'i **14 test** (11 → 14).

### Doğrulama
- `-u field_operation --test-enable --test-tags field_operation` → **0 failed / 0 error (14 test)**
- Sürüm **artırılmadı** (istenmedi): bu düzeltmeyi canlıya almak için elle `-u field_operation` gerekir.

## [field_operation_gantt: 19.0.1.0.0] — 2026-10-11

### Repoya alındı + `view_mode` yarışı düzeltildi (inceleme: `field_operation_gantt_inceleme_2026-10-11.md`)

`2026-10-07` raporundaki uyarlama planı uygulanmış bulundu: modül kendi `fo_gantt` view tipini ve gömülü
dhtmlxGantt'ı bırakmış, `soft_gantt` üzerinde `gantt_soft` görünümü kullanıyor, lisans **AGPL-3**, K1/K2
kararları işlenmiş. Bu turda yapılanlar:

- **P1 — `view_mode` yarışı (ölçüldü):** aksiyonun `view_mode` dizesini **üç modül tam dize** olarak
  yazıyordu (`field_operation`, `field_operation_map`, bu modül) → son güncellenen kazanıyordu. Scratch
  DB'de ölçüm: bu modülden sonra `-i field_operation_map` aksiyonu `kanban,list,form,activity,leaflet_map`
  bırakıyordu — Gantt **ve** `calendar`/`graph`/`pivot`/`activity` modları sessizce kayboluyordu.
  Artık veri kaydı yerine **idempotent `<function>`** (`models/ir_actions_act_window.py`): mod okunur,
  `gantt_soft` `calendar`'dan sonra eklenir, kalan modlar korunur. Ölçüm sonrası sıra:
  `list,kanban,form,calendar,gantt_soft,graph,pivot,activity,leaflet_map` — `-u field_operation`,
  `-u field_operation_gantt`, `-u field_operation_map` sonrası **hiçbir mod düşmüyor**.
- Kardeş ayak `field_operation_map` modülünde de düzeltildi (aşağıdaki girdi).
- **Test:** 7 → **10 test** (modun diğer modları düşürmeden eklenmesi, kardeş modül dizeyi ezse bile modun
  geri gelmesi, fonksiyonun idempotent olması).
- **Doküman düzeltmeleri:** README'de `label="partner_id"` yazıyordu (görünümde `label="team_id"`);
  soft_gantt test sayıları bayattı (21 python / 101 JS ölçümüyle güncellendi); `TEKNİK BORÇ` notu
  çözümün açıklamasıyla değişti.
- **i18n:** `i18n/field_operation_gantt.pot` + `i18n/tr.po` üretildi (10 msgid, msgid setleri aynı).
- **Başlıklar:** 6 dosyadaki core başlığı (`# Part of Odoo. See LICENSE...`) suite standardına
  (`# Copyright(C) 2026 - Today Softteknik Bilişim`) çevrildi.
- Sürüm `19.0.1.0.0` kaldı (şema/veri değişikliği yok).

### Doğrulama
- `-u field_operation_gantt --test-enable --test-tags field_operation_gantt` → **EXIT=0, 0 failed / 0 error (10 test)**.
- Scratch DB sıra testi: base → `+gantt` → `+map` → `-u field_operation` sonrası **tüm modlar yerinde**.
- Modül artık repodan yükleniyor: `field_operation_gantt.__file__` → `/home/tate/dev/saha/field_operation_gantt/__init__.py`.
- **`uzman_v19_test`'e dokunulmadı** (modül orada kurulu; repoya taşınma davranışı değiştirmez).

## [field_operation_map: 19.0.1.1.0] — 2026-10-11

### Düzeltildi — aksiyonun `view_mode`'u ezilmiyor, mod **ekleniyor**

`views/field_operation_view.xml` içindeki veri kaydı `view_mode`'u **tam dize** olarak yazıyordu
(`kanban,list,form,activity,leaflet_map`). Bu, aksiyonu paylaşan modüllerde "son güncellenen kazanır"
yarışı yaratıyordu ve iki yönlü hasar veriyordu (scratch DB'de ölçüldü): `-u field_operation_map`,
`field_operation_gantt`'ın `gantt_soft` modunu **ve** core'un `calendar`/`graph`/`pivot`/`activity`
modlarını siliyordu. Artık `models/ir_actions_act_window.py`'deki idempotent fonksiyon data dosyasından
`<function>` ile çağrılıyor: mevcut modlar korunur, `leaflet_map` sona eklenir. Bağlama kaydı
(`ir.actions.act_window.view`, sequence 8) ve `hooks.py` uninstall temizliği değişmedi.

**Davranış notu:** modül artık açılış görünümünü `kanban`'a çekmiyor — eski tam-dize yazımı bunu
dolaylı olarak yapıyordu; şimdi aksiyonun kendi dizesi geçerli (açılış `list`).

**Test:** 4 → **7 test** (modun diğer modları düşürmeden eklenmesi, kardeş modül dizeyi ezse bile modun
geri gelmesi, idempotentlik).

## [field_operation_stock: 19.0.1.0.0] — 2026-10-11

### Düzeltildi (inceleme raporu: `field_operation_stock_inceleme_2026-10-11.md`)

**P0 — modül kuruluyordu ama hiçbir iş yapmıyordu** (sarf onay akışı üç noktadan kırıktı; modül bu
yüzden hiçbir DB'de kurulu değildi ve hatalar hiç yüzeye çıkmamıştı):

1. `stock.move` üzerinde **`name` alanı v19'da yoktur** (v18'de vardı) → picking oluşturma
   `ValueError: Invalid field 'name' on model 'stock.move'` ile düşüyordu (`field_operation_stock_line.py:170`).
2. Ölçü birimi alanı `stock.move`'da **`product_uom`**'dur; `product_uom_id` `stock.move.line` alanıdır →
   birincisi düzeltilmeden görünmeyen ikinci `ValueError` (`…stock_line.py:172`).
3. **`picked` set edilmediği için `stock.move._action_done` hiçbir move'u doğrulamıyordu**
   (`odoo/addons/stock/models/stock_move.py:2282-2286`): transfer `assigned` kalıyor, **stok çıkmıyor**,
   ama sarf satırı `done` işaretleniyor ve iş maliyetine giriyordu (sessiz veri bozulması). Doğrulamadan
   önce `move.picked = True` eklendi.

- **README:** yol/dosya sayısı düzeltildi, "Odoo 19 stok API notları" (§5.1) ve test tablosu eklendi,
  akış adımlarındaki satır referansları güncellendi.
- **Test:** modülde hiç test yoktu → **9 test** eklendi; ilki P0 regresyonu (onaydan sonra move `done` +
  `picked`, picking `done`, kaynak stok **10 → 7**, hedef konumda 3 birim).
- Sürüm artırılmadı: şema/veri değişikliği yok (kod + test).

### Karar sonrası ek düzeltmeler (2026-10-11, aynı sürüm — modül hiçbir DB'de kurulu değil)

İnceleme raporundaki üç karar aynı gün uygulandı (`19.0.1.0.0` kaldı: şema/migration yok, modül henüz
hiçbir müşteri DB'sinde kurulu değil):

- **(c) `confirmed` çıkmazı kapatıldı:** satır formundaki elle **Confirm** butonu kaldırıldı
  (`views/field_operation_stock_line_view.xml`). Bu buton yalnız `state = 'confirmed'` yazıyor, stok
  hareketi üretmiyordu; operation onayı da yalnız `draft` satırları aldığı için o satır bir daha stoğa
  gidemiyor ama maliyete giriyordu. Tek akış artık operation formu → "Sarfı Onayla".
- **(d) `done` satır silinemez:** `unlink` override eklendi (`field_operation_stock_line.py:144-160`);
  doğrulanmış stok hareketinin tek izi o satırdır. Draft satırlar eskisi gibi silinebilir.
- **(e) Çok şirket + ACL:** `security/ir_rule.xml` eklendi (global `company_id in company_ids` kuralı,
  machine modülündeki desenin aynısı) ve manager ACL satırı `base.group_system` →
  `field_operation.service_group_manager`.
- **Test:** 9 → **13 test** (done satır unlink engeli, draft silinebilirliği, satır formunda elle Confirm
  kalmadığı, çok şirket izolasyonu — machine'daki testle aynı desen).
- **Karar beklemeyen/verilmeyen kalemler:** `unit_price`/`subtotal` Float olarak **kalıyor** (karar:
  şema değişikliği yapılmasın). Üçüncü turda uygulananlar: boş ikon (1×1 px) yerine **suite ikonu**
  (256×256, md5 `8a1c447c…`) · **i18n iskeleti** (`i18n/field_operation_stock.pot` + `i18n/tr.po`,
  76 msgid; metinler karar gereği değiştirilmedi, `tr.po` boş msgstr'lerle duruyor) · maliyet alanlarının
  pozisyonel `//group/group[2]/field[@name='total_work']` çapası **`//field[@name='total_work']`** oldu
  (isim tabanlı; form arch'ında tek geçiyor — inherit edilmiş arch'ta üç alan doğrudan `total_work`
  sonrasında görünüyor, kontrol edildi) · `action_confirm` metodu **kaldı** ama artık RPC/entegrasyon
  için olduğunu anlatan docstring taşıyor.

### Doğrulama
- Kurulum (`soft_gantt_check`): `-i field_operation_stock --stop-after-init` → **EXIT=0**, ERROR/CRITICAL/
  `ParseError` yok, `state=installed`.
- Testler (`-u field_operation_stock --test-enable --test-tags field_operation_stock`) →
  **0 failed, 0 error(s) of 13 tests**; aynı sonuç temiz kurulumda (uninstall → `-i`) da alındı.
- DB kontrolü: kural `[('company_id', 'in', company_ids)]` + `global=True` olarak yazıldı; ACL satırları
  `Saha Çalışanı` / `Ofis Kullanıcısı` / `Admin` (yani `service_group_*`) gruplarına bağlı.
- Modül `apps/saha_legacy`'den repo köküne taşındı; canlı yükleme yolu doğrulandı
  (`field_operation_stock.__file__` → `/home/tate/dev/saha/field_operation_stock/__init__.py`).
- **`uzman_v19_test`'e dokunulmadı** (modül orada kurulu değil).

## [field_operation_worker: 19.0.1.1.0] — 2026-10-10

### Düzeltildi (inceleme raporu: `field_operation_worker_inceleme_2026-10-10.md`)

**P0 — modül hiç kurulamıyordu** (`-i` → EXIT=255, `CRITICAL Failed to initialize database`).
Gerçek engel: form görünümü **var olmayan bir metodu** çağırıyordu — `<button name="action_send_mail">`,
oysa `field.operation` üzerindeki metot **`action_send_report_mail`** (`field_operation.py:390`); Odoo 19
`type="object"` butonların modele çözülmesini doğruluyor → görünüm doğrulaması kurulumu düşürüyordu.

> **Düzeltme (dürüstlük notu):** inceleme ilk turda kök nedeni aynı header'daki **yorumlanmış butonlar**
> olarak gösterdi (hata mesajının “near:” bağlamı yorum bloğunu basıyordu). Kontrollü A/B denemesi bunu
> çürüttü: base modül de yorum içeren görünümlerle sorunsuz kuruluyor; yorumlar varken metot düzeltilince
> kurulum **EXIT=0**. Yani asıl engel metottu. Yorumlanmış ölü kod yine de kaldırıldı (kural ihlali) ve
> **her iki nedeni de koruyan** bir regresyon testi eklendi.

- **Ölü kod:** form header'ındaki 6 satır yorumlanmış ölü buton (`action_planned`/`action_cancel`/`action_draft`)
  silindi (karar: butonlar geri getirilmedi, mevcut akış korundu).
- **Görünüm adları worker'a özgü yapıldı:** `field.operation.{select,list,form,kanban}.worker` (önce base
  modülle birebir aynıydı → Görünümler listesinde ayırt edilemiyordu).
- **Manifest:** sürüm `19.0.1.1.0`; gömülü `description` (var olmayan **calendar** görünümünü iddia ediyordu),
  `contributors` ve boş `demo`/`assets`/`external_dependencies` anahtarları kaldırıldı.
- **README:** yol düzeltildi, calendar iddiası kaldırıldı, dosya sayısı güncellendi, **kurulum notu (P0)**
  ve test durumu eklendi; `static/description/index.html`'deki eski sürüm numarası düzeltildi.
- **Test:** modülde hiç test yoktu → **6 test** eklendi (kurulum regresyonu: yorumsuz arch + çözülemeyen
  object buton yok; worker'a özgü görünüm adları; aksiyon + `act_window.view` bağlantıları; worker menüsü ve
  grubu; **worker kayıt kuralı görünürlüğü** (atanmış iş görünür, atanmamış görünmez); `my_jobs` filtresi).

### Doğrulama
- Temiz kurulum (`work_verify2`): `-i field_operation_worker --test-tags /field_operation_worker` →
  **EXIT=0, 6/6 test YEŞİL**; sürüm `19.0.1.1.0`; DB'de görünüm adları `field.operation.*.worker` ✔;
  yorum düğümü **0**; ruff 0; CRLF 0; pre-commit 10/10.
- **`uzman_v19_test`'e dokunulmadı** — modül orada kurulu değil (kurulamıyordu).

## [field_operation_map: 19.0.1.1.0] — 2026-10-10

### Düzeltildi (inceleme raporu: `field_operation_map_inceleme_2026-10-10.md`)

İnce bir harita yapıştırıcı modülü (`field.operation` için `leaflet_map` görünümü + `display_address` alanı).
Kurulum engeli yoktu (`soft_web_map` bağımlılığı çözülüyor).

- **`uninstall_hook` aşırı genişti:** `view_mode`'unda `leaflet_map` geçen **tüm** aksiyonları tarayıp "yalnız harita"
  olanları **siliyordu** → yöneticinin oluşturduğu ilgisiz bir aksiyon da silinebilirdi. Artık **yalnız bu modülün
  değiştirdiği aksiyonu** hedefliyor: `leaflet_map` modunu çıkarıyor, diğer modların sırasını koruyor, **hiçbir şey
  silmiyor** ve idempotent.
- **i18n tamamen ölüydü:** `.pot`/`tr.po` 109 msgid taşıyordu ama koddaki `_()` metni **0** (çok daha büyük bir eski
  sürümden kalma). Koddan **yeniden üretildi**: 4 gerçek girdi (`Display Address`, `Display Name`, `Field Operation`, `ID`),
  pot ve tr.po kümeleri birebir aynı, boş çeviri yok.
- **Ölü dosyalar silindi:** manifestte geçmeyen **0 baytlık** `data/ir_actions_server.xml`; hiçbir yerde referansı
  olmayan `static/src/img/marker-icon*.png`; içeriği README değil **OpenStreetMap karo sunucu notları** olan `README.rst`.
- **Manifest:** sürüm `19.0.1.1.0`; gömülü `description`, boş `demo`/`assets`/`external_dependencies` ve standart dışı
  `contributors` kaldırıldı; **`soft_web_map` dış bağımlılığı** (harita görünüm tipini sağlıyor; bu repoda değil,
  `apps/soft` altında) İngilizce yorumla ve README'de belgelendi.
- **Standart:** ruff **3 → 0** (I001, F401, E501), CRLF → LF, README yolu (`apps/saha/...`) ve iddiaları düzeltildi,
  `static/description/index.html`'deki yanlış "kendi JS katmanı var" iddiası kaldırıldı.

### Doğrulama
- Temiz kurulum (`map_verify2`): `-i field_operation_map --test-tags /field_operation_map` → **4/4 test YEŞİL**, EXIT=0;
  sürüm `19.0.1.1.0`; ruff 0; CRLF 0; XML'ler parse edildi; i18n pot=tr.po=4 (fark 0, boş 0); pre-commit 10/10.
  Testler: `display_address`, harita görünümü + aksiyon bağlantısı ve **ilgisiz bir harita aksiyonunun hook'tan
  sonra hâlâ durduğu** regresyon testi.
- **`uzman_v19_test`'e dokunulmadı** — modül orada kurulu değil.

## [field_operation_geolocation: 19.0.1.1.0] — 2026-10-10

### Düzeltildi (inceleme raporu: `field_operation_geolocation_inceleme_2026-10-10.md`)

P0 yoktu (kurulum EXIT=0, `post_init_hook` idempotent); **9 P1** kapatıldı:

- **Konum sızıntısı (gizlilik):** `get_positions` / `get_team_position` `.sudo()` ile **tüm takımları** döndürüyordu →
  her iç kullanıcı tüm takımların canlı konum/batarya/şef bilgisini görebiliyordu. Artık **yalnız kullanıcının kendi
  takımı** (yazma tarafı zaten sınırlıydı). Gerekçe kodda: konum = kişisel veri, en az yetki.
- **API anahtarı ifşası:** `maps.website` ofis grubunda **tam yetkiliydi** ve `api_key` düz metin `Char`'dı →
  artık ofis grubu **salt-okunur**, yazma/silme **manager**'da, `api_key` **`password=True`** (maskeli).
- **GPS geçmişi gizliliği:** `team.location.history` üzerinde **kayıt kuralı yoktu** (herkes her takımın izini
  okuyup silebiliyordu) → kullanıcı **kendi takımının** kayıtlarıyla sınırlandı, manager tam yetkili.
- **Cron:** "Daily" adıyla **saatlik ve AKTİF** kuruluyordu; "denendi" işareti olmadığı için koordinatı bulunamayan
  **aynı ilk 50 kayıt sonsuza dek** yeniden deneniyor, `time.sleep(1.1)` ile worker ~55 sn bloke ediliyordu →
  artık **kapalı kuruluyor** (`active=False`), **günlük** (`1 days`), her denemede `geo_localize_attempted` işareti
  yazılıyor ve başarısız kayıt **30 gün** sonra yeniden deneniyor; `noupdate` kaldırıldı (tanım yükseltmede uygulanır).
- **JS "başlat" sessizce başarısız oluyordu:** `status:'started'` Selection'da yok → yazım patlıyor, **hiçbir şey
  kaydedilmiyordu**, buna rağmen "GPS Takibi Başlatıldı" gösteriliyordu → geçerli status gönderiliyor, sunucu hatası
  kullanıcıya bildiriliyor, `onWillUnmount` ile temizlik, `_t` çevirileri, `device_id` artık `userAgent` değil
  (randevu jetonu); geçersiz status yüzünden **konum yazımı düşmüyor** (yalnız geçersiz alan atılıyor).
- **Girdi doğrulama:** enlem/boylam aralığı, `float()` dönüşümü, `battery_level` 0-100, `status`/`signal_strength`
  beyaz listesi, `timestamp` doğrulaması; **`0.0` koordinatı artık meşru** (truthiness tuzağı kapandı).
- **i18n tümüyle bayattı** (var olmayan alan/dosya/aksiyon, mevcut 24 metnin 21'i eksik) → koddan **yeniden üretildi**:
  `.pot` ve `tr.po` **127 msgid**, kümeler birebir aynı, çevirisiz girdi yok.
- **Windows NTFS artığı** (`tests/__init__.py<U+F02A>Zone.Identifier`) silindi; `data/maps_website_data.xml`
  URL'lerindeki kaçmış satır sonu/girintiler temizlendi + dosya `noupdate="1"`; mapbox `provider_type` düzeltildi.
- **P2:** N+1 (`search_count` döngüde → `_read_group`), rota geçmişi **en yeni** noktalar (`order desc`), geçmiş
  modeline indeks + `_order`, `res_users.create()` gereksiz override'ı kaldırıldı, `active=True` filtresi, geniş
  `except`/B904, Türkçe kod+loglar İngilizceye, `logout`/emoji loglar temizlendi, `widget="selection"` (legacy)
  kaldırıldı, README yolu/iddiaları düzeltildi, manifest `19.0.1.1.0` + `hr`/`base_geolocalize` beyanı, ruff **~63 → 0**, CRLF 0.

### Doğrulama
- Temiz kurulum (`geo_verify2`): `-i field_operation_geolocation --test-tags /field_operation_geolocation` →
  **15/15 test YEŞİL**, EXIT=0; cron **`active=false`, `1 days`** ✔; `maps.website` 5 kayıt; `api_key` alanı maskeli ✔;
  9 XML parse edildi; i18n pot=tr.po=127 (fark 0); pre-commit 10/10.
- **`uzman_v19_test`'e dokunulmadı** — modül orada kurulu değil.

## [field_operation_attendance: 19.0.1.1.0] — 2026-10-10

### Düzeltildi (inceleme raporu: `field_operation_attendance_inceleme_2026-10-10.md`)

**Modül bozuktu:** kendi 25 testinin **8'i kırmızıydı** (ölçüldü), ikisi gerçek muhasebe hatası:

- **P0 (ay sınırı):** ayı aşan işler **tamamen düşüyordu** — sorgu yalnız `start_date`'e bakıyordu. Artık gerçek
  kesişim kuralı (`start ∈ dönem` VEYA `end ∈ dönem` VEYA dönemi kapsayan iş).
- **P0 (gün kırpma):** gün **numarası** ay kontrolü olmadan kullanılıyordu → Şubat 28 işi Mart raporunda 28. günü
  sayıyordu ve ayı aşan aralıkta kalan günler atılıyordu. Artık **tarih kesişimi**: her ay kendi payını sayıyor
  (Şubat 27 → Mart 2 işi 52 saat yerine **26 saat**).
- **P1 (saat):** çok günlük işin tüm duvar saati süresi başlangıç ayına yazılıyordu → artık günlerde olduğu gibi
  dönem sınırına **kırpılıyor** (gün ve saat tutarlı).
- **P1 (yetki/tutarlılık):** rapor `field.operation`'ı çağıranın kayıt kuralıyla okuyordu → **aynı ay iki kullanıcıda
  farklı toplam** çıkıyordu; ayrıca şirket filtresi yoktu. Artık `sudo()` + açık `company_id` filtresi.
- **P1:** hafta sonu sayılmaya devam ediyor ama **işaretli ve ayrı toplanıyor** (`work_days` / `weekend_days` /
  `total_days`); "seçim yapılmadı = tüm aktif personel" davranışı belgelendi ve şirketle sınırlandı; dönem sınırları
  **kullanıcı saat diliminden** üretiliyor; `raise ... from e`; xlsxwriter hatası artık sessizce yutulmuyor;
  `ir.attachment` tekrar üretilmiyor (dedupe + `res_model/res_id` bağlama); `date.today()` → `context_today`.
- **P1 (rapor):** aksiyon `field.operation`'a binding'li, wizard ACL'i yalnız ofis grubunda olduğu için **Field Worker
  tıklayınca AccessError** alıyordu → aksiyona `group_ids` eklendi (menü ile ACL hizalandı).
- **P2:** ölü `team_name`/`day_details`/`days_in_month` kaldırıldı; PDF adı ay adını basıyor (`..._March_2026.pdf`);
  TransientModel'e rapor binding'i kaldırıldı; `paperformat default` (v19'da okunmuyor) kaldırıldı; manifest
  `external_dependencies={'python':['xlsxwriter']}` + `depends += hr`; i18n yeniden üretildi (59 girdi, header 19.0,
  ölü girdi silindi, PO biçim ihlali düzeltildi); README yolu/sayıları düzeltildi ve eksikler dürüstçe yazıldı.

### Doğrulama
- **Yeni scratch DB (`att_verify`): `-i field_operation_attendance --test-tags /field_operation_attendance` →
  33/33 test YEŞİL**, 0 failed/error (bağımsız koşu); ruff **~44 → 0**; CRLF 0; tüm XML'ler parse edildi; pre-commit temiz.
- **`soft_gantt_check` notu:** o DB'de test registry'si bozuk (`res_company.security_lead` NOT NULL; kolon DB'de var,
  normal kurulumda sorun yok) → testler orada ortamsal hata veriyor; temiz DB'de yeşil.
- **`uzman_v19_test`'e dokunulmadı** — modül orada kurulu değil.

## [field_operation_agreement: 19.0.1.1.0] — 2026-10-10

### Eklendi
- Modül repoya alındı (inceleme + Faz 1+2).
- `tests/test_field_operation_agreement.py` — **8 test** (modülde test yoktu).
- `is_expired` (computed) + `_cron_expire_agreements()` + `data/ir_cron_data.xml` (**kapalı** kurulur: `active=False`).
- İmza damgalama (`write()`) + imza bütünlüğü constraint'i; PDF'te imza görseli, tarih ve referans.

### Düzeltildi (inceleme raporu: `field_operation_agreement_inceleme_2026-10-10.md`)
- **P1 — şablon değişkenleri bozuluyordu:** `self.variable_ids = (5, 0, 0)` **çıplak tuple**; ORM bunu CLEAR komutu
  saymayıp elemanları id olarak yorumluyordu (liste temizlenmiyor, yanlış kayıt bağlanıyordu). `[fields.Command.clear()]`
  oldu. (Not: `fields.Command.clear()` tek başına yazılsaydı aynı hata geri gelirdi — dönen 3-tuple.)
- **P1 — constraint içinde yazma:** `_check_expired` bir `@api.constrains` içinde `status='expired'` yazıyordu ve
  docstring yanıltıcıydı. Yazma kaldırıldı; süre bitimi **günlük cron** + `is_expired` computed ile yönetiliyor.
- **P1 — yetki/durum guard'ları:** durum metotlarında sunucu tarafı grup kontrolü (yalnız ofis grubu) ve kaynak-durum
  kontrolü eklendi; view butonları da `groups=` ile sınırlandı (Field Worker salt-okunur olduğu için AccessError alıyordu).
- **P1 — imza bütünlüğü:** imza yazılınca `signed`/`signed_on`/`signed_by` damgalanıyor; `signed=True` ise imza ve
  imzalayan zorunlu. PDF artık imza görselini (bozuk `'%s' % bytes` yerine `image_data_uri`), tarih ve referansı basıyor.
- **P1 — silme:** `service_group_user`'ın unlink hakkı kaldırıldı (silme yalnız manager) + `unlink()` guard'ı:
  bağlı operasyonu olan sözleşme silinemez (öncesinde operasyonlar sessizce bağsız kalıyordu).
- **P1 — gerçek müşteri verisi:** örnek şablonda gerçek müşteri (ad, adres, telefon, VKN, e-posta) vardı ve her
  kurulumda yükleniyordu → **anonimleştirildi** ve `demo/` altına taşınıp manifest `demo` listesine alındı
  (üretim kurulumuna artık hiç girmiyor). Aynı içerikli yetim `data/demo_agreement_template.xml` silindi.
- **P2:** `reference` unique + sequence yoksa hata; `contact_id` partner doğrulaması; `currency_id` şirketle ilişkili;
  `template_id` domain'ine şirket/aktif filtresi; `check_company` etkin (`_check_company_auto`); şablon `content`
  sanitize açık; `_get_field_value` allowlist + dar `except` + doğru tarih/liste biçimi; `sample_value` help'i
  gerçek davranışa uyduruldu; `variable.sequence` + `unique(template_id, name)`; `Date.context_today`; menü sequence
  çakışması; boş `context` alanı; `pdf_menu.xml` → `agreement_report.xml`; `action_load_template` dolu içeriği ezmiyor.

### Doğrulama
- `soft_gantt_check`: `-u field_operation_agreement --test-tags /field_operation_agreement` → **8/8 test yeşil**,
  0 failed/error (bağımsız koşuyla doğrulandı); kurulum **EXIT=0**; tüm XML'ler parse edildi; **ruff 5 → 0**; CRLF 0.
- **`uzman_v19_test`'e dokunulmadı** — modül orada **kurulu değil**; kurulum ayrı onay bekliyor.

## [field_operation_contractor: 19.0.1.1.0] — 2026-10-10

### Eklendi
- Modül repoya alındı (inceleme + Faz 1+2).
- `tests/test_field_operation_contractor.py` — **16 test** (modülde hiç test yoktu).
- Partner formunda taşeron işleri için **smart buton** (`service_contractor_count` + listeye geçiş).
- `res.partner.contractor_job_ids` (ters o2m) — sayacın doğru tetiklenmesi için.

### Düzeltildi (inceleme raporu: `field_operation_contractor_inceleme_2026-10-10.md`)
- **N+1 sorgu:** `res.partner` sayacı döngü içinde `search_count` çağırıyordu → her partner için ayrı SQL.
  Artık tek `_read_group` + `@api.depends('contractor_job_ids')` (partner listesi binlerce kayıtta da tek sorgu).
- **`display_name`:** yalnız taşeron adını döndürüyordu → m2o'da hangi **iş** olduğu görünmüyordu; artık
  `"<taşeron> - <iş>"`, tek değer varsa o. Döngü değişkeni `camp` → `job`.
- **`is_contractor` senkronu:** davranış aynı, ama yalnız gerçekten değişen partnerler yazılıyor ve yazım
  gerekçeli `sudo()` ile (sistem bayrağı; `res.partner` yazma hakkı olmayan kullanıcı akışı kırmıyor).
  Kalan-iş kontrolü tek sorguya indi; `active_test=False` ile arşivli iş de "iş var" sayılıyor (gerekçesi kodda).
- **ACL:** taşeron işini silme hakkı `service_group_user`'dan alındı (silme yalnız manager) — sözleşme modülündeki
  kararla tutarlı.
- **Manifest:** sürüm `19.0.1.1.0`; gömülü `description`, boş `demo`/`assets`/`external_dependencies` ve
  standart dışı `contributors` kaldırıldı.
- **Standart:** ruff **2 → 0**, CRLF 0, kod/docstring İngilizce; XML'lerde `attrs` yok.

### Doğrulama
- `soft_gantt_check`: `-u field_operation_contractor --test-tags /field_operation_contractor` →
  **16/16 test yeşil**, 0 failed/error (bağımsız koşuyla doğrulandı); tüm XML'ler parse edildi; ruff 0.
- Canlı ölçüm: `uzman_v19_test`'te yalnız **2 iş kaydı** ve 1 bağlı operasyon var (modül pratikte kullanılmıyor);
  düzeltmeler bu iki kaydı etkilemiyor.

## [field_operation_contract: 19.0.1.1.0] — 2026-10-10

### Eklendi
- Modül repoya alındı (derin inceleme + düzeltmelerle).
- `tests/test_contract_review_fixes.py` — 16 spec testi (mevcut 50 testin üzerine).
- Sunucu tarafı grup guard'ları (`_check_service_group_user` / `_check_service_group_manager`); `action_recurring_process` yalnız manager.
- `unlink()` override (bağlı sipariş/operasyon varsa silmeyi reddeder).

### Düzeltildi (inceleme raporu: `field_operation_contract_inceleme_2026-10-10.md`)
- **P0 (canlıda patlamıştı):** header modunda tekrar, dönem sonu yerine **bugünü** `last_date_processed` yazıp
  `recurring_next_date`'i bir gün ileri kuruyordu → aylık sözleşme **her gün** sipariş + operasyon üretiyordu.
  Kanıt: 65 sözleşmeden **613 sipariş**; 2026-03-04..09 arası **günde 33-38 sipariş**; ardından cron kapatılmış
  (`ir_cron` pasif, son çalışma 2026-03-09). Header yolu artık satır yolundaki `_get_period_end_date()` mantığını
  kullanıyor; `recurring_next_date` elle yazılmıyor (computed alan eziliyordu).
- **Portal PDF ucu 500 veriyordu:** `_render_qweb_pdf([id])` — v19 imzası `(report_ref, res_ids, data)`; artık
  rapor referansı ile çağrılıyor ve portaldan yapıldığı için `sudo()` kullanılıyor.
- **Yetki:** durum metotları ve sihirbaz sunucu tarafında grup kontrolü yapıyor (view'daki `groups=` yeterli değildi).
- **Silme/iptal:** sözleşme silinince siparişleri sessizce öksüz bırakıyordu → artık reddediliyor; `action_cancel`
  bağlı taslak sipariş/operasyonları iptal ediyor. `sale.order.service_contract_id` `ondelete='restrict'`.
- **Sihirbaz guard'ları:** aynı sipariş iki kez dönüştürülemez; iptal/tamamlanmış sipariş reddedilir; `order_types`
  sunucuda doğrulanır; partner siparişten türetilir; tek tip periyot (ör. haftalık) artık sözleşmeye yazılıyor;
  boş satır/servis tipi kontrolü. Sipariş state'i koşulsuz `sent`'e çekilmiyor.
- **Tekrar motoru:** `recurring_interval >= 1` kısıtı (0/negatif değer `_get_period_end_date` döngüsünü sonsuza
  sokuyordu); döngüye ilerleme güvenliği; `@api.depends` listesine `remaining_count` eklendi; çok-şirkette
  `create` çağrıları doğru şirket env'i ile yapılıyor; döngüdeki `message_post` sözleşme başına tek özet mesaja indi.
- **İmza bütünlüğü:** `signature_status` True ise dosya/isim/tarih zorunlu (`ValidationError`).
- **Ölü kod:** `to_renew` state'i ve kullanılmayan `unit_price` alanı kaldırıldı; wizard'daki kullanılmayan alanlar,
  kullanılmayan importlar, yorumlu `numbercall`/`doall` temizlendi.

### Standart
- Kod/docstring/help tamamı İngilizce; `t-esc` → `t-out` (~30); portal imza görseli `image_data_uri` ile düzeltildi;
  PDF'te alıcı imzası basılıyor + sabit Türkçe metinler İngilizce; aynı tablodaki iki "Total" ayrıldı; cron
  `forcecreate="1"` + açık `nextcall`; ruff **127 → 0**, CRLF → LF.

### Doğrulama
- `soft_gantt_check`: `-u field_operation_contract --test-tags /field_operation_contract` →
  **67/67 test yeşil** (50 mevcut + 16 yeni + 1), 0 failed/error; tüm XML'ler parse edildi; ruff 0.

## [field_operation_disinfect: 19.0.1.1.0] — 2026-10-10

### Eklendi
- Modül repoya alındı (inceleme + düzeltmelerle).
- `tests/test_field_operation_disinfect.py` — 4 test.
- `action_send_disinfect_mail()` + forma "Email" butonu (şablonun artık çağıranı var).

### Düzeltildi (inceleme raporu: `field_operation_disinfect_inceleme_2026-10-10.md`)
- **Kayıt kuralı:** `disinfect_user_rule` yalnız takım liderini kapsıyordu ve
  `('forms_id.team_leader_id','=',False)` dalı **sahipsiz satırları bütün saha kullanıcılarına açıyordu**
  (canlıda 23 satır). Kural forms modülüyle hizalandı: `forms_id.team_leader_id = user.id` **veya**
  `forms_id.person_ids.user_id = user.id`; orphan satırlar yalnız manager'da kalıyor.
- **PH/CL ikiliği:** ölçüm — form tarafı (Char) 813/812/813 dolu, satır tarafı (Integer) **0/0/0**;
  satır seviyesindeki ölü alanlar kaldırıldı, gerçek değerler formda kalıyor.
- **Ölü `code` alanı** (0/1.326) kaldırıldı; referansı `DIS-` serili `name` tutuyor.
- **E-posta şablonu:** adı "Field Biocide" ve konusu Türkçe "EK-1 Biyosidal Uygulama Formu" idi, koda
  referansı yoktu → "Disinfection Service Form" olarak yeniden adlandırıldı ve bir aksiyona bağlandı.
- **Etiketler:** satır koleksiyonu "Dispenser Type" → "Disinfection Lines"; ACL `name` kolonu
  kopyala-yapıştır "field_biocidal" idi → "Disinfection Lines/Products".
- **Standart:** sürüm `19.0.1.1.0`; CRLF → LF, sonda satır sonları, ruff 16+ → 0 + `ruff format`;
  yorumlu ölü kod (model + res_company + ürün view) temizlendi; `field.disinfect.product` sıralaması eklendi.

### Doğrulama
- `soft_gantt_check`: `-u field_operation_disinfect --test-tags /field_operation_disinfect` →
  **4/4 test yeşil**, 0 failed/error; tüm XML'ler parse edildi, ruff 0, CRLF 0.
- Canlı ölçüm (uygulanmadan önce): 1.326 satır / 1.191 form; kural düzeltmesi atanmış personeli kapsar,
  23 orphan satır sahadan çekilir; PH/CL alan silmeleri 0 dolu olduğu için veri kaybı yok.

## [field_operation_pest: 19.0.1.1.0] — 2026-10-10

### Eklendi
- Modül repoya alındı (inceleme + düzeltmelerle).
- `data/ir_sequence_data.xml` — kodun yıllardır aradığı `field.biocidal` serisi (BIO-).
- `migrations/19.0.1.1.0/post-migrate.py` — 8.044 "Yeni" pesticide kaydını numaralar.
- `tests/test_field_operation_pest.py` — 4 test.

### Düzeltildi (inceleme raporu: `field_operation_pest_inceleme_2026-10-10.md`)
- **Modül v19'da kurulamıyordu:** `data/uom_uom_data.xml` var olmayan `uom.product_uom_categ_vol`
  xmlid'ine referans veriyordu (v19'da uom kategorileri XML verisi olarak tanımlı değil; dosyadaki dört kayıt
  da bu yüzden kırıktı) → dosya kaldırıldı. Ölçüm: `-i` → `External ID not found` ile registry çöküyordu.
- **Hiç yüklenmeyen iki dosya:** `pdf/field_pest_pdf.xml` (PDF raporu hiç oluşmuyordu; canlıda pest raporu
  `uzman_field_operation_forms` modülünden geliyor) ve `data/email_template.xml` (şablon DB'de yoktu →
  `send_biocidal()` patlardı) silindi; `send_biocidal()` + `action_send_mail()` kaldırıldı (koşulu olan
  `biocidal` seçeneği hiçbir modülde tanımlı değil).
- **Ölü model:** `models/field_pest_equipment.py` (`field.biocidal.equipment`) `models/__init__.py`'de import
  edilmiyordu, tablo yoktu → silindi.
- **Pesticide referansı:** seri hiç tanımlı olmadığı için 8.044 kaydın tamamı "Yeni" adını taşıyordu.
- **`action_transfer()`:** `ensure_one()` yorumdaydı, yetki kontrolü yoktu ve picking'i forma bağlamıyordu →
  canlıda 0 bağlı sevkiyat. Artık: ensure_one + `forms_user` kontrolü + satır kontrolü + `field_operation_form_id`
  yazımı + `picking_count`/`action_view_picking` ve forma "Delivery" akıllı butonu.
- **v19 kırılması:** `stock.move` oluştururken `name` alanı yok (`KeyError: 'name'`) → kaldırıldı.
- **Standart:** manifest sürümü `19.0.1.1.0`, CRLF → LF, ruff 38 → 0 + `ruff format`, yorumlu ölü bloklar
  (model + pest_type + res_company view) temizlendi.

### Doğrulama
- `soft_gantt_check`: `-i field_operation_pest` → **EXIT=0, 0 ERROR** (öncesi: kurulum çöküyordu).
- `-u field_operation_pest --test-tags /field_operation_pest` → **4/4 test yeşil**.
- ruff 0 ihlal · CRLF 0 · pre-commit 11/11 Passed.
- Canlı etki (uygulanmadan önce ölçüldü): `-u` ile 8.044 kaydın adı `BIO-…` olur ve etiket düzeltmesi iner.

## [field_operation_forms: 19.0.1.1.0] — 2026-10-10

### Eklendi
- Modül repoya alındı (inceleme + düzeltmelerle).
- `tests/test_field_operation_forms.py` — 10 test (9 `TransactionCase` + 1 `HttpCase`), hepsi yeşil.
- `migrations/19.0.1.1.0/post-migrate.py` — ayrışmış operasyon ↔ form bağlarını yeniden hesaplar.

### Düzeltildi (inceleme raporu: `field_operation_forms_inceleme_2026-10-10.md`)
- **Arama çökmesi:** "Customer" kutusunun `filter_domain`'i var olmayan `partner_id` alanına işaret ediyordu
  (`ValueError: Invalid field field.operation.forms.partner_id`) → `customer_id`.
- **Çift bağ:** `field.operation.forms_id` ile `field.operation.forms.operation_id` birbirinden bağımsızdı ve
  canlı veride 200 kayıtta ayrışmıştı; `forms_id` artık `operation_id`'den türetiliyor (compute + store +
  readonly) ve `action_done` bağ yoksa sessizce geçmek yerine `UserError` atıyor.
- **Saha görünürlüğü:** `forms_user_rule` yalnız takım liderini kapsıyordu → atanmış personel kendi işini
  göremiyor, "My Task" filtresi (person_ids.user_id = uid) hiç eşleşmiyordu. Yeni domain:
  `status in ('new','completed') AND (team_leader_id = user.id OR person_ids.user_id = user.id)`; kapanan iş
  listeden çıkmaya devam ediyor. Canlı ölçüm: 4.344 formda lider `person_ids` içinde değildi.
- **Portal yazma hakkı kaldırıldı:** portal grubu artık yalnız okuyor; imza yazımı denetleyiciden `sudo()` +
  sabit alan listesiyle (`_portal_sign_customer` / `_portal_sign_staff`) yapılıyor ve yük base64 olarak
  doğrulanıyor. Ölçüm: portal kullanıcısı `status`, `solution` ve `staff_signature` yazabiliyordu.
- **Mükerrer form:** `action_create_forms` her basışta yeni form üretiyordu (canlı: 24 operasyonda >1 form,
  61 operasyonsuz form) → mükerrer guard + sunucu tarafı yetki kontrolü (`AccessError`).
- **Sunucu tarafı yetki:** durum aksiyonları yalnız view'daki `groups=` ile sınırlıydı; artık metot içinde
  kontrol var (`AccessError`), `action_done`'un operasyona yazımı `sudo()` + sabit alan listesiyle.
- **`_signed_on`:** `fields.Date.today()` bir `Datetime` alana yazılıyordu (gece yarısı) → `Datetime.now()`.
- **Portal breadcrumb:** kayıt id'si olmayan ve token'ı düşüren bir URL'e gidiyordu → id + token korunuyor.
- **Standart:** manifest `description` + boş anahtarlar kaldırıldı; CRLF → LF, eksik satır sonları, ruff
  25 → 0 ihlal + `ruff format`; yorumlu ölü bloklar (2 view + controller + şablon) ve kullanılmayan import'lar
  silindi; kod içindeki Türkçe hata mesajı İngilizce; menü adı "Filed Forms" → "Field Forms"; etiket
  çakışmaları giderildi (`Service Type Code`, `Created By User`).

### Karar
- Saha çalışanı kendine **atanmış veya lideri olduğu** formu görür; iş kapandığında (`done`/`cancel`) form
  listenin dışına çıkar (kullanıcı kararı — mevcut davranış korunarak kapsam genişletildi).
- Portal **salt-okunur**; imza yazımı uçlardan yapılır (kullanıcı kararı).
- Boş e-posta şablonu, `internal_notes` alanı ve kullanılmayan `pdf_header_footer.xml` şablonu bilinçli olarak
  dokunulmadı (içerik/kaldırma kararı bekliyor).

### Doğrulama
- `soft_gantt_check`: `-u field_operation_forms --test-tags /field_operation_forms` → **10/10 test yeşil**,
  0 failed/0 error; kurulumda etiket uyarısı yok.
- Migration gerçek veriyle denendi: `forms_id` SQL ile boşaltılıp sürüm düşürüldü → `-u` → bağ en yeni forma
  yeniden hesaplandı.
- ruff 0 ihlal · CRLF 0 · pre-commit 11/11 Passed.
- Canlı etki (uygulanmadan önce ölçüldü): 223 operasyonun `forms_id`'si değişir (~200 yanlış bağ temizlenir,
  ~23 eksik bağ doğru forma bağlanır); forms_user'ın görebildiği kayıt sayısı 145 (kapsam: atanmış personel dahil).

## [field_operation_invoice: 19.0.1.0.1] — 2026-10-10

### Eklendi
- Modül repoya alındı (inceleme + düzeltmelerle).
- `tests/test_field_operation_invoice.py` — 8 test, hepsi yeşil.

### Düzeltildi (inceleme raporu: `field_operation_invoice_inceleme_2026-10-10.md`)
- **Ölü `action_cancel` override'ı:** Odoo 19'da `account.move.action_cancel` yok (yalnız
  `action_post`/`button_draft`/`button_cancel`); metot hiç çağrılmıyordu ve "iptalde servisin bağını
  kopar" niyeti hiç gerçekleşmiyordu. Ölçüldü: `button_cancel()` sonrası `account_move_id` bağlı
  kalıyordu. Override kaldırıldı; bağın iptalde korunması bilinçli davranış olarak belgelendi (test 3).
- **Silmede bayat `invoicing`:** m2o cascade'i bağ kolonunu doğrudan SQL'de boşalttığı için servisin
  saklanan `invoicing` alanı "Billed" olarak kalıyordu; `unlink` artık bağı silmeden önce ORM üzerinden
  boşaltıyor (test 4).
- **Konsolide sihirbazda mükerrer fatura:** kontrol yalnız `default_get`'te olduğu için bayat bir
  sihirbaz aynı servis için ikinci fatura üretip bağı sessizce başka faturaya taşıyabiliyordu (ölçüldü).
  Kontrol `_check_operations()` ile `action_create_invoice` içinde de çalışıyor; bağ artık satırlardan
  (`line_ids.operation_id`) türetiliyor (test 7).
- **Alan sözleşmesi:** `invoicing` (elle girilen değerin hesap tarafından ezilebileceği) ve `payment`
  (faturayla senkronize edilmeyen, elle tutulan alan) `help` metinleriyle belgelendi.
- **Standart:** manifestteki gömülü `description` ve boş `demo`/`assets`/`external_dependencies`
  kaldırıldı; CRLF → LF, eksik satır sonları, ruff 22 → 0 ihlal + `ruff format`; iki view'daki
  yorumlanmış ölü bloklar ve kullanılmayan `operations_by_move` sözlüğü silindi; README'den yerel yol
  ve bayat dosya sayısı çıkarıldı; yorumlar İngilizce.

### Karar
- İptal edilen faturaya servis bağlı **kalır** (kullanıcı kararı): geçmiş servis kaydından okunabilir.
- `payment` alanı elle tutulmaya devam eder; `account.move.payment_state` ile senkronlanmaz.
- `field_operation_sale` başlık alanına (`account.move.field_operation_id`), bu modül satır alanına
  (`account.move.line.field_operation_id`) yazıyor — hizalama suite genelinde ayrı karar.

### Doğrulama
- `soft_gantt_check`: `-i field_operation_invoice` (EXIT=0) ve
  `-u field_operation_invoice --test-tags /field_operation_invoice` → **8/8 test yeşil, 0 failed/error**.
- ruff 0 ihlal · `ruff format` temiz · pre-commit tümü Passed.

## [field_operation_sale: 19.0.1.0.1] — 2026-10-09

### Eklendi
- Modül repoya alındı (daha önce repoda değildi).
- `tests/test_field_operation_sale.py` — 6 test: wizard akışı (sipariş + satır + iki yönlü bağ + sayaçlar),
  müşterisiz servis reddi, modül grubu reddi (wizard ve `create_sale_service`), fatura referansı (iki bağ
  yönü), satır başına servis + çift kayıt koruması + gerçek `start_date`.

### Düzeltildi (inceleme raporu: `field_operation_sale_inceleme_2026-10-09.md`)
- **Bağımlılıksız sayaçlar:** `sale.order.field_operation_count` artık `field_operation_ids` one2many'sine
  bağlı — dekoratör yorum satırındaydı, sayaç hiç tetiklenmiyordu. `field.operation.sale_count` → `sale_id`.
  `account.move.field_operation_count` kayıt bazlı hesaplanıyor ve
  `@api.depends("line_ids.sale_line_ids.order_id")` aldı; önce tüm kayıtlara tek (toplam) değer yazıyordu.
- **`sale_count` anlamı:** artık `sale_id` dolu ise 1. Önce hep boş kalan `sale.order.field_operation_id`
  sayıldığı için "Sale" butonu bağlı servislerde görünmüyordu. **Görünürlük değişikliği:** buton artık
  satışı olan her serviste çıkıyor.
- **Fatura referansı:** `_prepare_invoice()` `field_operation_id` boşsa ters bağa (`field.operation.sale_id`)
  bakıyor; mevcut siparişlerden kesilen fatura servis referansını alıyor.
- **`date` → `Datetime`:** `create_sale_service` `fields.Datetime.now()` yazıyor (önce `fields.Date.today()`
  ORM tarafından UTC 00:00'a çevriliyordu, servis "bugün 03:00" görünüyordu).
- **Satır adı:** `subject` artık ürün adını iki kez yazmıyor, sonda boşluk bırakmıyor.
- **Wizard:** `self.env.context` (19.0'da deprecated olan `self._context` yerine); varsayılan ürün config
  parametresi doğrulanıyor (bozuk değerde `ValueError` ile açılmıyordu); müşterisiz servis için okunur `UserError`.
- **Yetki:** `action_create_sale` ve `create_sale_service` modül grubunu sunucuda uyguluyor (`AccessError`);
  "Service" butonuna `groups=` eklendi.
- **Çift kayıt koruması:** `create_sale_service` siparişin servisi varsa `UserError` yükseltir.
- **Standart:** manifest gömülü `description` ve boş `demo`/`assets`/`external_dependencies` kaldırıldı;
  `order_types` view'da artık zorunlu değil (DB'de 2 boş kayıt vardı); 6 dosya CRLF→LF; Türkçe docstring'ler
  İngilizce; ruff 8 ihlal → 0.

### Karar
- İki yönlü bağ (`field.operation.sale_id` ↔ `sale.order.field_operation_id`) korundu: tek alana indirmek
  kurulu 12.032 kaydı ve diğer modülleri etkilerdi. `_prepare_invoice` ikisini de okur; `create_sale_service`
  yalnız `sale_id` yazar (n servis tek alana sığmaz), wizard ikisini birlikte.

### Doğrulama
- Scratch DB: `-u field_operation_sale --test-tags /field_operation_sale` → **6 test, 0 failed, 0 error**.
- Kurulu çalışma DB'sinde `-u field_operation_sale` → **0 ERROR / 0 CRITICAL**, `latest_version=19.0.1.0.1`,
  7 view yenilendi, yeni `sale.order.field_operation_ids` alanı yüklendi; öncesinde `pg_dump -Fc` yedeği alındı.

## [field_operation: 19.0.0.1.0] — 2026-10-09

### Düzeltildi
- Tek README: `README.rst` (oca-gen-addon-readme şablonu, onu üreten bir araç yok) kaldırıldı,
  `README.md` tek kaynak. Manifest'teki gömülü `description` kaldırıldı — Odoo 19'da verilirse
  README'yi ezer (`odoo/modules/module.py`).
- Portal PDF indirme başlığı sanitize edildi (ASCII'e indirgeme + tırnak/satır sonu temizliği);
  imza route'undan kullanılmayan parametre kaldırıldı, base64 gövdeye 512 KB üst sınır konuldu.
- `Cancel` / `Draft` durum geçişleri artık modelde de ofis grubuna kapalı: butonlar view'da
  `groups=` ile gizliydi ama yazma yetkisi olan herkes geçişi RPC'den çalıştırabiliyordu.
- `_check_company_auto = True` eklendi (`user_id.check_company` etkisiz durumdaydı).
- `field.operation.team` kısıtı `UserError` yerine `ValidationError` fırlatıyor.
- Modülün paperformat'ı artık sistem varsayılanı ilan edilmiyor (`default=False`).
- `data/module_category.xml` -> `data/res_groups_privilege.xml` (adı içeriğini yanlış anlatıyordu).
- Ölü kod silindi (`planned_date`, `planned_end`, `work_hours`, yorumlanmış `action_send_mail`).
- `_check_team_integrity` kayıt başına 2 sorgu yerine 2 toplu sorgu kullanıyor (N+1).
- Kod içi Türkçe yorumlar İngilizceye çevrildi.
- `t-esc` -> `t-out` (7 yer; Odoo 19'da `t-esc` deprecated), satır sonları LF'e normalleştirildi.

### Test
- 11 test, tamamı geçiyor.
- `test_11` düzeltildi: boş `fields.Json` değeri `False` döner (`[]` değil) — Odoo 19
  `Json.convert_to_cache` boş değeri `None`'a, `convert_to_record` `False`'a çeviriyor.
- `test_02` artık toplu sorguyu ölçüyor: iki kayıt tek `create` ile yazılıp `hr.leave` aramasının
  bir kez çağrıldığı doğrulanıyor.

## [field_operation_gantt_nexgen: 19.0.1.0.0] — 2026-10-07

### Eklendi
- Yeni modül `apps/saha/field_operation_gantt_nexgen`: `field.operation` kayıtlarını
  **`gantt_nex`** görünüm tipinde zaman çizelgesi olarak gösterir (view + action +
  menü, "Field Operation → Schedule"), duruma göre renk ve tamamlanma yüzdesi sunar.
- Sunucu tarafı tek servis: `field.operation.get_timeline_data(range_start, range_end,
  offset, limit, search_domain)` — kayıt kurallarına saygılı (sudo yok), `start_date`/
  `end_date` UTC Datetime penceresiyle kesişen kayıtları döner; istemci tarafı
  `SynGanttAction`'ı genişletip yalnız `loadData()` / `loadMore()`'u geçersiz kılar.
- v1 **salt-okunur**: `can_move`/`can_resize`/`can_delete`/`can_create` kapalı; sürükle-bırak
  ve dışa aktarma kapsam dışı. Arşivli (`active=False`) servisler zaman çizelgesine girmez.
- Bilinen sınır (v1): base'in dışa aktarma düğmeleri yalnız kendi adapter'ını tanıdığı için
  bu zaman çizelgesinde "adapter desteklemiyor" uyarısı verir; düzeltmek base'in exchange
  modelini genişletmeyi gerektirir.
- Doğrulama (scratch DB): modül kuruldu, **9 test 0 failed** (payload/paging, kayıt sözleşmesi,
  pencere kesişimi, geçersiz aralık, grup anahtarı, durum→renk/yüzde, arşiv filtresi);
  base'in kendi 13 testi de geçti.

### Bağımlılık / lisans uyarısı
- Modül **`gantt_base_nexgen`** (NexGen Gantt Base) modülüne bağlıdır; o modül **OPL-1
  (tescilli)** lisanslıdır ve müşteri tarafından ayrıca lisanslanmalıdır. Bu modülün
  kendi kodu **AGPL-3**'tür ve temel modülün kodundan hiçbir satır içermez.

## [field_operation: ekip kanban grafiği] — 2026-10-07

### Düzeltildi
- Ekipler kanban'ındaki haftalık servis grafiği OWL hatası veriyordu:
  `TypeError: Cannot read properties of undefined (reading 'map')`
  (`JournalDashboardGraphField.getLineChartConfig`). Kök neden: `_get_graph_data_batch`
  core'un **v17 öncesi** veri şeklini üretiyordu (`[{'label': 'Week 1', 'value': 26,
  'date_range': ...}]`); v17+ `dashboard_graph` widget'ı `data[0].values` okuyor
  (`web` › `views/fields/journal_dashboard_graph/journal_dashboard_graph_field.js:53`),
  bu yüzden **bugün servisi olan her ekipte** kanban çöküyordu. Veri şekli `account`/`mrp`
  ile aynı sözleşmeye çevrildi:
  `[{'key': 'Services', 'values': [{'x': '14/09', 'y': 26, 'name': '14/09 - 20/09'}, ...],
  'is_sample_data': False}]` — 4 haftalık kova başına tek sorgu korundu.
- `tests/test_field_operation.py`: grafik testi artık **şekli** doğruluyor (tek seri,
  `values` anahtarı, nokta `x`/`y`, boş ekipte dört sıfır nokta) ve widget'ın okumasını
  `json.loads(team.kanban_graph)[0]['values']` ile taklit ediyor. Önceki hâli yalnız
  "4 eleman var" diyerek yanlış sözleşmeyi kilitliyordu.

### Bilinen (bu değişiklikten bağımsız)
- `tests/test_field_operation.py::test_11_partner_statistics_expose_service_counter`
  v19'da kırık: `res.partner.application_statistics` bir `json` alan ve **boşken `False`**
  döndürüyor, test `[]` bekliyor (`assertEqual(company.application_statistics, [])`).
  1 satırlık düzeltme onay bekliyor.

## [soft_gantt: iki katmanlı başlık + ölçek = yakınlaştırma] — 2026-10-07

### Eklendi
- **Başlık iki katman**: üstte kapsayan bant (ay / hafta / gün), altta o ölçeğin ince
  birimi (saat / gün / hafta / ay) + hafta sonu gölgelemesi + **Today** etiketi ve
  bugün çizgisi.
- **Ölçek = yakınlaştırma**: `Gün` → o günün **saatleri** (00:00…23:00), `Hafta` → haftanın
  **günleri** (07 Çar gibi), `Ay` → ayın günleri, `Çeyrek` → haftaları, `Yıl` → ayları.
  Ölçek seçmek pencereyi de o ölçeğin uzunluğuna getirir, böylece hücreler sayılabilir
  kalır (ay + saat ölçeği 744 çizgi olurdu: birim otomatik kabalaştırılır).

## [field_operation_gantt: satır = ekip (group_by)] — 2026-10-07

### Eklendi
- `gantt_soft` görünümüne **`group_by="team_id"`**: satırlar artık kayıt başına değil
  **ekip başına**. Bir ekibin servisleri o satırda **tarih ekseninde** çubuklar olarak
  dizilir (dikeyde ekip, yatayda tarihler = gantt'ın okunma biçimi). Aynı gün çakışan
  servisler satır içinde **şeritlere** (lane) dağıtılır; satır yüksekliği şerit sayısı
  kadar büyür. Satırlar grup adına göre sıralı; grup değeri boş kayıtlar "Not set"
  satırında kalır (kaybolmaz).
- `soft_gantt`'a bu iş için: `group_by` arch niteliği (sunucu whitelist'i + tip
  doğrulaması: tarih/float alanlar "her değer bir satır olur" diye reddedilir), istemci
  ayrıştırıcısında aynı doğrulama, saf `packLanes` şerit paketleyicisi, satır başına
  değişken yükseklik (sanallaştırma yükseklik dizisi ile besleniyor), gruplu satırda
  çubuk metni = kaydın adı (satır zaten ekibi söylüyor).

### Not
- Test: **61 hoot + 28 python**, hepsi geçti (yeni: 4 şerit paketleme, 3 `group_by`
  ayrıştırma, 4 gruplu çizim).

## [field_operation_gantt: tarih penceresi] — 2026-10-07

### Değişti
- `gantt_soft` görünümü artık **takvim penceresi** ile okur (`default_range="month"`):
  13.258 kayıtlık tabloda görünüm yalnız içinde bulunulan ay ile kesişen ~200-400 kaydı
  çeker; `◀ 📅 Ekim 2026 ▶` düğmeleri pencereyi kaydırır, ortadaki düğme bugüne döner.
  `default_order` `desc`'ten `asc`'e alındı (pencere içinde kronolojik okuma);
  `limit="1000"` yalnız güvenlik ağı olarak kaldı.
- Çubuğa tıklamak **detay kartını** açar (tarihler + arch'taki `<field>`'lar + "Aç").
- Sol sütunda `label="partner_id"` → **müşteri** adı.

### Not
- `soft_gantt` (view tipi) bu iş için genişletildi: `default_range` niteliği, `◀ Bugün ▶`
  gezinmesi, many2one etiketlerinin metne çevrilmesi (`[object Object]` hatası),
  grid çizgilerinin tam yüksekliğe yayılması. Test: **50 hoot + 28 python**, hepsi geçti.

## [field_operation_gantt: soft_gantt'e taşındı] — 2026-10-07

### Değişti
- `field_operation_gantt` baştan yazıldı: kendi `fo_gantt` view tipi ve gömülü
  dhtmlxGantt 6.2.3 (GPL-2, 443 KB) kaldırıldı; görünüm artık `soft_gantt`
  (AGPL-3) view tipi üzerindeki tek `<gantt_soft>` kaydıyla çiziliyor.
  Lisans: GPL-2 → AGPL-3 (modül artık müşteriye kapalı dağıtımda lisans yükü doğurmuyor).
- `field.operation` üzerine iki `store=False` hesaplanmış alan eklendi:
  `gantt_progress` (Float, yüzde) ve `gantt_color` (Integer, renk indeksi) —
  status eşlemesi: draft 0/gri, planned 25/teal, progress 50/amber, done 100/yeşil,
  cancel 0/kırmızı. Kolon eklenmez, göç yok.
- `start_date`/`end_date` Datetime olduğu için çizim UTC'de yapılıyor: eski sürümdeki
  yerel saat kayması (UTC+3'te 3 saat, gece yarısına yakın kayıtlarda bir gün) düzeldi.
- Aksiyona `ir.actions.act_window.view` kaydı **eklenmiyor** (pivot ile sequence=5
  çakışıyordu); mod yalnız `view_mode` dizesine eklenir, açılış görünümü `list` kalır.
- `hooks.py` uninstall hook'u korundu ve daraltıldı: yalnız
  `field_operation.action_field_operation` üzerinden `gantt_soft` modunu düşürür.

### Kaldırıldı
- `static/lib/dhtmlxgantt/**` (443 KB), `static/src/fo_gantt_view/**` (5 JS + 2 SCSS),
  `static/src/fo_gantt_view.xml`, modülün kendi `models/ir_ui_view.py`,
  `models/ir_act_window.py`, `static/tests/**` (view tipi davranışı artık `soft_gantt`'ın
  testlerinde) ve yerel-saat çevirisi yapan `parseGanttDate`.

### Test
- Yeni: `tests/test_gantt_view.py` — görünümün çözülmesi, arch alan adları, aksiyonun
  `gantt_soft` modu, açılış görünümünün `list` kalması, 5 durum için ilerleme ve renk,
  uninstall hook'unun modu düşürmesi.
- Silinen `tests/test_ir_ui_view.py` `assertRaises(ValueError)` bekliyordu; core v19
  `_raise_view_error` **ValidationError** atıyor, yani 5 testin 2'si düşerdi (modül hiç
  kurulmadığı için fark edilmemişti). Arch doğrulaması artık `soft_gantt`'ta test ediliyor.

## [Kişi istatistik rozeti] — 2026-10-04

### Değişti
- `field_operation`: kişi listesindeki "Stats" hücresine servis sayacı rozeti core hook ile eklendi —
  `res.partner._compute_application_statistics_hook()` override'ı (upstream deseni: `sale`, `crm`,
  `purchase`, `calendar`, `point_of_sale`; hook, compute metodunu ezmenin cache sorununu önlemek için
  vardır). Rozet yalnız `field_operation_count > 0` olan kişilerde eklenir; sayaca alt kişi kayıtları
  da dahildir.
- Rozet içeriği: `iconClass='fa-tasks'`, `value=<sayaç>`, `label='Services'`, `tagClass='o_tag_color_0'`.

### Kaldırıldı
- `field_operation/views/res_partner_view.xml`: `view_partner_list_field_operation` kaydı silindi. Bu
  kayıt `base.view_partner_tree`'yi miras alıp aynı bilgiyi core Contacts listesine ikinci bir kolon
  ("Services" başlığı + aynı etiketli satır butonu) olarak ekliyordu. Rozet yaklaşımı bunu gereksiz
  kılar; core kişi listesini modül dışına taşırmak da gerekmez. Form görünümündeki `oe_stat_button`
  (`field_operation_count`) ve arama filtresi (`field_operation_count > 0`) aynen korunur.

### Test
- `test_11_partner_statistics_expose_service_counter` eklendi: servisi olmayan kişide hücre boş kalır,
  servis eklendiğinde tek kayıt düşer ve değer sayaçla (alt kişi dahil) aynıdır.

## [Portal düzeltmeleri] — 2026-09-27

### Düzeltildi
- **Portal ön-yüz hatası (P1):** `field_operation`, `field_operation_forms` ve `field_operation_contract`
  portal şablonları sale modülünün yerleşim sınıfını (`o_portal_sale_sidebar`) ödünç alıyordu. Bu sınıf
  `sale_management`'ın `sale_update_line_button` interaction'ını da tetikliyor; interaction beklediği
  `table#sales_order_table`'ı bulamayınca `null.dataset` okunuyor ve ziyaretçiye
  `UncaughtPromiseError > TypeError: Cannot read properties of null (reading 'dataset')` düşüyordu.
  Sınıf modül sahipli adla değiştirildi → `o_portal_operation_sidebar`
  (upstream deseni: `account` → `o_portal_invoice_sidebar`, `purchase` → `o_portal_purchase_sidebar`)
  (commit `34bb91b`).
- **Deprecated API:** `field_operation_forms/controllers/operation_forms_portal.py` içindeki 2 çağrı
  `check_access_rights(..., raise_exception=False)` → `has_access()` (18.0'dan beri deprecated).
  Davranış birebir: core shim `raise_exception=False` durumunda zaten `has_access()` çağırıyor
  (aynı commit `34bb91b`).

### Doğrulama
- Kopya DB (canlı verinin kopyası) üzerinde: 3 portal sayfası HTTP 200, sayfa kaynağında eski sınıf 0,
  yeni sınıf 1; `/my` ve `/my/operation_forms` istekleri sonrası logda `DeprecationWarning` 0.
- Core kontrol grubu: `/my/orders/<id>` sayfasında tablo sidebar'ın İÇİNDE → core'da hata yok.

## [Standartlaştırma] — 2026-09-26

### Eklendi
- `README.md` — 21 modülün tamamına kod kanıtlı, Türkçe modül dokümantasyonu (commit `038b35f`)
- `static/description/index.html` — 21 modülde Odoo Apps açıklama sayfası (commit `aa9377a`)
- `.gitignore` — derlenmiş çeviriler (`*.mo`), Python/JS araç önbellekleri, modül içine düşen araç dosyaları
  ve kökte izin verilen araç dosyaları için `**/x !/x` kalıbı (commit `2db12d6`)

### Değişti
- Manifest standardizasyonu (21 dosya, commit `40bb185`):
  - `contributors` ve `images` alanları eklendi (21 modülde eksikti)
  - 16 modülde sürüm 4 haneden 5 haneye çıkarıldı (`19.0.1.0` → `19.0.1.0.0`, Odoo standardı)
  - `field_operation_gantt`: author `Saha Odoo` → `Softteknik Bilişim`, boş `website` dolduruldu
- `field_operation_contract/README.md`: sürüm referansı `19.0.1.0.8` → `19.0.1.0.9` (manifest ile hizalandı)
- Modül README şablonu sadeleştirildi: "Bilinen Sınırlamalar / Teknik Borç" bölümü 20 modülden
  kaldırıldı ve kalan bölümler (8. Test Kapsamı, 9. Geliştirici Notları) yeniden numaralandı.
  README'ler artık modülün ne yaptığını anlatır; bulgu takibi repo dışında yapılır.
  (`field_operation_contract/README.md` elle yazılmış mevcut doküman olduğu için dokunulmadı.)

### Kaldırıldı
- Git izlemesinden çıkarıldı: 7 modülde `i18n/tr.mo` (Odoo `.po`'dan üretir, kaynak dosya değildir).
  Dosyalar diskte kaldı; geçmiş yeniden yazılmadı.

## Bilinen açık maddeler (kod değişikliği onayı bekliyor)

- **P0 (gizlilik):** `field_operation_agreement/data/{sample,demo}_agreement_template.xml` içinde
  gerçek müşteri verisi var (şirket ünvanı, telefon, VKN, e-posta, sokak adresleri).
- `field_operation_map/data/ir_actions_server.xml` — 0 byte, manifest `data` listesinde kayıtlı değil.
- Bulgu / teknik borç takibi README'lerin dışında tutulur (repo içinde bulgu listesi yoktur):
  `field_operation_machine` cron'unun `for rec in self` ile çalışması, `field_operation_pest` PDF ve
  e-posta şablonlarının manifest dışında olması, `field_operation_map` JS katmanının yüklenmemesi gibi
  maddeler dahil (satır kanıtlı liste için iç rapora bakınız).
- `field_operation_gantt` lisansı: **AGPL-3** (07 raporundaki GPL-2 + gömülü dhtmlxGantt 2026-10-07'de
  kaldırıldı; sürüm tablosundaki `GPL-2` girdisi 2026-10-11'de düzeltildi).
- **Operasyonel not (`view_mode` düzeltmesi):** `uzman_v19_test`'te kurulu `field_operation_gantt` kopyası
  düzeltmeden **önceki** kodu çalıştırıyor (tam-dize yazımı). Yeni davranış için o DB'de
  `-u field_operation_gantt` (ve harita kuruluysa `-u field_operation_map`) gerekir — o DB'ye sorulmadan
  dokunulmadı.
- `field_operation_stock` (inceleme raporu: `field_operation_stock_inceleme_2026-10-11.md`): P0'lar
  düzeltildi; **karar bekleyen** açık maddeler — çok şirket `ir.rule` yok ve manager ACL
  `base.group_system` · `done` sarf satırı silinebiliyor · satır formundaki `Confirm` stok hareketi
  üretmediği hâlde maliyete giriyor (tek akışa indirilsin mi?) · `unit_price`/`subtotal` Float
  (Monetary olmalı, şema değişikliği → sürüm artışı) · `i18n/` boş, etiketler TR/EN karışık ·
  onay akışındaki kör `except Exception` (ruff BLE001/B904) gerçek hatayı yutuyor.

## Güncel modül sürümleri

| Modül | Sürüm | Lisans | Manifest adı |
|---|---|---|---|
| `field_operation` | `19.0.2.4.0` | AGPL-3 | Field Operation |
| `field_operation_agreement` | `19.0.1.0.0` | AGPL-3 | Field Operation Agreement |
| `field_operation_attendance` | `19.0.1.0.0` | AGPL-3 | Field Operation Attendance Report |
| `field_operation_contract` | `19.0.1.0.10` | AGPL-3 | Field Operation Contract Management |
| `field_operation_contract_repeat` | `19.0.1.0.0` | AGPL-3 | Field Operation Contract Repeat Wizard |
| `field_operation_contractor` | `19.0.1.0.0` | AGPL-3 | Field Operation Contractor |
| `field_operation_disinfect` | `19.0.1.0.0` | AGPL-3 | Field Operation Disinfect Form |
| `field_operation_forms` | `19.0.1.0.1` | AGPL-3 | Field Operation Forms |
| ~~`field_operation_forms_ext`~~ | — | — | **Kaldırıldı (2026-10-12):** servis formu kısayolları `field_operation_geolocation` (harita/konum) ve `field_operation_whatsapp` (WhatsApp) modüllerine taşındı |
| `field_operation_gantt` | `19.0.1.0.0` | AGPL-3 | Field Operation Gantt |
| `field_operation_geolocation` | `19.0.1.2.0` | AGPL-3 | Field Operation Geolocation |
| `field_operation_inspection` | `19.0.1.0.0` | AGPL-3 | Field Operation Inspection Template |
| `field_operation_invoice` | `19.0.1.0.0` | AGPL-3 | Field Operation Invoice |
| `field_operation_machine` | `19.0.1.0.0` | AGPL-3 | Field Operation Machine |
| `field_operation_map` | `19.0.1.0.0` | AGPL-3 | Field Operation Map |
| `field_operation_pest` | `19.0.1.0.0` | AGPL-3 | Field Operation Pest Form |
| `field_operation_resequence` | `19.0.1.0.0` | AGPL-3 | Field Operation Resequence |
| `field_operation_sale` | `19.0.1.0.0` | AGPL-3 | Field Operation Sale |
| `field_operation_stock` | `19.0.1.0.0` | AGPL-3 | Field Operation Stock |
| `field_operation_whatsapp` | `19.0.1.1.0` | AGPL-3 | Field Operation WhatsApp |
| `field_operation_worker` | `19.0.1.0.0` | AGPL-3 | Field Operation Worker |

## Commit geçmişi

```
7dff823 feat(field_operation_geolocation,field_operation_whatsapp): own the service form shortcuts
5403ba5 feat(field_operation_whatsapp): port the module in with its P1 fixes
8512656 fix(forms_portal): drop avatar block bound to undefined 'operation' variable
86eb052 feat(field_operation): show service counter as contact stat badge (19.0.2.3.0)
34bb91b fix(portal): module-owned sidebar class + has_access() instead of deprecated check_access_rights
5b8fd59 fix(field_operation): portal, pdf, wizard and kanban fixes + tests (19.0.2.2.0)
0eaae69 docs: sync module READMEs and app description with current tree
88a328c chore(cleanup): remove dead assets, templates and ACL files from 4 modules
97c062f feat(disinfect): define field.disinfect sequence and use it for empty names
de7806a fix(gantt): export uninstall_hook and clear view_mode via ORM
3667f75 docs(readme): drop technical-debt section from module READMEs
b5e0297 docs: add root CHANGELOG.md with module version table
aa9377a docs(description): add Odoo Apps description page for all 21 modules
038b35f docs: add per-module README for all 21 modules (code-derived, Turkish)
40bb185 chore(manifest): unify metadata (contributors, images, 5-part versions)
2db12d6 chore(gitignore): ignore generated .mo files and tooling caches
2640af8 chore: baseline import of remaining 20 field_operation modules
ece53e6 Initial import: field_operation module (Odoo 19)
```

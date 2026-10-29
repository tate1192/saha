# Field Operation Gantt

> `field.operation` kayıtları için **Gantt (zaman çizelgesi) görünümü** — `soft_gantt`
> view tipi üzerinde. Sürükle-bırak ile yeniden planlama, duruma göre renk/ilerleme,
> arama-filtre, kayıt açma.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.2`
> Modül: `apps/saha/field_operation_gantt` · yeni iş modeli yok (view + 2 hesaplanmış alan)

## 1. Neden yeniden yazıldı

Önceki sürüm kendi `fo_gantt` view tipini ve **gömülü dhtmlxGantt 6.2.3** kütüphanesini
(397 KB min.js + 46 KB CSS) taşıyordu; modül bu nedenle **GPL-2** beyan etmek zorundaydı ve
DHTMLX lisansı yalnız GPL projelerde ücretsizdir. Kapalı/kurumsal bir müşteri dağıtımında
lisans yükü doğuyordu.

Yeni sürüm bu kütüphaneyi ve kendi view tipini bırakır; tüm çizim `soft_gantt` (AGPL-3,
vendor kütüphane yok) tarafından yapılır. Bu modül yalnızca **görünüm tanımı + iki
hesaplanmış alan** içerir.

| Eski | Yeni |
|---|---|
| `fo_gantt` view tipi (`models/ir_ui_view.py`, `ir_act_window.py`) | `soft_gantt`'ın `gantt_soft` tipi (bağımlılık) |
| dhtmlxGantt 6.2.3 (GPL-2, 443 KB) | yok |
| 5 JS + 2 SCSS + şablon | yok |
| `hooks.py` uninstall (view_mode temizliği) | korundu (artık `gantt_soft` için) |
| GPL-2 | AGPL-3 |

## 2. Görünüm ve alan eşlemesi

`views/field_operation_gantt_views.xml`:

| Nitelik | Alan | Not |
|---|---|---|
| `date_start` / `date_stop` | `start_date` / `end_date` | **Datetime**, UTC saklanır ve kullanıcının saat diliminde çizilir (eski sürümdeki yerel saat hatası düzeldi) |
| `progress` | `gantt_progress` | Hesaplanmış `Float`, **yüzde** (0–100) |
| `color` | `gantt_color` | Hesaplanmış `Integer` → `o_gantt_soft_color_<index>` |
| `mode` / `scales` | — | `week` açılış, `day,week,month` seçenekleri |
| `default_order` | — | `start_date asc, id asc` (pencere içinde kronolojik) |
| `default_range` | — | `week` — açılış penceresi: **planlanan hafta** (planlama ileriye yazılır; ay penceresi bugüne kadar 4 hafta bitmiş iş gösteriyordu) |
| `group_by` | — | `team_id` — **satır = ekip**, o ekibin servisleri satır boyunca tarih ekseninde çubuklar; satır etiketi grubun görünen adıdır |
| `limit` | — | 1000 kayıt; artık yalnız **güvenlik ağı** (hangisinin görüneceğini pencere belirler) |
| `<field>` | `subject`, `team_id`, `partner_id`, `status` | çubuk ipucunda |

`status` → ilerleme ve renk (`models/field_operation.py`):

| status | `gantt_progress` | `gantt_color` | Renk |
|---|---|---|---|
| `draft` | 0 | 2 | gri |
| `planned` | 25 | 9 | teal |
| `progress` | 50 | 10 | amber |
| `done` | 100 | 8 | yeşil |
| `cancel` | 0 | 11 | kırmızı |

İki alan da **`store=False`**: veritabanına kolon eklenmez, göç gerekmez.

## 3. Davranış

- **Görünüm sunumu:** `gantt_soft` aksiyonun `view_mode` dizesine **eklenir** — dize asla baştan
  yazılmaz. Veri kaydı `view_mode`'u yalnızca **değiştirebilir** (Char), ve o aksiyonu **üç modül**
  yazıyor (`field_operation`, `field_operation_map`, bu modül): son güncellenen kazanıyordu ve diğer
  modlar sessizce düşüyordu. Ölçüm: bu modülden sonra `field_operation_map` kurulunca aksiyon
  `kanban,list,form,activity,leaflet_map` kalıyordu — ne Gantt, ne `calendar`/`graph`/`pivot`/`activity`.
  Şimdi data dosyası `models/ir_actions_act_window.py`'deki idempotent fonksiyonu `<function>` ile
  çağırıyor: modu okur, `gantt_soft`'u `calendar`'dan sonra ekler, geri yazar. Yeniden koşmak bir şey
  değiştirmez; `<function>` hem kurulumda hem `-u`'da çalışır. Alt `ir.actions.act_window.view` kaydı
  **bilinçli olarak eklenmez** (alt kayıt sıralamaya girip açılış görünümünü değiştirebilir; test
  açılış görünümünü `list` olarak sabitler).
- **Pencere (13.258 kaydın cevabı):** görünüm tablonun tamamını **okumaz**. İçinde
  bulunulan **takvim haftası** ile kesişen kayıtları okur (`default_range="week"`;
  pratikte ~50–120 satır), pencereyi kontrol panelindeki `◀ 📅 26 Eki - 1 Kas ▶` düğmeleri
  kaydırır, ortadaki düğme bugüne döner. **Neden hafta, neden ay değil:** bu bir
  *planlama* ekranı ve planlama ileriye yazılır. Ay penceresi, ayın 29'unda 31 günün
  28'ini geçmiş işlerle dolduruyordu — yani planlamacının ilk gördüğü şey tarih oluyordu.
  Hafta penceresi planlanan haftada açılır: geride bir iki gün bağlam, önünde haftanın
  kalanı. Geçmiş sürümdeki `limit="1000"` + `default_order desc` çözümü en yeni 1000
  kaydı çekiyordu: 13.258 kayıtlık tabloda bu bir yama, doğru cevap değildi. `limit`
  şimdi yalnızca yoğun bir pencere için güvenlik ağıdır.
- **Satır = ekip:** `group_by="team_id"` ile sol sütun **ekip** adını taşır ve o ekibin
  servisleri satır boyunca **tarih ekseninde** çubuk olarak dizilir (dikeyde ekip, yatayda
  tarihler). Aynı gün çakışan iki servis üst üste binmesin diye satır **şeritlere** (lane)
  bölünür ve o kadar büyür; ekibi boş kayıtlar "Not set" satırında görünür. Çubuğa tıklama
  yine kaydın detay kartını açar (satır adına tıklamak gruplu satırda bir şey açmaz: satır
  birden çok kaydı temsil eder).
- **Sol sütun ve detay:** sol sütunda **ekip** adı görünür (`group_by="team_id"`;
  satır adı gruplu görünümde grup adıdır), boş ekipli kayıtlar "Not set" satırında toplanır.
  Çubuğa **tıklamak** detay kartını açar (Başlangıç/Bitiş, Konu, Ekip, Müşteri, Durum + "Aç" → form);
  **sürüklemek** kaydı taşır.
- **Yetki:** yazma yetkisi olmayan kullanıcıda sunucu arch'a `edit="False"` yazar ve
  `soft_gantt` çubukları sürüklenemez duruma getirir; modül bunun için ek kod içermez.
- **Tarihsiz kayıtlar:** pencere ile kesişmeyen kayıtlar (tarihi olmayanlar dahil) okunmaz.
  Alt bilgi satırındaki "N record(s) without a date" sayacı pencere açıkken bu yüzden 0'dır:
  kayıt pencerenin dışındadır, tarihi eksik demek değildir.
- **Kurulum kaldırma:** `hooks.py`, `field_operation.action_field_operation`'ın
  `view_mode`'undan `gantt_soft` girişini ORM ile temizler (yalnız o aksiyon; başka bir
  modülün eklediği moda dokunmaz).

## 4. Testler

`tests/test_gantt_view.py` (post_install, **12 test**): görünümün model tarafından çözülmesi,
arch'ın beklenen alanları adlandırması, **çevrilebilir `label` niteliğinde alan adı bulunmaması**,
aksiyonun `gantt_soft` modunu sunması, **modun diğer modları
düşürmeden eklendiği** (kardeş modül dizesini ezse bile geri geldiği), fonksiyonun **idempotent**
olması, **açılış görünümünün `list` kalması**, 5 durum için ilerleme ve renk eşlemesi,
**eşlemenin her durumu kapsadığı** (yeni bir durum eklendiğinde kırmızı olan nöbetçi test),
uninstall hook'unun modu düşürmesi.

View tipinin kendisi `soft_gantt` modülünde kapsanır: `tests/test_gantt_view.py`'de **31 python testi**
ve `static/tests/*.js` (8 dosya) içinde **169 hoot testi** — pencere matematiği
(`windowRange`/`shiftWindow`, takvim ayı/çeyrek/yıl sınırları, pencerelerin boşluksuz bitişmesi), arch
ayrıştırma, sanallaştırılmış çizim, detay kartı, alan metni; ayrıca arch doğrulama, ACL ve tarih
matematiği uçları.

    odoo-bin -c v19.conf -d <scratch|çalışma-db> -u field_operation_gantt \
      --test-enable --test-tags field_operation_gantt --stop-after-init

## 5. Geliştirici notları

- Paket bağımlılığı: `field_operation`, `soft_gantt`. Çeviri: `i18n/field_operation_gantt.pot`
  + `i18n/tr.po` (`odoo-bin i18n export ... field_operation_gantt -l pot|tr_TR`; 9 msgid, iki
  dosyanın msgid seti aynı). Yeni iş modeli yok, ACL dosyası yok
  (erişim tamamen `field.operation` ACL'inden gelir).
- `soft_gantt`ın `label` arch niteliği **alan adı** taşır ama Odoo bu niteliği çevrilebilir metin
  olarak POT'a alır. Bir view'da `label="team_id"` yazıp bu terimi çevirmek arch'ı
  `label="Ekip"` yapar ve view'ı kırar. Bu yüzden bu modül `label` kullanmaz; satır etiketi
  `group_by`dan gelir. Başka bir gantt view'ı `label` kullanacaksa `.po` dosyasına o terimi
  **çeviri olarak eklememelidir**.
- `store=False` hesaplanmış alanlar okuma sırasında hesaplanır; `status` dışında bağımlılığı
  yoktur, bu yüzden liste/gantt okumalarını yavaşlatmaz.
- `view_mode` bir `Char` olduğu için mod **eklenerek** yazılır (`models/ir_actions_act_window.py` +
  data dosyasındaki `<function>`); kardeş modüller (`field_operation_map`) kendi modlarını eklerken
  bu modu düşürmez. Yine de kural şu: `field_operation` aksiyonuna yeni bir mod eklenirse, o modu
  kendi kuran modül ekler; bu modülün güncellenmesi gerekmez (testler modun kalıcılığını ve
  idempotentliğini korur, "yeni modları yakalama" iddiası yoktur).

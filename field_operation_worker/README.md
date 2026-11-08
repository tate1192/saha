# Field Operation Worker

> Saha personeli için sınırlı görünürlüklü arayüz — iş emirlerini (field.operation)
> görüntüleme ve servis/done adımlarını yürütme.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `field_operation_worker/` · 11 dosya · model içermez (view-only modül)

Bu doküman modül kodundan üretilmiştir (manifest + view XML + testler + i18n).
Kodda kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## Kurulum notu (P0 — kurulum engelleyen hata ve düzeltmesi)

Modül temiz bir veritabanında **kurulamıyordu**: `-i field_operation_worker`
komutu `EXIT=255` ve `odoo.tools.convert.ParseError` ile bitiyordu. Görünüm
doğrulayıcısı şu mesajı veriyordu:

```
ParseError: while parsing .../views/field_operation_worker_view.xml:62
Error while validating view near:
    <button name="action_send_mail" type="object" string="Email" .../>
action_send_mail is not a valid action on field.operation
```

**Gerçek kök neden:** formun `Email` butonu `action_send_mail` metodunu
çağırıyordu; `field.operation` modelinde böyle bir metot **yok**. Model gerçek
metodu `action_send_report_mail`'dir (base modülün kendi formu da bunu kullanır).
Odoo 19 görünüm doğrulaması `type="object"` butonların modelde karşılığı olmasını
zorunlu kılar; olmayınca kurulum `ParseError` ile durur.

**Düzeltme:** buton metodu `action_send_report_mail` olarak düzeltildi. Buton
yine `Email` etiketiyle, `base.group_user` grubu ve `btn-danger` sınıfıyla aktif
kalır.

**Ölü kod (yorumlanmış XML düğümleri):** formun `<header>`'ında ayrıca
`action_planned` / `action_cancel` / `action_draft` butonlarının
yorumlanmış (`<!-- ... -->`) kopyaları vardı. Bunlar ölü koddur ve kaldırıldı;
butonlar geri getirilmedi. Aktif `action_progress` / `action_done` /
`action_send_report_mail` butonları aynen korundu.

> Ölçüm notu: yorumlanmış XML blokları **tek başına** kurulumu engellemez —
> base `field_operation` modülü de yorum içeren görünümler taşır ve sorunsuz
> kurulur. Kurulumu durduran tek gerçek etken geçersiz `action_send_mail`
> referansıydı. Ölü yorum düğümleri yine de (karar gereği) kaldırılmıştır ve
> `test_01` bunu kalıcı olarak denetler.

**Doğrulama:** temiz DB'de `-i field_operation_worker --test-tags
/field_operation_worker` → `EXIT=0`, `0 failed, 0 error(s) of 6 tests`, modül
durumu `installed`.

## 1. Genel Bakış

`field.operation` modeli üzerine saha çalışanına özel bir görünüm seti kurar:
kendi işlerine odaklı liste, kanban ve form ekranları.

- Çalışan odaklı liste / kanban / form görünümleri
  (`view_field_operation_worker_list|kanban|form`) — **calendar görünümü yoktur**
- Varsayılan filtre **My Jobs** — açılışta yalnız kullanıcının atandığı işler
- Deneyimli hızlı liste: `multi_edit=1`, `duplicate=false`, `sample=1`
- Formda sadece **Service** ve **Done** durum butonları aktif; ayrıca **Email**
- Durum çubuğu `planned → progress → done` ile sınırlandırılmış

Kapsam dışı: bu modül yeni model/alan tanımlamaz, ACL üretmez, cron kurmaz.

Saha çalışanından gizlenen alanlar model düzeyinde tanımlıdır (view değil):
`field.operation.service_price`, stok maliyet toplamları, sözleşme tutarı ve
makine maliyetleri `groups=` ile ofis grubuna kısıtlanmıştır; personel bu alanları
RPC'den bile okuyamaz (`AccessError`). Para dışındaki iş bilgileri (adres, telefon,
açıklama, form, imza) görünür kalır.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli, `service_group_worker` grubu, `menu_field_operation_root` menüsü ve `action_progress` / `action_done` / `action_send_report_mail` metodları bu modülden gelir |

## 3. Ana Modeller

Modül kendi modelini tanımlamaz (models/ dizini yok). Tüm görünümler `field.operation`
(model: `field_operation`) üzerinedir.

| Kullanılan model | Kaynak modül |
|---|---|
| `field.operation` | `field_operation` |
| `ir.ui.view`, `ir.actions.act_window`, `ir.actions.act_window.view` | Odoo base |

## 4. Roller ve Güvenlik

- **ACL:** modülde `security/` dizini yok — erişim `field_operation` modülünün ACL'inden gelir.
- **Menü görünürlüğü:** `menu_field_operation_worker` → `groups="field_operation.service_group_worker"`
  (yalnız saha çalışanı grubu görür)
- **Form butonu:** `action_send_report_mail` → `groups="base.group_user"`
  (Service ve Done butonlarında grup kısıtı yok; görünürlük `invisible` koşuluyla yönetiliyor)
- **Kayıt kuralı:** modülde tanımlı değil; **ama** görünürlük güvenlik sınırı base
  modülden gelir: `field_operation.rule_service_worker` (okuma) domain'i
  `[('person_ids.user_id','=',user.id),('status','in',['planned','progress','done','cancel'])]`
  — personel atandığı işleri her statüde okur (mobil/desktop geçmiş), draft işleri ve
  başkasının işini görmez. `field_operation.rule_service_worker_write` (yazma) ise
  `status in ('planned','progress')` ile sınırlıdır: kapanmış iş salt-okunurdur, yalnız
  ofis düzenleyebilir. "My Jobs" bir varsayılan **filtre**dir; asıl kayıt kısıtını bu
  iki kural sağlar.

## 5. Ana Akış

Menü yolu: **Field Operation → Field** (sequence 7)

| Adım | Kayıt | Detay |
|---|---|---|
| Menü | `menu_field_operation_worker` | ad: "Field", parent: `field_operation.menu_field_operation_root` |
| Aksiyon | `action_field_operation_worker` | ad: "Field Worker", `res_model=field.operation` |
| Varsayılan filtre | `context` | `{'search_default_my_jobs': 1}` |
| Görünüm sırası | `ir.actions.act_window.view` | list (seq 0) → kanban (seq 1) → form (seq 2) |
| Boş ekran metni | `help` | "No service order found. Let's create one!" |

Görünümler (`ir.ui.view`) — adlar artık **worker'a özgüdür** ve base modülün
`field.operation.select|list|form|kanban` adlarıyla çakışmaz:

| View | Kayıt id | Ad |
|---|---|---|
| Arama | `view_field_operation_worker_filter` | `field.operation.select.worker` |
| Liste | `view_field_operation_worker_list` | `field.operation.list.worker` |
| Form | `view_field_operation_worker_form` | `field.operation.form.worker` |
| Kanban | `view_field_operation_worker_kanban` | `field.operation.kanban.worker` |

Form butonları:

| Buton | Metod | Görünürlük |
|---|---|---|
| Service | `action_progress` | `status in ('draft','progress','done','cancel')` dışında |
| Done | `action_done` | `status in ('draft','planned','done','cancel')` dışında |
| Email | `action_send_report_mail` | `status in ('draft','done','cancel')` dışında, grup `base.group_user`, `btn-danger` |

Durum çubuğu: `statusbar_visible="planned,progress,done"`, `readonly="1"`

## 6. Liste Görünümü Alanları

| Varsayılan görünür (`optional="show"`) | Gizli (`optional="hide"`) |
|---|---|
| `priority` (widget priority), `name`, `subject`, `partner_id` (readonly), `contact_mobile`, `team_id`, `start_date`, `total_work` (float_time), `activity_exception_decoration`, `status` (badge) | `user_id`, `contact_id`, `address_id`, `region_id`, `team_leader_id`, `person_ids`, `id`, `service_type_id`, `end_date`, `company_id` (readonly) |

Satır renklendirme: `draft`→primary, `planned`→info, `progress`→danger, `done`→success

## 7. Arama Filtreleri

| Filtre | Domain |
|---|---|
| Alan ("No") | `name ilike self` |
| My Tasks | `user_id = uid` |
| **My Jobs** (varsayılan) | `person_ids.user_id = uid` |
| Progress | `status = 'progress'` |
| Create Date | tarih filtresi (`create_date`) |

Not: Formdaki durum çubuğunun aksine arama tarafında `draft`, `planned`, `done` için hazır filtre yok.

## 8. Test Kapsamı

`tests/test_field_operation_worker.py` — 6 test, `TransactionCase`,
`@tagged('post_install','-at_install')`:

| Test | Doğrulanan |
|---|---|
| `test_01_worker_views_ship_no_commented_nodes` | **P0 regresyonu:** dört worker görünümünün `arch`/`arch_db` içinde `<!--` yok; tüm xml:id'ler çözülür; formun `type="object"` butonları `field.operation` üzerinde var olan metoda işaret eder |
| `test_02_view_names_are_worker_specific` | Dört görünümün `name` alanı `field.operation.*.worker`; base adlarıyla çakışmıyor (`search` sonucunda bu modülün kaydı yok) |
| `test_03_action_is_wired_to_worker_views` | `action_field_operation_worker`: `res_model`, `view_mode` (`list,kanban,form`), `search_view_id`, `context`; üç `ir.actions.act_window.view` doğru `view_id` ile |
| `test_04_menu_is_restricted_to_workers` | `menu_field_operation_worker`: `parent_id` = base kök menü, `group_ids` içinde `field_operation.service_group_worker` |
| `test_05_worker_only_sees_assigned_jobs` | Worker grup kullanıcısı: atanmış (`status='progress'`) iş görünür; atanmamış ve atanmış-ama-`done` iş görünmez (base `rule_service_worker`) |
| `test_06_my_jobs_filter_targets_assigned_user` | `view_field_operation_worker_filter` içinde `my_jobs` filtresi ve domain'i `[('person_ids.user_id','=',uid)]` |

Kurulum doğrulaması (temiz veritabanı, `work_verify`):

```
cd /home/tate/odoo/v19 && venv/bin/python odoo/odoo-bin -c v19.conf \
  -d work_verify --http-port 9092 \
  -i field_operation_worker --stop-after-init --test-tags /field_operation_worker
```

Sonuç: `EXIT=0`, `0 failed, 0 error(s) of 6 tests`, `field_operation_worker` → `installed`.

## 9. Geliştirici Notları

- Migration yok (`migrations/` bulunmuyor).
- Çeviri: `i18n/field_operation_worker.pot`, `i18n/tr.po`.
- Görsel: `static/description/` altında `icon.png`, `icon.svg`, `index.html`.
- Dosya sayısı: 11 (yukarıdaki kaynak/veri dosyaları; `__pycache__`/`.ruff_cache` hariç).
- `attrs` kullanılmaz; buton alanları `invisible`/`readonly`/`required` ile koşullanır (v17+).

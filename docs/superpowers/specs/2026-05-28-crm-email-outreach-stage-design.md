# Email Outreach (Рассылки) — дизайн модуля CRM

**Дата:** 2026-05-28
**Статус:** дизайн на согласовании
**Целевой репозиторий:** `CRM_system` (NestJS + Prisma + PostgreSQL + Redis + Next.js)
**Сервер:** VPS `213.109.202.45`, деплой `/opt/crm` (docker-compose.prod)

> ⚠️ Секреты (SMTP/IMAP пароли, токены, API-ключи) — только в `.env.production` на сервере (chmod 600), как уже принято в проекте. В репозиторий и в этот файл не пишутся.

---

## 1. Цель

Встроить исходящие email-рассылки прямо в CRM: вести холодную базу объектов, отправлять
персональные коммерческие предложения с прогревом и троттлингом, ловить ответы и
**автоматически превращать их в лиды**, замыкая воронку на уже существующий модуль лидов.
Всё — на сервере, 24/7, без Cowork и без ручных шагов.

## 2. Контекст и интеграция

CRM уже содержит: `Users/Roles/Permissions`, `Clients + ClientContacts`, `Leads`
(`new→assigned→in_progress→converted→closed`, ответственный, `firstResponseAt`, конверт в клиента),
`ActivityLog`. Стек: NestJS-модули (Controller+Service+DTO+RBAC+audit), Prisma, PostgreSQL 16,
**Redis 7** (уже есть — используем под очередь), Next.js (App Router), Docker, nginx.
email и Telegram уже значатся в роадмапе как будущие модули — этот документ их и реализует.

Аутентификация домена для отправки уже настроена на пилоте: **SPF/DKIM/DMARC = pass**
(mail-tester 8.2/10), отправитель `alexey.gurinenko@simfer.com.ru` (SprintHost,
SMTP `smtp.simfer.com.ru`, IMAP `mail.simfer.com.ru`).

## 3. Ключевые решения

| Тема | Решение |
|------|---------|
| Холодная база | Отдельная таблица `OutreachContact` (не засоряет `Clients`) |
| Замыкание воронки | Ответ → авто-создание `Lead` (source `email_outreach`) → существующий модуль лидов |
| Генерация текста | Шаблоны с переменными (v1). Claude API — отдельная стадия E5 |
| Отправка | Nodemailer → `smtp.simfer.com.ru`, прогрев + троттлинг |
| Приём ответов | IMAP-поллер → `mail.simfer.com.ru` |
| Очередь/расписание | BullMQ на существующем Redis |
| Управление/уведомления | Web `/outreach` + Telegram (E4) |
| Хранение/правка базы | PostgreSQL — источник правды; Excel-подобный редактируемый грид (AG Grid/Handsontable) + импорт/экспорт xlsx/CSV. Google Sheets и Apps Script выводятся из эксплуатации |

## 4. Scope

**Входит:**
- Модели `OutreachContact`, `Campaign`, `EmailTemplate`, `EmailMessage` + миграции + seed прав.
- `OutreachModule` (API): CRUD кампаний/контактов/шаблонов, импорт базы (CSV), start/pause, статистика.
- Движок отправки: Nodemailer, троттлинг, прогрев, статусы, обработка bounce.
- Очередь BullMQ: ежедневный дрип, прогрев, фоллоу-апы.
- IMAP-поллер: матч ответов → `replied` + авто-создание `Lead`.
- Telegram: уведомления (новый ответ/запрос, дневная сводка, ошибки) + команды `/pause`, `/stats`.
- Web `/outreach`: кампании, статистика, **Excel-подобный редактируемый грид контактов** (AG Grid/Handsontable: инлайн-правка, копипаст, сорт/фильтр, массовые операции), импорт/экспорт **xlsx/CSV**.
- RBAC: `outreach.view/create/update/send/import`.
- Вывод из эксплуатации пилотных костылей: Google-таблица и Apps Script (источник правды переезжает в БД CRM; файл .xlsx — по кнопке «Экспорт»).

**Не входит (отложено):**
- Claude API «живой» текст (E5).
- Канал Авито (E5+).
- Гос/корпоративная кампания с акцентом 44-ФЗ/223-ФЗ (отдельная кампания позже).
- Полноценный модуль сделок (используем существующие лиды/клиентов).

## 5. Модель данных (Prisma)

**Enums:** `OutreachSource {parsing, avito, manual}`,
`OutreachContactStatus {new, queued, sent, replied, bounced, unsubscribed, skipped}`,
`CampaignStatus {draft, active, paused, done}`,
`EmailMessageStatus {queued, sent, failed, bounced}`.

**`OutreachContact`** — холодная база:
- `id` UUID; `name`, `type`, `city`, `email`, `phone`, `website`, `social`, `address`;
- `source` (OutreachSource); `status` (OutreachContactStatus, default `new`);
- `touchCount` Int default 0; `lastTouchAt` DateTime?; `leadId` UUID? (связь при ответе);
- `note`; `createdAt/updatedAt/deletedAt/createdBy`.
- Индексы: `email`, `status`, `city`, `source`, `deletedAt`.

**`Campaign`:**
- `id`; `name`; `status` default `draft`; `dailyCap` Int (старт 20);
- `warmupEnabled` Bool; `warmupStartCap` Int; `templateId` → EmailTemplate;
- `followupEnabled` Bool; `followupAfterDays` Int default 5;
- `createdBy`; `createdAt/updatedAt`.

**`EmailTemplate`:**
- `id`; `name`; `subjectVariants` Json (массив тем);
- `bodyTemplate` Text (с переменными `{name}{type}{city}` и блоком по типу);
- `links` Json; `signature` Text; `createdBy`; `createdAt/updatedAt`.

**`EmailMessage`** — лог отправок:
- `id`; `campaignId`; `contactId`; `toEmail`; `subject`; `bodySnapshot` Text;
- `status` (EmailMessageStatus, default `queued`); `providerMessageId`; `threadId`;
- `sentAt` DateTime?; `error`; `followupOfId` UUID? (self-relation для повторных касаний);
- `createdAt`.
- Индексы: `campaignId`, `contactId`, `status`, `threadId`, `providerMessageId`.

## 6. Бэкенд (NestJS, по стилю ClientsModule/LeadsModule)

**Эндпоинты:**
- `GET/POST /outreach/campaigns`, `GET/PATCH /outreach/campaigns/:id`,
  `POST /outreach/campaigns/:id/start`, `/pause`.
- `GET/POST /outreach/contacts`, `POST /outreach/contacts/import` (CSV нашего формата).
- `GET/POST /outreach/templates`, `GET/PATCH /outreach/templates/:id`.
- `GET /outreach/stats` (счётчики по статусам, за день/всего).

**Сервисы:**
- `CampaignService`, `ContactService`, `TemplateService` — Prisma + RBAC + audit.
- `SenderService` — Nodemailer → SMTP, рендер шаблона, троттлинг, запись `EmailMessage`.
- `ImapPollerService` — imapflow, разбор входящих, матч, обновление статусов, создание лида.
- `OutreachQueue` (BullMQ): процессоры `drip`, `send`, `followup`, `imapPoll`.

**Логика очереди:**
- `drip` (cron, будни, рабочее время): выбрать `OutreachContact.status=new` до `dailyCap`
  (с учётом прогрева), поставить в `send`. Прогрев: день1–3→10–15, 4–7→20–30, далее→cap.
- `send`: рендер письма по шаблону, отправка с паузой 30–60 c, статус `sent`, `lastTouchAt`,
  `touchCount++`, `EmailMessage.sent`.
- `followup` (cron): `sent` без ответа ≥ `followupAfterDays` → второе касание (другой текст).
- `imapPoll` (cron, каждые N минут): новые письма → см. раздел 7.
- Bounce: письма от mailer-daemon → `EmailMessage.bounced`, `OutreachContact.bounced`.

## 7. Воронка: ответ → Lead (замыкание на существующий модуль)

При входящем ответе `ImapPollerService`:
1. Извлекает From-email, тему, текст, `In-Reply-To`/`References` (threadId).
2. Матчит на `OutreachContact` по email (или `EmailMessage` по threadId/messageId).
3. Ставит `OutreachContact.status = replied`.
4. **Создаёт `Lead`**: `source='email_outreach'`, `email`, `name`/`city` из контакта,
   `message` = выдержка ответа, `status='new'`, `firstResponseAt=null` (отвечает менеджер),
   и проставляет `OutreachContact.leadId`.
5. Пишет `ActivityLog`. Дальше — штатный модуль лидов (правило 15 минут, назначение,
   конверт в клиента).
6. Дедуп: если по этому email уже есть открытый Lead — не плодить, добавить комментарий.
7. Авто-отписка: если ответ содержит «отпишите/не интересно/нет» — `unsubscribed`,
   Lead не создаётся (или создаётся со статусом `closed`, причина `unsubscribe`).

## 8. Фронтенд (Next.js, компактно, как clients/leads)

- Сайдбар: пункт `Рассылки`.
- `/outreach` — дашборд: счётчики (new/sent/replied/bounced/unsubscribed), кнопки кампаний.
- `/outreach/campaigns/[id]` — настройки кампании, прогресс, лог отправок.
- `/outreach/contacts` — **Excel-подобный редактируемый грид** (AG Grid/Handsontable): инлайн-правка ячеек, копипаст, сортировка/фильтры, массовые операции; импорт/экспорт **xlsx/CSV**. Источник правды — БД; файл .xlsx по кнопке «Экспорт».
- Ответы видны как лиды в существующем `/leads` (source = `email_outreach`).

## 9. RBAC

Seed прав: `outreach.view/create/update/send/import`.
- owner/admin — все;
- manager_head — view/create/update/send;
- manager — view (+ работа с лидами по существующим правам).

## 10. Деливерабилити

SPF/DKIM/DMARC уже pass. Прогрев 10→50/день, троттлинг 30–60 c, строка-отписка в шаблоне,
проверка `status` перед постановкой (не слать `replied/unsubscribed/bounced`), мониторинг
bounce/жалоб. Потолок одного ящика ~50/день; больше — второй ящик/домен (отдельная стадия).

## 11. Под-стадии (внедряем по одной: verify → commit → push → handoff → подтверждение)

- **E1 — Данные + грид:** Prisma-модели + миграция + seed прав + импорт/экспорт xlsx/CSV (наши ~921). Web: Excel-подобный редактируемый грид контактов (AG Grid/Handsontable).
- **E2 — Отправка:** Nodemailer + BullMQ (`drip`/`send`) + прогрев/троттлинг + статусы + bounce. Кампания/шаблон CRUD + start/pause.
- **E3 — Ответы:** IMAP-поллер → `replied` + авто-создание Lead + дедуп + отписка. Замыкание на лиды.
- **E4 — Автоматизация контроля:** фоллоу-апы + Telegram (уведомления/команды) + веб-дашборд статистики.
- **E5 — Позже:** Claude API «живой» текст, канал Авито, гос-кампания.

## 12. Конфигурация (`.env.production`, только на сервере)

`OUTREACH_SMTP_HOST/PORT/USER/PASS`, `OUTREACH_IMAP_HOST/PORT/USER/PASS`,
`OUTREACH_FROM_NAME`, `OUTREACH_FROM_EMAIL`, `OUTREACH_DAILY_CAP`, `OUTREACH_WARMUP_*`,
`OUTREACH_THROTTLE_MS`; (E4) `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`; (E5) `ANTHROPIC_API_KEY`.

## 13. Verification (по образцу проекта)

Локально: `prisma validate` + `generate`; unit-тесты сервисов (рендер шаблона; матч ответа →
Lead; дедуп; прогрев/лимит; bounce); `npm.cmd run test`; `npm.cmd run build`; `git diff --check`.
VPS: `git pull --ff-only` → сборка api/web → `up -d --no-build` → `prisma migrate deploy` →
seed → `GET /api/health` → smoke (импорт, тестовая отправка на свой ящик, имитация ответа → Lead).

## 14. Допущения

- SMTP/IMAP-доступы рабочие (пилот подтвердил); пароль почты будет сменён и положен в `.env.production`.
- Redis доступен (есть в стеке) под BullMQ.
- Объёмы в пределах лимитов хостинга; рост — отдельная стадия (второй ящик/сервис).
- Claude API и Авито — осознанно отложены в E5.
- Источник правды по клиентам — существующий модуль клиентов; OutreachContact — только холодная база.

## 15. Self-Review

- Плейсхолдеров-заглушек нет; Claude API/Авито явно вынесены в E5.
- Модель данных не дублирует Clients/Leads, а дополняет и замыкается на них.
- Объём разбит на под-стадии под ваш процесс (verify/commit/push/handoff).
- Секреты не в репозитории.
- RBAC и audit — по существующим конвенциям.

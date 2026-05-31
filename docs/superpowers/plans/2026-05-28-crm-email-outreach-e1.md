# Email Outreach — E1 (Данные + грид + импорт/экспорт) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Завести в CRM холодную базу контактов рассылки (`OutreachContact`) с REST API, импортом/экспортом xlsx/CSV и Excel-подобным редактируемым гридом, как первый shippable срез модуля «Рассылки».

**Architecture:** Новый NestJS-модуль `OutreachModule` (Controller + Service + DTO + RBAC + audit) по образцу `LeadsModule`; Prisma-модель `OutreachContact` в PostgreSQL; импорт/экспорт через `exceljs`; фронт — страница Next.js с AG Grid. Источник правды — БД; Google Sheets/Apps Script не используются.

**Tech Stack:** NestJS, Prisma 6.19.x, PostgreSQL 16, class-validator, exceljs, Next.js App Router, ag-grid-react, Jest.

> **Целевой репозиторий:** `CRM_system` (монорепо, workspaces `@crm/api`, `@crm/web`). Этот план исполняется внутри клона CRM, не в текущем парсинг-проекте.
> **Конвенции для зеркалирования (executor читает эти файлы перед началом):**
> - Бэкенд-модуль: `apps/api/src/leads/leads.module.ts`, `leads.controller.ts`, `leads.service.ts`, `leads.service.spec.ts`, `dto/*.ts`.
> - Guards/декораторы: `apps/api/src/common/guards/jwt-auth.guard.ts`, `permissions.guard.ts`, `common/decorators/permissions.decorator.ts`, `current-user.decorator.ts`, `common/types/authenticated-user.ts`.
> - Prisma: `apps/api/src/prisma/prisma.service.ts`, `apps/api/prisma/schema.prisma`, `apps/api/prisma/seed.ts`.
> - Аудит: запись в `activity_logs` так же, как в `LeadsService` (action/entityType/entityId/old/new/userId).
> - Регистрация модуля: `apps/api/src/app.module.ts`.
> - Фронт: `apps/web/src/app/leads/page.tsx`, `apps/web/src/lib/api.ts`, `apps/web/src/components/app-shell.tsx`.
> **Команды (PowerShell, как в README):** используем `npm.cmd`, `DATABASE_URL` экспортируется в сессию.

**Scope E1:** только `OutreachContact` (холодная база) + грид + импорт/экспорт. Модели `Campaign`/`EmailTemplate`/`EmailMessage` и отправка — в E2 (YAGNI: добавляем, когда нужны).

---

## File Structure

**Создаём:**
- `apps/api/src/outreach/outreach.module.ts` — модуль рассылок (E1: только contacts).
- `apps/api/src/outreach/contacts/outreach-contacts.controller.ts` — роуты `/outreach/contacts`.
- `apps/api/src/outreach/contacts/outreach-contacts.service.ts` — бизнес-логика + Prisma + audit.
- `apps/api/src/outreach/contacts/outreach-contacts.service.spec.ts` — unit-тесты сервиса.
- `apps/api/src/outreach/contacts/dto/create-outreach-contact.dto.ts`
- `apps/api/src/outreach/contacts/dto/update-outreach-contact.dto.ts`
- `apps/api/src/outreach/contacts/dto/outreach-contact-query.dto.ts`
- `apps/api/src/outreach/contacts/outreach-import.service.ts` — парсинг CSV/xlsx → upsert.
- `apps/api/src/outreach/contacts/outreach-import.service.spec.ts`
- `apps/web/src/app/outreach/contacts/page.tsx` — грид контактов (AG Grid).
- `apps/web/src/app/outreach/contacts/contacts-grid.tsx` — клиентский компонент грида.

**Модифицируем:**
- `apps/api/prisma/schema.prisma` — enums + модель `OutreachContact`.
- `apps/api/prisma/seed.ts` — права `outreach.*` + назначение ролям.
- `apps/api/src/app.module.ts` — регистрация `OutreachModule`.
- `apps/web/src/lib/api.ts` — методы API для контактов рассылки.
- `apps/web/src/components/app-shell.tsx` — пункт сайдбара «Рассылки».

---

## Task 1: Prisma-модель OutreachContact + миграция

**Files:**
- Modify: `apps/api/prisma/schema.prisma`
- Create: `apps/api/prisma/migrations/<timestamp>_outreach_contacts/migration.sql` (генерируется Prisma)

- [ ] **Step 1: Добавить enums и модель в schema.prisma**

В конец `apps/api/prisma/schema.prisma` (стиль — как у `Lead`: `@map`, `@db.Uuid`, soft delete, индексы):

```prisma
enum OutreachSource {
  parsing
  avito
  manual
}

enum OutreachContactStatus {
  new
  queued
  sent
  replied
  bounced
  unsubscribed
  skipped
}

model OutreachContact {
  id          String                @id @default(uuid()) @db.Uuid
  name        String?
  type        String?
  city        String?
  email       String
  phone       String?
  website     String?
  social      String?
  address     String?
  source      OutreachSource        @default(parsing)
  status      OutreachContactStatus @default(new)
  touchCount  Int                   @default(0) @map("touch_count")
  lastTouchAt DateTime?             @map("last_touch_at")
  leadId      String?               @map("lead_id") @db.Uuid
  note        String?
  createdAt   DateTime              @default(now()) @map("created_at")
  updatedAt   DateTime              @updatedAt @map("updated_at")
  deletedAt   DateTime?             @map("deleted_at")
  createdBy   String?               @map("created_by") @db.Uuid

  @@index([email])
  @@index([status])
  @@index([city])
  @@index([source])
  @@index([deletedAt])
  @@map("outreach_contacts")
}
```

- [ ] **Step 2: Проверить схему**

Run:
```powershell
$env:DATABASE_URL="postgresql://crm:crm@localhost:5432/crm?schema=public"; npm.cmd exec -w @crm/api -- prisma validate
```
Expected: `The schema at ... is valid 🚀`

- [ ] **Step 3: Создать миграцию и сгенерировать клиент**

Run:
```powershell
$env:DATABASE_URL="postgresql://crm:crm@localhost:5432/crm?schema=public"; npm.cmd run prisma:migrate -w @crm/api -- --name outreach_contacts
$env:DATABASE_URL="postgresql://crm:crm@localhost:5432/crm?schema=public"; npm.cmd run prisma:generate -w @crm/api
```
Expected: новая папка миграции создана; `Generated Prisma Client`.

- [ ] **Step 4: Commit**

```bash
git add apps/api/prisma/schema.prisma apps/api/prisma/migrations
git commit -m "feat(outreach): add OutreachContact prisma model and migration"
```

---

## Task 2: Права доступа в seed

**Files:**
- Modify: `apps/api/prisma/seed.ts`

- [ ] **Step 1: Добавить permissions и назначения ролям**

В `seed.ts`, в список permissions (рядом с `leads.*`) добавить объекты:

```ts
{ code: 'outreach.view', name: 'Просмотр рассылок' },
{ code: 'outreach.create', name: 'Создание контактов рассылки' },
{ code: 'outreach.update', name: 'Изменение контактов рассылки' },
{ code: 'outreach.import', name: 'Импорт базы рассылки' },
```

В назначениях ролей (тем же способом, что для `leads.*`):
- `owner`, `admin`: все `outreach.*`.
- `manager_head`: `outreach.view`, `outreach.create`, `outreach.update`, `outreach.import`.
- `manager`: `outreach.view`.

> Зеркалировать точную форму массивов из существующего `seed.ts` (там permissions создаются upsert по `code`, а role-permission — по паре `roleId+permissionId`).

- [ ] **Step 2: Прогнать seed**

Run:
```powershell
$env:DATABASE_URL="postgresql://crm:crm@localhost:5432/crm?schema=public"; npm.cmd run prisma:seed -w @crm/api
```
Expected: seed завершается без ошибок (exit 0).

- [ ] **Step 3: Commit**

```bash
git add apps/api/prisma/seed.ts
git commit -m "feat(outreach): seed outreach permissions and role assignments"
```

---

## Task 3: DTO контактов

**Files:**
- Create: `apps/api/src/outreach/contacts/dto/create-outreach-contact.dto.ts`
- Create: `apps/api/src/outreach/contacts/dto/update-outreach-contact.dto.ts`
- Create: `apps/api/src/outreach/contacts/dto/outreach-contact-query.dto.ts`

- [ ] **Step 1: create-outreach-contact.dto.ts**

```ts
import { IsEmail, IsEnum, IsOptional, IsString, MaxLength } from 'class-validator';
import { OutreachSource } from '@prisma/client';

export class CreateOutreachContactDto {
  @IsEmail()
  email!: string;

  @IsOptional() @IsString() @MaxLength(300) name?: string;
  @IsOptional() @IsString() @MaxLength(100) type?: string;
  @IsOptional() @IsString() @MaxLength(150) city?: string;
  @IsOptional() @IsString() @MaxLength(100) phone?: string;
  @IsOptional() @IsString() @MaxLength(500) website?: string;
  @IsOptional() @IsString() @MaxLength(500) social?: string;
  @IsOptional() @IsString() @MaxLength(1000) address?: string;
  @IsOptional() @IsEnum(OutreachSource) source?: OutreachSource;
  @IsOptional() @IsString() @MaxLength(1000) note?: string;
}
```

- [ ] **Step 2: update-outreach-contact.dto.ts**

```ts
import { PartialType } from '@nestjs/mapped-types';
import { IsEnum, IsOptional } from 'class-validator';
import { OutreachContactStatus } from '@prisma/client';
import { CreateOutreachContactDto } from './create-outreach-contact.dto';

export class UpdateOutreachContactDto extends PartialType(CreateOutreachContactDto) {
  @IsOptional() @IsEnum(OutreachContactStatus) status?: OutreachContactStatus;
}
```

- [ ] **Step 3: outreach-contact-query.dto.ts**

```ts
import { IsEnum, IsOptional, IsString } from 'class-validator';
import { OutreachContactStatus, OutreachSource } from '@prisma/client';

export class OutreachContactQueryDto {
  @IsOptional() @IsString() search?: string;
  @IsOptional() @IsEnum(OutreachContactStatus) status?: OutreachContactStatus;
  @IsOptional() @IsEnum(OutreachSource) source?: OutreachSource;
  @IsOptional() @IsString() city?: string;
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/outreach/contacts/dto
git commit -m "feat(outreach): add outreach contact DTOs"
```

---

## Task 4: Сервис контактов — список/поиск/фильтры (TDD)

**Files:**
- Create: `apps/api/src/outreach/contacts/outreach-contacts.service.ts`
- Test: `apps/api/src/outreach/contacts/outreach-contacts.service.spec.ts`

- [ ] **Step 1: Написать падающий тест**

```ts
import { Test } from '@nestjs/testing';
import { PrismaService } from '../../prisma/prisma.service';
import { OutreachContactsService } from './outreach-contacts.service';

const prismaMock = () => ({
  outreachContact: {
    findMany: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    findFirst: jest.fn(),
  },
  activityLog: { create: jest.fn() },
});

describe('OutreachContactsService', () => {
  let service: OutreachContactsService;
  let prisma: ReturnType<typeof prismaMock>;

  beforeEach(async () => {
    prisma = prismaMock();
    const moduleRef = await Test.createTestingModule({
      providers: [
        OutreachContactsService,
        { provide: PrismaService, useValue: prisma },
      ],
    }).compile();
    service = moduleRef.get(OutreachContactsService);
  });

  it('list filters by status and searches name/email', async () => {
    prisma.outreachContact.findMany.mockResolvedValue([{ id: '1', email: 'a@b.ru' }]);
    const res = await service.list({ status: 'new', search: 'sofia' } as any);
    expect(res).toHaveLength(1);
    const arg = prisma.outreachContact.findMany.mock.calls[0][0];
    expect(arg.where.status).toBe('new');
    expect(arg.where.deletedAt).toBeNull();
    expect(JSON.stringify(arg.where.OR)).toContain('sofia');
  });
});
```

- [ ] **Step 2: Запустить — должно упасть**

Run:
```powershell
npm.cmd run test -w @crm/api -- outreach-contacts.service.spec.ts
```
Expected: FAIL (`Cannot find module './outreach-contacts.service'`).

- [ ] **Step 3: Реализовать минимально**

```ts
import { Injectable } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import { OutreachContactQueryDto } from './dto/outreach-contact-query.dto';

@Injectable()
export class OutreachContactsService {
  constructor(private readonly prisma: PrismaService) {}

  list(query: OutreachContactQueryDto) {
    const where: Prisma.OutreachContactWhereInput = { deletedAt: null };
    if (query.status) where.status = query.status;
    if (query.source) where.source = query.source;
    if (query.city) where.city = { contains: query.city, mode: 'insensitive' };
    if (query.search) {
      where.OR = [
        { name: { contains: query.search, mode: 'insensitive' } },
        { email: { contains: query.search, mode: 'insensitive' } },
        { city: { contains: query.search, mode: 'insensitive' } },
        { phone: { contains: query.search, mode: 'insensitive' } },
      ];
    }
    return this.prisma.outreachContact.findMany({ where, orderBy: { createdAt: 'desc' } });
  }
}
```

- [ ] **Step 4: Запустить — должно пройти**

Run:
```powershell
npm.cmd run test -w @crm/api -- outreach-contacts.service.spec.ts
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/outreach/contacts/outreach-contacts.service.ts apps/api/src/outreach/contacts/outreach-contacts.service.spec.ts
git commit -m "feat(outreach): contacts service list with filters and search"
```

---

## Task 5: Сервис контактов — create/update/softDelete + audit (TDD)

**Files:**
- Modify: `apps/api/src/outreach/contacts/outreach-contacts.service.ts`
- Modify: `apps/api/src/outreach/contacts/outreach-contacts.service.spec.ts`

- [ ] **Step 1: Дописать падающие тесты**

```ts
it('create stores contact and writes audit', async () => {
  prisma.outreachContact.create.mockResolvedValue({ id: '1', email: 'a@b.ru' });
  const res = await service.create({ email: 'a@b.ru', name: 'Sofia' } as any, 'user-1');
  expect(res.id).toBe('1');
  expect(prisma.outreachContact.create).toHaveBeenCalled();
  expect(prisma.activityLog.create).toHaveBeenCalledWith(
    expect.objectContaining({ data: expect.objectContaining({ action: 'create', entityType: 'outreach_contact' }) }),
  );
});

it('softDelete sets deletedAt', async () => {
  prisma.outreachContact.findFirst.mockResolvedValue({ id: '1', email: 'a@b.ru' });
  prisma.outreachContact.update.mockResolvedValue({ id: '1', deletedAt: new Date() });
  await service.softDelete('1', 'user-1');
  const arg = prisma.outreachContact.update.mock.calls[0][0];
  expect(arg.data.deletedAt).toBeInstanceOf(Date);
});
```

- [ ] **Step 2: Запустить — должно упасть**

Run: `npm.cmd run test -w @crm/api -- outreach-contacts.service.spec.ts`
Expected: FAIL (`service.create is not a function`).

- [ ] **Step 3: Реализовать методы**

Добавить в `OutreachContactsService`:

```ts
import { NotFoundException } from '@nestjs/common';
import { CreateOutreachContactDto } from './dto/create-outreach-contact.dto';
import { UpdateOutreachContactDto } from './dto/update-outreach-contact.dto';

private audit(userId: string | null, action: string, entityId: string, newValue?: unknown, oldValue?: unknown) {
  return this.prisma.activityLog.create({
    data: {
      userId: userId ?? undefined,
      action,
      entityType: 'outreach_contact',
      entityId,
      newValueJson: newValue as any,
      oldValueJson: oldValue as any,
    },
  });
}

async getOne(id: string) {
  const c = await this.prisma.outreachContact.findFirst({ where: { id, deletedAt: null } });
  if (!c) throw new NotFoundException('Контакт не найден');
  return c;
}

async create(dto: CreateOutreachContactDto, userId: string) {
  const created = await this.prisma.outreachContact.create({
    data: { ...dto, createdBy: userId },
  });
  await this.audit(userId, 'create', created.id, created);
  return created;
}

async update(id: string, dto: UpdateOutreachContactDto, userId: string) {
  const old = await this.getOne(id);
  const updated = await this.prisma.outreachContact.update({ where: { id }, data: { ...dto } });
  await this.audit(userId, 'update', id, updated, old);
  return updated;
}

async softDelete(id: string, userId: string) {
  await this.getOne(id);
  const deleted = await this.prisma.outreachContact.update({
    where: { id },
    data: { deletedAt: new Date() },
  });
  await this.audit(userId, 'delete', id, deleted);
  return { success: true };
}
```

- [ ] **Step 4: Запустить — должно пройти**

Run: `npm.cmd run test -w @crm/api -- outreach-contacts.service.spec.ts`
Expected: PASS (3 теста).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/outreach/contacts/outreach-contacts.service.ts apps/api/src/outreach/contacts/outreach-contacts.service.spec.ts
git commit -m "feat(outreach): contacts create/update/softDelete with audit"
```

---

## Task 6: Контроллер + регистрация модуля + RBAC

**Files:**
- Create: `apps/api/src/outreach/contacts/outreach-contacts.controller.ts`
- Create: `apps/api/src/outreach/outreach.module.ts`
- Modify: `apps/api/src/app.module.ts`

- [ ] **Step 1: Контроллер** (зеркалировать guards/декораторы из `leads.controller.ts`)

```ts
import { Body, Controller, Delete, Get, Param, Patch, Post, Query, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { PermissionsGuard } from '../../common/guards/permissions.guard';
import { Permissions } from '../../common/decorators/permissions.decorator';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { AuthenticatedUser } from '../../common/types/authenticated-user';
import { OutreachContactsService } from './outreach-contacts.service';
import { CreateOutreachContactDto } from './dto/create-outreach-contact.dto';
import { UpdateOutreachContactDto } from './dto/update-outreach-contact.dto';
import { OutreachContactQueryDto } from './dto/outreach-contact-query.dto';

@UseGuards(JwtAuthGuard, PermissionsGuard)
@Controller('outreach/contacts')
export class OutreachContactsController {
  constructor(private readonly service: OutreachContactsService) {}

  @Get() @Permissions('outreach.view')
  list(@Query() query: OutreachContactQueryDto) { return this.service.list(query); }

  @Get(':id') @Permissions('outreach.view')
  getOne(@Param('id') id: string) { return this.service.getOne(id); }

  @Post() @Permissions('outreach.create')
  create(@Body() dto: CreateOutreachContactDto, @CurrentUser() user: AuthenticatedUser) {
    return this.service.create(dto, user.id);
  }

  @Patch(':id') @Permissions('outreach.update')
  update(@Param('id') id: string, @Body() dto: UpdateOutreachContactDto, @CurrentUser() user: AuthenticatedUser) {
    return this.service.update(id, dto, user.id);
  }

  @Delete(':id') @Permissions('outreach.update')
  remove(@Param('id') id: string, @CurrentUser() user: AuthenticatedUser) {
    return this.service.softDelete(id, user.id);
  }
}
```

> Если в `leads.controller.ts` декоратор называется иначе (напр. `@RequirePermissions`) — использовать тот же. Имя свойства id в `AuthenticatedUser` тоже зеркалировать.

- [ ] **Step 2: Модуль**

```ts
import { Module } from '@nestjs/common';
import { PrismaModule } from '../prisma/prisma.module';
import { OutreachContactsController } from './contacts/outreach-contacts.controller';
import { OutreachContactsService } from './contacts/outreach-contacts.service';

@Module({
  imports: [PrismaModule],
  controllers: [OutreachContactsController],
  providers: [OutreachContactsService],
  exports: [OutreachContactsService],
})
export class OutreachModule {}
```

- [ ] **Step 3: Зарегистрировать в app.module.ts**

В `imports: [...]` массив `AppModule` добавить `OutreachModule` (рядом с `LeadsModule`), импортнуть сверху:
```ts
import { OutreachModule } from './outreach/outreach.module';
```

- [ ] **Step 4: Сборка и тесты**

Run:
```powershell
npm.cmd run test -w @crm/api
npm.cmd run build -w @crm/api
```
Expected: все тесты PASS; API билд успешен.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/outreach apps/api/src/app.module.ts
git commit -m "feat(outreach): contacts controller, module, RBAC wiring"
```

---

## Task 7: Импорт CSV/xlsx (TDD)

**Files:**
- Create: `apps/api/src/outreach/contacts/outreach-import.service.ts`
- Test: `apps/api/src/outreach/contacts/outreach-import.service.spec.ts`
- Modify: `apps/api/src/outreach/outreach.module.ts` (добавить провайдер/контроллерный метод)
- Modify: `apps/api/src/outreach/contacts/outreach-contacts.controller.ts` (эндпоинт импорта/экспорта)

- [ ] **Step 1: Установить exceljs**

Run:
```powershell
npm.cmd install exceljs -w @crm/api
```
Expected: пакет добавлен в `apps/api/package.json`.

- [ ] **Step 2: Падающий тест на парсинг CSV**

```ts
import { OutreachImportService } from './outreach-import.service';

describe('OutreachImportService.parseCsv', () => {
  const svc = new OutreachImportService();

  it('parses rows, validates email, dedupes', () => {
    const csv = [
      'Email,Название,Тип,Город,Телефон',
      'a@b.ru,София,гостевой дом,Крым,+7978',
      'a@b.ru,Дубль,отель,Крым,+7000',     // дубль по email
      'bad-email,НЛО,отель,Крым,',          // невалидный email
    ].join('\n');
    const rows = svc.parseCsv(Buffer.from(csv, 'utf-8'));
    expect(rows).toHaveLength(1);
    expect(rows[0].email).toBe('a@b.ru');
    expect(rows[0].name).toBe('София');
  });
});
```

- [ ] **Step 3: Запустить — упадёт**

Run: `npm.cmd run test -w @crm/api -- outreach-import.service.spec.ts`
Expected: FAIL (модуль не найден).

- [ ] **Step 4: Реализовать парсер + upsert**

```ts
import { Injectable } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

const EMAIL_RE = /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/;

export interface ParsedContact {
  email: string; name?: string; type?: string; city?: string;
  phone?: string; website?: string; social?: string; address?: string;
}

@Injectable()
export class OutreachImportService {
  constructor(private readonly prisma?: PrismaService) {}

  parseCsv(buf: Buffer): ParsedContact[] {
    const text = buf.toString('utf-8').replace(/^﻿/, '');
    const lines = text.split(/\r?\n/).filter((l) => l.trim());
    if (lines.length < 2) return [];
    const sep = lines[0].includes(';') ? ';' : ',';
    const header = lines[0].split(sep).map((h) => h.trim().toLowerCase());
    const idx = (names: string[]) => header.findIndex((h) => names.includes(h));
    const cEmail = idx(['email']);
    const cName = idx(['название', 'name']);
    const cType = idx(['тип', 'type']);
    const cCity = idx(['город', 'city']);
    const cPhone = idx(['телефон', 'phone']);
    const cSite = idx(['сайт', 'website']);
    const cSocial = idx(['соцсети', 'social']);
    const cAddr = idx(['адрес', 'address']);
    const seen = new Set<string>();
    const out: ParsedContact[] = [];
    for (const line of lines.slice(1)) {
      const cells = line.split(sep);
      const raw = (cEmail >= 0 ? cells[cEmail] : '')?.toLowerCase().trim() ?? '';
      const m = raw.match(EMAIL_RE);
      if (!m) continue;
      const email = m[0];
      if (seen.has(email)) continue;
      seen.add(email);
      out.push({
        email,
        name: cName >= 0 ? cells[cName]?.trim() : undefined,
        type: cType >= 0 ? cells[cType]?.trim() : undefined,
        city: cCity >= 0 ? cells[cCity]?.trim() : undefined,
        phone: cPhone >= 0 ? cells[cPhone]?.trim() : undefined,
        website: cSite >= 0 ? cells[cSite]?.trim() : undefined,
        social: cSocial >= 0 ? cells[cSocial]?.trim() : undefined,
        address: cAddr >= 0 ? cells[cAddr]?.trim() : undefined,
      });
    }
    return out;
  }

  async importContacts(rows: ParsedContact[], userId: string) {
    let created = 0, skipped = 0;
    for (const r of rows) {
      const exists = await this.prisma!.outreachContact.findFirst({ where: { email: r.email, deletedAt: null } });
      if (exists) { skipped++; continue; }
      await this.prisma!.outreachContact.create({ data: { ...r, source: 'parsing', createdBy: userId } });
      created++;
    }
    return { created, skipped, total: rows.length };
  }
}
```

> Примечание: CSV с кавычками и переносами строк внутри ячеек (как в исходном парсере) исполнитель при необходимости заменит наивный `split` на `exceljs`/CSV-парсер. Для нашего экспортного формата (без многострочных ячеек) `split` достаточно; тест это фиксирует.

- [ ] **Step 5: Запустить — пройдёт**

Run: `npm.cmd run test -w @crm/api -- outreach-import.service.spec.ts`
Expected: PASS.

- [ ] **Step 6: Эндпоинт импорта в контроллере**

Добавить в `OutreachContactsController` (multipart через `@nestjs/platform-express` `FileInterceptor`):

```ts
import { UploadedFile, UseInterceptors } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { OutreachImportService } from './outreach-import.service';
// в конструктор добавить: private readonly importService: OutreachImportService

@Post('import') @Permissions('outreach.import')
@UseInterceptors(FileInterceptor('file'))
async import(@UploadedFile() file: { buffer: Buffer }, @CurrentUser() user: AuthenticatedUser) {
  const rows = this.importService.parseCsv(file.buffer);
  return this.importService.importContacts(rows, user.id);
}
```

Зарегистрировать `OutreachImportService` в `providers` модуля.

- [ ] **Step 7: Сборка + тесты + commit**

```powershell
npm.cmd run test -w @crm/api
npm.cmd run build -w @crm/api
```
```bash
git add apps/api/src/outreach apps/api/package.json package-lock.json
git commit -m "feat(outreach): csv/xlsx import endpoint with dedupe"
```

---

## Task 8: Экспорт xlsx

**Files:**
- Modify: `apps/api/src/outreach/contacts/outreach-import.service.ts` (метод exportXlsx)
- Modify: `apps/api/src/outreach/contacts/outreach-contacts.controller.ts` (эндпоинт export)

- [ ] **Step 1: Метод экспорта (exceljs)**

В `OutreachImportService`:

```ts
import * as ExcelJS from 'exceljs';

async exportXlsx(rows: Array<Record<string, unknown>>): Promise<Buffer> {
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet('Рассылка');
  ws.columns = [
    { header: 'Email', key: 'email' }, { header: 'Название', key: 'name' },
    { header: 'Тип', key: 'type' }, { header: 'Город', key: 'city' },
    { header: 'Телефон', key: 'phone' }, { header: 'Сайт', key: 'website' },
    { header: 'Статус', key: 'status' },
  ];
  rows.forEach((r) => ws.addRow(r));
  return (await wb.xlsx.writeBuffer()) as Buffer;
}
```

- [ ] **Step 2: Эндпоинт экспорта**

```ts
import { Res } from '@nestjs/common';
import type { Response } from 'express';

@Get('export') @Permissions('outreach.view')
async export(@Query() query: OutreachContactQueryDto, @Res() res: Response) {
  const rows = await this.service.list(query);
  const buf = await this.importService.exportXlsx(rows as any);
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.setHeader('Content-Disposition', 'attachment; filename="outreach_contacts.xlsx"');
  res.send(buf);
}
```

> `export` объявить ДО `':id'` маршрута, чтобы не перехватывался параметром (либо вынести под `/outreach/contacts/export`).

- [ ] **Step 3: Сборка + commit**

```powershell
npm.cmd run build -w @crm/api
```
```bash
git add apps/api/src/outreach
git commit -m "feat(outreach): xlsx export endpoint"
```

---

## Task 9: Фронт — API-клиент

**Files:**
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Добавить методы** (зеркалировать стиль существующих fetch-обёрток в `api.ts`)

```ts
export const outreachApi = {
  listContacts: (params?: Record<string, string>) =>
    apiFetch(`/outreach/contacts${params ? '?' + new URLSearchParams(params) : ''}`),
  updateContact: (id: string, body: unknown) =>
    apiFetch(`/outreach/contacts/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  importContacts: (file: File) => {
    const fd = new FormData(); fd.append('file', file);
    return apiFetch('/outreach/contacts/import', { method: 'POST', body: fd, rawBody: true });
  },
  exportUrl: (params?: Record<string, string>) =>
    `/api/outreach/contacts/export${params ? '?' + new URLSearchParams(params) : ''}`,
};
```

> `apiFetch` и обработку токена/заголовков зеркалировать из текущего `api.ts`. Если `apiFetch` всегда ставит `Content-Type: application/json`, добавить флаг `rawBody`, чтобы для `FormData` не выставлять JSON-заголовок.

- [ ] **Step 2: Сборка web**

Run: `npm.cmd run build -w @crm/web`
Expected: билд успешен.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat(outreach): web api client for contacts"
```

---

## Task 10: Фронт — Excel-подобный грид

**Files:**
- Create: `apps/web/src/app/outreach/contacts/page.tsx`
- Create: `apps/web/src/app/outreach/contacts/contacts-grid.tsx`
- Modify: `apps/web/src/components/app-shell.tsx` (пункт «Рассылки»)

- [ ] **Step 1: Установить AG Grid**

Run:
```powershell
npm.cmd install ag-grid-react ag-grid-community -w @crm/web
```
Expected: пакеты добавлены.

- [ ] **Step 2: Клиентский компонент грида**

`contacts-grid.tsx`:
```tsx
'use client';
import { useEffect, useState, useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';
import { outreachApi } from '@/lib/api';

export function ContactsGrid() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { outreachApi.listContacts().then(setRows); }, []);

  const columnDefs = useMemo(() => ([
    { field: 'email', editable: false, filter: true, sortable: true },
    { field: 'name', headerName: 'Название', editable: true, filter: true, sortable: true },
    { field: 'type', headerName: 'Тип', editable: true, filter: true },
    { field: 'city', headerName: 'Город', editable: true, filter: true },
    { field: 'phone', headerName: 'Телефон', editable: true },
    { field: 'website', headerName: 'Сайт', editable: true },
    { field: 'status', headerName: 'Статус', editable: true, filter: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ['new','queued','sent','replied','bounced','unsubscribed','skipped'] } },
  ]), []);

  const onCellValueChanged = async (e: any) => {
    await outreachApi.updateContact(e.data.id, { [e.colDef.field]: e.newValue });
  };

  const onImport = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const f = ev.target.files?.[0]; if (!f) return;
    const r = await outreachApi.importContacts(f);
    alert(`Импортировано: ${r.created}, пропущено: ${r.skipped}`);
    outreachApi.listContacts().then(setRows);
  };

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
        <a href={outreachApi.exportUrl()} className="btn">Экспорт xlsx</a>
        <label className="btn">Импорт CSV<input type="file" accept=".csv,.xlsx" hidden onChange={onImport} /></label>
      </div>
      <div className="ag-theme-quartz" style={{ height: 600, width: '100%' }}>
        <AgGridReact rowData={rows} columnDefs={columnDefs as any}
          onCellValueChanged={onCellValueChanged}
          defaultColDef={{ resizable: true, filter: true, sortable: true }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Страница**

`page.tsx`:
```tsx
import { ContactsGrid } from './contacts-grid';

export default function OutreachContactsPage() {
  return (
    <div style={{ padding: 24 }}>
      <h1>Рассылки — База контактов</h1>
      <ContactsGrid />
    </div>
  );
}
```

> Если страницы в проекте оборачиваются в `AppShell`/проверку авторизации — обернуть так же, как `apps/web/src/app/leads/page.tsx`.

- [ ] **Step 4: Пункт сайдбара**

В `app-shell.tsx` добавить ссылку `{ href: '/outreach/contacts', label: 'Рассылки' }` рядом с «Лиды» (зеркалировать формат существующего массива пунктов).

- [ ] **Step 5: Сборка web**

Run: `npm.cmd run build -w @crm/web`
Expected: билд успешен; маршрут `/outreach/contacts` присутствует.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/app/outreach apps/web/src/components/app-shell.tsx apps/web/package.json package-lock.json
git commit -m "feat(outreach): excel-like contacts grid page with import/export"
```

---

## Task 11: Полная верификация + импорт боевой базы + handoff

**Files:** нет (проверки и деплой)

- [ ] **Step 1: Локальная проверка (как в README/HANDOFF)**

Run:
```powershell
$env:DATABASE_URL="postgresql://crm:crm@localhost:5432/crm?schema=public"; npm.cmd exec -w @crm/api -- prisma validate
$env:DATABASE_URL="postgresql://crm:crm@localhost:5432/crm?schema=public"; npm.cmd run prisma:generate -w @crm/api
npm.cmd run test
npm.cmd run build
git diff --check
```
Expected: prisma valid; тесты PASS; монорепо-билд PASS; нет whitespace-ошибок.

- [ ] **Step 2: Импорт боевой базы (788/921)**

Через UI `/outreach/contacts` → «Импорт CSV» → загрузить `data/outreach_contacts.csv` из парсинг-проекта. Проверить счётчик created/skipped и что грид показывает строки со статусом `new`.

- [ ] **Step 3: VPS-деплой (по процессу проекта)**

```bash
cd /opt/crm
git pull --ff-only
COMPOSE_PARALLEL_LIMIT=1 docker compose --env-file .env.production -f docker-compose.prod.yml build api --progress plain
COMPOSE_PARALLEL_LIMIT=1 docker compose --env-file .env.production -f docker-compose.prod.yml build web --progress plain
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --no-build
docker compose --env-file .env.production -f docker-compose.prod.yml exec api npx prisma migrate deploy
docker compose --env-file .env.production -f docker-compose.prod.yml exec api npm run prisma:seed -w @crm/api
curl http://213.109.202.45/api/health
```
Expected: `{"status":"ok","service":"crm-api"}`; миграция `outreach_contacts` применена; seed ok.

- [ ] **Step 4: Smoke на VPS**

- Логин owner → открыть `/outreach/contacts` (200).
- Импорт небольшого CSV через UI → видны строки.
- Инлайн-правка ячейки `name` → PATCH 200, значение сохранилось после refresh.
- Экспорт xlsx → файл скачивается.

- [ ] **Step 5: Handoff + push**

```bash
git push
```
Записать handoff (что сделано, коммиты, проверки, ограничения, следующий шаг = E2 отправка). Не начинать E2 без подтверждения пользователя.

---

## Self-Review

**Покрытие спеки (E1-часть):**
- `OutreachContact` модель + индексы — Task 1 ✅
- RBAC `outreach.*` — Task 2, 6 ✅
- CRUD + поиск/фильтры + audit — Task 4, 5, 6 ✅
- Импорт CSV/xlsx + дедуп — Task 7 ✅
- Экспорт xlsx — Task 8 ✅
- Excel-подобный грид (AG Grid, инлайн-правка) — Task 10 ✅
- Импорт боевой базы 788/921 — Task 11 ✅
- (E2–E5: отправка, IMAP→Lead, фоллоу-апы/Telegram/дашборд, Claude/Авито — отдельные планы.)

**Сканирование плейсхолдеров:** конкретный код в каждом шаге; где зеркалируем существующие хелперы (guards/декораторы/apiFetch/seed-формат) — явно указан файл-образец, т.к. это устоявшиеся паттерны репозитория.

**Согласованность типов:** `OutreachContactsService` методы (`list/getOne/create/update/softDelete`) совпадают между Task 4–6; `OutreachImportService` (`parseCsv/importContacts/exportXlsx`) — между Task 7–8; `outreachApi` методы — между Task 9–10. Enum-значения статусов совпадают в Prisma (Task 1), grid select (Task 10) и тестах.

**Известные допущения:** наивный CSV-`split` достаточен для нашего экспортного формата; для исходных файлов парсера с многострочными ячейками исполнитель переключит парсинг на exceljs (отмечено в Task 7).

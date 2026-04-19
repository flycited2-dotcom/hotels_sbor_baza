from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from datetime import date
from services import db, excel, notifier, sheets
from handlers.inline import status_kb

router = Router()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Нет активного действия для отмены.", reply_markup=ReplyKeyboardRemove())
        return
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=ReplyKeyboardRemove())


@router.message(Command("status"))
async def cmd_status(message: Message):
    today = await db.count_today()
    total = await db.count_total()
    await message.answer(
        f"📊 <b>Статистика</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Сегодня добавлено: <b>{today}</b>\n"
        f"Всего в базе: <b>{total}</b>",
        parse_mode="HTML",
    )


@router.message(Command("report"))
async def cmd_report(message: Message):
    await message.answer("⏳ Генерирую отчёт за сегодня...")
    leads = await db.get_leads_today()
    if not leads:
        await message.answer("Сегодня контактов не добавлено.")
        return
    filepath = excel.generate_daily_report(leads)
    with open(filepath, "rb") as f:
        await message.answer_document(
            document=f,
            caption=f"📎 Отчёт за {date.today().strftime('%d.%m.%Y')} — {len(leads)} контактов",
        )


@router.message(Command("master"))
async def cmd_master(message: Message):
    """Выгрузка полной базы прямо сейчас, не дожидаясь пятницы."""
    await message.answer("⏳ Генерирую мастер-файл...")
    leads = await db.get_all_leads()
    if not leads:
        await message.answer("База пуста.")
        return
    filepath = excel.generate_master_report(leads)
    with open(filepath, "rb") as f:
        await message.answer_document(
            document=f,
            caption=f"📎 Мастер-файл на {date.today().strftime('%d.%m.%Y')} — {len(leads)} контактов",
        )


@router.message(Command("edit"))
async def cmd_edit(message: Message):
    """Последние 5 контактов пользователя с inline-кнопками смены статуса."""
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    leads = await db.get_recent_leads_by_user(username, limit=5)
    if not leads:
        await message.answer("Вы ещё не добавляли контактов.")
        return
    from services.notifier import format_lead_card
    for lead in leads:
        card = format_lead_card(lead)
        await message.answer(
            f"📝 <b>Контакт #{lead['id']}</b>\n\n{card}",
            parse_mode="HTML",
            reply_markup=status_kb(lead["id"]),
        )


@router.message(Command("getlead"))
async def cmd_getlead(message: Message):
    """Карточка контакта по ID. Использование: /getlead 5"""
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(
            "Использование: <code>/getlead ID</code>\nПример: <code>/getlead 5</code>",
            parse_mode="HTML",
        )
        return
    lead_id = int(parts[1])
    lead = await db.get_lead_by_id(lead_id)
    if not lead:
        await message.answer(f"Контакт #{lead_id} не найден.")
        return
    from services.notifier import format_lead_card
    card = format_lead_card(lead)
    await message.answer(
        f"📋 <b>Контакт #{lead_id}</b>\n\n{card}",
        parse_mode="HTML",
        reply_markup=status_kb(lead_id),
    )


@router.message(Command("find"))
async def cmd_find(message: Message):
    """Поиск по имени, телефону или городу. Использование: /find Симферополь"""
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Использование: <code>/find запрос</code>\n"
            "Поиск по названию, телефону, городу.\n"
            "Пример: <code>/find Симферополь</code>",
            parse_mode="HTML",
        )
        return
    query = parts[1].strip()
    leads = await db.search_leads(query)
    if not leads:
        await message.answer(f"По запросу «{query}» ничего не найдено.")
        return
    await message.answer(
        f"🔍 Найдено: <b>{len(leads)}</b> контактов по запросу «{query}»",
        parse_mode="HTML",
    )
    from services.notifier import format_lead_card
    for lead in leads:
        card = format_lead_card(lead)
        await message.answer(
            f"📋 <b>#{lead['id']}</b>\n\n{card}",
            parse_mode="HTML",
            reply_markup=status_kb(lead["id"]),
        )


@router.message(Command("setstatus"))
async def cmd_setstatus(message: Message):
    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Использование: <code>/setstatus ID Новый_статус</code>\n"
            "Доступные статусы: Новый, В работе, Отправлено КП, Отказ, Клиент",
            parse_mode="HTML",
        )
        return
    try:
        lead_id = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    new_status = parts[2].strip()
    from config import STATUSES
    if new_status not in STATUSES:
        await message.answer(f"Неверный статус. Доступные: {', '.join(STATUSES)}")
        return
    updated_at = await db.update_lead_status(lead_id, new_status)
    await sheets.update_lead_status_in_sheet(lead_id, new_status, updated_at)
    await message.answer(
        f"✅ Статус контакта #{lead_id} изменён на <b>{new_status}</b>",
        parse_mode="HTML",
    )


@router.message(Command("sync"))
async def cmd_sync(message: Message):
    """Полная пересинхронизация базы в Google Sheets."""
    await message.answer("⏳ Синхронизирую базу с Google Sheets...")
    leads = await db.get_all_leads()
    ok = await sheets.sync_all_to_sheet(leads)
    if ok:
        await message.answer(f"✅ Google Sheets синхронизирован: <b>{len(leads)}</b> контактов.", parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка синхронизации. Проверьте credentials.json и GOOGLE_SHEET_ID.")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Команды бота</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "/new — Добавить новый контакт\n"
        "/status — Статистика (сегодня / всего)\n"
        "/report — Скачать Excel за сегодня\n"
        "/master — Скачать полную базу (Excel)\n"
        "/find запрос — Поиск по имени, телефону, городу\n"
        "/getlead ID — Карточка контакта по номеру\n"
        "/edit — Последние 5 ваших контактов\n"
        "/setstatus ID Статус — Изменить статус\n"
        "/sync — Синхронизировать базу с Google Sheets\n"
        "/cancel — Отменить текущее действие\n"
        "/help — Эта справка",
        parse_mode="HTML",
    )

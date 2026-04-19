from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import OBJECT_TYPES, OBJECT_SIZES, INTEREST_CATEGORIES, STATUSES
from services import db, sheets, notifier
from handlers.inline import status_kb

router = Router()


class LeadForm(StatesGroup):
    name = State()
    object_type = State()
    city = State()
    region = State()
    address = State()
    phone = State()
    email = State()
    telegram = State()
    website = State()
    size = State()
    interests = State()
    status = State()
    comment = State()
    confirm = State()


def _make_kb(items: list, skip_label: str = None, columns: int = 2) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for item in items:
        builder.button(text=item)
    builder.adjust(columns)
    if skip_label:
        builder.button(text=f"⏩ {skip_label}")
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def _skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏩ Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _confirm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Сохранить")],
            [KeyboardButton(text="🔁 Начать заново")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _format_preview(data: dict) -> str:
    return (
        f"📋 <b>Проверьте данные:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 <b>Название:</b> {data.get('name', '—')}\n"
        f"🏷 <b>Тип:</b> {data.get('object_type', '—')}\n"
        f"📍 <b>Город:</b> {data.get('city', '—')}\n"
        f"🗺 <b>Регион:</b> {data.get('region', '—')}\n"
        f"🏠 <b>Адрес:</b> {data.get('address') or '—'}\n"
        f"📞 <b>Телефон:</b> {data.get('phone', '—')}\n"
        f"📧 <b>Email:</b> {data.get('email') or '—'}\n"
        f"✈️ <b>Telegram:</b> {data.get('telegram') or '—'}\n"
        f"🌐 <b>Сайт:</b> {data.get('website') or '—'}\n"
        f"📐 <b>Размер:</b> {data.get('size', '—')}\n"
        f"🔧 <b>Интерес:</b> {data.get('interests', '—')}\n"
        f"📊 <b>Статус:</b> {data.get('status', '—')}\n"
        f"💬 <b>Комментарий:</b> {data.get('comment') or '—'}\n"
    )


@router.message(F.text.in_(["/new", "/start"]))
async def cmd_new(message: Message, state: FSMContext):
    if message.chat.type != "private":
        me = await message.bot.get_me()
        await message.answer(
            f"Добавление контактов доступно только в личных сообщениях.\n"
            f"Напишите боту напрямую: @{me.username}",
            parse_mode="HTML",
        )
        return
    await state.clear()
    await state.set_state(LeadForm.name)
    await message.answer(
        "➕ <b>Добавление нового контакта</b>\n\nШаг 1/13 — Введите <b>название объекта</b>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(LeadForm.name)
async def step_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(LeadForm.object_type)
    await message.answer(
        "Шаг 2/13 — Выберите <b>тип объекта</b>:",
        parse_mode="HTML",
        reply_markup=_make_kb(OBJECT_TYPES),
    )


@router.message(LeadForm.object_type)
async def step_object_type(message: Message, state: FSMContext):
    text = message.text.strip()
    if text not in OBJECT_TYPES:
        await message.answer("Выберите из кнопок ниже:", reply_markup=_make_kb(OBJECT_TYPES))
        return
    await state.update_data(object_type=text)
    await state.set_state(LeadForm.city)
    await message.answer(
        "Шаг 3/13 — Введите <b>город</b>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(LeadForm.city)
async def step_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(LeadForm.region)
    await message.answer("Шаг 4/13 — Введите <b>регион</b>:", parse_mode="HTML")


@router.message(LeadForm.region)
async def step_region(message: Message, state: FSMContext):
    await state.update_data(region=message.text.strip())
    await state.set_state(LeadForm.address)
    await message.answer(
        "Шаг 5/13 — Введите <b>адрес</b> (или пропустите):",
        parse_mode="HTML",
        reply_markup=_skip_kb(),
    )


@router.message(LeadForm.address)
async def step_address(message: Message, state: FSMContext):
    val = "" if message.text.strip() == "⏩ Пропустить" else message.text.strip()
    await state.update_data(address=val)
    await state.set_state(LeadForm.phone)
    await message.answer(
        "Шаг 6/13 — Введите <b>телефон</b>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(LeadForm.phone)
async def step_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(LeadForm.email)
    await message.answer(
        "Шаг 7/13 — Введите <b>email</b> (или пропустите):",
        parse_mode="HTML",
        reply_markup=_skip_kb(),
    )


@router.message(LeadForm.email)
async def step_email(message: Message, state: FSMContext):
    val = "" if message.text.strip() == "⏩ Пропустить" else message.text.strip()
    await state.update_data(email=val)
    await state.set_state(LeadForm.telegram)
    await message.answer(
        "Шаг 8/13 — Введите <b>Telegram</b> username или канал (или пропустите):",
        parse_mode="HTML",
        reply_markup=_skip_kb(),
    )


@router.message(LeadForm.telegram)
async def step_telegram(message: Message, state: FSMContext):
    val = "" if message.text.strip() == "⏩ Пропустить" else message.text.strip()
    await state.update_data(telegram=val)
    await state.set_state(LeadForm.website)
    await message.answer(
        "Шаг 9/13 — Введите <b>сайт</b> (или пропустите):",
        parse_mode="HTML",
        reply_markup=_skip_kb(),
    )


@router.message(LeadForm.website)
async def step_website(message: Message, state: FSMContext):
    val = "" if message.text.strip() == "⏩ Пропустить" else message.text.strip()
    await state.update_data(website=val)
    await state.set_state(LeadForm.size)
    await message.answer(
        "Шаг 10/13 — Выберите <b>размер объекта</b>:",
        parse_mode="HTML",
        reply_markup=_make_kb(OBJECT_SIZES),
    )


@router.message(LeadForm.size)
async def step_size(message: Message, state: FSMContext):
    text = message.text.strip()
    if text not in OBJECT_SIZES:
        await message.answer("Выберите из кнопок ниже:", reply_markup=_make_kb(OBJECT_SIZES))
        return
    await state.update_data(size=text)
    await state.set_state(LeadForm.interests)
    await message.answer(
        "Шаг 11/13 — Выберите <b>категорию интереса</b>\n"
        "(можно несколько через запятую или выберите одну кнопку):",
        parse_mode="HTML",
        reply_markup=_make_kb(INTEREST_CATEGORIES, columns=1),
    )


@router.message(LeadForm.interests)
async def step_interests(message: Message, state: FSMContext):
    await state.update_data(interests=message.text.strip())
    await state.set_state(LeadForm.status)
    await message.answer(
        "Шаг 12/13 — Выберите <b>статус</b>:",
        parse_mode="HTML",
        reply_markup=_make_kb(STATUSES),
    )


@router.message(LeadForm.status)
async def step_status(message: Message, state: FSMContext):
    text = message.text.strip()
    if text not in STATUSES:
        await message.answer("Выберите из кнопок ниже:", reply_markup=_make_kb(STATUSES))
        return
    await state.update_data(status=text)
    await state.set_state(LeadForm.comment)
    await message.answer(
        "Шаг 13/13 — Добавьте <b>комментарий</b> (или пропустите):",
        parse_mode="HTML",
        reply_markup=_skip_kb(),
    )


@router.message(LeadForm.comment)
async def step_comment(message: Message, state: FSMContext):
    val = "" if message.text.strip() == "⏩ Пропустить" else message.text.strip()
    await state.update_data(comment=val)
    data = await state.get_data()
    preview = _format_preview(data)
    await state.set_state(LeadForm.confirm)
    await message.answer(
        preview + "\nВсё верно?",
        parse_mode="HTML",
        reply_markup=_confirm_kb(),
    )


@router.message(LeadForm.confirm, F.text == "✅ Сохранить")
async def step_save(message: Message, state: FSMContext):
    data = await state.get_data()
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    data["added_by"] = username

    lead_id = await db.add_lead(data)
    data["id"] = lead_id
    total = await db.count_total()

    await notifier.send_lead_to_group(message.bot, data)
    await sheets.append_lead_to_sheet(data)

    await state.clear()
    await message.answer(
        f"✅ Контакт <b>#{lead_id}</b> сохранён!\nВсего в базе: <b>{total}</b>\n\n"
        f"Быстрая смена статуса:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        f"📊 Текущий статус: <b>{data.get('status', 'Новый')}</b>",
        parse_mode="HTML",
        reply_markup=status_kb(lead_id),
    )


@router.message(LeadForm.confirm, F.text == "🔁 Начать заново")
async def step_restart(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(LeadForm.name)
    await message.answer(
        "🔄 Начинаем заново.\n\nШаг 1/13 — Введите <b>название объекта</b>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(LeadForm.confirm, F.text == "❌ Отмена")
async def step_cancel_confirm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=ReplyKeyboardRemove())

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import STATUSES
from services import db, sheets

router = Router()


def status_kb(lead_id: int) -> InlineKeyboardMarkup:
    """Inline-клавиатура смены статуса для конкретного лида."""
    builder = InlineKeyboardBuilder()
    for status in STATUSES:
        builder.button(text=status, callback_data=f"status:{lead_id}:{status}")
    builder.adjust(3)
    return builder.as_markup()


@router.callback_query(F.data.startswith("status:"))
async def cb_set_status(call: CallbackQuery):
    _, lead_id_str, new_status = call.data.split(":", 2)
    lead_id = int(lead_id_str)

    updated_at = await db.update_lead_status(lead_id, new_status)
    await sheets.update_lead_status_in_sheet(lead_id, new_status, updated_at)

    await call.answer(f"✅ Статус → {new_status}")

    # Обновляем подпись кнопок: убираем клавиатуру, добавляем отметку
    try:
        new_text = call.message.text + f"\n\n📊 Статус обновлён: <b>{new_status}</b>"
        await call.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
    except Exception:
        pass  # сообщение уже было изменено ранее — не критично

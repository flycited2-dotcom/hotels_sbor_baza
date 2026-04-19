from aiogram import Bot
from config import GROUP_CHAT_ID
import logging

logger = logging.getLogger(__name__)


def format_lead_card(lead: dict) -> str:
    lines = [
        "🏨 <b>Новый контакт</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏢 <b>Название:</b> {lead.get('name', '—')}",
        f"🏷 <b>Тип:</b> {lead.get('object_type', '—')}",
        f"📍 <b>Город:</b> {lead.get('city', '—')}",
        f"🗺 <b>Регион:</b> {lead.get('region', '—')}",
    ]
    if lead.get("address"):
        lines.append(f"🏠 <b>Адрес:</b> {lead['address']}")
    lines.append(f"📞 <b>Телефон:</b> {lead.get('phone', '—')}")
    if lead.get("email"):
        lines.append(f"📧 <b>Email:</b> {lead['email']}")
    if lead.get("telegram"):
        lines.append(f"✈️ <b>Telegram:</b> {lead['telegram']}")
    if lead.get("website"):
        lines.append(f"🌐 <b>Сайт:</b> {lead['website']}")
    lines += [
        f"📐 <b>Размер:</b> {lead.get('size', '—')}",
        f"🔧 <b>Интерес:</b> {lead.get('interests', '—')}",
        f"📊 <b>Статус:</b> {lead.get('status', '—')}",
    ]
    if lead.get("comment"):
        lines.append(f"💬 <b>Комментарий:</b> {lead['comment']}")
    lines.append(f"👤 <b>Добавил:</b> {lead.get('added_by', '—')}")
    return "\n".join(lines)


async def send_lead_to_group(bot: Bot, lead: dict):
    try:
        text = format_lead_card(lead)
        await bot.send_message(GROUP_CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending lead to group: {e}")


async def send_daily_digest(bot: Bot, leads: list, filepath: str):
    try:
        today_count = len(leads)
        text = (
            f"📋 <b>Дайджест за сегодня</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Новых контактов: <b>{today_count}</b>\n\n"
        )
        if leads:
            cards = []
            for lead in leads:
                cards.append(format_lead_card(lead))
            full_text = text + "\n\n".join(cards)
        else:
            full_text = text + "Сегодня контактов не добавлено."

        # Telegram limit 4096 chars — split if needed
        if len(full_text) > 4000:
            await bot.send_message(GROUP_CHAT_ID, text + f"Контактов добавлено: {today_count}", parse_mode="HTML")
        else:
            await bot.send_message(GROUP_CHAT_ID, full_text, parse_mode="HTML")

        if leads and filepath:
            with open(filepath, "rb") as f:
                await bot.send_document(
                    GROUP_CHAT_ID,
                    document=f,
                    caption=f"📎 Excel-отчёт за сегодня ({today_count} контактов)",
                )
    except Exception as e:
        logger.error(f"Error sending daily digest: {e}")


async def send_weekly_master(bot: Bot, total: int, week_count: int, filepath: str):
    try:
        text = (
            f"📦 <b>Еженедельный мастер-файл</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Всего контактов в базе: <b>{total}</b>\n"
            f"За неделю добавлено: <b>{week_count}</b>"
        )
        await bot.send_message(GROUP_CHAT_ID, text, parse_mode="HTML")
        if filepath:
            from datetime import date
            with open(filepath, "rb") as f:
                await bot.send_document(
                    GROUP_CHAT_ID,
                    document=f,
                    caption=f"📎 Мастер-файл на {date.today().strftime('%d.%m.%Y')}",
                )
    except Exception as e:
        logger.error(f"Error sending weekly master: {e}")

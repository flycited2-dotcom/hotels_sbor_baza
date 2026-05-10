import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_CREDENTIALS_JSON, GOOGLE_SHEET_ID, EXCEL_HEADERS
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_COL_STATUS = 14          # колонка "Статус" (1-based)
_COL_STATUS_UPDATED = 17  # колонка "Дата изменения статуса" (1-based)

_client = None
_sheet = None
_spreadsheet = None


# ───────────────────────── форматирование ─────────────────────────

def _format_sheet_full(spreadsheet, worksheet, num_data_rows: int):
    """Полное форматирование: шапка, чередование строк, границы, автовысота, автоширина."""
    sheet_id = worksheet.id
    num_cols = len(EXCEL_HEADERS)
    total_rows = num_data_rows + 1  # +1 шапка

    requests = []

    # 1. Шапка — тёмно-синий фон, белый жирный текст, центр, перенос
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0, "endRowIndex": 1,
                "startColumnIndex": 0, "endColumnIndex": num_cols,
            },
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.122, "green": 0.306, "blue": 0.471},
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                    "fontSize": 10,
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
            }},
            "fields": "userEnteredFormat",
        }
    })

    # 2. Высота шапки
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 48},
            "fields": "pixelSize",
        }
    })

    # 3. Заморозить первую строку
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # 4. Чередование цветов строк данных + выравнивание + перенос
    BLUE_LIGHT = {"red": 0.922, "green": 0.953, "blue": 0.984}
    WHITE      = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
    if num_data_rows > 0:
        for i in range(num_data_rows):
            row_idx = i + 1
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                        "startColumnIndex": 0, "endColumnIndex": num_cols,
                    },
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": BLUE_LIGHT if i % 2 == 0 else WHITE,
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "OVERFLOW_CELL",
                        "textFormat": {"fontSize": 9},
                    }},
                    "fields": "userEnteredFormat",
                }
            })

    # 5. Границы всей таблицы
    if total_rows > 0:
        border = {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}}
        requests.append({
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0, "endRowIndex": total_rows,
                    "startColumnIndex": 0, "endColumnIndex": num_cols,
                },
                "top": border, "bottom": border,
                "left": border, "right": border,
                "innerHorizontal": border, "innerVertical": border,
            }
        })

    # 6. Автоширина колонок
    requests.append({
        "autoResizeDimensions": {
            "dimensions": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": 0, "endIndex": num_cols,
            }
        }
    })

    # 7. Автовысота строк данных
    if num_data_rows > 0:
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 1, "endIndex": total_rows,
                }
            }
        })

    spreadsheet.batch_update({"requests": requests})
    logger.info("Google Sheets formatting applied")


def _format_new_row(spreadsheet, worksheet, row_index: int, is_even: bool):
    """Форматирует одну только что добавленную строку данных."""
    sheet_id = worksheet.id
    num_cols = len(EXCEL_HEADERS)
    color = {"red": 0.922, "green": 0.953, "blue": 0.984} if is_even else {"red": 1.0, "green": 1.0, "blue": 1.0}
    border = {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}}
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index - 1, "endRowIndex": row_index,
                    "startColumnIndex": 0, "endColumnIndex": num_cols,
                },
                "cell": {"userEnteredFormat": {
                    "backgroundColor": color,
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "OVERFLOW_CELL",
                    "textFormat": {"fontSize": 9},
                }},
                "fields": "userEnteredFormat",
            }
        },
        {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index - 1, "endRowIndex": row_index,
                    "startColumnIndex": 0, "endColumnIndex": num_cols,
                },
                "top": border, "bottom": border,
                "left": border, "right": border,
                "innerVertical": border,
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0, "endIndex": num_cols,
                }
            }
        },
    ]
    spreadsheet.batch_update({"requests": requests})


# ───────────────────────── подключение ─────────────────────────

def _get_sheet():
    global _client, _sheet, _spreadsheet
    if _sheet is not None:
        return _sheet
    try:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_JSON, scopes=SCOPES)
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(GOOGLE_SHEET_ID)
        try:
            _sheet = _spreadsheet.worksheet("Лиды")
        except gspread.WorksheetNotFound:
            _sheet = _spreadsheet.add_worksheet(title="Лиды", rows=10000, cols=len(EXCEL_HEADERS))
            _sheet.append_row(EXCEL_HEADERS)
            _format_sheet_full(_spreadsheet, _sheet, 0)
        return _sheet
    except Exception as e:
        logger.error(f"Google Sheets init error: {e}")
        return None


def _lead_to_row(lead: dict) -> list:
    return [
        lead.get("id", ""),
        lead.get("created_at", ""),
        lead.get("name", ""),
        lead.get("object_type", ""),
        lead.get("city", ""),
        lead.get("region", ""),
        lead.get("address", ""),
        lead.get("phone", ""),
        lead.get("email", ""),
        lead.get("telegram", ""),
        lead.get("website", ""),
        lead.get("size", ""),
        lead.get("interests", ""),
        lead.get("status", ""),
        lead.get("comment", ""),
        lead.get("added_by", ""),
        lead.get("status_updated_at", ""),
    ]


def _find_row_by_id(sheet, lead_id: int):
    col_a = sheet.col_values(1)
    target = str(lead_id)
    for i, val in enumerate(col_a):
        if val == target:
            return i + 1
    return None


# ───────────────────────── публичные функции ─────────────────────────

async def append_lead_to_sheet(lead: dict):
    try:
        sheet = _get_sheet()
        if sheet is None:
            return
        sheet.append_row(_lead_to_row(lead))
        # Количество строк после добавления
        num_rows = len(sheet.col_values(1))  # включая шапку
        is_even = (num_rows - 1) % 2 == 1   # нечётные строки данных = чётный индекс
        _format_new_row(_spreadsheet, sheet, num_rows, is_even)
        logger.info(f"Lead #{lead.get('id')} appended to Google Sheets")
    except Exception as e:
        logger.error(f"Google Sheets append error: {e}")


async def update_lead_status_in_sheet(lead_id: int, new_status: str, updated_at: str):
    try:
        sheet = _get_sheet()
        if sheet is None:
            return
        row_idx = _find_row_by_id(sheet, lead_id)
        if row_idx is None:
            logger.warning(f"Lead #{lead_id} not found in Google Sheets")
            return
        sheet.update_cell(row_idx, _COL_STATUS, new_status)
        sheet.update_cell(row_idx, _COL_STATUS_UPDATED, updated_at)
        logger.info(f"Lead #{lead_id} status updated in Sheets -> {new_status}")
    except Exception as e:
        logger.error(f"Google Sheets status update error: {e}")


async def sync_all_to_sheet(leads: list) -> bool:
    try:
        sheet = _get_sheet()
        if sheet is None:
            return False
        all_rows = sheet.get_all_values()
        if len(all_rows) > 1:
            sheet.delete_rows(2, len(all_rows))
        if leads:
            rows = [_lead_to_row(lead) for lead in leads]
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
        _format_sheet_full(_spreadsheet, sheet, len(leads))
        logger.info(f"Google Sheets synced: {len(leads)} leads")
        return True
    except Exception as e:
        logger.error(f"Google Sheets sync error: {e}")
        return False

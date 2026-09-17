import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def sync_case_to_sheet(case):
    """Escribe los campos de gestión Back Office de vuelta al Google Sheet.

    Returns True si se sincronizó correctamente, False si falló.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from flask import current_app

        creds_json = current_app.config.get("GOOGLE_CREDENTIALS_JSON", "")
        sheet_id = current_app.config.get("GOOGLE_SHEETS_ID", "")

        if not creds_json or not sheet_id:
            logger.warning("Credenciales de Google no configuradas. Saltando sincronización.")
            return False

        # Autenticar con service account
        creds_data = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
        gc = gspread.authorize(credentials)

        # Abrir el spreadsheet
        spreadsheet = gc.open_by_key(sheet_id)

        # Buscar la hoja (usando el nombre base del tab en Google Sheets)
        sheet_config = case.sheet_config
        tab_name = sheet_config.sheet_name.split(" - ")[0]
        worksheet = spreadsheet.worksheet(tab_name)

        # Obtener columnas de salida
        output_columns = json.loads(sheet_config.output_columns) if sheet_config.output_columns else []
        output_data = json.loads(case.output_data) if case.output_data else {}

        if not case.row_number or not output_columns:
            logger.warning(f"Case {case.id}: sin row_number o output_columns. Saltando sync.")
            return False

        # Escribir cada campo de salida en su celda correspondiente
        for col in output_columns:
            col_letter = col.get("column", "")  # Ej: "K", "L", "M"
            col_key = col.get("key", col.get("name", ""))
            value = output_data.get(col_key, "")

            if col_letter and value:
                cell = f"{col_letter}{case.row_number}"
                worksheet.update_acell(cell, value)

        # Marcar como sincronizado
        from models import db
        case.synced_to_sheet = True
        case.synced_at = datetime.now(timezone.utc)
        db.session.commit()

        logger.info(f"Case {case.id} sincronizado con Sheet fila {case.row_number}")
        return True

    except Exception as e:
        logger.error(f"Error sincronizando caso {case.id} al Sheet: {e}")
        return False


def read_all_cases_from_sheet(sheet_name):
    """Lee todas las filas de una hoja del Sheet.

    Devuelve lista de dicts con los datos.
    Útil para la carga inicial o re-sincronización.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from flask import current_app
        from models import SheetConfig

        creds_json = current_app.config.get("GOOGLE_CREDENTIALS_JSON", "")
        sheet_id = current_app.config.get("GOOGLE_SHEETS_ID", "")

        if not creds_json or not sheet_id:
            return []

        creds_data = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
        gc = gspread.authorize(credentials)

        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        # Obtener config de la hoja
        sheet_config = SheetConfig.query.filter_by(sheet_name=sheet_name).first()
        if not sheet_config:
            return []

        header_row = sheet_config.header_row
        input_columns = json.loads(sheet_config.input_columns) if sheet_config.input_columns else []

        # Leer todos los valores
        all_values = worksheet.get_all_values()

        if len(all_values) <= header_row:
            return []

        # Los headers están en header_row (1-indexed, pero list es 0-indexed)
        headers = all_values[header_row - 1]
        data_rows = all_values[header_row:]

        results = []
        for i, row in enumerate(data_rows):
            row_num = header_row + 1 + i  # Número de fila real en el sheet

            # Saltar filas vacías
            if not any(cell.strip() for cell in row):
                continue

            row_data = {}
            for col in input_columns:
                col_index = col.get("index", 0)  # Índice 0-based de la columna
                col_key = col.get("key", col.get("name", ""))
                if col_index < len(row):
                    row_data[col_key] = row[col_index]
                else:
                    row_data[col_key] = ""

            results.append({
                "row_number": row_num,
                "row_data": row_data,
            })

        return results

    except Exception as e:
        logger.error(f"Error leyendo hoja '{sheet_name}': {e}")
        return []

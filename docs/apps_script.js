/**
 * CRM BGH — Google Apps Script
 * 
 * Este script detecta cuando se agrega una nueva fila en las hojas activas
 * del spreadsheet y envía los datos al CRM en Railway via webhook.
 * 
 * INSTALACIÓN:
 * 1. Abrí tu Google Sheet
 * 2. Extensiones → Apps Script
 * 3. Pegá este código
 * 4. Cambiá CRM_URL por tu URL de Railway
 * 5. Cambiá WEBHOOK_SECRET por tu token secreto
 * 6. Guardá y luego: Activadores → Agregar activador
 *    - Función: onEditTrigger
 *    - Evento: Al editar
 */

// ══════════════════════════════════════════════════
// CONFIGURACIÓN — Cambiá estos valores
// ══════════════════════════════════════════════════
const CRM_URL = "https://TU-APP.up.railway.app";  // URL de tu CRM en Railway
const WEBHOOK_SECRET = "mi-webhook-secreto";       // Mismo token que en .env

// Hojas activas que envían datos al CRM
const HOJAS_ACTIVAS = [
  "SOLICITUDES BGH 2026",
  "Cancelaciones 2026",
  "CAMBIO DE DIRECCION 2026",
  "SEGUIMIENTO ENTREGAS 2026",
  "SOLICITUDES CON RECLAMO ABIERTO",
  "REEMBOLSOS",
  "CASOS SALESFORCE - FRONT BGH",
  "No tocar Retiros arrepentimient",
];

// Fila donde empiezan los headers por cada hoja
const HEADER_ROWS = {
  "SOLICITUDES BGH 2026": 1,
  "Cancelaciones 2026": 3,
  "CAMBIO DE DIRECCION 2026": 2,
  "SEGUIMIENTO ENTREGAS 2026": 3,
  "SOLICITUDES CON RECLAMO ABIERTO": 1,
  "REEMBOLSOS": 1,
  "CASOS SALESFORCE - FRONT BGH": 1,
  "No tocar Retiros arrepentimient": 1,
};


// ══════════════════════════════════════════════════
// TRIGGER PRINCIPAL
// ══════════════════════════════════════════════════

function onEditTrigger(e) {
  try {
    if (!e || !e.range) return;

    var sheet = e.range.getSheet();
    var sheetName = sheet.getName();

    // Solo procesar hojas activas
    if (HOJAS_ACTIVAS.indexOf(sheetName) === -1) return;

    var editedRow = e.range.getRow();
    var headerRow = HEADER_ROWS[sheetName] || 1;

    // Ignorar ediciones en los headers o filas superiores
    if (editedRow <= headerRow) return;

    // Obtener headers
    var lastCol = sheet.getLastColumn();
    var headers = sheet.getRange(headerRow, 1, 1, lastCol).getValues()[0];

    // Obtener datos de la fila editada
    var rowData = sheet.getRange(editedRow, 1, 1, lastCol).getValues()[0];

    // Verificar que la fila no está completamente vacía
    var hasData = rowData.some(function(cell) {
      return cell !== "" && cell !== null && cell !== undefined;
    });
    if (!hasData) return;

    // Armar el objeto con los datos
    var rowObj = {};
    for (var i = 0; i < headers.length; i++) {
      var headerName = headers[i];
      if (headerName && headerName.toString().trim() !== "") {
        // Crear una key limpia para el JSON
        var key = headerName.toString().trim()
          .toLowerCase()
          .replace(/[^a-z0-9áéíóúñü]/g, "_")
          .replace(/_+/g, "_")
          .replace(/^_|_$/g, "");
        
        var value = rowData[i];
        // Convertir fechas a string
        if (value instanceof Date) {
          value = Utilities.formatDate(value, Session.getScriptTimeZone(), "dd/MM/yyyy");
        }
        rowObj[key] = value !== null && value !== undefined ? value.toString() : "";
      }
    }

    // Enviar al CRM
    var payload = {
      "sheet_name": sheetName,
      "row_number": editedRow,
      "row_data": rowObj,
    };

    var options = {
      "method": "post",
      "contentType": "application/json",
      "headers": {
        "X-Webhook-Secret": WEBHOOK_SECRET,
      },
      "payload": JSON.stringify(payload),
      "muteHttpExceptions": true,
    };

    var response = UrlFetchApp.fetch(CRM_URL + "/webhook/nuevo-caso", options);
    var responseCode = response.getResponseCode();

    if (responseCode === 201) {
      Logger.log("✅ Caso enviado desde " + sheetName + " fila " + editedRow);
    } else {
      Logger.log("❌ Error " + responseCode + ": " + response.getContentText());
    }

  } catch (error) {
    Logger.log("❌ Error en onEditTrigger: " + error.toString());
  }
}


// ══════════════════════════════════════════════════
// SYNC MASIVA (para carga inicial)
// Ejecutar manualmente desde Apps Script
// ══════════════════════════════════════════════════

function syncHojaCompleta(nombreHoja) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(nombreHoja);

  if (!sheet) {
    Logger.log("❌ Hoja '" + nombreHoja + "' no encontrada");
    return;
  }

  var headerRow = HEADER_ROWS[nombreHoja] || 1;
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();

  if (lastRow <= headerRow) {
    Logger.log("ℹ️ Hoja vacía");
    return;
  }

  var headers = sheet.getRange(headerRow, 1, 1, lastCol).getValues()[0];
  var dataRange = sheet.getRange(headerRow + 1, 1, lastRow - headerRow, lastCol);
  var allData = dataRange.getValues();

  var rows = [];
  for (var r = 0; r < allData.length; r++) {
    var rowData = allData[r];

    // Saltar filas vacías
    var hasData = rowData.some(function(cell) {
      return cell !== "" && cell !== null && cell !== undefined;
    });
    if (!hasData) continue;

    var rowObj = {};
    for (var i = 0; i < headers.length; i++) {
      var headerName = headers[i];
      if (headerName && headerName.toString().trim() !== "") {
        var key = headerName.toString().trim()
          .toLowerCase()
          .replace(/[^a-z0-9áéíóúñü]/g, "_")
          .replace(/_+/g, "_")
          .replace(/^_|_$/g, "");

        var value = rowData[i];
        if (value instanceof Date) {
          value = Utilities.formatDate(value, Session.getScriptTimeZone(), "dd/MM/yyyy");
        }
        rowObj[key] = value !== null && value !== undefined ? value.toString() : "";
      }
    }

    rows.push({
      "row_number": headerRow + 1 + r,
      "row_data": rowObj,
    });
  }

  // Enviar en lotes de 50
  var batchSize = 50;
  for (var b = 0; b < rows.length; b += batchSize) {
    var batch = rows.slice(b, b + batchSize);

    var payload = {
      "sheet_name": nombreHoja,
      "rows": batch,
    };

    var options = {
      "method": "post",
      "contentType": "application/json",
      "headers": {
        "X-Webhook-Secret": WEBHOOK_SECRET,
      },
      "payload": JSON.stringify(payload),
      "muteHttpExceptions": true,
    };

    var response = UrlFetchApp.fetch(CRM_URL + "/webhook/sync-sheet", options);
    Logger.log("Lote " + (b / batchSize + 1) + ": " + response.getResponseCode() + " - " + response.getContentText());

    // Esperar un poco entre lotes para no saturar
    Utilities.sleep(1000);
  }

  Logger.log("✅ Sincronización de '" + nombreHoja + "' completada: " + rows.length + " filas");
}


// Funciones de conveniencia para sync de cada hoja
function syncSolicitudesBGH() { syncHojaCompleta("SOLICITUDES BGH 2026"); }
function syncCancelaciones() { syncHojaCompleta("Cancelaciones 2026"); }
function syncCambioDireccion() { syncHojaCompleta("CAMBIO DE DIRECCION 2026"); }
function syncSeguimientoEntregas() { syncHojaCompleta("SEGUIMIENTO ENTREGAS 2026"); }
function syncReclamos() { syncHojaCompleta("SOLICITUDES CON RECLAMO ABIERTO"); }
function syncReembolsos() { syncHojaCompleta("REEMBOLSOS"); }
function syncCasosSalesforce() { syncHojaCompleta("CASOS SALESFORCE - FRONT BGH"); }
function syncRetiros() { syncHojaCompleta("No tocar Retiros arrepentimient"); }

// Sync de TODAS las hojas
function syncTodasLasHojas() {
  HOJAS_ACTIVAS.forEach(function(hoja) {
    syncHojaCompleta(hoja);
  });
}

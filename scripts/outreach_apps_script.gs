// ===== Технолайн Трейд: рассылка из Google-таблицы (v3, с фиксом таймаута) =====
const SHEET_NAME = 'Рассылка';
const DAILY_CAP = 15;               // писем за один запуск (на прогреве)
const PAUSE_MS = 4000;              // пауза между отправками, мс
const TIME_BUDGET_MS = 4 * 60 * 1000; // стоп до лимита Apps Script (6 мин)

function _sheet(){ const ss=SpreadsheetApp.getActive(); return ss.getSheetByName(SHEET_NAME)||ss.getSheets()[0]; }
function _cols(h){ const c={}; ['Email','Статус','Дата_отправки','Этап'].forEach(n=>c[n]=h.indexOf(n)); return c; }
function _email(s){ const m=String(s||'').toLowerCase().match(/[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/); return m?m[0]:''; }
function _parseDate(v){ if(v instanceof Date)return v; const s=String(v).trim(); let m=s.match(/^(\d{4})-(\d{2})-(\d{2})/); if(m)return new Date(+m[1],+m[2]-1,+m[3]); m=s.match(/^(\d{2})\.(\d{2})\.(\d{4})/); if(m)return new Date(+m[3],+m[2]-1,+m[1]); const d=new Date(s); return isNaN(d)?null:d; }
function _alert(t){ try{SpreadsheetApp.getUi().alert(t);}catch(e){} }

function onOpen(){
  SpreadsheetApp.getUi().createMenu('📧 Рассылка')
    .addItem('Отправить черновики (до '+DAILY_CAP+')','sendCampaignDrafts')
    .addItem('Отметить ответивших','markReplied')
    .addItem('Пометить для фоллоу-апа (5+ дней)','flagFollowups')
    .addItem('Обновить дашборд','buildDashboard')
    .addSeparator()
    .addItem('Включить авто-отправку (ежедневно)','enableAutoSend')
    .addItem('Выключить авто-отправку','disableAutoSend')
    .addToUi();
}

function sendCampaignDrafts(){
  const deadline=Date.now()+TIME_BUDGET_MS;
  const sh=_sheet(), data=sh.getDataRange().getValues(), c=_cols(data[0]); const map={};
  for(let i=1;i<data.length;i++){ const em=_email(data[i][c.Email]), st=String(data[i][c['Статус']]).trim().toLowerCase(); if(em&&(st==='новый'||st==='черновик'))map[em]=i; }
  const today=Utilities.formatDate(new Date(),Session.getScriptTimeZone(),'yyyy-MM-dd'); let sent=0;
  for(const d of GmailApp.getDrafts()){
    if(sent>=DAILY_CAP || Date.now()>deadline) break;        // стоп по лимиту/времени
    const to=_email(d.getMessage().getTo()); if(!to||!(to in map))continue;
    d.send(); const r=map[to];
    sh.getRange(r+1,c['Статус']+1).setValue('отправлено');
    sh.getRange(r+1,c['Дата_отправки']+1).setValue(today);
    sent++; Utilities.sleep(PAUSE_MS);
  }
  buildDashboard(); _alert('Отправлено: '+sent);
}

function markReplied(){
  const deadline=Date.now()+TIME_BUDGET_MS;
  const sh=_sheet(), data=sh.getDataRange().getValues(), c=_cols(data[0]); let n=0;
  for(let i=1;i<data.length && n<50 && Date.now()<deadline;i++){   // стоп по времени
    const em=_email(data[i][c.Email]), st=String(data[i][c['Статус']]).trim().toLowerCase(), sg=String(data[i][c['Этап']]).trim().toLowerCase();
    if(em&&st==='отправлено'&&sg!=='ответил'&&GmailApp.search('from:'+em+' newer_than:30d').length){ sh.getRange(i+1,c['Этап']+1).setValue('ответил'); n++; }
  }
  buildDashboard(); _alert('Помечено «ответил»: '+n);
}

function flagFollowups(){
  const sh=_sheet(), data=sh.getDataRange().getValues(), c=_cols(data[0]); const now=new Date(); let n=0;
  for(let i=1;i<data.length;i++){ const st=String(data[i][c['Статус']]).trim().toLowerCase(), sg=String(data[i][c['Этап']]).trim().toLowerCase();
    if(st==='отправлено'&&!sg){ const d=_parseDate(data[i][c['Дата_отправки']]); if(d&&(now-d)/86400000>=5){ sh.getRange(i+1,c['Этап']+1).setValue('нужен фоллоу-ап'); n++; } } }
  _alert('Помечено для фоллоу-апа: '+n);
}

function buildDashboard(){
  const ss=SpreadsheetApp.getActive(), sh=_sheet(), data=sh.getDataRange().getValues(), c=_cols(data[0]); const cnt={}; let total=0;
  for(let i=1;i<data.length;i++){ const st=String(data[i][c['Статус']]).trim().toLowerCase()||'(пусто)'; cnt[st]=(cnt[st]||0)+1; total++; }
  let db=ss.getSheetByName('Дашборд')||ss.insertSheet('Дашборд'); db.clear();
  const rows=[['Статус','Кол-во']]; Object.keys(cnt).sort().forEach(k=>rows.push([k,cnt[k]])); rows.push(['ВСЕГО',total]);
  db.getRange(1,1,rows.length,2).setValues(rows);
}

function enableAutoSend(){ disableAutoSend(); ScriptApp.newTrigger('sendCampaignDrafts').timeBased().everyDays(1).atHour(10).create(); _alert('Авто-отправка включена: каждый день ~10:00, до '+DAILY_CAP+' писем.'); }
function disableAutoSend(){ ScriptApp.getProjectTriggers().forEach(t=>{ if(t.getHandlerFunction()==='sendCampaignDrafts')ScriptApp.deleteTrigger(t); }); _alert('Авто-отправка выключена.'); }

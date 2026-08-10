// ===== EXTRACTOR PREMIUMPAY · DEFINITIVO =====
// Pegar en la consola de Chrome (F12 -> Console) en campanias gestionadas
(async()=>{
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const post=async(url,body)=>{
  const r=await fetch(url,{method:'POST',credentials:'same-origin',
    headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'},
    body:new URLSearchParams(body)});
  if(!r.ok)throw new Error(url+' -> HTTP '+r.status);
  return r.json();
};
const filas=j=>j.aaData||j.data||[];

// --- cuerpo exacto que envia la pagina (capturado del propio DataTables) ---
const COLS=['telegram_userid','fecha_entrada','fecha_salida','pagos_num','pagos_importe'];
function cuerpoEntradas(idenlace,start,length){
  const b={draw:1};
  COLS.forEach((c,i)=>{
    b[`columns[${i}][data]`]=c; b[`columns[${i}][name]`]='';
    b[`columns[${i}][searchable]`]='true'; b[`columns[${i}][orderable]`]='true';
    b[`columns[${i}][search][value]`]=''; b[`columns[${i}][search][regex]`]='false';
  });
  b['order[0][column]']='1'; b['order[0][dir]']='asc';
  b.start=start; b.length=length;
  b['search[value]']=''; b['search[regex]']='false';
  b.idenlace=idenlace; b.fechaInicio=''; b.fechaFin='';
  return b;
}

const sel=prompt('IDs de canal, separados por coma','698,766'); if(!sel)return;
const ids=sel.split(',').map(x=>x.trim()).filter(Boolean);
const D=prompt('Desde (AAAA-MM-DD)','2026-08-01'); if(!D)return;
const H=prompt('Hasta (AAAA-MM-DD)',new Date().toISOString().slice(0,10)); if(!H)return;
const FI=D+'T00:00',FF=H+'T23:59';

// ---------- 1. enlaces ----------
const OUT={rango:{desde:D,hasta:H},generado:new Date().toISOString(),canales:[],suscriptores:[]};
for(const idc of ids){
  const le=await post('/tipster_ajax_pb_get_enlacescanal_paginated',
    {idcanal:idc,fechaInicio:FI,fechaFin:FF,consolidate:'false',draw:1,start:0,length:1000,
     'search[value]':'','search[regex]':'false'});
  const enl=filas(le);
  const nom=((enl[0]&&enl[0].telegram_namecanal)||('Canal '+idc)).replace(/[\s.|]+$/,'').trim();
  OUT.canales.push({tipster:nom,idcanal:+idc,enlaces:enl});
  console.log(`Canal ${idc} (${nom}): ${enl.length} enlaces`);
  await sleep(200);
}
const L=[];
OUT.canales.forEach(c=>c.enlaces.forEach(e=>{
  if(e.idtelegram_publi_enlace)L.push({id:e.idtelegram_publi_enlace,nombre:e.nombre,
    canal:c.idcanal,tipster:c.tipster,esperadas:+(e.entradas_total||0)});
}));
const CON=L.filter(x=>x.esperadas>0);
const ESP=CON.reduce((a,x)=>a+x.esperadas,0);
console.log(`${L.length} enlaces · ${CON.length} con entradas en el periodo · ${ESP} entradas esperadas`);
if(!CON.length){console.warn('Nada que extraer.');return}

// ---------- 2. extraer (la ventana no filtra por fecha: filtramos aqui) ----------
console.log('%cExtrayendo... (la API devuelve el historico completo de cada enlace y se filtra por fecha aqui)','font-weight:bold;color:#1e3a6e');
const dentro=f=>{const s=String(f||'').slice(0,10);return s>=D&&s<=H};
let bruto=0;
for(let i=0;i<CON.length;i++){
  const x=CON[i]; let start=0, n=0;
  while(true){
    const j=await post('/tipster_ajax_listado_entradas',cuerpoEntradas(x.id,start,1000));
    const rows=filas(j);
    if(start===0&&i===0&&!rows.length){
      console.error('Sigue devolviendo vacio. Copia esto y mandaselo a Claude:');
      console.log(JSON.stringify(j).slice(0,1200)); return;
    }
    rows.forEach(r=>{
      bruto++;
      if(dentro(r.fecha_entrada))
        OUT.suscriptores.push({...r,idcanal:x.canal,tipster:x.tipster,idenlace:x.id,nombre_enlace:x.nombre});
    });
    n+=rows.length;
    const tot=+(j.iTotalRecords||j.iTotalDisplayRecords||0);
    if(rows.length<1000||(tot&&n>=tot))break;
    start+=1000; await sleep(250);
  }
  if((i+1)%5===0||i===CON.length-1)
    console.log(`  ${i+1}/${CON.length} · ${OUT.suscriptores.length} en rango (${bruto} revisadas)`);
  await sleep(250);
}

// ---------- 3. cuadre ----------
const got=OUT.suscriptores.length;
const pagos=OUT.suscriptores.reduce((a,r)=>a+(+r.pagos_num||0),0);
console.log('%c=== LISTO ===','font-size:14px;font-weight:bold;color:#188a55');
console.log(`Suscriptores en rango: ${got} | Esperados segun la API: ${ESP} | Filas revisadas: ${bruto}`);
console.log(`Pagos: ${pagos}`);
if(got===ESP)console.log('%cCuadre OK','color:#188a55;font-weight:bold;font-size:13px');
else console.log(`%cAVISO: diferencia de ${Math.abs(ESP-got)} entradas. Revisar antes de usar los datos.`,'color:#c8353a;font-weight:bold');
const a=document.createElement('a');
a.href=URL.createObjectURL(new Blob([JSON.stringify(OUT)],{type:'application/json'}));
a.download='premiumpay_'+D+'_'+H+'.json';
document.body.appendChild(a);a.click();a.remove();
console.log('Archivo descargado.');
})();

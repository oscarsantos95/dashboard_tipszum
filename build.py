import pandas as pd, json, re, numpy as np
from datetime import datetime

# ============================================================
#  build.py  ·  Meta Ads (USD) x PremiumPay (EUR) -> data.json
#  Uso:  python3 build.py [--fx 0.8673]
#  Pon los archivos en la carpeta ./entrada :
#     - cualquier .xlsx  = export de Meta Ads
#     - cualquier .json  = extraccion de PremiumPay (del bookmarklet)
#  Salida: data.json en esta misma carpeta
# ============================================================
import sys, glob, os
from datetime import date

FX=0.8673                    # USD -> EUR (Wise). Editable tambien en el dashboard.
FX_FECHA=date.today().strftime('%d/%m/%Y')
if '--fx' in sys.argv: FX=float(sys.argv[sys.argv.index('--fx')+1])

ENT='entrada'
xl=sorted(glob.glob(os.path.join(ENT,'*.xlsx')))+sorted(glob.glob(os.path.join(ENT,'*.xls')))
js=sorted(glob.glob(os.path.join(ENT,'*.json')))
if not xl or not js:
    sys.exit(f'Faltan archivos en ./{ENT}/  (encontrados: {len(xl)} Excel, {len(js)} JSON)')
print(f'Meta: {len(xl)} archivo(s) | PremiumPay: {len(js)} archivo(s) | FX {FX}')

df=pd.concat([pd.read_excel(f) for f in xl],ignore_index=True)
subs=[]; canales=[]
for f in js:
    d=json.load(open(f,encoding='utf-8'))
    subs+=d.get('suscriptores',[]); canales+=d.get('canales',[])
s=pd.DataFrame(subs)
d={'canales':canales,'suscriptores':subs}

# ---------- clave canonica ----------
RUIDO={'PRO','INTERESES','PROINTERESES'}
MES=re.compile(r'^(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\d{4}$')
def clave(n):
    t=[x.strip().upper() for x in str(n).split('_') if x.strip()]
    t=[x for x in t if x not in RUIDO and not MES.match(x)]
    return '_'.join(t)
def campos(n):
    t=[x.strip().upper() for x in str(n).split('_') if x.strip()]
    t=[x for x in t if x not in RUIDO and not MES.match(x)]
    return dict(tipster=t[0] if t else '?', pais=t[1] if len(t)>1 else '?',
                segmento='_'.join(t[2:-1]) if len(t)>3 else (t[2] if len(t)>2 else '?'))

# ---------- Meta ----------
NUM=['Results','Reach','Amount spent (USD)','Impressions','Link clicks','Clicks (all)','Landing page views']
for c in NUM: df[c]=pd.to_numeric(df[c],errors='coerce').fillna(0)
df['dia']=pd.to_datetime(df['Day']).dt.strftime('%Y-%m-%d')
df['pref']=df['Ad set name'].str.split('_').str[0]
df['clave']=df['Ad set name'].apply(clave)
df['pais']=df['Ad set name'].apply(lambda x: campos(x)['pais'])
PLAC={'Feed':'Feed','Instagram Reels':'IG Reels','Facebook Reels':'FB Reels','Instagram Stories':'IG Stories',
      'Facebook Stories':'FB Stories','Facebook profile feed':'FB perfil','Marketplace':'Marketplace',
      'Instagram search results':'IG búsqueda','Search results':'Búsqueda','In-stream reels':'In-stream',
      'Rewarded video':'Vídeo recompensado','Native, banner & interstitial':'Audience Network','Unknown':'Desconocido'}
df['placement']=df['Placement'].map(PLAC).fillna(df['Placement']).fillna('Desconocido')

# ---------- PremiumPay ----------
s['imp']=s.pagos_importe.apply(lambda x: float(str(x).replace('.','').replace(',','.')) if str(x).strip() else 0.0)
s['pag']=pd.to_numeric(s.pagos_num,errors='coerce').fillna(0).astype(int)
s['fe']=pd.to_datetime(s.fecha_entrada); s['fs']=pd.to_datetime(s.fecha_salida)
s['dia']=s.fe.dt.strftime('%Y-%m-%d')
s['perm']=(s.fs-s.fe).dt.total_seconds()/86400
s['clave']=s.nombre_enlace.apply(clave)
# --- descubrir tipsters automaticamente: prefijo del nombre de enlace ---
def pref_de(sub):
    """El prefijo del tipster es el primer campo del nombre de enlace mas frecuente."""
    c={}
    for n in sub.nombre_enlace:
        p=str(n).split('_')[0].strip().upper()
        if len(p)>2 and not p.startswith(('GEN','FB','ESPA','MEX','MÉX')): c[p]=c.get(p,0)+1
    return max(c,key=c.get) if c else '?'
NOMBRE={}
pf_map={}
for canal,sub in s.groupby('tipster'):
    p=pref_de(sub); pf_map[canal]=p
    limpio=str(canal).replace('Publicidad Tipszum - ','').replace('-tipszum','').strip()
    NOMBRE[p]=limpio
s['pref']=s.tipster.map(pf_map)
s['tname']=s.pref.map(NOMBRE)
print('Tipsters detectados:',NOMBRE)

# ---------- emparejar POR TIPSTER ----------
PREFS=list(NOMBRE.keys())
metaT=df[df.pref.isin(PREFS)].copy()
pares={}; avisos=[]
for p in PREFS:
    mk=set(metaT[metaT.pref==p].clave); pk=set(s[s.pref==p].clave)
    for k in mk&pk: pares[(p,k)]='exacto'
    for k in mk-pk: avisos.append(dict(tipo='Conjunto de Meta sin enlace en PremiumPay',tipster=NOMBRE[p],
        valor=metaT[(metaT.pref==p)&(metaT.clave==k)]['Ad set name'].iloc[0],
        detalle=f"{metaT[(metaT.pref==p)&(metaT.clave==k)]['Amount spent (USD)'].sum()*FX:.2f} € invertidos sin entradas atribuibles"))
    for k in pk-mk:
        sub=s[(s.pref==p)&(s.clave==k)]
        avisos.append(dict(tipo='Enlace de PremiumPay sin conjunto en Meta',tipster=NOMBRE[p],
            valor=sub.nombre_enlace.iloc[0],detalle=f"{len(sub)} entradas, {sub.pag.sum()} pagos, sin inversión asociada"))
# colisiones de clave entre tipsters
allk={}
for p in PREFS:
    for k in set(metaT[metaT.pref==p].clave): allk.setdefault(k,[]).append(p)
COLIS=sum(1 for k,v in allk.items() if len(v)>1)

SIN='Genérico (sin conjunto)'
metaT['ok']=[ (r.pref,r.clave) in pares for r in metaT.itertuples()]
s['ok']=[ (r.pref,r.clave) in pares for r in s.itertuples()]
s['grupo']=np.where(s.ok,s.clave,SIN)
metaT['grupo']=np.where(metaT.ok,metaT.clave,metaT.clave)  # meta sin pareja mantiene su clave (gasto sin entradas)

# ---------- diario por tipster x grupo ----------
gas=metaT.groupby(['dia','pref','grupo','pais']).agg(
    gasto_usd=('Amount spent (USD)','sum'),impresiones=('Impressions','sum'),alcance=('Reach','sum'),
    clics=('Link clicks','sum'),clics_all=('Clicks (all)','sum'),lpv=('Landing page views','sum'),
    leads=('Results','sum')).reset_index()
ent=s.groupby(['dia','pref','grupo']).agg(entradas=('pag','size'),pagadores=('pag',lambda x:(x>0).sum()),
    pagos=('pag','sum'),ingresos=('imp','sum')).reset_index()
baj=s.dropna(subset=['fs']).assign(dd=lambda x:x.fs.dt.strftime('%Y-%m-%d')).groupby(['dd','pref','grupo']).size().rename('bajas').reset_index().rename(columns={'dd':'dia'})
D=gas.merge(ent,on=['dia','pref','grupo'],how='outer').merge(baj,on=['dia','pref','grupo'],how='outer')
for c in ['gasto_usd','impresiones','alcance','clics','clics_all','lpv','leads','entradas','pagadores','pagos','ingresos','bajas']:
    D[c]=pd.to_numeric(D[c],errors='coerce').fillna(0)
D['pais']=D.pais.fillna('—'); D['tipster']=D.pref.map(NOMBRE)
D=D.sort_values(['dia','pref','grupo'])

# placement (solo Meta)
PL=metaT.groupby(['dia','pref','placement']).agg(gasto_usd=('Amount spent (USD)','sum'),
    impresiones=('Impressions','sum'),clics=('Link clicks','sum'),lpv=('Landing page views','sum'),
    leads=('Results','sum')).reset_index()
PL['tipster']=PL.pref.map(NOMBRE)

# retención
ret=[]
for p in PREFS:
    ss=s[s.pref==p]; n=len(ss)
    for h in [0,0.25,0.5,1,2,3,5,7]:
        vivos=n-((ss.perm<h)&ss.perm.notna()).sum()
        ret.append(dict(tipster=NOMBRE[p],dias=h,pct=round(vivos/n*100,2) if n else 0))

# otros tipsters en el export sin datos de PremiumPay
otros=[]
for p,g in df[~df.pref.isin(PREFS)].groupby('pref'):
    otros.append(dict(tipster=p,gasto_eur=round(g['Amount spent (USD)'].sum()*FX,2),
        adsets=int(g['Ad set name'].nunique()),leads=int(g['Results'].sum())))

out=dict(fx=FX, fx_fecha=FX_FECHA, fx_fuente='Wise (mid-market)',
    daily=D.to_dict('records'), placement=PL.to_dict('records'), retencion=ret,
    avisos=avisos, otros=otros, colisiones=COLIS, sin_conjunto=SIN,
    nombres=NOMBRE, rango=[D.dia.min(),D.dia.max()],
    rango_meta=[metaT.dia.min(),metaT.dia.max()], rango_pp=[s.dia.min(),s.dia.max()],
    cuadre=dict(entradas=int(len(s)),pagos=int(s.pag.sum()),ingresos=float(s.imp.sum()),
                gasto_usd=float(metaT['Amount spent (USD)'].sum())))
json.dump(out,open('data.json','w'),ensure_ascii=False,default=str,separators=(',',':'))
print(f"data.json escrito ({os.path.getsize('data.json')/1024:.0f} KB)")
print('emparejados:',len(pares),'| avisos:',len(avisos),'| colisiones:',COLIS)
print('cuadre:',out['cuadre'])
print('gasto EUR:',round(out['cuadre']['gasto_usd']*FX,2))
print('filas D:',len(D),'| placement:',len(PL))
print('otros tipsters en export sin PP:',[o['tipster'] for o in otros])

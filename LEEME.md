# Pipeline · Meta Ads × PremiumPay

Estructura pensada para que **actualizar los datos no cueste nada**: el código está en
`index.html` y los datos en `data.json`. Para refrescar solo se regenera el JSON.

## Carpeta

```
pipeline/
├── index.html        el dashboard (no se toca nunca)
├── data.json         los datos (se regenera cada vez)
├── build.py          genera data.json
├── extractor_FINAL.js  extrae los datos de PremiumPay
└── entrada/          aquí se dejan los archivos descargados
```

## Puesta en marcha (una sola vez)

1. **Instalar las librerías de Python**
   ```
   pip install pandas openpyxl
   ```

## Rutina de actualización (2 min)

1. Entra en PremiumPay (campañas gestionadas), pulsa `F12` → pestaña `Console`,
   escribe `allow pasting` + Enter, pega el contenido de `extractor_FINAL.js`
   y pulsa Enter. Introduce los IDs de canal y las fechas.
   Descarga un `premiumpay_....json`.

   Los bookmarklets no funcionan aquí: la web bloquea la ejecución con CSP.
2. Descarga el export de Meta Ads (desglose por día y por ubicación).
3. Mueve los dos archivos a `entrada/`.
4. Ejecuta:
   ```
   python3 build.py
   ```
   O con un tipo de cambio concreto:
   ```
   python3 build.py --fx 0.8712
   ```
5. Sube **solo `data.json`** al hosting. El `index.html` ya está allí y no cambia.

## Ver el dashboard en local

El navegador bloquea la lectura de `data.json` al abrir el HTML con doble clic.
Levanta un servidor local en la carpeta:

```
python3 -m http.server 8000
```
y abre `http://localhost:8000`

## Añadir tipsters

No hay que tocar código. `build.py` detecta los tipsters solo, a partir del
prefijo del nombre de enlace. Basta con que el JSON de PremiumPay incluya sus
canales y que el export de Meta incluya sus conjuntos.

## Notas

- El tipo de cambio USD→EUR se aplica a la inversión de Meta. Los ingresos de
  PremiumPay ya vienen en euros y no se convierten.
- El emparejamiento Meta ↔ PremiumPay usa clave estructurada: separa el nombre
  por guiones bajos e ignora los tokens de relleno (`PRO`, `INTERESES`) y los de
  mes (`AGO2026`). Se hace siempre dentro del mismo tipster.
- Los agregados a nivel de enlace que devuelve PremiumPay son **de por vida**, no
  del periodo. El pipeline usa solo el detalle por suscriptor.

## Detalles técnicos del extractor

El endpoint `/tipster_ajax_listado_entradas` es un DataTables en modo servidor y
necesita el cuerpo completo, con las definiciones `columns[i][data]` de las cinco
columnas. Sin ellas responde con todo a `null`. El parámetro del enlace se llama
`idenlace` (no `idtelegram_publi_enlace`, aunque ése sea el nombre del campo en la
respuesta de enlaces).

Ese endpoint **no filtra por fecha**: devuelve el histórico completo del enlace y
el filtrado se hace en el propio script sobre `fecha_entrada`. Para canales con
cientos de enlaces esto será lento, y convendrá guardar extracciones previas y
bajar solo los enlaces recientes.

El cuadre se valida en cada ejecución contra `entradas_total`, que sí viene
filtrado por fecha en la respuesta de enlaces.

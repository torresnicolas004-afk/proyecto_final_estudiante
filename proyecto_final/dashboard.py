"""
Dashboard del Proyecto Final - Programacion Aplicada
=====================================================
Frontend (Streamlit) que consume la API de terremotos (api.py).
Todo lo que se ve aqui viene de la API; el dashboard NUNCA se conecta
directamente a MongoDB.

Pestanas:
    Resumen      indicadores generales y terremotos por anio
    Preguntas    las 4 preguntas del segundo corte con sus graficas
    Explorador   agrupar por cualquier categoria y resumir cualquier variable
    Datos        tabla de registros con orden, paginacion y busqueda por event_id
    Registrar    formulario que crea un terremoto (POST /datos)

Como ejecutar (en OTRA terminal, con el venv activo):
    python -m streamlit run dashboard.py

Por defecto usa la API publicada en Render. Para usar la API local:
    Windows (PowerShell):  $env:API_URL="http://localhost:8000"; python -m streamlit run dashboard.py
    Mac / Linux:           API_URL=http://localhost:8000 python -m streamlit run dashboard.py
"""

import os
from datetime import datetime, timezone

import altair as alt
import pandas as pd
import requests
import streamlit as st


# ============================================================
# 1. CONFIGURACION
# ============================================================
API = os.environ.get(
    "API_URL", "https://proyecto-final-estudiante-271721.onrender.com"
).rstrip("/")

ANIO_INICIO = 2020
ANIO_ACTUAL = datetime.now(timezone.utc).year

NOMBRES = {
    "magnitude_type": "Tipo de magnitud",
    "alert": "Nivel de alerta",
    "status": "Estado de revision",
    "network": "Red sismica",
    "tsunami": "Indicador de tsunami",
    "zona": "Zona (pais o region)",
    "anio": "Año",
    "mes": "Mes",
    "categoria_profundidad": "Rango de profundidad",
    "magnitude": "Magnitud",
    "depth_km": "Profundidad (km)",
    "significance": "Significancia",
    "felt": "Reportes de personas (felt)",
    "stations": "Estaciones",
    "distance": "Distancia a estacion (dmin)",
    "rms": "RMS",
    "gap": "Gap azimutal",
}
ORDEN_PROFUNDIDAD = ["superficial", "intermedio", "profundo"]

st.set_page_config(page_title="Terremotos USGS", page_icon="🌎", layout="wide")


# ============================================================
# 2. FUNCIONES DE APOYO
# ============================================================
class ErrorAPI(Exception):
    """Error devuelto por la API (con su codigo y mensaje)."""


@st.cache_data(ttl=300, show_spinner=False)
def consultar(ruta, params=None):
    """GET a la API. Se guarda en cache 5 minutos para no repetir consultas."""
    r = requests.get(f"{API}{ruta}", params=params, timeout=90)
    if not r.ok:
        try:
            detalle = r.json().get("detail", r.text)
        except ValueError:
            detalle = r.text
        raise ErrorAPI(f"{r.status_code}: {detalle}")
    return r.json()


def pedir(ruta, **params):
    """Llama a la API y muestra el error en pantalla si algo falla."""
    params = {k: v for k, v in params.items() if v is not None}
    try:
        return consultar(ruta, params)
    except ErrorAPI as e:
        st.error(f"La API respondio con error en {ruta} → {e}")
    except requests.RequestException as e:
        st.error(f"No se pudo consultar {ruta}: {e}")
    return None


def numero(valor, decimales=0):
    """Formato con separador de miles en espanol: 107650 -> 107.650"""
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fecha(ms):
    if ms is None:
        return "—"
    return pd.to_datetime(ms, unit="ms", utc=True).strftime("%Y-%m-%d %H:%M UTC")


def mostrar(funcion, *args, **kwargs):
    """Dibuja un elemento a lo ancho, compatible con versiones viejas y nuevas de Streamlit."""
    try:
        return funcion(*args, width="stretch", **kwargs)  # Streamlit reciente
    except Exception:
        return funcion(*args, use_container_width=True, **kwargs)  # Streamlit anterior


# ============================================================
# 3. CONEXION CON LA API
# ============================================================
st.title("🌎 Dashboard de Terremotos — USGS")
st.caption(
    "Terremotos de magnitud 4.0 o más registrados por el USGS desde 2020. "
    "MongoDB Atlas → API (FastAPI) → este dashboard (Streamlit)."
)


@st.cache_data(ttl=60, show_spinner=False)
def estado_api():
    r = requests.get(f"{API}/", timeout=90)
    r.raise_for_status()
    return r.json()


with st.spinner("Conectando con la API… (si Render estaba dormida puede tardar hasta 1 minuto)"):
    try:
        estado = estado_api()
    except requests.RequestException as e:
        st.error(
            f"No pude conectarme a la API en {API}. "
            "Verifica que FastAPI esté corriendo o que Render esté activo.\n\n"
            f"Detalle: {e}"
        )
        st.stop()

if estado.get("base_de_datos") != "conectada":
    st.error("La API está activa pero no puede conectarse a MongoDB Atlas (revisa MONGO_URI y Network Access).")
    st.stop()


# ============================================================
# 4. FILTROS (barra lateral) — se aplican a todas las pestanas
# ============================================================
st.sidebar.header("🔎 Filtros")

rango_mag = st.sidebar.slider("Magnitud", 0.0, 10.0, (0.0, 10.0), 0.1)
rango_anios = st.sidebar.slider("Años", ANIO_INICIO, ANIO_ACTUAL, (ANIO_INICIO, ANIO_ACTUAL))

opciones_tipo = pedir("/estadisticas", agrupar_por="magnitude_type", top=50)
lista_tipos = [g["magnitude_type"] for g in opciones_tipo["grupos"]] if opciones_tipo else []
tipo = st.sidebar.selectbox("Tipo de magnitud", ["(todos)"] + lista_tipos)

alerta = st.sidebar.selectbox(
    "Nivel de alerta", ["(todas)", "sin alerta", "green", "yellow", "orange", "red"]
)

opciones_red = pedir("/estadisticas", agrupar_por="network", top=50)
lista_redes = [g["network"] for g in opciones_red["grupos"]] if opciones_red else []
red = st.sidebar.selectbox("Red sísmica", ["(todas)"] + lista_redes)

tsunami = st.sidebar.radio("Indicador de tsunami", ["Todos", "Con tsunami", "Sin tsunami"], horizontal=True)

lugar = st.sidebar.text_input("El lugar contiene…", placeholder="Ej: Colombia, Japan, Chile")

# Solo se envian a la API los filtros que el usuario cambio
filtros = {
    "mag_min": rango_mag[0] if rango_mag[0] > 0.0 else None,
    "mag_max": rango_mag[1] if rango_mag[1] < 10.0 else None,
    "anio_desde": rango_anios[0] if rango_anios[0] > ANIO_INICIO else None,
    "anio_hasta": rango_anios[1] if rango_anios[1] < ANIO_ACTUAL else None,
    "magnitude_type": None if tipo == "(todos)" else tipo,
    "alert": None if alerta == "(todas)" else alerta,
    "network": None if red == "(todas)" else red,
    "tsunami": {"Todos": None, "Con tsunami": 1, "Sin tsunami": 0}[tsunami],
    "lugar": lugar.strip() if len(lugar.strip()) >= 2 else None,
}
filtros = {k: v for k, v in filtros.items() if v is not None}

st.sidebar.divider()
tam_muestra = st.sidebar.select_slider(
    "Tamaño de la muestra (dispersión, cajas y mapa)", [500, 1000, 2000, 3000, 5000], value=2000
)
if st.sidebar.button("🔄 Recargar datos"):
    st.cache_data.clear()
    st.rerun()

if filtros:
    st.info(f"Filtros activos: {', '.join(f'{k} = {v}' for k, v in filtros.items())}")


# ============================================================
# 5. CONSULTAS PRINCIPALES
# ============================================================
res = pedir("/resumen", **filtros)
if not res or res.get("total", 0) == 0:
    st.warning("No hay terremotos que cumplan los filtros seleccionados.")
    st.stop()

tab_resumen, tab_preguntas, tab_explorar, tab_datos, tab_registrar = st.tabs(
    ["📊 Resumen", "❓ Preguntas de análisis", "🔍 Explorador", "📋 Datos", "➕ Registrar"]
)


# ============================================================
# 6. PESTANA: RESUMEN
# ============================================================
with tab_resumen:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Terremotos", numero(res["total"]))
    c2.metric("Magnitud promedio", numero(res["magnitud_promedio"], 2))
    c3.metric("Magnitud máxima", numero(res["magnitud_maxima"], 1))
    c4.metric("Profundidad promedio", f"{numero(res['profundidad_promedio'], 1)} km")
    pct_tsunami = res["con_tsunami"] / res["total"] * 100
    c5.metric("Con indicador de tsunami", numero(res["con_tsunami"]), f"{numero(pct_tsunami, 2)} %", delta_color="off")

    st.caption(f"Período: {fecha(res['primer_evento'])} → {fecha(res['ultimo_evento'])}")

    fuerte = res.get("mas_fuerte")
    if fuerte:
        st.info(
            f"**Terremoto más fuerte:** magnitud {fuerte['magnitude']} — {fuerte['place']} "
            f"({fecha(fuerte['time'])}, {numero(fuerte['depth_km'], 1)} km de profundidad)"
        )

    por_anio = pedir("/estadisticas/tiempo", periodo="anio", **filtros)
    if por_anio and por_anio["serie"]:
        df_anio = pd.DataFrame(por_anio["serie"])
        df_anio["anio"] = df_anio["anio"].astype(str)
        st.subheader("Terremotos registrados por año")
        grafica = (
            alt.Chart(df_anio)
            .mark_bar(color="#4c78a8")
            .encode(
                x=alt.X("anio:O", title="Año"),
                y=alt.Y("conteo:Q", title="Cantidad de terremotos"),
                tooltip=[
                    alt.Tooltip("anio:O", title="Año"),
                    alt.Tooltip("conteo:Q", title="Terremotos", format=","),
                    alt.Tooltip("magnitud_promedio:Q", title="Magnitud promedio", format=".2f"),
                    alt.Tooltip("magnitud_maxima:Q", title="Magnitud máxima"),
                ],
            )
            .properties(height=320)
        )
        mostrar(st.altair_chart, grafica)
        st.caption(f"El año {ANIO_ACTUAL} está incompleto (llega hasta la fecha de la última carga).")


# ============================================================
# 7. PESTANA: PREGUNTAS DE ANALISIS (las 4 del segundo corte)
# ============================================================
with tab_preguntas:

    # ---------- Pregunta 1 ----------
    st.subheader("1. ¿Cómo varía la magnitud de los terremotos a lo largo del tiempo?")
    mensual = pedir("/estadisticas/tiempo", periodo="mes", **filtros)
    if mensual and mensual["serie"]:
        df_mes = pd.DataFrame(mensual["serie"])
        df_mes["fecha"] = pd.to_datetime(df_mes["periodo"] + "-01")

        linea = (
            alt.Chart(df_mes)
            .mark_line(point=alt.OverlayMarkDef(size=20))
            .encode(
                x=alt.X("fecha:T", title="Año-mes"),
                y=alt.Y("magnitud_promedio:Q", title="Magnitud promedio", scale=alt.Scale(zero=False)),
                tooltip=[
                    alt.Tooltip("periodo:N", title="Mes"),
                    alt.Tooltip("magnitud_promedio:Q", title="Magnitud promedio", format=".3f"),
                    alt.Tooltip("conteo:Q", title="Terremotos", format=","),
                    alt.Tooltip("magnitud_maxima:Q", title="Magnitud máxima"),
                ],
            )
        )
        promedio_general = res["magnitud_promedio"]
        referencia = (
            alt.Chart(pd.DataFrame({"y": [promedio_general]}))
            .mark_rule(color="red", strokeDash=[6, 4])
            .encode(y="y:Q")
        )
        mostrar(st.altair_chart, alt.layer(linea, referencia).properties(height=350))

        if por_anio and len(por_anio["serie"]) > 1:
            df_a = pd.DataFrame(por_anio["serie"])
            menor = df_a.loc[df_a["magnitud_promedio"].idxmin()]
            mayor = df_a.loc[df_a["magnitud_promedio"].idxmax()]
            diferencia = mayor["magnitud_promedio"] - menor["magnitud_promedio"]
            conclusion = (
                "La fuerza típica de los terremotos es estable en el tiempo; los picos se deben a eventos aislados."
                if diferencia < 0.15
                else "Hay variación entre años; conviene revisar qué eventos fuertes explican los picos."
            )
            st.markdown(
                f"**Respuesta:** la magnitud promedio general es **{numero(promedio_general, 2)}** "
                f"(línea roja). Por año, el promedio más bajo fue **{numero(menor['magnitud_promedio'], 2)}** "
                f"({int(menor['anio'])}) y el más alto **{numero(mayor['magnitud_promedio'], 2)}** "
                f"({int(mayor['anio'])}): una diferencia de {numero(diferencia, 2)}. {conclusion}"
            )
        st.caption("El eje vertical no empieza en cero: diferencias de centésimas se ven grandes. El último mes puede estar incompleto.")

    st.divider()

    # ---------- Pregunta 2 ----------
    st.subheader("2. ¿Qué tipos de magnitud son más frecuentes?")
    tipos = pedir("/estadisticas", agrupar_por="magnitude_type", sumar="magnitude", top=8, **filtros)
    if tipos and tipos["grupos"]:
        df_tipos = pd.DataFrame(tipos["grupos"])
        col_a, col_b = st.columns([3, 2])
        with col_a:
            barras = (
                alt.Chart(df_tipos)
                .mark_bar(color="steelblue")
                .encode(
                    x=alt.X("conteo:Q", title="Cantidad de terremotos"),
                    y=alt.Y("magnitude_type:N", sort="-x", title="Tipo de magnitud"),
                    tooltip=[
                        alt.Tooltip("magnitude_type:N", title="Tipo"),
                        alt.Tooltip("conteo:Q", title="Terremotos", format=","),
                        alt.Tooltip("porcentaje:Q", title="% del total"),
                        alt.Tooltip("promedio:Q", title="Magnitud promedio", format=".2f"),
                    ],
                )
                .properties(height=300)
            )
            mostrar(st.altair_chart, barras)
        with col_b:
            tabla = df_tipos[["magnitude_type", "conteo", "porcentaje", "promedio"]].rename(
                columns={
                    "magnitude_type": "Tipo",
                    "conteo": "Cantidad",
                    "porcentaje": "% del total",
                    "promedio": "Magnitud promedio",
                }
            )
            mostrar(st.dataframe, tabla, hide_index=True)
        primero = df_tipos.iloc[0]
        st.markdown(
            f"**Respuesta:** el tipo más usado es **{primero['magnitude_type']}** con "
            f"**{numero(primero['porcentaje'], 1)} %** de los eventos. Son métodos distintos para "
            "calcular la magnitud, no tamaños distintos de terremoto; los tipos *mw* se usan sobre "
            "todo para los eventos grandes (por eso su magnitud promedio es mayor)."
        )

    st.divider()

    # ---------- Pregunta 3 ----------
    st.subheader("3. ¿Existe relación entre la magnitud y la profundidad?")
    corr = pedir("/estadisticas/correlacion", x="magnitude", y="depth_km", **filtros)
    prof = pedir("/estadisticas", agrupar_por="categoria_profundidad", sumar="magnitude", top=3, **filtros)
    mues = pedir("/muestra", n=tam_muestra, **filtros)

    if corr:
        m1, m2, m3 = st.columns(3)
        m1.metric("Correlación de Pearson", numero(corr["pearson"], 3))
        m2.metric("Interpretación", corr["interpretacion"])
        m3.metric("Terremotos usados", numero(corr["n"]))

    df_muestra = pd.DataFrame(mues["datos"]) if mues and mues["datos"] else pd.DataFrame()
    if not df_muestra.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            base = alt.Chart(df_muestra).encode(
                x=alt.X("depth_km:Q", title="Profundidad (km)"),
                y=alt.Y("magnitude:Q", title="Magnitud", scale=alt.Scale(zero=False)),
            )
            puntos = base.mark_circle(opacity=0.25, size=14).encode(
                tooltip=["place:N", "magnitude:Q", "depth_km:Q"]
            )
            # Linea de tendencia (regresion lineal), como el regplot del notebook
            tendencia = base.transform_regression("depth_km", "magnitude").mark_line(color="red", size=2)
            mostrar(
                st.altair_chart,
                alt.layer(puntos, tendencia).properties(
                    height=350, title=f"Dispersión (muestra aleatoria de {numero(len(df_muestra))})"
                ),
            )
        with col_b:
            cajas = (
                alt.Chart(df_muestra)
                .mark_boxplot(extent=1.5, size=50)
                .encode(
                    x=alt.X("categoria_profundidad:N", sort=ORDEN_PROFUNDIDAD, title="Rango de profundidad"),
                    y=alt.Y("magnitude:Q", title="Magnitud", scale=alt.Scale(zero=False)),
                    color=alt.Color("categoria_profundidad:N", sort=ORDEN_PROFUNDIDAD, legend=None),
                )
                .properties(height=350, title="Magnitud según el rango de profundidad")
            )
            mostrar(st.altair_chart, cajas)

    if prof and prof["grupos"]:
        df_prof = pd.DataFrame(prof["grupos"])
        df_prof["orden"] = df_prof["categoria_profundidad"].map({c: i for i, c in enumerate(ORDEN_PROFUNDIDAD)})
        df_prof = df_prof.sort_values("orden")
        mostrar(
            st.dataframe,
            df_prof[["categoria_profundidad", "conteo", "porcentaje", "promedio", "maximo"]].rename(
                columns={
                    "categoria_profundidad": "Rango (superficial <70 km, profundo >300 km)",
                    "conteo": "Terremotos",
                    "porcentaje": "% del total",
                    "promedio": "Magnitud promedio",
                    "maximo": "Magnitud máxima",
                }
            ),
            hide_index=True,
        )
        if corr:
            promedios = dict(zip(df_prof["categoria_profundidad"], df_prof["promedio"]))
            plurales = {"superficial": "superficiales", "intermedio": "intermedios", "profundo": "profundos"}
            texto_prom = ", ".join(
                f"{numero(promedios[c], 2)} en los {plurales[c]}" for c in ORDEN_PROFUNDIDAD if c in promedios
            )
            if corr["pearson"] <= -0.1:
                conclusion = ("Los terremotos más profundos tienden a ser levemente menos fuertes, "
                              "pero la profundidad explica muy poco de la magnitud.")
            elif corr["pearson"] >= 0.1:
                conclusion = ("Los terremotos más profundos tienden a ser levemente más fuertes, "
                              "pero la profundidad explica poco de la magnitud.")
            else:
                conclusion = "Con estos filtros la profundidad prácticamente no se relaciona con la magnitud."
            st.markdown(
                f"**Respuesta:** la correlación es **{numero(corr['pearson'], 3)}**: "
                f"{corr['interpretacion'].lower().replace('relación', 'una relación')}. "
                f"La magnitud promedio es {texto_prom}. {conclusion}"
            )
    st.caption("La correlación y la tabla usan todos los registros; las dos gráficas usan una muestra aleatoria para que se puedan leer.")

    st.divider()

    # ---------- Pregunta 4 ----------
    st.subheader("4. ¿Qué zonas presentan la mayor cantidad de terremotos?")
    zonas = pedir("/estadisticas", agrupar_por="zona", sumar="magnitude", top=10, **filtros)
    if zonas and zonas["grupos"]:
        df_zonas = pd.DataFrame(zonas["grupos"])
        barras_zonas = (
            alt.Chart(df_zonas)
            .mark_bar(color="darkorange")
            .encode(
                x=alt.X("conteo:Q", title="Cantidad de terremotos"),
                y=alt.Y("zona:N", sort="-x", title="Zona"),
                tooltip=[
                    alt.Tooltip("zona:N", title="Zona"),
                    alt.Tooltip("conteo:Q", title="Terremotos", format=","),
                    alt.Tooltip("porcentaje:Q", title="% del total"),
                    alt.Tooltip("promedio:Q", title="Magnitud promedio", format=".2f"),
                    alt.Tooltip("maximo:Q", title="Magnitud máxima"),
                ],
            )
            .properties(height=360)
        )
        mostrar(st.altair_chart, barras_zonas)
        top3 = ", ".join(f"{z} ({numero(c)})" for z, c in zip(df_zonas["zona"][:3], df_zonas["conteo"][:3]))
        concentracion = df_zonas["porcentaje"].sum()
        if zonas["cantidad_grupos"] <= len(df_zonas):
            texto_zonas = f"Solo hay {len(df_zonas)} zona(s) con datos."
        else:
            texto_zonas = (
                f"Las {len(df_zonas)} primeras de {numero(zonas['cantidad_grupos'])} zonas concentran el "
                f"**{numero(concentracion, 1)} %** de los eventos"
                + (": la actividad sísmica está muy concentrada." if concentracion >= 40 else ".")
            )
        st.markdown(f"**Respuesta:** las zonas con más terremotos son {top3}. {texto_zonas}")
        st.caption(
            f"La zona es el texto después de la última coma de `place` (hay {numero(zonas['cantidad_grupos'])} zonas distintas)."
        )

    if not df_muestra.empty:
        st.markdown("**Mapa de terremotos** (muestra aleatoria; el tamaño depende de la magnitud)")
        mapa = df_muestra.dropna(subset=["latitude", "longitude"]).copy()
        mapa["tamano"] = (mapa["magnitude"] - 3).clip(lower=0.5) * 25_000
        try:
            st.map(mapa, latitude="latitude", longitude="longitude", size="tamano", color="#e4572e99")
        except TypeError:  # versiones viejas de Streamlit
            st.map(mapa[["latitude", "longitude"]])


# ============================================================
# 8. PESTANA: EXPLORADOR (agregacion libre)
# ============================================================
with tab_explorar:
    st.subheader("Agrupar y resumir")
    st.caption("Usa el endpoint GET /estadisticas de la API (agregación de MongoDB con $group).")

    e1, e2, e3, e4 = st.columns(4)
    agrupables = ["magnitude_type", "zona", "network", "alert", "categoria_profundidad", "anio", "mes", "tsunami", "status"]
    agrupar = e1.selectbox("Agrupar por", agrupables, format_func=lambda c: NOMBRES.get(c, c))
    numericas = ["magnitude", "depth_km", "significance", "felt", "stations", "distance", "rms", "gap"]
    variable = e2.selectbox("Variable numérica", numericas, format_func=lambda c: NOMBRES.get(c, c))
    metricas = {"conteo": "Cantidad", "promedio": "Promedio", "maximo": "Máximo", "suma": "Suma"}
    metrica = e3.selectbox("Mostrar", list(metricas), format_func=metricas.get)
    top = e4.slider("Grupos a mostrar", 3, 50, 15)

    orden_grupo = "grupo" if agrupar in ("anio", "mes") else metrica
    g = pedir("/estadisticas", agrupar_por=agrupar, sumar=variable, ordenar_por=orden_grupo, top=top, **filtros)
    if g and g["grupos"]:
        df_g = pd.DataFrame(g["grupos"])
        df_g[agrupar] = df_g[agrupar].astype(str)
        eje_categoria = (
            alt.Y(f"{agrupar}:N", sort=None, title=NOMBRES.get(agrupar, agrupar))
            if agrupar in ("anio", "mes")
            else alt.Y(f"{agrupar}:N", sort="-x", title=NOMBRES.get(agrupar, agrupar))
        )
        titulo_x = "Cantidad de terremotos" if metrica == "conteo" else f"{metricas[metrica]} de {NOMBRES.get(variable, variable)}"
        grafica = (
            alt.Chart(df_g)
            .mark_bar(color="#54a24b")
            .encode(
                x=alt.X(f"{metrica}:Q", title=titulo_x),
                y=eje_categoria,
                tooltip=list(df_g.columns),
            )
            .properties(height=max(250, 26 * len(df_g)))
        )
        mostrar(st.altair_chart, grafica)
        mostrar(st.dataframe, df_g, hide_index=True)
        st.caption(
            f"{numero(g['total_registros'])} terremotos en {numero(g['cantidad_grupos'])} grupos. "
            "Promedio, mínimo y máximo ignoran los valores nulos."
        )
    elif g:
        st.info("No hay resultados para esta combinación.")


# ============================================================
# 9. PESTANA: DATOS
# ============================================================
with tab_datos:
    st.subheader("Registros de terremotos")

    d1, d2, d3, d4 = st.columns(4)
    ordenar_por = d1.selectbox(
        "Ordenar por", ["time", "magnitude", "depth_km", "significance"],
        format_func=lambda c: {"time": "Fecha"}.get(c, NOMBRES.get(c, c)),
    )
    orden = d2.radio("Orden", ["desc", "asc"], horizontal=True, format_func=lambda o: "Mayor a menor" if o == "desc" else "Menor a mayor")
    limite = d3.selectbox("Registros por página", [25, 50, 100, 500], index=1)
    total_paginas = max(1, -(-res["total"] // limite))
    pagina = d4.number_input(f"Página (de {numero(total_paginas)})", min_value=1, max_value=total_paginas, value=1)

    datos = pedir(
        "/datos", ordenar_por=ordenar_por, orden=orden, limite=limite, saltar=(pagina - 1) * limite, **filtros
    )
    if datos and datos["datos"]:
        df = pd.DataFrame(datos["datos"]).drop(columns=["_id"], errors="ignore")
        df.insert(1, "fecha_utc", pd.to_datetime(df["time"], unit="ms", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S"))
        principales = ["event_id", "fecha_utc", "magnitude", "magnitude_type", "place", "depth_km",
                       "latitude", "longitude", "significance", "alert", "tsunami", "status", "network"]
        df = df[[c for c in principales if c in df.columns] + [c for c in df.columns if c not in principales]]
        if "alert" in df.columns:
            df["alert"] = df["alert"].fillna("sin alerta")

        inicio = (pagina - 1) * limite + 1
        st.caption(f"Mostrando {numero(inicio)}–{numero(inicio + len(df) - 1)} de {numero(datos['total'])} terremotos")
        mostrar(
            st.dataframe,
            df,
            hide_index=True,
            column_config={
                "url": st.column_config.LinkColumn("url"),
                "detail_url": st.column_config.LinkColumn("detail_url"),
            },
        )
        st.download_button(
            "⬇️ Descargar esta página (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"terremotos_pagina_{pagina}.csv",
            mime="text/csv",
        )

    st.markdown("**Buscar un terremoto por su identificador**")
    b1, b2 = st.columns([3, 1])
    buscado = b1.text_input("event_id", placeholder="Ej: us6000pjr0", label_visibility="collapsed")
    if b2.button("Buscar") and buscado.strip():
        try:
            r = requests.get(f"{API}/datos/{buscado.strip()}", timeout=60)
            if r.status_code == 404:
                st.warning(r.json()["detail"])
            elif r.ok:
                st.json(r.json())
            else:
                st.error(f"Error {r.status_code}: {r.text}")
        except requests.RequestException as e:
            st.error(f"No se pudo consultar la API: {e}")


# ============================================================
# 10. PESTANA: REGISTRAR UN TERREMOTO (POST /datos)
# ============================================================
with tab_registrar:
    st.subheader("Registrar un nuevo terremoto")
    st.caption(
        "Los datos se envían a POST /datos. La API valida tipos y rangos (422), "
        "rechaza identificadores repetidos (409) y responde 201 si lo guarda."
    )

    with st.form("nuevo_terremoto", clear_on_submit=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            event_id = st.text_input("Identificador (event_id) *", placeholder="Ej: prueba001")
            place = st.text_input("Lugar *", placeholder="Ej: 10 km N of Tona, Colombia")
            ahora = datetime.now(timezone.utc)
            fecha_evento = st.date_input("Fecha del evento (UTC) *", value=ahora.date())
            hora_evento = st.time_input("Hora del evento (UTC) *", value=ahora.time().replace(microsecond=0))
        with col2:
            magnitude = st.number_input("Magnitud *", min_value=0.0, max_value=10.0, value=4.5, step=0.1)
            magnitude_type = st.selectbox("Tipo de magnitud", lista_tipos or ["mb", "mww", "mwr", "ml", "mw", "md"])
            depth_km = st.number_input("Profundidad (km) *", min_value=-10.0, max_value=800.0, value=10.0, step=1.0)
            significance = st.number_input("Significancia *", min_value=0, value=300, step=1)
        with col3:
            latitude = st.number_input("Latitud *", min_value=-90.0, max_value=90.0, value=4.71, format="%.4f")
            longitude = st.number_input("Longitud *", min_value=-180.0, max_value=180.0, value=-74.07, format="%.4f")
            alert = st.selectbox("Nivel de alerta", ["sin alerta", "green", "yellow", "orange", "red"])
            tsunami_nuevo = st.radio("Indicador de tsunami", [0, 1], horizontal=True, format_func=lambda x: "Sí" if x else "No")

        with st.expander("Campos opcionales"):
            o1, o2, o3 = st.columns(3)
            status = o1.selectbox("Estado", ["reviewed", "automatic"])
            network = o2.text_input("Red sísmica", value="us")
            felt = o3.number_input("Reportes de personas (felt, 0 = sin dato)", min_value=0, value=0, step=1)
            distance = o1.number_input("Distancia dmin (grados, 0 = sin dato)", min_value=0.0, value=0.0, step=0.01)
            stations = o2.number_input("Estaciones (0 = sin dato)", min_value=0, value=0, step=1)
            gap = o3.number_input("Gap azimutal (0 = sin dato)", min_value=0.0, max_value=360.0, value=0.0)

        enviar = st.form_submit_button("💾 Guardar terremoto", type="primary")

    if enviar:
        if len(event_id.strip()) < 3 or len(place.strip()) < 2:
            st.error("El identificador (mínimo 3 caracteres) y el lugar son obligatorios.")
        else:
            momento = datetime.combine(fecha_evento, hora_evento).replace(tzinfo=timezone.utc)
            payload = {
                "event_id": event_id.strip(),
                "magnitude": round(float(magnitude), 2),
                "place": place.strip(),
                "time": int(momento.timestamp() * 1000),
                "depth_km": float(depth_km),
                "latitude": float(latitude),
                "longitude": float(longitude),
                "significance": int(significance),
                "magnitude_type": magnitude_type,
                "tsunami": int(tsunami_nuevo),
                "alert": None if alert == "sin alerta" else alert,
                "status": status,
                "network": network.strip() or None,
                # 0 en el formulario significa "sin dato": se guarda nulo, igual que en el USGS
                "felt": int(felt) or None,
                "distance": float(distance) or None,
                "stations": int(stations) or None,
                "gap": float(gap) or None,
            }
            try:
                r = requests.post(f"{API}/datos", json=payload, timeout=60)
                if r.status_code == 201:
                    st.success(f"✅ {r.json()['mensaje']} (event_id: {payload['event_id']}, _id: {r.json()['id']})")
                    st.cache_data.clear()  # para que las graficas y tablas incluyan el nuevo registro
                    st.json(payload)
                elif r.status_code == 409:
                    st.warning(f"⚠️ {r.json()['detail']}. Usa otro identificador.")
                elif r.status_code == 422:
                    errores = r.json().get("detail", [])
                    lineas = [f"- **{e['loc'][-1]}**: {e['msg']}" for e in errores if isinstance(e, dict)]
                    st.error("La API rechazó los datos:\n" + ("\n".join(lineas) or str(errores)))
                else:
                    st.error(f"Error {r.status_code} de la API: {r.text}")
            except requests.RequestException as e:
                st.error(f"No se pudo conectar con la API: {e}")

import os
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import gspread 
import json 

# ---------------------------------------------------------
# 1. ESQUEMA DE DATOS (Incluye campo de Estandarización)
# ---------------------------------------------------------
class JobDescription(BaseModel):
    titulo_puesto: str = Field(description="El título FINAL del puesto (ya estandarizado si hubo coincidencia).")
    nivel: str = Field(description="Nivel de seniority.")
    origen_titulo: str = Field(description="Debe decir 'ESTANDARIZADO' si se tomó de la lista oficial, o 'NUEVO' si se creó desde cero.")
    mision_puesto: str = Field(description="Propósito principal del cargo.")
    responsabilidades_clave: list[str] = Field(description="5-7 funciones principales orientadas a resultados.")
    competencias_conductuales_seleccionadas: list[str] = Field(description="Las 4-5 competencias del diccionario seleccionadas.")
    competencias_tecnicas: list[str] = Field(description="Habilidades duras (Hard Skills).")
    requisitos_formacion: list[str] = Field(description="Formación académica.")
    kpis_sugeridos: list[str] = Field(description="Indicadores clave (KPIs).")
    observacion_ia: str = Field(description="Explicación si cambió el título (Ej: 'Cambié Vendedor Jr por Asistente de Ventas según catálogo').")

GOOGLE_SHEET_ID = "1QPJ1JoCW7XO-6sf-WMz8SvAtylKTAShuMr_yGBoF-Xg" 

# ---------------------------------------------------------
# 2. CONEXIÓN A SHEETS (Ahora lee 2 hojas)
# ---------------------------------------------------------
def get_google_sheet_client():
    creds = st.secrets["gspread"]["gcp_service_account_credentials"]
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_key(GOOGLE_SHEET_ID)

@st.cache_data(ttl=3600)
def get_competencias(worksheet_name: str = "Diccionario_JobCraft"):
    try:
        sh = get_google_sheet_client()
        worksheet = sh.worksheet(worksheet_name)
        return pd.DataFrame(worksheet.get_all_records()), None
    except Exception as e:
        return None, f"Error cargando Diccionario: {e}"

@st.cache_data(ttl=3600)
def get_perfiles_estandar(worksheet_name: str = "Perfiles_Base_JobCraft"):
    try:
        sh = get_google_sheet_client()
        # Intentamos cargar la hoja de perfiles base
        worksheet = sh.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        # Convertimos a texto simple para que la IA lo lea rápido: "Cargo (Nivel)"
        lista_formateada = [f"{row['Cargo']} ({row.get('Nivel', 'N/A')})" for row in data]
        return "\n".join(lista_formateada), None
    except Exception as e:
        # Si falla (ej: no existe la hoja aún), devolvemos texto vacío pero no rompemos la app
        return "", f"Nota: No se encontró hoja de perfiles base ({e}). Se generará libremente."

# ---------------------------------------------------------
# 3. CEREBRO DE LA IA (Prompt con Lógica de Cruce)
# ---------------------------------------------------------
def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str, competencias_df: pd.DataFrame, lista_perfiles_base: str):
    try:
        client = genai.Client(api_key=api_key)
        
        # Preparamos el diccionario de competencias
        lista_competencias = "\n".join([
            f"- {row['Familia']}: {row['COREES_Definición_Core_N1_Inicial']}" 
            for index, row in competencias_df.iterrows()
        ])
        
        # PROMPT DE ESTANDARIZACIÓN
        prompt = f"""
        Actúa como un Director de Talento Humano experto en Estructura Organizacional.
        Objetivo: Definir un perfil de puesto para: '{title}' (Nivel deseado: {level}).
        Habilidad Crítica: {critical_skill}
        
        --- BASE DE DATOS DE PUESTOS EXISTENTES (CATÁLOGO OFICIAL) ---
        {lista_perfiles_base}
        ------------------------------------------------------------
        
        INSTRUCCIONES DE ESTANDARIZACIÓN (PRIORIDAD ALTA):
        1. Busca en el CATÁLOGO OFICIAL arriba si existe un puesto similar o equivalente al solicitado.
           - Ejemplo: Si piden "Vendedor Jr" y en la lista existe "Asistente de Ventas", USA "Asistente de Ventas".
           - Ejemplo: Si piden "Gerente de Ventas" (Nivel Junior), y eso es ilógico, busca si existe "Coordinador" o "Analista Senior".
        
        2. SI ENCUENTRAS COINCIDENCIA EN EL CATÁLOGO:
           - Usa el 'titulo_puesto' exacto del catálogo.
           - Marca 'origen_titulo' como "ESTANDARIZADO".
           - En 'observacion_ia' explica: "Se reemplazó [Titulo Usuario] por [Titulo Oficial] para cumplir el estándar".
           
        3. SI NO HAY COINCIDENCIA (Es un puesto nuevo):
           - Usa el título propuesto por el usuario (ajustándolo si es semánticamente incorrecto, ej: Gerente Junior -> Coordinador).
           - Marca 'origen_titulo' como "NUEVO".
        
        INSTRUCCIONES DE CONTENIDO:
        4. Competencias Conductuales: Selecciona 4-5 EXCLUSIVAMENTE del siguiente diccionario:
           {lista_competencias}
        5. Redacta Misión, Responsabilidades y KPIs con alto nivel técnico.
        
        Genera JSON estricto.
        """
        
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=JobDescription)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
        return None, JobDescription(**json.loads(response.text))
    except Exception as e:
        return f"Error AI: {e}", None

# ---------------------------------------------------------
# 4. GUARDAR RESULTADOS
# ---------------------------------------------------------
def guardar_datos_en_sheets(titulo_puesto: str, nivel: str, origen: str):
    try:
        sh = get_google_sheet_client()
        worksheet = sh.worksheet("Seguimiento Generaciones") 
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        # Guardamos también si fue estandarizado o no
        worksheet.append_row([timestamp, titulo_puesto, nivel, origen]) 
        return True, None
    except Exception as e:
        return False, f"Error al guardar: {e}"

# ---------------------------------------------------------
# 5. INTERFAZ GRÁFICA
# ---------------------------------------------------------
st.set_page_config(page_title="JobCraft AI Pro", layout="wide", page_icon="👔") 

st.markdown("## 👔 JobCraft AI: Diseñador Estandarizado")
st.markdown("---")

api_key = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else None
if not api_key:
    st.error("⚠️ Falta API KEY")
    st.stop()

# Carga de Datos (Diccionario + Catálogo de Puestos)
col_load1, col_load2 = st.columns(2)
with col_load1:
    df_comp, err_comp = get_competencias()
    if err_comp: st.error(err_comp); st.stop()
    st.success(f"✅ Diccionario: {len(df_comp)} registros", icon="📘")

with col_load2:
    # Cargamos el catálogo de puestos para estandarizar
    txt_perfiles, err_perf = get_perfiles_estandar()
    if "Error" in str(err_perf): 
        st.warning(err_perf) # Solo aviso, no detiene la app
    else:
        st.success(f"✅ Catálogo Oficial conectado", icon="🗂️")

with st.container():
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        t = st.text_input("Nombre del Cargo (Búsqueda)", value="Analista de Ventas")
    with col2:
        l = st.selectbox("Nivel de Seniority", ["Junior (0-2 años)", "Semi-Senior (3-5 años)", "Senior (5+ años)", "Líder/Gerente"])
    with col3:
        s = st.text_input("Habilidad Crítica / Foco", placeholder="Ej: Python, Ventas B2B...")

    btn = st.button("✨ Buscar y Generar Perfil", type="primary", use_container_width=True)

if btn:
    with st.spinner("🔍 Consultando catálogo oficial y generando perfil..."):
        # Le pasamos a la IA la lista de perfiles (txt_perfiles)
        err_ai, res = run_jobcraft_ai(api_key, t, l, s, df_comp, txt_perfiles)
        
        if err_ai: 
            st.error(err_ai)
        else:
            guardar_datos_en_sheets(res.titulo_puesto, res.nivel, res.origen_titulo)
            
            st.divider()
            
            # Encabezado Inteligente
            if res.origen_titulo == "ESTANDARIZADO":
                st.success(f"✅ **PUESTO OFICIAL ENCONTRADO:** El sistema ajustó tu búsqueda al estándar de la empresa.")
            else:
                st.info(f"🆕 **NUEVO PUESTO:** No se encontró en catálogo, se creó uno nuevo.")

            st.markdown(f"<h1 style='text-align: center; color: #1E88E5;'>{res.titulo_puesto}</h1>", unsafe_allow_html=True)
            
            if res.observacion_ia:
                st.warning(f"🤖 **Nota de Estandarización:** {res.observacion_ia}")
            
            st.markdown(f"<p style='text-align: center;'>Nivel: <b>{res.nivel}</b></p>", unsafe_allow_html=True)
            st.info(f"🎯 **Misión:** {res.mision_puesto}")
            
            col_izq, col_der = st.columns(2)
            with col_izq:
                st.subheader("🚀 Responsabilidades")
                for item in res.responsabilidades_clave: st.markdown(f"✅ {item}")
                st.subheader("🧠 Competencias (ADN)")
                for item in res.competencias_conductuales_seleccionadas: st.markdown(f"🔹 {item}")
            with col_der:
                st.subheader("🛠️ Técnicas")
                for item in res.competencias_tecnicas: st.markdown(f"🔧 {item}")
                st.subheader("🎓 Requisitos")
                for item in res.requisitos_formacion: st.markdown(f"🎓 {item}")
            
            st.divider()
            st.caption("KPIs Sugeridos:")
            if res.kpis_sugeridos:
                cols = st.columns(len(res.kpis_sugeridos))
                for idx, k in enumerate(res.kpis_sugeridos): cols[idx].success(k)

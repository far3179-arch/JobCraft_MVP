import time
import os
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import gspread 
import json 

# ---------------------------------------------------------
# 1. ESQUEMA DE DATOS
# ---------------------------------------------------------
class JobDescription(BaseModel):
    titulo_puesto: str = Field(description="El título que se mostrará en el perfil (solicitado por el usuario).")
    titulo_oficial_match: str = Field(description="El título exacto encontrado en el catálogo oficial (si hubo coincidencia).")
    origen_titulo: str = Field(description="Debe decir 'ESTANDARIZADO' si se encontró match, o 'NUEVO' si no.")
    mision_puesto: str = Field(description="Propósito principal del cargo.")
    responsabilidades_clave: list[str] = Field(description="5-7 funciones principales orientadas a resultados.")
    competencias_conductuales_seleccionadas: list[str] = Field(description="Las 4-5 competencias del diccionario seleccionadas.")
    competencias_tecnicas: list[str] = Field(description="Habilidades duras (Hard Skills).")
    requisitos_formacion: list[str] = Field(description="Formación académica.")
    kpis_sugeridos: list[str] = Field(description="Indicadores clave (KPIs).")
    observacion_ia: str = Field(description="Explicación de la equivalencia o estandarización.")

GOOGLE_SHEET_ID = "1QPJ1JoCW7XO-6sf-WMz8SvAtylKTAShuMr_yGBoF-Xg" 

# ---------------------------------------------------------
# 2. CONEXIÓN A SHEETS
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
        worksheet = sh.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        # Formato simple para la IA: Cargo (Nivel)
        lista_formateada = [f"{row['Cargo']} ({row.get('Nivel', 'N/A')})" for row in data]
        return "\n".join(lista_formateada), None
    except Exception as e:
        return "", f"Nota: No se encontró hoja de perfiles base ({e}). Se generará libremente."

# ---------------------------------------------------------
# 3. CEREBRO DE LA IA (CON REINTENTOS AUTOMÁTICOS)
# ---------------------------------------------------------
def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str, competencias_df: pd.DataFrame, lista_perfiles_base: str):
    # Intentaremos hasta 3 veces si el servidor está ocupado
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            client = genai.Client(api_key=api_key)
            
            lista_competencias = "\n".join([
                f"- {row['Familia']}: {row['COREES_Definición_Core_N1_Inicial']}" 
                for index, row in competencias_df.iterrows()
            ])
            
            prompt = f"""
            Actúa como Director de Estructura Organizacional.
            Objetivo: Definir perfil para: '{title}' (Nivel: {level}).
            Habilidad Crítica: {critical_skill}
            
            --- CATÁLOGO OFICIAL DE PUESTOS ---
            {lista_perfiles_base}
            -----------------------------------
            
            INSTRUCCIONES DE ESTANDARIZACIÓN (HÍBRIDA):
            1. Busca en el CATÁLOGO OFICIAL si existe un puesto equivalente.
               - Ejemplo: Usuario pide "Analista de Ventas". Catálogo tiene "Analista Comercial". SON EQUIVALENTES.
            
            2. SI ENCUENTRAS COINCIDENCIA (Equivalencia):
               - 'titulo_puesto': Mantén el nombre que pidió el usuario.
               - 'titulo_oficial_match': Pon el nombre oficial del catálogo.
               - 'origen_titulo': "ESTANDARIZADO".
               - 'observacion_ia': "Este puesto es equivalente a [Titulo Oficial] en el Catálogo Maestro".
               
            3. SI NO HAY COINCIDENCIA:
               - 'titulo_puesto': El solicitado por el usuario.
               - 'titulo_oficial_match': "N/A"
               - 'origen_titulo': "NUEVO".
            
            INSTRUCCIONES DE CONTENIDO:
            4. Usa las competencias del diccionario adjunto (definiciones exactas).
            5. Genera Misión, Responsabilidades y KPIs profesionales.
            
            Genera JSON estricto.
            """
            
            config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=JobDescription)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
            return None, JobDescription(**json.loads(response.text))
            
        except Exception as e:
            # Si es error 503 (Sobrecarga) o 429 (Límite), esperamos y reintentamos
            if "503" in str(e) or "overloaded" in str(e).lower() or "429" in str(e):
                time.sleep(2) # Espera 2 segundos
                continue 
            else:
                # Otros errores (ej: API Key inválida) se reportan de inmediato
                return f"Error AI: {e}", None

    return "El servidor de IA está muy ocupado. Por favor intenta en unos segundos.", None

# ---------------------------------------------------------
# 4. GUARDAR RESULTADOS
# ---------------------------------------------------------
def guardar_datos_en_sheets(titulo_puesto: str, nivel: str, origen: str):
    try:
        sh = get_google_sheet_client()
        worksheet = sh.worksheet("Seguimiento Generaciones") 
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
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
    st.error("⚠️ Falta API KEY en Secrets")
    st.stop()

# Carga de Datos
col_load1, col_load2 = st.columns(2)
with col_load1:
    df_comp, err_comp = get_competencias()
    if err_comp: st.error(err_comp); st.stop()
    st.success(f"✅ Diccionario: {len(df_comp)} registros", icon="📘")

with col_load2:
    txt_perfiles, err_perf = get_perfiles_estandar()
    if "Error" in str(err_perf): 
        st.warning(err_perf)
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
        err_ai, res = run_jobcraft_ai(api_key, t, l, s, df_comp, txt_perfiles)
        
        if err_ai: 
            st.error(err_ai)
        else:
            guardar_datos_en_sheets(res.titulo_puesto, res.nivel, res.origen_titulo)
            
            st.divider()
            
            # --- VISUALIZACIÓN MEJORADA ---
            if res.origen_titulo == "ESTANDARIZADO":
                st.success(f"✅ **PUESTO VALIDADO:** Se encontró equivalencia en el catálogo oficial.")
            else:
                st.info(f"🆕 **NUEVO PUESTO:** Creando perfil desde cero (No existe en catálogo).")

            # TITULO
            st.markdown(f"<h1 style='text-align: center; color: #1E88E5;'>{res.titulo_puesto}</h1>", unsafe_allow_html=True)
            
            # NOTA DE EQUIVALENCIA
            if res.titulo_oficial_match and res.titulo_oficial_match != "N/A" and res.titulo_oficial_match != res.titulo_puesto:
                 st.markdown(
                     f"<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; text-align: center; color: #856404; margin-bottom: 20px;'>"
                     f"⚠️ <b>Nota de Estandarización:</b> Este puesto equivale oficialmente a <b>'{res.titulo_oficial_match}'</b> en el Catálogo Maestro."
                     f"</div>", 
                     unsafe_allow_html=True
                 )
            elif res.observacion_ia:
                 st.caption(f"🤖 Nota: {res.observacion_ia}")

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

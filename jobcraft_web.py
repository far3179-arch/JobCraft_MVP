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
    titulo_puesto: str = Field(description="Título normalizado del puesto.")
    nivel: str = Field(description="Nivel de seniority.")
    mision_puesto: str = Field(description="Propósito principal del cargo (El 'para qué').")
    responsabilidades_clave: list[str] = Field(description="Lista de 5-7 funciones principales orientadas a resultados.")
    competencias_conductuales_seleccionadas: list[str] = Field(description="Las 4-5 competencias del diccionario que mejor encajen.")
    competencias_tecnicas: list[str] = Field(description="Habilidades duras (Hard Skills).")
    requisitos_formacion: list[str] = Field(description="Formación académica indispensable y deseable.")
    kpis_sugeridos: list[str] = Field(description="3-4 Indicadores clave (KPIs).")
    observacion_ia: str = Field(description="Nota de la IA sobre la consistencia del perfil (Ej: Si el título no cuadra con el nivel).")

GOOGLE_SHEET_ID = "1QPJ1JoCW7XO-6sf-WMz8SvAtylKTAShuMr_yGBoF-Xg" 

# ---------------------------------------------------------
# 2. CONEXIÓN A SHEETS
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_competencias(worksheet_name: str = "Diccionario_JobCraft"):
    try:
        creds = st.secrets["gspread"]["gcp_service_account_credentials"]
        gc = gspread.service_account_from_dict(creds)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data), None
    except Exception as e:
        return None, f"Error de conexión con Google Sheets. Detalle: {e}"

# ---------------------------------------------------------
# 3. CEREBRO DE LA IA (Prompt Actualizado con más cargos)
# ---------------------------------------------------------
def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str, competencias_df: pd.DataFrame):
    try:
        client = genai.Client(api_key=api_key)
        
        lista_competencias = "\n".join([
            f"- {row['Familia']}: {row['COREES_Definición_Core_N1_Inicial']}" 
            for index, row in competencias_df.iterrows()
        ])
        
        # PROMPT ACTUALIZADO
        prompt = f"""
        Actúa como un Consultor Senior de Desarrollo Organizacional.
        Diseña un PERFIL DE PUESTO para: '{title}' (Seniority: {level}).
        Habilidad Crítica: {critical_skill}
        
        INSTRUCCIONES ESTRATÉGICAS:
        1. **VALIDACIÓN DE CONSISTENCIA (CRÍTICO)**: Analiza el título vs el nivel.
           - Si el título implica liderazgo (Gerente, Director, VP, Coordinador, Jefe) y el nivel es "Junior", es una INCONSISTENCIA.
           - En ese caso, añade una nota clara en 'observacion_ia' sugiriendo cambiar el título o subir el nivel.
        2. **Misión**: Propósito en una frase inspiradora.
        3. **Responsabilidades**: Redacta funciones orientadas a RESULTADOS.
        4. **Competencias Conductuales**: Selecciona 4-5 del siguiente DICCIONARIO (Usa sus definiciones exactas):
           {lista_competencias}
        5. **KPIs**: Sugiere indicadores de éxito medibles.
        
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
def guardar_datos_en_sheets(titulo_puesto: str, nivel: str, critical_skill: str):
    try:
        creds = st.secrets["gspread"]["gcp_service_account_credentials"]
        gc = gspread.service_account_from_dict(creds)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet("Seguimiento Generaciones") 
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        worksheet.append_row([timestamp, titulo_puesto, nivel, critical_skill]) 
        return True, None
    except Exception as e:
        return False, f"Error al guardar: {e}"

# ---------------------------------------------------------
# 5. INTERFAZ GRÁFICA (Lista ampliada de palabras clave)
# ---------------------------------------------------------
st.set_page_config(page_title="JobCraft AI Pro", layout="wide", page_icon="👔") 

st.markdown("## 👔 JobCraft AI: Diseñador de Puestos Inteligente")
st.markdown("---")

api_key = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else None
if not api_key:
    st.error("⚠️ Falta la GEMINI_API_KEY en los secretos.")
    st.stop()

df, err = get_competencias()
if err:
    st.error(f"⚠️ {err}")
    st.stop()
else:
    st.success(f"✅ Diccionario conectado: {len(df)} competencias cargadas.", icon="📊")

# --- FORMULARIO ---
with st.container():
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        t = st.text_input("Nombre del Cargo", value="Analista de Ventas")
    with col2:
        l = st.selectbox("Nivel de Seniority", ["Junior (0-2 años)", "Semi-Senior (3-5 años)", "Senior (5+ años)", "Líder/Gerente"])
    with col3:
        s = st.text_input("Habilidad Crítica / Foco del Rol", placeholder="Ej: Expansión de mercado...")

    # --- LÓGICA DE VALIDACIÓN AMPLIADA ---
    # Aquí hemos agregado todas las palabras que pediste y más variaciones
    palabras_clave_altas = [
        "gerente", "manager", "director", "jefe", "lead", "head", 
        "vp", "vicepresidente", "president", "presidente",
        "coordinador", "supervisor", "subgerente", "encargado"
    ]
    
    # Verificamos si alguna de esas palabras está en el título escrito por el usuario
    es_cargo_alto = any(palabra in t.lower() for palabra in palabras_clave_altas)
    es_nivel_bajo = "Junior" in l
    
    advertencia = False
    if es_cargo_alto and es_nivel_bajo:
        advertencia = True
        st.warning(
            f"⚠️ **Posible Inconsistencia:** El cargo **'{t}'** suele requerir experiencia de liderazgo, "
            f"pero has seleccionado nivel **'Junior'**. La IA ajustará las expectativas o sugerirá un cambio.", 
            icon="🚨"
        )

    btn = st.button("✨ Generar Perfil de Puesto Profesional", type="primary", use_container_width=True)

if btn:
    with st.spinner("🧠 Analizando coherencia del puesto y diseñando perfil..."):
        err_ai, res = run_jobcraft_ai(api_key, t, l, s, df)
        
        if err_ai: 
            st.error(err_ai)
        else:
            guardar_datos_en_sheets(res.titulo_puesto, res.nivel, s)
            
            st.divider()
            
            # Encabezado
            st.markdown(f"<h1 style='text-align: center; color: #1E88E5;'>{res.titulo_puesto}</h1>", unsafe_allow_html=True)
            
            # OBSERVACIÓN DE LA IA
            if res.observacion_ia and len(res.observacion_ia) > 5:
                st.warning(f"🤖 **Nota de JobCraft:** {res.observacion_ia}")
            
            st.markdown(f"<p style='text-align: center; font-size: 1.2em;'>Nivel: <b>{res.nivel}</b></p>", unsafe_allow_html=True)
            
            st.info(f"🎯 **Misión del Cargo:** {res.mision_puesto}")
            
            col_izq, col_der = st.columns(2)
            
            with col_izq:
                st.subheader("🚀 Responsabilidades Clave")
                for item in res.responsabilidades_clave:
                    st.markdown(f"✅ {item}")
                
                st.subheader("🧠 Competencias Conductuales (ADN)")
                st.caption("Seleccionadas de tu Diccionario Corporativo:")
                for item in res.competencias_conductuales_seleccionadas:
                    st.markdown(f"🔹 {item}")

            with col_der:
                st.subheader("🛠️ Competencias Técnicas")
                for item in res.competencias_tecnicas:
                    st.markdown(f"🔧 {item}")

                st.subheader("🎓 Requisitos y Formación")
                for item in res.requisitos_formacion:
                    st.markdown(f"🎓 {item}")

            st.divider()
            st.subheader("📈 Indicadores de Éxito (KPIs)")
            
            if len(res.kpis_sugeridos) > 0:
                kpi_cols = st.columns(len(res.kpis_sugeridos))
                for idx, kpi in enumerate(res.kpis_sugeridos):
                    with kpi_cols[idx]:
                        st.success(f"📊 {kpi}")

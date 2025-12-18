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
# 1. ESQUEMA DE DATOS (Mantenemos V4 que funciona perfecto)
# ---------------------------------------------------------
class JobDescriptionV4(BaseModel):
    titulo_puesto: str = Field(description="El título que se mostrará en el perfil.")
    nivel: str = Field(description="Nivel de seniority del puesto.")
    titulo_oficial_match: str = Field(description="El título exacto encontrado en el catálogo oficial.")
    origen_titulo: str = Field(description="Debe decir 'ESTANDARIZADO' o 'NUEVO'.")
    mision_puesto: str = Field(description="Propósito principal del cargo.")
    responsabilidades_clave: list[str] = Field(description="5-7 funciones principales.")
    competencias_conductuales_seleccionadas: list[str] = Field(description="Las 4-5 competencias seleccionadas.")
    competencias_tecnicas: list[str] = Field(description="Habilidades duras.")
    requisitos_formacion: list[str] = Field(description="Formación académica.")
    kpis_sugeridos: list[str] = Field(description="KPIs.")
    observacion_ia: str = Field(description="Explicación de la equivalencia.")

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
        lista_formateada = [f"{row['Cargo']} ({row.get('Nivel', 'N/A')})" for row in data]
        return "\n".join(lista_formateada), None
    except Exception as e:
        return "", f"Nota: No se encontró hoja de perfiles base ({e}). Se generará libremente."

# ---------------------------------------------------------
# 3. CEREBRO DE LA IA (PERFIL TÉCNICO)
# ---------------------------------------------------------
def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str, competencias_df: pd.DataFrame, lista_perfiles_base: str):
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
            2. SI ENCUENTRAS COINCIDENCIA:
               - 'titulo_puesto': Mantén el nombre que pidió el usuario.
               - 'titulo_oficial_match': Pon el nombre oficial del catálogo.
               - 'origen_titulo': "ESTANDARIZADO".
               - 'observacion_ia': "Este puesto es equivalente a [Titulo Oficial] en el Catálogo Maestro".
            3. SI NO HAY COINCIDENCIA:
               - 'titulo_puesto': El solicitado por el usuario.
               - 'titulo_oficial_match': "N/A"
               - 'origen_titulo': "NUEVO".
            
            INSTRUCCIONES DE CONTENIDO:
            4. Usa las competencias del diccionario adjunto.
            5. Genera Misión, Responsabilidades y KPIs profesionales.
            
            Genera JSON estricto.
            """
            
            config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=JobDescriptionV4)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
            return None, JobDescriptionV4(**json.loads(response.text))
            
        except Exception as e:
            if "503" in str(e) or "overloaded" in str(e).lower() or "429" in str(e):
                time.sleep(2)
                continue 
            else:
                return f"Error AI: {e}", None

    return "El servidor de IA está muy ocupado. Por favor intenta en unos segundos.", None

# ---------------------------------------------------------
# 3.1 CEREBRO DE LA IA (MODO RECLUTADOR / LINKEDIN) - ¡NUEVO!
# ---------------------------------------------------------
def generate_linkedin_post(api_key: str, job_data: JobDescriptionV4):
    try:
        client = genai.Client(api_key=api_key)
        
        # Le pasamos los datos del perfil generado
        prompt = f"""
        Actúa como un Copywriter Experto en Employer Branding y LinkedIn.
        
        TAREA:
        Escribe un POST DE LINKEDIN viral y atractivo para buscar candidatos para el siguiente puesto:
        
        - Título: {job_data.titulo_puesto} ({job_data.nivel})
        - Misión: {job_data.mision_puesto}
        - Habilidades Clave: {', '.join(job_data.competencias_tecnicas[:3])} y {', '.join(job_data.competencias_conductuales_seleccionadas[:2])}
        
        ESTRUCTURA DEL POST:
        1. **Gancho (Hook):** Una pregunta o frase impactante para captar atención.
        2. **El Reto:** Describe brevemente el desafío (usando la misión).
        3. **Qué buscamos:** Punteo rápido de lo esencial.
        4. **Llamado a la Acción (CTA):** "Envía tu CV a..." o "Postúlate aquí".
        5. **Hashtags:** 3-5 hashtags relevantes.
        
        TONO: Profesional pero cercano, dinámico y moderno. Usa Emojis estratégicos.
        """
        
        # Aquí no necesitamos JSON, solo texto plano
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"No se pudo generar el post: {e}"

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
# 5. FUNCION AUXILIAR PARA DESCARGAR TEXTO
# ---------------------------------------------------------
def convert_to_text(res):
    # Creamos un formato de texto bonito para descargar
    texto = f"""
PERFIL DE PUESTO: {res.titulo_puesto.upper()}
--------------------------------------------------
Nivel: {res.nivel}
Misión: {res.mision_puesto}

RESPONSABILIDADES CLAVE:
{chr(10).join(['- ' + item for item in res.responsabilidades_clave])}

COMPETENCIAS CONDUCTUALES (ADN):
{chr(10).join(['- ' + item for item in res.competencias_conductuales_seleccionadas])}

COMPETENCIAS TÉCNICAS:
{chr(10).join(['- ' + item for item in res.competencias_tecnicas])}

REQUISITOS DE FORMACIÓN:
{chr(10).join(['- ' + item for item in res.requisitos_formacion])}

KPIs SUGERIDOS:
{chr(10).join(['- ' + item for item in res.kpis_sugeridos])}

--------------------------------------------------
Generado por JobCraft AI
    """
    return texto

# ---------------------------------------------------------
# 6. INTERFAZ GRÁFICA
# ---------------------------------------------------------
st.set_page_config(page_title="JobCraft AI Pro", layout="wide", page_icon="👔") 

st.markdown("## 👔 JobCraft AI: Suite de Reclutamiento")
st.markdown("---")

api_key = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else None
if not api_key:
    st.error("⚠️ Falta API KEY en Secrets")
    st.stop()

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

    btn = st.button("✨ Generar Perfil Técnico", type="primary", use_container_width=True)

# Lógica principal
if btn:
    # Usamos session_state para guardar el resultado y que no se borre al tocar otros botones
    st.session_state['job_result'] = None 
    with st.spinner("🔍 Diseñando perfil..."):
        err_ai, res = run_jobcraft_ai(api_key, t, l, s, df_comp, txt_perfiles)
        
        if err_ai: 
            st.error(err_ai)
        else:
            st.session_state['job_result'] = res # Guardamos en memoria
            
            # Guardado en Sheets
            origen_seguro = getattr(res, 'origen_titulo', 'NUEVO')
            nivel_seguro = getattr(res, 'nivel', l)
            guardar_datos_en_sheets(res.titulo_puesto, nivel_seguro, origen_seguro)

# --- MOSTRAR RESULTADOS SI EXISTEN EN MEMORIA ---
if 'job_result' in st.session_state and st.session_state['job_result']:
    res = st.session_state['job_result']
    
    st.divider()
    
    # --- BOTÓN DE DESCARGA (Opción 2) ---
    col_res_header, col_download = st.columns([3, 1])
    with col_res_header:
        if getattr(res, 'origen_titulo', 'NUEVO') == "ESTANDARIZADO":
            st.success(f"✅ PUESTO VALIDADO EN CATÁLOGO")
        else:
            st.info(f"🆕 NUEVO PUESTO CREADO")
    
    with col_download:
        # Preparamos el texto
        texto_descarga = convert_to_text(res)
        st.download_button(
            label="💾 Descargar Ficha (.txt)",
            data=texto_descarga,
            file_name=f"Perfil_{res.titulo_puesto}.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.markdown(f"<h1 style='text-align: center; color: #1E88E5;'>{res.titulo_puesto}</h1>", unsafe_allow_html=True)

    # Notas y Alertas
    titulo_oficial = getattr(res, 'titulo_oficial_match', 'N/A')
    obs_ia = getattr(res, 'observacion_ia', '')
    
    if titulo_oficial != "N/A" and titulo_oficial != res.titulo_puesto:
            st.warning(f"⚠️ **Nota:** Oficialmente equivale a **'{titulo_oficial}'**.")
    elif obs_ia:
            st.caption(f"🤖 Nota: {obs_ia}")

    st.markdown(f"<p style='text-align: center;'>Nivel: <b>{getattr(res, 'nivel', 'N/A')}</b></p>", unsafe_allow_html=True)
    st.info(f"🎯 **Misión:** {res.mision_puesto}")
    
    # Columnas de contenido
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
    
    # --- SECCIÓN MODO RECLUTADOR (Opción 3) ---
    st.markdown("### 📢 Modo Reclutador")
    st.caption("¿Listo para publicar? Genera un anuncio optimizado para redes sociales.")
    
    if st.button("🚀 Generar Post para LinkedIn"):
        with st.spinner("✍️ Redactando anuncio viral..."):
            post_linkedin = generate_linkedin_post(api_key, res)
            
            st.markdown("#### 📝 Tu Post sugerido:")
            st.text_area("Copia este texto para LinkedIn:", value=post_linkedin, height=300)
            st.balloons()

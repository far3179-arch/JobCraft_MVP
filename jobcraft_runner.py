import os
import json
import pandas as pd
import yagmail
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# =========================================================
# 1. DEFINICIÓN DEL ESQUEMA DE SALIDA (El Contrato JSON)
# =========================================================
class JobDescription(BaseModel):
    """Esquema de la descripción de puesto de trabajo generado por el agente JobCraft AI."""
    titulo_puesto: str = Field(description="Título completo y claro del puesto.")
    nivel: str = Field(description="Nivel de experiencia (Ej: Junior, Intermedio, Senior, Manager).")
    resumen_puesto: str = Field(description="Descripción concisa y atractiva del rol y su impacto.")
    responsabilidades_clave: list[str] = Field(description="Lista de 5 a 7 responsabilidades principales del rol.")
    requisitos_minimos: list[str] = Field(description="Lista de 5 requisitos técnicos y de habilidades blandas indispensables.")
    competencias_deseables: list[str] = Field(description="Lista de 2 a 3 competencias o certificaciones que añaden valor.")
    palabras_clave_seo_rrhh: list[str] = Field(description="Lista de 3 a 5 palabras clave optimizadas para búsquedas de empleo.")

# =========================================================
# 2. CONFIGURACIÓN Y FUNCIÓN PRINCIPAL DEL AGENTE
# =========================================================

def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str):
    """Función que ejecuta el Agente JobCraft AI."""

    # 2.1 Configuración de la clave
    os.environ['GEMINI_API_KEY'] = api_key

    try:
        client = genai.Client()
    except Exception as e:
        print(f"Error: No se pudo conectar a Gemini. Asegúrate de que la clave API es correcta. Error: {e}")
        return

    # --- El Prompt Maestro (La Lógica del Agente) ---
    prompt = f"""
    Eres el Agente de Diseño de Puestos de Trabajo Inteligente (JobCraft AI). 
    Tu objetivo es generar una descripción de puesto completa, atractiva y estructurada 
    para el sector de Recursos Humanos. El resultado debe ser 100% libre de sesgos.

    **ENTRADAS DEL USUARIO:**
    1.  Título del Puesto: {title}
    2.  Nivel Requerido: {level}
    3.  Habilidad Crítica de Enfoque: {critical_skill}

    **TAREAS CLAVE DEL AGENTE (Simulación de la tripulación):**
    1.  **Analista de Roles:** Identifica las responsabilidades y requisitos de mercado para el puesto y nivel indicados.
    2.  **Escritor Persuasivo:** Redacta un resumen del puesto conciso y profesional.
    3.  **Garante de Estructura:** Asegura que las `responsabilidades_clave` integren la `Habilidad Crítica de Enfoque`.

    **REGLA DE SALIDA VITAL:** DEBES devolver la respuesta únicamente en el formato JSON que te indico, SIN añadir ningún texto explicativo o introducción.
    """

    # Configuración para forzar la salida JSON usando el esquema Pydantic
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=JobDescription,
    )

    print(f"🤖 Ejecutando JobCraft AI para: {title} ({level})...")

    # Llamada a la API
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=config
    )

    # Procesar la respuesta
    json_data = response.text

    try:
        # **ESTE BLOQUE DE TRY ESTÁ CORREGIDO**
        job_description_object = JobDescription.model_validate_json(json_data)
        data_dict = job_description_object.model_dump()
        
        # --- LÓGICA DE EXPORTACIÓN DE DATOS (EL PASO DE ACCIÓN) ---
        
        # 1. Creamos un DataFrame (tabla) a partir de los datos.
        #    Normalizamos para que las listas (responsabilidades, requisitos) se unan en una sola cadena.
        data_dict_flat = {k: ', '.join(v) if isinstance(v, list) else v for k, v in data_dict.items()}
        
        # 2. Convertimos el diccionario a un DataFrame (tabla de pandas)
        df = pd.DataFrame([data_dict_flat])
        
        # 3. Guardamos la tabla en un archivo CSV en la carpeta del proyecto.
        output_file = "jobcraft_output.csv"
        
        # Usamos mode='a' para "append" (añadir al archivo si ya existe) y header=False para evitar repetir encabezados.
        if os.path.exists(output_file):
            df.to_csv(output_file, index=False, mode='a', header=False, encoding='utf-8')
        else:
            # Si no existe, creamos el archivo con los encabezados (header=True)
            df.to_csv(output_file, index=False, encoding='utf-8')
            
        print(f"\n✅ MVP Generado y Exportado con Éxito por JobCraft AI:")
        print(f"   - Título: {data_dict['titulo_puesto']}")
        print(f"   - Archivo: {output_file} (Guardado/Actualizado en la carpeta JobCraft_MVP)")

        # --- DEVUELVE EL JSON TEXTUAL PARA EL CORREO ---
        job_output = json.dumps(data_dict, indent=2, ensure_ascii=False) 
        return job_output
        
    except Exception as e:
        print(f"❌ Error crítico en el procesamiento o validación del JSON: {e}")
        print(f"Salida cruda del modelo: {json_data}")
        # --- DEVUELVE None EN CASO DE ERROR ---
        return None

# =========================================================
# 2.3 FUNCIÓN DE ACCIÓN EXTERNA: Envío de Correo
# =========================================================
def send_job_email(recipient: str, title: str, body: str, sender_email: str, app_password: str):
    """Envía el resultado de la descripción de puesto por correo electrónico."""

    # Simulación de Conexión a un Servidor de Publicación
    print(f"\n📧 Conectando para enviar la descripción a: {recipient}...")

    try:
        # Conexión y autenticación con la Contraseña de Aplicación
        yag = yagmail.SMTP(sender_email, app_password)

        # Contenido del correo
        subject = f"[JobCraft AI] Puesto Generado: {title}"

        # Enviamos el contenido en el cuerpo del correo
        yag.send(
            to=recipient,
            subject=subject,
            contents=body
        )
        print(f"✅ Notificación enviada exitosamente al gerente/publicador ({recipient}).")

    except Exception as e:
        print(f"❌ ERROR: Fallo al enviar el correo. Revisa tu Contraseña de Aplicación.")
        print(f"Error detallado: {e}")
        
# =========================================================
# 3. EJECUCIÓN DEL PROCESADOR DE LOTES (BATCH RUNNER)
# =========================================================

# **¡IMPORTANTE! PEGA TU CLAVE API DE GEMINI AQUÍ:**
MY_GEMINI_API_KEY = "PEGA_TU_CLAVE_AQUI_A_PARTIR_DE_AIza..."
# Si ya la pegaste, pégala de nuevo arriba.

# 3.1 Función que lee el archivo de entrada y procesa cada puesto
def process_job_batch(api_key: str, input_file: str):
    """
    Lee el archivo CSV de entrada y procesa cada puesto de trabajo
    usando el agente JobCraft AI.
    """
    # --- CONFIGURACIÓN DE CORREO ---
    # ¡IMPORTANTE! Reemplaza los placeholders con tu información:
    SENDER_EMAIL = "TU_CORREO_GMAIL@gmail.com"  # <- Pega tu correo aquí
    APP_PASSWORD = "TU_CLAVE_DE_APLICACION_DE_16_CARACTERES"  # <- Pega tu clave de 16 caracteres aquí
    RECIPIENT_EMAIL = "correo_del_gerente_destino@dominio.com" # <- Pega un correo de destino de prueba
    # -----------------------------
    
    if not os.path.exists(input_file):
        print(f"\n🚨 ERROR CRÍTICO: El archivo de entrada '{input_file}' no fue encontrado.")
        print("Asegúrate de haber creado el archivo input_jobs.csv en la carpeta del proyecto.")
        return

    print(f"\n📚 Leyendo lista de tareas desde '{input_file}'...")
    
    try:
        # Leer el archivo CSV en un DataFrame de pandas
        jobs_to_process = pd.read_csv(input_file)
        total_jobs = len(jobs_to_process)
        
        print(f"✅ Tareas encontradas: {total_jobs} puestos listos para procesar.")
        
        # Iterar sobre cada fila del DataFrame
        for index, row in jobs_to_process.iterrows():
            title = row['title']
            level = row['level']
            skill = row['critical_skill']
            
            print(f"\n--- 🔄 Procesando Tarea {index + 1} de {total_jobs} ---")
            
            # Llama a la función principal del agente y guarda el JSON de salida
            job_json_output = run_jobcraft_ai(api_key, title, level, skill)
            
            # --- ACCIÓN ADICIONAL DE ENVÍO DE CORREO (Simulación de Publicación) ---
            # Enviamos el correo solo para el primer puesto (index == 0) para no saturar el buzón.
            if job_json_output and index == 0:
                send_job_email(
                    recipient=RECIPIENT_EMAIL,
                    title=title,
                    body=job_json_output,
                    sender_email=SENDER_EMAIL,
                    app_password=APP_PASSWORD
                )
            
        # Esta línea estaba mal indentada en el código anterior. Debe estar fuera del bucle 'for'.
        print(f"\n🎉 Lote de {total_jobs} puestos procesado con éxito.") 
        
    except Exception as e:
        print(f"\n❌ ERROR: Ocurrió un error durante el procesamiento del lote: {e}")
        print("Verifica que las columnas del CSV de entrada se llamen: title, level, critical_skill")

# 3.2 Ejecución Principal
if MY_GEMINI_API_KEY == "PEGA_TU_CLAVE_AQUI_A_PARTIR_DE_AIza...":
     print("\n🚨 ERROR: Por favor, pega tu Clave API de Gemini en la línea 170 del código.")
else:
     # EL PUNTO DE ENTRADA AL PROCESO DE BATCH
     process_job_batch(MY_GEMINI_API_KEY, "input_jobs.csv")
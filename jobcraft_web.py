import time # <--- Asegúrate de tener esto importado al inicio del archivo

# ... (El resto de tus imports)

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
            
            # PROMPT (Mantenemos el mismo que ya funcionaba perfecto)
            prompt = f"""
            Actúa como Director de Estructura Organizacional.
            Objetivo: Definir perfil para: '{title}' (Nivel: {level}).
            Habilidad Crítica: {critical_skill}
            
            --- CATÁLOGO OFICIAL ---
            {lista_perfiles_base}
            ------------------------
            
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
            4. Usa las competencias del diccionario adjunto.
            5. Genera Misión, Responsabilidades y KPIs profesionales.
            
            Genera JSON estricto.
            """
            
            config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=JobDescription)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
            return None, JobDescription(**json.loads(response.text))
            
        except Exception as e:
            # Si el error es 503 (Sobrecarga), esperamos y reintentamos
            if "503" in str(e) or "overloaded" in str(e).lower():
                time.sleep(2) # Espera 2 segundos antes de reintentar
                continue 
            else:
                # Si es otro error (ej: credenciales), fallamos inmediatamente
                return f"Error AI: {e}", None

    return "El servidor de IA está muy ocupado. Por favor intenta en unos segundos.", None

# --- ALMA 4.0: NEW GOOGLE GENAI SDK ---
print("🚀 SYSTEM STARTUP: Инициализация...", flush=True)

import warnings
warnings.filterwarnings("ignore")

import os
import glob
import smtplib
import shutil
import pandas as pd
import geopandas as gpd
# НОВАЯ БИБЛИОТЕКА
from google import genai
from google.genai import types

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from mergin import MerginClient

print("✅ Библиотеки загружены.", flush=True)

# --- НАСТРОЙКИ ---
MERGIN_PROJECT = "ALMA_exmachina/alma_bot"
PROJECT_PATH = "./project"
INCIDENTS_FILE = "Инцидент.gpkg" 
PHOTOS_FILE = "photos.gpkg"
LAWS_FOLDER = "laws"
GARDEN_KEYWORDS = ["сады", "orchards", "защищенные", "проверке", "возвращенный"]

def get_env(name):
    val = os.environ.get(name)
    if not val: print(f"⚠️ Секрет {name} не найден!")
    return val

def load_knowledge_base():
    full_text = ""
    files = sorted(glob.glob(os.path.join(LAWS_FOLDER, "*.txt")))
    if not files: return "База законов пуста."
    print(f"📚 База знаний: {len(files)} файлов.", flush=True)
    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                full_text += f"\n\n--- ДОКУМЕНТ: {os.path.basename(f_path)} ---\n" + f.read()
        except: pass
    return full_text

def get_legal_prompt(inc_type, desc, cad_id, coords, legal_db):
    return f"""
    РОЛЬ: Юрист-эколог движения ALMA.
    НАРУШЕНИЕ: {inc_type}. ОПИСАНИЕ: {desc}. ЛОКАЦИЯ: {cad_id} ({coords}).
    
    БАЗА ЗНАНИЙ:
    {legal_db}

    ЗАДАЧА (СТРОГО 2 ЧАСТИ):
    1. КОНСУЛЬТАЦИЯ ВОЛОНТЕРУ:
       - Кратко: какая статья нарушена.
       - Совет: что снять на фото.
    
    2. ЗАЯВЛЕНИЕ В АКИМАТ:
       - Официальный стиль.
       - ЦИТИРУЙ статьи из Базы Знаний.
       - Укажи координаты.
       - Подпись: "Волонтер движения ALMA".
    """

def send_email_with_attachments(to_email, subject, body, attachment_paths):
    sender = get_env('MERGIN_USER') 
    password = get_env('GMAIL_APP_PASS')
    if not sender or not password: return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = f"{sender}, {to_email}"
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    for f_path in attachment_paths:
        if f_path and os.path.exists(f_path):
            try:
                with open(f_path, 'rb') as f:
                    msg.attach(MIMEImage(f.read(), name=os.path.basename(f_path)))
            except: pass

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(sender, password)
            s.send_message(msg)
        print(f"   ✉️ Почта отправлена: {to_email}", flush=True)
    except Exception as e:
        print(f"   ❌ Ошибка почты: {e}", flush=True)

def main():
    print("🚀 ЗАПУСК ALMA 4.0 (NEW GENAI SDK)", flush=True)
    
    mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
    
    # --- ИНИЦИАЛИЗАЦИЯ НОВОГО КЛИЕНТА GOOGLE ---
    try:
        client = genai.Client(api_key=get_env('GEMINI_API_KEY'))
        print("✅ Google Client инициализирован.")
    except Exception as e:
        print(f"❌ Ошибка клиента AI: {e}")
        return

    # Загрузка законов
    legal_knowledge = load_knowledge_base()

    # Скачивание проекта
    if os.path.exists(PROJECT_PATH): shutil.rmtree(PROJECT_PATH)
    mc.download_project(MERGIN_PROJECT, PROJECT_PATH)

    try:
        incidents = gpd.read_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE))
        photos_gdf = gpd.read_file(os.path.join(PROJECT_PATH, PHOTOS_FILE))
    except Exception as e:
        print(f"❌ Ошибка таблиц: {e}"); return

    if 'is_sent' not in incidents.columns: incidents['is_sent'] = 0
    incidents['is_sent'] = incidents['is_sent'].fillna(0).astype(int)
    
    new_recs = incidents[incidents['is_sent'] == 0]
    if new_recs.empty: 
        print("✅ Новых данных нет (Синхронизируйте приложение).", flush=True)
        return

    garden_files = []
    for f in glob.glob(f"{PROJECT_PATH}/*.gpkg"):
        if os.path.basename(f) not in [INCIDENTS_FILE, PHOTOS_FILE]:
            if any(k in os.path.basename(f).lower() for k in GARDEN_KEYWORDS):
                garden_files.append(f)

    print(f"⚡ Обработка {len(new_recs)} дел.", flush=True)

    for idx, row in new_recs.iterrows():
        uid = row.get('unique-id')
        print(f"\n--- Дело № {uid} ---", flush=True)
        
        # Фото
        attachments = []
        rel_photos = photos_gdf[photos_gdf['external_pk'] == uid]
        if not rel_photos.empty:
            for _, p_row in rel_photos.iterrows():
                path = p_row.get('photo')
                if path:
                    candidates = [os.path.join(PROJECT_PATH, path), os.path.join(PROJECT_PATH, os.path.basename(path))]
                    for c in candidates:
                        if os.path.exists(c): attachments.append(c); break

        # Координаты
        if incidents.crs != "EPSG:4326":
            p_geo = gpd.GeoDataFrame([row], crs=incidents.crs).to_crs("EPSG:4326").iloc[0].geometry
        else:
            p_geo = row.geometry
        coords_str = f"{p_geo.y:.6f}, {p_geo.x:.6f}"
        
        # Кадастр
        cad_id = "Кадастровый номер не установлен"
        for g_file in garden_files:
            try:
                temp_gdf = gpd.read_file(g_file).to_crs("EPSG:4326")
                match = temp_gdf[temp_gdf.contains(p_geo)]
                if not match.empty:
                    if 'layer' in match.columns: val = match.iloc[0]['layer']
                    else: val = None
                    if val: cad_id = str(val)
                    else: cad_id = os.path.splitext(os.path.basename(g_file))[0]
                    break
            except: pass
        if cad_id == "Кадастровый номер не установлен": cad_id = f"Участок {coords_str}"
        
        # ГЕНЕРАЦИЯ (НОВЫЙ МЕТОД)
        prompt = get_legal_prompt(row.get('incident_type'), row.get('description'), cad_id, coords_str, legal_knowledge)
        
        try:
            print("   ⏳ Gemini 1.5 Flash думает...", flush=True)
            # Новый синтаксис вызова
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    safety_settings=[
                        types.SafetySetting(
                            category='HARM_CATEGORY_HATE_SPEECH',
                            threshold='BLOCK_NONE'
                        ),
                        types.SafetySetting(
                            category='HARM_CATEGORY_DANGEROUS_CONTENT',
                            threshold='BLOCK_NONE'
                        ),
                        types.SafetySetting(
                            category='HARM_CATEGORY_HARASSMENT',
                            threshold='BLOCK_NONE'
                        ),
                        types.SafetySetting(
                            category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
                            threshold='BLOCK_NONE'
                        )
                    ]
                )
            )
            text = response.text
            print("   ✅ Текст готов!", flush=True)
        except Exception as e:
            err_msg = f"ОШИБКА ГЕНЕРАЦИИ (NEW SDK): {e}"
            print(f"   ❌ {err_msg}", flush=True)
            text = f"{err_msg}\n\nПопробуйте позже."

        send_email_with_attachments(row.get('volunteer_email'), f"ALMA КОНСУЛЬТАЦИЯ: {cad_id}", text, attachments)
        
        for f in attachments:
            try: os.remove(f)
            except: pass

        incidents.at[idx, 'cadastre_id'] = cad_id
        incidents.at[idx, 'ai_complaint'] = text
        incidents.at[idx, 'is_sent'] = 1

    incidents.to_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE), driver="GPKG")
    mc.push_project(PROJECT_PATH)
    print("💾 Готово. Синхронизация.", flush=True)

if __name__ == "__main__":
    main()

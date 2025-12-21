import os
import glob
import smtplib
import shutil
import pandas as pd
import geopandas as gpd
import google.generativeai as genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from mergin import MerginClient
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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
    print(f"📚 Загрузка базы ({len(files)} файлов)...")
    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                full_text += f"\n\n--- ДОКУМЕНТ: {os.path.basename(f_path)} ---\n" + f.read()
        except: pass
    return full_text

def get_legal_prompt(inc_type, desc, cad_id, coords, legal_db):
    return f"""
    РОЛЬ: Юрист-эколог ALMA.
    НАРУШЕНИЕ: {inc_type}. ДЕТАЛИ: {desc}. МЕСТО: {cad_id} ({coords}).
    БАЗА ЗНАНИЙ: {legal_db}
    
    ЗАДАЧА:
    1. КОНСУЛЬТАЦИЯ ВОЛОНТЕРУ (Кратко: какая статья нарушена, что снять на фото).
    2. ЗАЯВЛЕНИЕ В АКИМАТ (Официально, с цитатами законов, требованием проверки).
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
        print(f"   ✉️ Почта отправлена: {to_email}")
    except Exception as e:
        print(f"   ❌ Ошибка почты: {e}")

def main():
    print("🚀 ALMA 3.7: DIAGNOSTIC MODE")
    
    mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
    genai.configure(api_key=get_env('GEMINI_API_KEY'))
    
    # --- НАСТРОЙКИ БЕЗОПАСНОСТИ ---
    safety = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # --- УМНЫЙ ВЫБОР МОДЕЛИ ---
    target_model = 'gemini-1.5-flash'
    try:
        print(f"🛠 Проверка модели {target_model}...")
        model = genai.GenerativeModel(model_name=target_model, safety_settings=safety)
        # Тестовый запрос. Если упадет - перейдем к плану Б
        model.generate_content("test") 
        print(f"✅ Модель {target_model} активна!")
    except Exception as e:
        print(f"⚠️ Модель {target_model} недоступна: {e}")
        
        # ДИАГНОСТИКА: ЧТО ВООБЩЕ ЕСТЬ?
        print("\n📋 ДОСТУПНЫЕ МОДЕЛИ (ИЗ ЛОГА):")
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    print(f"   - {m.name}")
        except: pass

        # ПЛАН Б: Переключаемся на GEMINI-PRO (она работает всегда)
        print("\n🔄 ВКЛЮЧАЮ РЕЗЕРВ: gemini-pro")
        model = genai.GenerativeModel(model_name='gemini-pro', safety_settings=safety)

    # --- ДАЛЕЕ ОБЫЧНЫЙ КОД ---
    legal_knowledge = load_knowledge_base()
    if os.path.exists(PROJECT_PATH): shutil.rmtree(PROJECT_PATH)
    mc.download_project(MERGIN_PROJECT, PROJECT_PATH)

    try:
        incidents = gpd.read_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE))
        photos_gdf = gpd.read_file(os.path.join(PROJECT_PATH, PHOTOS_FILE))
    except: return

    if 'is_sent' not in incidents.columns: incidents['is_sent'] = 0
    incidents['is_sent'] = incidents['is_sent'].fillna(0).astype(int)
    
    new_recs = incidents[incidents['is_sent'] == 0]
    if new_recs.empty: print("✅ Новых данных нет."); return

    garden_files = []
    for f in glob.glob(f"{PROJECT_PATH}/*.gpkg"):
        if os.path.basename(f) not in [INCIDENTS_FILE, PHOTOS_FILE]:
            if any(k in os.path.basename(f).lower() for k in GARDEN_KEYWORDS):
                garden_files.append(f)

    print(f"⚡ Обработка {len(new_recs)} дел.")

    for idx, row in new_recs.iterrows():
        uid = row.get('unique-id')
        print(f"\n--- Дело № {uid} ---")
        
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
        
        # ГЕНЕРАЦИЯ
        prompt = get_legal_prompt

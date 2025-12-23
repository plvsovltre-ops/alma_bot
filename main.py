# --- ALMA 8.4: DIAGNOSTIC MODE ---
print("🚀 SYSTEM STARTUP...", flush=True)

import warnings
warnings.filterwarnings("ignore")

import os
import glob
import smtplib
import shutil
import time
import pandas as pd
import geopandas as gpd
from datetime import datetime
from google import genai
from google.genai import types

# Гугл Таблицы
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from mergin import MerginClient

print("✅ Библиотеки загружены.", flush=True)

# --- НАСТРОЙКИ ---
MERGIN_PROJECT = "ALMA_exmachina/alma_bot"
PROJECT_PATH = "./project"
ARCHIVE_PATH = "./ALMA_ARCHIVE"
GOOGLE_SHEET_NAME = "ALMA_Registry"
CREDENTIALS_FILE = "service_account.json"

INCIDENTS_FILE = "Инцидент.gpkg" 
PHOTOS_FILE = "photos.gpkg"
LAWS_FOLDER = "laws"
GARDEN_KEYWORDS = ["сады", "orchards", "защищенные", "проверке", "возвращенный"]
MAX_LAW_CHARS = 200000 

MODEL_CANDIDATES = [
    "gemini-1.5-flash-002",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]

FILE_MAPPING = {
    "00_guidelines.txt": "Руководство и Стратегия ALMA",
    "01_land_code.txt": "Земельный кодекс РК",
    "02_eco_code.txt": "Экологический кодекс РК",
    "03_water_code.txt": "Водный кодекс РК",
    "04_adm_code.txt": "КоАП РК",
    "05_crime_code.txt": "Уголовный кодекс РК",
    "06_law_architecture.txt": "Закон об архитектуре",
    "07_almaty_rules.txt": "ПЗЗ и Генплан Алматы",
    "08_biodiversity.txt": "Биоразнообразие",
    "10_presidential_acts.txt": "Акты Президента",
    "11_paris_agreement.txt": "Парижское соглашение",
    "12_biodiversity_convention.txt": "Конвенция о биоразнообразии",
    "13_aarhus_convention.txt": "Орхусская конвенция",
    "14_land_inspection.txt": "Полномочия Земельной инспекции"
}

os.makedirs(ARCHIVE_PATH, exist_ok=True)
os.makedirs(os.path.join(ARCHIVE_PATH, "PHOTOS"), exist_ok=True)

def get_env(name):
    val = os.environ.get(name)
    if not val: print(f"⚠️ ВНИМАНИЕ: Секрет {name} не найден в настройках!", flush=True)
    return val

def log_to_google_sheet(data_row):
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ ОШИБКА: Файл {CREDENTIALS_FILE} не найден. Таблицы не работают.", flush=True)
        return

    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client_gs = gspread.authorize(creds)
        sheet = client_gs.open(GOOGLE_SHEET_NAME).sheet1
        if not sheet.cell(1, 1).value:
            headers = ["Дата", "ID Дела", "Кадастр", "Тип нарушения", "Координаты", "Ответ AI (RU)", "Ответ AI (KZ)", "Локальный путь к фото"]
            sheet.append_row(headers)
        sheet.append_row(data_row)
        print("   📊 Данные успешно записаны в Google Sheets.", flush=True)
    except Exception as e:
        print(f"   ❌ ОШИБКА Google Sheets: {e}", flush=True)

def load_knowledge_base():
    full_text = ""
    files = sorted(glob.glob(os.path.join(LAWS_FOLDER, "*.txt")))
    if not files: 
        print("⚠️ ПРЕДУПРЕЖДЕНИЕ: Папка laws пуста или не найдена.", flush=True)
        return "База законов пуста."
    
    total_chars = 0
    print(f"📚 Читаю законы ({len(files)} файлов)...", flush=True)
    for f_path in files:
        if total_chars >= MAX_LAW_CHARS: break
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                content = f.read()
                filename_raw = os.path.basename(f_path)
                doc_title = FILE_MAPPING.get(filename_raw, filename_raw)
                if "00_" not in filename_raw and len(content) > 30000:
                    content = content[:30000] + "\n...[СОКР]..."
                full_text += f"\n\n--- ДОКУМЕНТ: {doc_title} ---\n" + content
                total_chars += len(content)
        except: pass
    return full_text

def get_legal_prompt(lang, inc_type, desc, cad_id, coords, legal_db):
    if lang == "RU":
        lang_instruction = "1. ЯЗЫК ОТВЕТА: РУССКИЙ. Отвечай строго на русском."
        glossary = ""
        subject_hint = "ЗАЯВЛЕНИЕ"
    else:
        lang_instruction = "1. ЯЗЫК ОТВЕТА: КАЗАХСКИЙ (Қазақ тілі). Отвечай строго на казахском."
        glossary = """
        ТЕРМИНОЛОГИЯ (ГЛОССАРИЙ):
        - "Земельная инспекция (ДУЗР)" -> "Жер ресурстарын басқару департаменті (Жер инспекциясы)".
        - "Нецелевое использование" -> "Мақсатсыз пайдалану".
        - "Признаки нарушения" -> "Бұзушылық белгілері".
        """
        subject_hint = "ӨТІНІШ (ЗАЯВЛЕНИЕ)"

    return f"""
    ТЫ — Юрист-эколог движения ALMA.
    ЗАДАЧА: Проанализировать ФОТО и ОПИСАНИЕ нарушения.
    
    ВВОДНЫЕ ДАННЫЕ:
    - Нарушение: {inc_type}
    - Описание: {desc}
    - Кадастр: {cad_id}
    - Координаты: {coords}
    
    БАЗА ЗНАНИЙ:
    {legal_db}

    ================================================================
    СТРОГАЯ ИНСТРУКЦИЯ:
    {lang_instruction}
    2. ИСТОЧНИКИ: Ссылайся ТОЛЬКО на названия документов (после "--- ДОКУМЕНТ:").
    3. АНАЛИЗ ФОТО: Опиши, что видно на фото.
    4. АЛГОРИТМ: Если это Критическая угроза (Сценарий А), предложи обратиться в ДУЗР.
    {glossary}
    ================================================================
    СТРУКТУРА:
    1. АНАЛИЗ СИТУАЦИИ.
    2. ПРОЕКТ {subject_hint}.
    """

def send_email_with_attachments(to_email, subject, body, attachment_paths):
    sender = get_env('MERGIN_USER') 
    password = get_env('GMAIL_APP_PASS')
    if not sender or not password: 
        print("❌ ОШИБКА: Нет логина/пароля для почты.", flush=True)
        return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = f"{sender}, {to_email}"
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    for f_path in attachment_paths:
        if f_path and os.path.exists(f_path):
            try:
                with open(f_path, 'rb') as f:
                    img_data = f.read()
                    image = MIMEImage(img_data, name=os.path.basename(f_path))
                    msg.attach(image)
            except: pass

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(sender, password)
            s.send_message(msg)
        print(f"   ✉️ Почта отправлена ({subject})", flush=True)
    except Exception as e:
        print(f"   ❌ ОШИБКА отправки почты: {e}", flush=True)

def main():
    print("🚀 ЗАПУСК ALMA 8.4 (DIAGNOSTIC)", flush=True)
    
    # 1. ПРОВЕРКА MERGIN
    try:
        mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
        print("✅ Mergin Maps: Вход выполнен.", flush=True)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА MERGIN: {e}", flush=True)
        return

    # 2. ПРОВЕРКА GEMINI
    try:
        api_key = get_env('GEMINI_API_KEY')
        if not api_key: raise ValueError("Ключ пустой")
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА GEMINI KEY: {e}", flush=True)
        return

    # 3. ПОДБОР МОДЕЛИ
    print("🔍 Проверка связи с нейросетью...", flush=True)
    active_model = None
    for m in MODEL_CANDIDATES:
        try:
            client.models.generate_content(model=m, contents="Ping")
            print(f"   ✅ Модель {m} работает!", flush=True)
            active_model = m
            break
        except Exception as e:
            print(f"   ⚠️ Модель {m} не отвечает: {e}", flush=True)
            continue
            
    if not active_model:
        print("❌ ВСЕ МОДЕЛИ GEMINI НЕДОСТУПНЫ. Проверьте ключ или лимиты.", flush=True)
        return

    legal_knowledge = load_knowledge_base()
    
    if os.path.exists(PROJECT_PATH): shutil.rmtree(PROJECT_PATH)
    try:
        mc.download_project(MERGIN_PROJECT, PROJECT_PATH)
    except Exception as e:
        print(f"❌ Ошибка скачивания проекта: {e}", flush=True); return

    try:
        incidents = gpd.read_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE))
        photos_gdf = gpd.read_file(os.path.join(PROJECT_PATH, PHOTOS_FILE))
    except Exception as e:
        print(f"❌ Ошибка чтения GPKG файлов: {e}", flush=True); return

    if 'is_sent' not in incidents.columns: incidents['is_sent'] = 0
    incidents['is_sent'] = incidents['is_sent'].fillna(0).astype(int)
    new_recs = incidents[incidents['is_sent'] == 0]
    
    if new_recs.empty: 
        print("✅ Новых данных нет. Ожидание...", flush=True); return

    garden_files = []
    for f in glob.glob(f"{PROJECT_PATH}/*.gpkg"):
        if os.path.basename(f) not in [INCIDENTS_FILE, PHOTOS_FILE]:
            if any(k in os.path.basename(f).lower() for k in GARDEN_KEYWORDS):
                garden_files.append(f)

    print(f"⚡ Найдено {len(new_recs)} новых дел.", flush=True)

    for idx, row in new_recs.iterrows():
        uid = str(row.get('unique-id'))
        print(f"\n--- Дело № {uid} ---", flush=True)
        
        attachments = []
        incident_photo_dir = os.path.join(ARCHIVE_PATH, "PHOTOS", f"{datetime.now().strftime('%Y-%m-%d')}_{uid}")
        os.makedirs(incident_photo_dir, exist_ok=True)

        rel_photos = photos_gdf[photos_gdf['external_pk'] == uid]
        if not rel_photos.empty:
            for _, p_row in rel_photos.iterrows():
                original = p_row.get('photo')
                if original:
                    possible_paths = [os.path.join(PROJECT_PATH, original), os.path.join(PROJECT_PATH, os.path.basename(original))]
                    src = next((p for p in possible_paths if os.path.exists(p)), None)
                    if src:
                        dst = os.path.join(incident_photo_dir, os.path.basename(src))
                        shutil.copy2(src, dst)
                        attachments.append(dst)

        if incidents.crs != "EPSG:4326":
            p_geo = gpd.GeoDataFrame([row], crs=incidents.crs).to_crs("EPSG:4326").iloc[0].geometry
        else: p_geo = row.geometry
        coords_str = f"{p_geo.y:.6f}, {p_geo.x:.6f}"
        
        cad_id = "Не определен"
        for g_file in garden_files:
            try:
                temp_gdf = gpd.read_file(g_file).to_crs("EPSG:4326")
                if not temp_gdf[temp_gdf.contains(p_geo)].empty:
                    cad_id = os.path.splitext(os.path.basename(g_file))[0]
                    break
            except: pass

        responses = {"RU": "", "KZ": ""}
        for lang in ["RU", "KZ"]:
            print(f"   🧬 Генерация {lang}...", flush=True)
            prompt = get_legal_prompt(lang, row.get('incident_type'), row.get('description'), cad_id, coords_str, legal_knowledge)
            req = [prompt]
            for img in attachments:
                try:
                    with open(img, 'rb') as f:
                        mime = 'image/png' if img.lower().endswith('.png') else 'image/jpeg'
                        req.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
                except: pass

            try:
                resp = client.models.generate_content(model=active_model, contents=req, config=types.GenerateContentConfig(temperature=0.0))
                responses[lang] = resp.text
                subj = f"ALMA {'КОНСУЛЬТАЦИЯ (RU)' if lang=='RU' else 'КЕҢЕСІ (KZ)'}: {cad_id}"
                send_email_with_attachments(row.get('volunteer_email'), subj, resp.text, attachments)
                time.sleep(2)
            except Exception as e:
                print(f"   ❌ Ошибка генерации {lang}: {e}", flush=True)

        # 3. ЗАПИСЬ В GOOGLE SHEETS
        sheet_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            uid,
            cad_id,
            row.get('incident_type'),
            coords_str,
            responses["RU"],
            responses["KZ"],
            os.path.abspath(incident_photo_dir)
        ]
        log_to_google_sheet(sheet_row)

        incidents.at[idx, 'cadastre_id'] = cad_id
        incidents.at[idx, 'ai_complaint'] = responses["RU"]
        incidents.at[idx, 'is_sent'] = 1

    incidents.to_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE), driver="GPKG")
    mc.push_project(PROJECT_PATH)
    print("💾 Все данные обработаны и отправлены.", flush=True)

if __name__ == "__main__":
    main()

import os
import glob
import smtplib
import pandas as pd
import geopandas as gpd
import google.generativeai as genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mergin import MerginClient
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 1. КОНФИГУРАЦИЯ ---
MERGIN_PROJECT = "ALMA_exmachina/alma_bot
PROJECT_PATH = "./project"
INCIDENTS_FILE = "Инцидент.gpkg"
PHOTOS_FILE = "photos.gpkg"
DRIVE_FOLDER_ID = "1SgDQZdlv_nn0nLfTZWY8r7KyIOKjH2pv" # <--- ОБЯЗАТЕЛЬНО!

# Ключевые слова для поиска садов
GARDEN_KEYWORDS = ["сады", "orchards", "защищенные", "проверке", "возвращенный"]

def get_env(name):
    val = os.environ.get(name)
    if not val: raise ValueError(f"❌ Нет секрета {name}")
    return val

# --- 2. ЮРИДИЧЕСКИЙ ИНТЕЛЛЕКТ (КАЗАХСТАН) ---
def get_legal_prompt(inc_type, desc, cad_id, photo_url):
    return f"""
    РОЛЬ: Ты опытный судебный, экологический, административный юрист из г. Алматы.
    ЗАДАЧА: Написать текст обращения в E-Otinish (Департамент управления земельными ресурсами города Алматы Минсельхоза, Акимат Алматы, Прокуратура Алматы, Полиция Алматы в зависимости от подведомственности).
    
    ФАКТЫ:
    - Предполагаемое Нарушение: {inc_type}
    - Непосредственное наблюдение: {desc}
    - Место (Кадастр/Ориентир): {cad_id}
    - Ссылка на фото-доказательство: {photo_url}
    
    ПРАВОВАЯ БАЗА:
    1. Экологический кодекс РК:
    2. Земельный кодекс РК.
    3. Водный кодекс РК.
    4. КоАП РК.
    
    ТРЕБОВАНИЯ:
    - Текст должен быть готов к отправке (Шапка -> Суть -> Статьи -> Требование), лишних знаков типа кавычек быть не должно.
    - Стиль: Строгий, бюрократический. Без приветствий.
    - В конце укажи: "Фото-материалы прилагаются по ссылке".
    """

# --- 3. ИНСТРУМЕНТЫ ---
def auth_google():
    import json
    creds_dict = json.loads(get_env('GOOGLE_CREDENTIALS_JSON'))
    return Credentials.from_service_account_info(creds_dict)

def upload_photo(service, local_path):
    """Грузит фото на Drive и возвращает ссылку"""
    name = os.path.basename(local_path)
    meta = {'name': name, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(local_path, mimetype='image/jpeg')
    f = service.files().create(body=meta, media_body=media, fields='webViewLink').execute()
    return f.get('webViewLink')

def send_email(to, subj, body):
    u, p = get_env('GMAIL_USER'), get_env('GMAIL_APP_PASS')
    msg = MIMEMultipart()
    msg['From'] = u
    msg['To'] = f"{u}, {to}" if to else u
    msg['Subject'] = subj
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(u, p); s.send_message(msg)
    except Exception as e: print(f"Mail error: {e}")

# --- 4. ОСНОВНОЙ ПРОЦЕСС ---
def main():
    print("🚀 ALMA 2.0: Legal Bot Launching...")
    
    # Авторизация
    mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
    drive_svc = build('drive', 'v3', credentials=auth_google())
    genai.configure(api_key=get_env('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    # Синхронизация
    if not os.path.exists(PROJECT_PATH): mc.download_project(MERGIN_PROJECT, PROJECT_PATH)
    else: mc.pull_project(PROJECT_PATH)

    # Загрузка таблиц
    try:
        incidents = gpd.read_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE))
        photos_gdf = gpd.read_file(os.path.join(PROJECT_PATH, PHOTOS_FILE))
        # Загрузка садов для кадастра
        garden_files = [f for f in glob.glob(f"{PROJECT_PATH}/*.gpkg") if any(k in f.lower() for k in GARDEN_KEYWORDS)]
        gardens = pd.concat([gpd.read_file(f).to_crs("EPSG:4326") for f in garden_files]) if garden_files else None
    except Exception as e:
        print(f"❌ Ошибка чтения файлов: {e}"); return

    # Подготовка полей
    if 'is_sent' not in incidents.columns: incidents['is_sent'] = 0
    incidents['is_sent'] = incidents['is_sent'].fillna(0).astype(int)
    
    # Фильтр новых
    new_recs = incidents[incidents['is_sent'] == 0]
    if new_recs.empty: print("✅ Новых данных нет."); return

    print(f"⚡ Обработка {len(new_recs)} записей...")

    for idx, row in new_recs.iterrows():
        unique_id = row.get('unique-id') # Связующий ключ
        
        # 1. Поиск ФОТО в таблице photos (Связь 1-ко-многим)
        photo_link = "Фото отсутствует"
        # Ищем в таблице photos запись, где external_pk == unique-id инцидента
        related_photos = photos_gdf[photos_gdf['external_pk'] == unique_id]
        
        if not related_photos.empty:
            # Берем первое фото
            photo_rel_path = related_photos.iloc[0].get('photo')
            if photo_rel_path:
                full_path = os.path.join(PROJECT_PATH, photo_rel_path)
                if os.path.exists(full_path):
                    try:
                        # Грузим на Диск
                        photo_link = upload_photo(drive_svc, full_path)
                        # Удаляем оригинал, чтобы очистить Mergin
                        os.remove(full_path) 
                        print(f"   📸 Фото перенесено на Drive: {photo_link}")
                    except Exception as e: print(f"   ⚠️ Ошибка фото: {e}")

        # 2. Поиск КАДАСТРА
        cad_id = "Не определен"
        if gardens is not None:
            pt = gpd.GeoDataFrame([row], crs="EPSG:4326")
            res = gpd.sjoin(pt, gardens, how="inner", predicate="intersects")
            if not res.empty: cad_id = str(res.iloc[0]['layer'])

        # 3. AI ЮРИСТ
        prompt = get_legal_prompt(row.get('incident_type'), row.get('description'), cad_id, photo_link)
        try: ai_resp = model.generate_content(prompt).text
        except: ai_resp = "Ошибка AI"

        # 4. Запись результатов
        incidents.at[idx, 'cadastre_id'] = cad_id
        incidents.at[idx, 'ai_complaint'] = ai_resp
        incidents.at[idx, 'is_sent'] = 1 # Помечаем как отправленное
        
        # 5. Email
        send_email(row.get('volunteer_email'), f"ALMA: Нарушение {cad_id}", f"{ai_resp}\n\nФОТО: {photo_link}")

    # Сохранение и отправка
    incidents.to_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE), driver="GPKG")
    # Таблицу фото мы не меняли, но файл фото удалили физически
    mc.push_project(PROJECT_PATH)
    print("💾 Синхронизация завершена.")

if __name__ == "__main__":
    main()
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
from email.mime.application import MIMEApplication
from mergin import MerginClient

# --- КОНФИГУРАЦИЯ ---
MERGIN_PROJECT = "ALMA_exmachina/alma_bot"
PROJECT_PATH = "./project"
INCIDENTS_FILE = "Инцидент.gpkg" 
PHOTOS_FILE = "photos.gpkg"

# Ключевые слова для поиска слоев садов
GARDEN_KEYWORDS = ["сады", "orchards", "защищенные", "проверке", "возвращенный"]

def get_env(name):
    val = os.environ.get(name)
    if not val: print(f"⚠️ Секрет {name} не найден!")
    return val

def get_legal_prompt(inc_type, desc, cad_id):
    return f"""
    РОЛЬ: Природоохранный прокурор г. Алматы.
    ЗАДАЧА: Написать текст обращения в Акимат (E-Otinish).
    НАРУШЕНИЕ: {inc_type}.
    ОПИСАНИЕ: {desc}.
    МЕСТО (Кадастр): {cad_id}.
    ВАЖНО: Укажи, что фото-доказательства прилагаются к данному обращению.
    ТРЕБОВАНИЕ: Провести проверку по нормам Экологического и Земельного кодексов РК.
    """

def send_email_with_attachments(to_email, subject, body, attachment_paths):
    """Отправляет письмо с вложениями (фото)"""
    sender = get_env('MERGIN_USER') # Используем почту монитора как отправителя
    password = get_env('GMAIL_APP_PASS')
    
    if not sender or not password:
        print("❌ Ошибка: Нет логина/пароля для почты.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = f"{sender}, {to_email}" # Копия себе и волонтеру
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Прикрепляем фото
    for f_path in attachment_paths:
        if f_path and os.path.exists(f_path):
            try:
                with open(f_path, 'rb') as f:
                    file_data = f.read()
                    # Пытаемся определить имя файла
                    fname = os.path.basename(f_path)
                    # Создаем объект картинки
                    image = MIMEImage(file_data, name=fname)
                    msg.attach(image)
                    print(f"   📎 Прикреплен файл: {fname}")
            except Exception as e:
                print(f"   ⚠️ Не удалось прикрепить {f_path}: {e}")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"   ✉️ Письмо с фото отправлено: {to_email}")
    except Exception as e:
        print(f"   ❌ Ошибка отправки почты: {e}")

def main():
    print("🚀 ALMA 2.1: Email Attachments Mode")
    
    # 1. Авторизация
    mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
    genai.configure(api_key=get_env('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    # 2. Скачивание (с полной очисткой кэша для надежности)
    if os.path.exists(PROJECT_PATH): shutil.rmtree(PROJECT_PATH)
    print("📥 Скачиваю проект...")
    mc.download_project(MERGIN_PROJECT, PROJECT_PATH)

    # 3. Чтение данных
    try:
        inc_p = os.path.join(PROJECT_PATH, INCIDENTS_FILE)
        pho_p = os.path.join(PROJECT_PATH, PHOTOS_FILE)
        
        incidents = gpd.read_file(inc_p)
        photos_gdf = gpd.read_file(pho_p)
        
        # Сады
        garden_files = [f for f in glob.glob(f"{PROJECT_PATH}/*.gpkg") if any(k in f.lower() for k in GARDEN_KEYWORDS)]
        gardens = pd.concat([gpd.read_file(f).to_crs("EPSG:4326") for f in garden_files]) if garden_files else None
    except Exception as e:
        print(f"❌ Ошибка чтения таблиц: {e}"); return

    # Инициализация
    if 'is_sent' not in incidents.columns: incidents['is_sent'] = 0
    incidents['is_sent'] = incidents['is_sent'].fillna(0).astype(int)
    
    # Фильтр новых
    new_recs = incidents[incidents['is_sent'] == 0]
    
    if new_recs.empty:
        print("✅ Новых инцидентов нет."); return

    print(f"⚡ Найдено новых записей: {len(new_recs)}")

    for idx, row in new_recs.iterrows():
        uid = row.get('unique-id')
        print(f"\n--- Обработка {uid} ---")
        
        # А. Сбор фото (Локальные пути)
        attachments = []
        related_photos = photos_gdf[photos_gdf['external_pk'] == uid]
        
        if not related_photos.empty:
            for _, p_row in related_photos.iterrows():
                raw_path = p_row.get('photo')
                if raw_path:
                    # Ищем файл (он может быть в корне или в подпапке)
                    candidates = [
                        os.path.join(PROJECT_PATH, raw_path),
                        os.path.join(PROJECT_PATH, os.path.basename(raw_path))
                    ]
                    for c in candidates:
                        if os.path.exists(c):
                            attachments.append(c)
                            break
        
        # Б. Кадастр
        cad_id = "Не определен"
        if gardens is not None:
            pt = gpd.GeoDataFrame([row], crs="EPSG:4326")
            res = gpd.sjoin(pt, gardens, how="inner", predicate="intersects")
            if not res.empty: cad_id = str(res.iloc[0]['layer'])

        # В. Gemini
        prompt = get_legal_prompt(row.get('incident_type'), row.get('description'), cad_id)
        try: text = model.generate_content(prompt).text
        except: text = "Ошибка AI"

        # Г. Отправка и Очистка
        send_email_with_attachments(row.get('volunteer_email'), f"ALMA: {cad_id}", text, attachments)
        
        # Д. Удаление фото (чтобы очистить Mergin Cloud)
        for f_path in attachments:
            try:
                os.remove(f_path)
                print(f"   🗑 Файл удален локально: {os.path.basename(f_path)}")
            except: pass

        # Е. Обновление статуса
        incidents.at[idx, 'cadastre_id'] = cad_id
        incidents.at[idx, 'ai_complaint'] = text
        incidents.at[idx, 'is_sent'] = 1

    # 4. Финальная синхронизация
    # (Mergin увидит, что файлов фото нет, и удалит их из облака, но они уже у вас на почте)
    incidents.to_file(inc_p, driver="GPKG")
    mc.push_project(PROJECT_PATH)
    print("💾 Синхронизация завершена. Облако очищено.")

if __name__ == "__main__":
    main()

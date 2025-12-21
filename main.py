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

# --- 1. НАСТРОЙКИ ---
MERGIN_PROJECT = "ALMA_exmachina/alma_bot"
PROJECT_PATH = "./project"
INCIDENTS_FILE = "Инцидент.gpkg" 
PHOTOS_FILE = "photos.gpkg"

# Ключевые слова для поиска файлов с садами
GARDEN_KEYWORDS = ["сады", "orchards", "защищенные", "проверке", "возвращенный"]

def get_env(name):
    val = os.environ.get(name)
    if not val: print(f"⚠️ Секрет {name} не найден!")
    return val

# --- 2. ЮРИДИЧЕСКИЙ ПРОМПТ (СУДЕБНЫЙ ЭКСПЕРТ) ---
def get_legal_prompt(inc_type, desc, cad_id):
    return f"""
    РОЛЬ: Опытный судебный юрист, эксперт по земельному и экологическому праву РК.
    СТИЛЬ: Официально-деловой, жесткий, процессуальный.
    
    ЗАДАЧА: 
    Подготовить юридически обоснованное обращение в Государственный орган (Акимат, ГАСК, Экология) через E-Otinish.
    
    ФАКТУРА ДЕЛА:
    1. Квалификация нарушения: {inc_type}.
    2. Пояснения свидетеля: {desc}.
    3. Место совершения (Кадастровый номер / Локация): {cad_id}.
    4. Доказательная база: Фотоматериалы прилагаются к заявлению.

    ПРАВОВОЕ ОБОСНОВАНИЕ (Использовать императивные нормы):
    - Ссылаться на Земельный кодекс РК (ст. 43, 65, 136) о целевом использовании и охране земель.
    - Ссылаться на Экологический кодекс РК (Принцип «Загрязнитель платит», ст. 202-205).
    - Если применимо, указывать на признаки состава адм. правонарушения (КоАП РК ст. 337, 344).

    ПРОСИТЕЛЬНАЯ ЧАСТЬ:
    1. Организовать выездную проверку фактов.
    2. Установить собственника участка {cad_id} и привлечь к ответственности.
    3. Выдать предписание об устранении нарушений.
    
    ВЫВОД: Сформируй готовый текст заявления без приветствий и лишних слов.
    """

# --- 3. ОТПРАВКА ПОЧТЫ С ФОТО ---
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
                    img = MIMEImage(f.read(), name=os.path.basename(f_path))
                    msg.attach(img)
            except: pass

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(sender, password)
            s.send_message(msg)
        print(f"   ✉️ Почта отправлена: {to_email}")
    except Exception as e:
        print(f"   ❌ Ошибка почты: {e}")

# --- 4. ОСНОВНОЙ КОД ---
def main():
    print("🚀 ALMA 2.5: Legal Expert & Exact Layer Field")
    
    mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
    genai.configure(api_key=get_env('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    # Очистка и скачивание (чтобы не было конфликтов)
    if os.path.exists(PROJECT_PATH): shutil.rmtree(PROJECT_PATH)
    mc.download_project(MERGIN_PROJECT, PROJECT_PATH)

    try:
        incidents = gpd.read_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE))
        photos_gdf = gpd.read_file(os.path.join(PROJECT_PATH, PHOTOS_FILE))
    except Exception as e:
        print(f"❌ Ошибка открытия таблиц: {e}"); return

    # Подготовка статусов
    if 'is_sent' not in incidents.columns: incidents['is_sent'] = 0
    incidents['is_sent'] = incidents['is_sent'].fillna(0).astype(int)
    
    new_recs = incidents[incidents['is_sent'] == 0]
    if new_recs.empty: print("✅ Новых данных нет."); return

    # Собираем пути к файлам садов (не открываем их все сразу)
    garden_files = []
    for f in glob.glob(f"{PROJECT_PATH}/*.gpkg"):
        if os.path.basename(f) not in [INCIDENTS_FILE, PHOTOS_FILE]:
            if any(k in os.path.basename(f).lower() for k in GARDEN_KEYWORDS):
                garden_files.append(f)

    print(f"⚡ Новых инцидентов: {len(new_recs)}. Баз данных садов: {len(garden_files)}")

    for idx, row in new_recs.iterrows():
        uid = row.get('unique-id')
        print(f"\n--- Дело № {uid} ---")
        
        # A. Сбор фото
        attachments = []
        rel_photos = photos_gdf[photos_gdf['external_pk'] == uid]
        if not rel_photos.empty:
            for _, p_row in rel_photos.iterrows():
                path = p_row.get('photo')
                if path:
                    # Проверка путей (иногда Mergin пишет полный путь, иногда относительный)
                    candidates = [
                        os.path.join(PROJECT_PATH, path),
                        os.path.join(PROJECT_PATH, os.path.basename(path))
                    ]
                    for c in candidates:
                        if os.path.exists(c):
                            attachments.append(c)
                            break

        # B. ОПРЕДЕЛЕНИЕ КАДАСТРА ИЗ ПОЛЯ LAYER (READ-ONLY)
        cad_id = "Кадастровый номер не установлен"
        
        # Создаем точку геометрии для проверки
        point_geom = row.geometry
        
        # Пробегаем по файлам садов
        for g_file in garden_files:
            try:
                # Читаем файл в память (не блокируя его)
                temp_gdf = gpd.read_file(g_file).to_crs("EPSG:4326")
                
                # Ищем полигон, содержащий точку
                # contains - строго внутри, intersects - касается или внутри
                match = temp_gdf[temp_gdf.contains(point_geom)]
                
                if not match.empty:
                    # БИНГО! Нашли полигон.
                    # Пытаемся взять значение из поля 'layer'
                    if 'layer' in match.columns:
                        val = match.iloc[0]['layer']
                        if val: 
                            cad_id = str(val)
                            print(f"   🎯 Найден кадастр в поле layer: {cad_id}")
                    else:
                        # Если поля layer в файле нет - берем имя файла
                        cad_id = os.path.splitext(os.path.basename(g_file))[0]
                        print(f"   ⚠️ Поле layer отсутствует, взято имя файла: {cad_id}")
                    
                    # Прерываем поиск, так как сад найден
                    break
            except Exception as e:
                print(f"   ⚠️ Ошибка чтения файла {os.path.basename(g_file)}: {e}")
        
        if cad_id == "Кадастровый номер не установлен":
            print("   📍 Точка находится вне известных границ садов")

        # C. ГЕНЕРАЦИЯ ЮРИДИЧЕСКОГО ТЕКСТА
        prompt = get_legal_prompt(row.get('incident_type'), row.get('description'), cad_id)
        try: text = model.generate_content(prompt).text
        except: text = "Ошибка генерации AI"

        # D. ОТПРАВКА И ЧИСТКА
        send_email_with_attachments(row.get('volunteer_email'), f"ALMA ИСК: {cad_id}", text, attachments)
        
        for f in attachments:
            try: os.remove(f)
            except: pass

        incidents.at[idx, 'cadastre_id'] = cad_id
        incidents.at[idx, 'ai_complaint'] = text
        incidents.at[idx, '

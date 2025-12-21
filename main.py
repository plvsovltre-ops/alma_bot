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
LAWS_FOLDER = "laws" # Папка с вашими txt файлами

# Ключевые слова для поиска слоев садов
GARDEN_KEYWORDS = ["сады", "orchards", "защищенные", "проверке", "возвращенный"]

def get_env(name):
    val = os.environ.get(name)
    if not val: print(f"⚠️ Секрет {name} не найден!")
    return val

def load_knowledge_base():
    """
    Читает файлы из папки laws строго по порядку имен (00, 01, 02...).
    Это гарантирует, что Методичка (00) будет в начале промпта.
    """
    full_text = ""
    # Ищем все .txt файлы
    search_path = os.path.join(LAWS_FOLDER, "*.txt")
    # Сортируем (sorted), чтобы 00 шло перед 01
    files = sorted(glob.glob(search_path))
    
    if not files:
        print("⚠️ ПРЕДУПРЕЖДЕНИЕ: Папка laws пуста или не найдена!")
        return "База законов недоступна. Используй общие знания."

    print(f"📚 Загрузка Юридической Базы ({len(files)} док):")
    for f_path in files:
        fname = os.path.basename(f_path)
        print(f"   📖 Читаю: {fname}")
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Разделитель для ясности
                full_text += f"\n\n--- НАЧАЛО ДОКУМЕНТА: {fname} ---\n"
                full_text += content
                full_text += f"\n--- КОНЕЦ ДОКУМЕНТА: {fname} ---\n"
        except Exception as e:
            print(f"   ❌ Ошибка чтения {fname}: {e}")
            
    return full_text

# --- 2. ПРОМПТ (МОЗГ ЮРИСТА) ---
def get_legal_prompt(inc_type, desc, cad_id, coords, legal_db):
    return f"""
    ТВОЯ РОЛЬ: Ты — блестящий юрист-эколог движения ALMA. Твоя квалификация позволяет выигрывать суды против застройщиков.
    
    ВХОДНЫЕ ДАННЫЕ ИНЦИДЕНТА:
    - Тип нарушения: {inc_type}
    - Комментарий волонтера: {desc}
    - Кадастр/Локация: {cad_id}
    - Координаты: {coords}
    
    ===================================================================
    ТВОЯ БАЗА ЗНАНИЙ (СНАЧАЛА МЕТОДИЧКА, ЗАТЕМ КОДЕКСЫ):
    {legal_db}
    ===================================================================

    ЗАДАЧА: Сформировать ответ, состоящий из двух частей.

    ЧАСТЬ 1: ЮРИДИЧЕСКАЯ КОНСУЛЬТАЦИЯ (Для волонтера)
    - Тон: Поддерживающий, профессиональный, наставнический.
    - Объясни, какую статью из Базы Знаний нарушили в данном случае.
    - Дай краткий совет: что именно важно зафиксировать на фото для суда по этой статье.

    ЧАСТЬ 2: ПРОЦЕССУАЛЬНОЕ ЗАЯВЛЕНИЕ (Для E-Otinish)
    - Адресат: Акимат г. Алматы (или ГАСК/Экология, выбери исходя из сути нарушения).
    - Заголовок: ЗАЯВЛЕНИЕ о нарушении законодательства.
    - Текст: Сухой, жесткий, юридический.
    - Мотивировочная часть: ЦИТИРУЙ пункты и статьи из приложенных Кодексов (файлы 01-05). Ссылайся на Методичку (файл 00) для логики.
    - Просительная часть: Требуй проверку, привлечение к ответственности, снос/возмещение.
    - Обязательно укажи координаты GPS.
    - Подпись: "Волонтер Альянса ALMA". (Без даты и ФИО).
    """

# --- 3. ОТПРАВКА ---
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
    except: pass

# --- 4. ГЛАВНЫЙ ЦИКЛ ---
def main():
    print("🚀 ALMA 3.3: Full Legal Brain Launch")
    
    mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
    genai.configure(api_key=get_env('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    # 1. Загрузка всей базы знаний
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

    # Подготовка слоев садов (Read-Only)
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
        
        if cad_id == "Кадастровый номер не установлен":
             cad_id = f"Участок по координатам {coords_str}"
        
        print(f"   📍 Локация: {cad_id}")

        # ГЕНЕРАЦИЯ
        prompt = get_legal_prompt(row.get('incident_type'), row.get('description'), cad_id, coords_str, legal_knowledge)
        try: text = model.generate_content(prompt).text
        except: text = "Ошибка генерации AI"

        # Отправка
        send_email_with_attachments(row.get('volunteer_email'), f"ALMA КОНСУЛЬТАЦИЯ: {cad_id}", text, attachments)
        
        # Чистка
        for f in attachments:
            try: os.remove(f)
            except: pass

        incidents.at[idx, 'cadastre_id'] = cad_id
        incidents.at[idx, 'ai_complaint'] = text
        incidents.at[idx, 'is_sent'] = 1

    incidents.to_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE), driver="GPKG")
    mc.push_project(PROJECT_PATH)
    print("💾 Готово.")

if __name__ == "__main__":
    main()

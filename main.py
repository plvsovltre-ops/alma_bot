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
    """Читает базу законов."""
    full_text = ""
    # Ищем все файлы .txt и сортируем их
    files = sorted(glob.glob(os.path.join(LAWS_FOLDER, "*.txt")))
    
    if not files:
        return "База законов пуста."

    print(f"📚 Загрузка базы ({len(files)} файлов)...")
    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                full_text += f"\n\n--- ДОКУМЕНТ: {os.path.basename(f_path)} ---\n"
                full_text += f.read()
        except Exception as e:
            print(f"   ❌ Ошибка чтения {f_path}: {e}")
            
    return full_text

def get_legal_prompt(inc_type, desc, cad_id, coords, legal_db):
    return f"""
    РОЛЬ: Ведущий юрист-эколог движения ALMA.
    ЗАДАЧА: Подготовить юридическое заключение и заявление.
    
    СУТЬ ДЕЛА:
    - Нарушение: {inc_type}
    - Детали: {desc}
    - Место: {cad_id} ({coords})
    
    ТВОЯ БИБЛИОТЕКА ЗАКОНОВ (ИСПОЛЬЗУЙ ЕЁ):
    {legal_db}

    ТРЕБОВАНИЯ К ОТВЕТУ:

    ЧАСТЬ 1. КОНСУЛЬТАЦИЯ ВОЛОНТЕРУ
    - Кратко: какая статья нарушена.
    - Совет: что именно зафиксировать (номера машин, глубину ямы, спилы деревьев).

    ЧАСТЬ 2. ОФИЦИАЛЬНОЕ ЗАЯВЛЕНИЕ В ГОСОРГАН
    - Адресат: Акимат г. Алматы (или ГАСК/Экология по ситуации).
    - Стиль: Строгий, процессуальный.
    - Обязательно цитируй статьи из Библиотеки Законов (выше).
    - Если нарушение серьезное — ссылайся на УК РК или КоАП.
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
                    img = MIMEImage(f.read(), name=os.path.basename(f_path))
                    msg.attach(img)
            except: pass

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(sender, password)
            s.send_message(msg)
        print(f"   ✉️ Почта отправлена: {to_email}")
    except Exception as e:
        print(f"   ❌ Ошибка отправки почты: {e}")

def main():
    print("🚀 ALMA 3.6: Gemini 1.5 Flash (Stable High-Quota)")
    
    mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
    genai.configure(api_key=get_env('GEMINI_API_KEY'))
    
    # --- МОДЕЛЬ 1.5 FLASH (Самая стабильная для больших текстов) ---
    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash', 
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
    except Exception as e:
        print(f"⚠️ Ошибка инициализации модели: {e}")
        return

    # Загружаем базу знаний
    legal_knowledge = load_knowledge_base()
    # Если база слишком огромная, можно обрезать (но 1.5 Flash выдержит до 1 млн токенов)
    print(f"🧠 Объем базы знаний: {len(legal_knowledge)} символов.")

    if os.path.exists(PROJECT_PATH): shutil.rmtree(PROJECT_PATH)
    mc.download_project(MERGIN_PROJECT, PROJECT_PATH)

    try:
        incidents = gpd.read_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE))
        photos_gdf = gpd.read_file(os.path.join(PROJECT_PATH, PHOTOS_FILE))
    except Exception as e:
        print(f"❌ Ошибка данных: {e}"); return

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
        
        if cad_id == "Кадастровый номер не установлен":
             cad_id = f"Участок по координатам {coords_str}"
        
        # ГЕНЕРАЦИЯ
        prompt = get_legal_prompt(row.get('incident_type'), row.get('description'), cad_id, coords_str, legal_knowledge)
        
        try:
            print("   ⏳ Запрос к Gemini 1.5 Flash...")
            response = model.generate_content(prompt)
            text = response.text
            print("   ✅ Ответ получен!")
        except Exception as e:
            err_msg = f"ОШИБКА AI: {e}"
            print(f"   ❌ {err_msg}")
            text = f"Произошла ошибка при генерации ответа: {e}\n\nПопробуйте перезапустить робота через 5 минут."

        send_email_with_attachments(row.get('volunteer_email'), f"ALMA КОНСУЛЬТАЦИЯ: {cad_id}", text, attachments)
        
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

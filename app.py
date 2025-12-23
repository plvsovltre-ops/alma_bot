import streamlit as st
import os
import glob
from google import genai
from google.genai import types

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Юрист АЛМА / ALMA Заңгері", page_icon="⚖️", layout="centered")

# Скрываем лишние элементы интерфейса
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stChatInput {bottom: 20px;}
    </style>
    """, unsafe_allow_html=True)

st.title("⚖️ Юрист АЛМА (Alma Zanger)")
st.caption("Виртуальный консультант по защите предгорий / Тау бөктерін қорғау жөніндегі виртуалды кеңесші")

# --- 2. ВЫБОР ЯЗЫКА ---
with st.container():
    selected_lang = st.radio(
        "Выберите язык / Тілді таңдаңыз:",
        ["Русский 🇷🇺", "Қазақша 🇰🇿"],
        horizontal=True,
        index=0
    )

# --- 3. НАСТРОЙКА МОДЕЛЕЙ (FAILSAFE) ---
MODEL_CANDIDATES = [
    "gemini-1.5-flash-002",
    "gemini-1.5-flash",
    "gemini-1.5-flash-001",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp"
]

api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("Ошибка: Не найден API ключ (GEMINI_API_KEY).")
    st.stop()

try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Error creating client: {e}")
    st.stop()

@st.cache_resource
def get_working_model():
    for model_name in MODEL_CANDIDATES:
        try:
            client.models.generate_content(model=model_name, contents="Ping")
            return model_name
        except Exception:
            continue
    return None

active_model = get_working_model()
if not active_model:
    st.error("Сервер перегружен. Попробуйте позже.")
    st.stop()

# --- 4. ДИСКЛЕЙМЕР ---
with st.expander("📜 Условия использования / Пайдалану шарттары", expanded=True):
    st.warning("""
    **RU:** Ответы носят информационный характер и не являются профессиональной юридической консультацией.
    **KZ:** Жауаптар ақпараттық сипатқа ие және кәсіби заңгерлік кеңес болып табылмайды.
    """)
    agreement = st.checkbox("Я согласен / Мен келісемін")

if not agreement:
    st.info("Нажмите галочку выше, чтобы начать. / Бастау үшін жоғарыдағы құсбелгіні қойыңыз.")
    st.stop()

# --- 5. ЗАГРУЗКА БАЗЫ ЗНАНИЙ ---
@st.cache_resource
def load_knowledge():
    knowledge = ""
    folder_path = "laws"
    if not os.path.exists(folder_path):
        return "ERROR: Folder 'laws' not found."
    
    files = sorted(glob.glob(os.path.join(folder_path, "*.txt")))
    if not files:
        return "ERROR: No text files found."

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                filename = os.path.basename(file_path)
                knowledge += f"\n\n--- SOURCE_ID: {filename} ---\n"
                knowledge += f.read()
        except Exception as e:
            knowledge += f"\n[Error reading {file_path}: {e}]\n"
    return knowledge

knowledge_base = load_knowledge()

# --- 6. ЧАТ И ЗАГРУЗКА ФОТО ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Очистка истории при смене языка
if "last_lang" not in st.session_state:
    st.session_state.last_lang = selected_lang
if st.session_state.last_lang != selected_lang:
    st.session_state.messages = []
    st.session_state.last_lang = selected_lang

# Приветствие
if not st.session_state.messages:
    if "Русский" in selected_lang:
        welcome = "Здравствуйте! Опишите проблему или прикрепите фото нарушения (например, стройка на горе, вырубка)."
    else:
        welcome = "Сәлеметсіз бе! Мәселені сипаттаңыз немесе бұзушылықтың суретін тіркеңіз (мысалы, таудағы құрылыс, ағаш кесу)."
    st.session_state.messages.append({"role": "assistant", "content": welcome})

# Вывод истории
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Если в сообщении есть картинка, показываем её
        if "image" in msg:
            st.image(msg["image"], caption="Загруженное фото / Жүктелген фото", width=300)
        st.write(msg["content"])

# --- ИНТЕРФЕЙС ЗАГРУЗКИ ФОТО ---
# Используем expander, чтобы не загромождать экран
label_upload = "📸 Загрузить фото (Опционально) / Фотосурет жүктеу (Міндетті емес)"
with st.expander(label_upload):
    uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"])

# --- ОБРАБОТКА ВВОДА ---
prompt_text = "Введите описание..." if "Русский" in selected_lang else "Сипаттаманы енгізіңіз..."

if prompt := st.chat_input(prompt_text):
    # 1. Формируем сообщение пользователя для истории
    user_msg_obj = {"role": "user", "content": prompt}
    
    # Если есть фото, добавляем его в объект сообщения (для отображения)
    image_part = None
    if uploaded_file:
        user_msg_obj["image"] = uploaded_file
        # Конвертируем для Gemini
        try:
            image_bytes = uploaded_file.getvalue()
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=uploaded_file.type
            )
        except Exception as e:
            st.error(f"Ошибка обработки фото: {e}")

    st.session_state.messages.append(user_msg_obj)
    
    # Показываем сообщение пользователя сразу
    with st.chat_message("user"):
        if uploaded_file:
            st.image(uploaded_file, width=300)
        st.write(prompt)

    # 2. Генерация ответа
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        
        target_lang = "РУССКИЙ" if "Русский" in selected_lang else "КАЗАХСКИЙ (Қазақ тілі)"

        # Инструкция с учетом зрения
        system_instruction = f"""
        ТЫ — Виртуальный Юрист ALMA (Alma Zanger).
        ТВОЯ ЗАДАЧА: Консультировать по вопросам защиты природы Алматы, анализируя ТЕКСТ и ФОТО (если есть), используя Базу Знаний.
        
        ТВОЯ БАЗА ЗНАНИЙ:
        {knowledge_base}
        
        СТРОГАЯ ИНСТРУКЦИЯ:
        1. ЯЗЫК ОТВЕТА: {target_lang}.
        2. ЕСЛИ ЕСТЬ ФОТО: Сначала опиши, что ты видишь (крутизна склона, техника, спиленные деревья, близость к воде), и подтверждает ли это нарушение.
        3. ИСТОЧНИКИ: Ссылайся ТОЛЬКО на официальные названия законов (не пиши названия файлов .txt).
        4. ЕСЛИ НАРУШЕНИЕ СЕРЬЕЗНОЕ: Предложи пошаговый алгоритм (Сценарий А/Б).
        5. Не выдумывай законы.
        """

        # Собираем контент для отправки (Инструкция + Текст + Картинка)
        request_contents = [system_instruction, prompt]
        if image_part:
            request_contents.append(image_part)

        try:
            response = client.models.generate_content(
                model=active_model,
                contents=request_contents,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=8000,
                    safety_settings=[
                        types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                        types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                        types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                        types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE')
                    ]
                )
            )
            full_response = response.text
            placeholder.markdown(full_response)
        except Exception as e:
            err_msg = f"Ошибка / Қате: {e}"
            placeholder.error(err_msg)
            full_response = err_msg

    st.session_state.messages.append({"role": "assistant", "content": full_response})

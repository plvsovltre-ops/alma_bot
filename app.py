import streamlit as st
import os
import glob
from google import genai
from google.genai import types

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Юрист АЛМА", page_icon="⚖️", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stChatInput {bottom: 20px;}
    </style>
    """, unsafe_allow_html=True)

st.title("⚖️ Юрист АЛМА (Alma Zanger)")
st.caption("Виртуальный консультант по защите предгорий и экологии Алматы")

# --- 2. СПИСОК МОДЕЛЕЙ (ИЗ ВАШЕГО MAIN.PY) ---
# Бот будет пробовать их по очереди, пока одна не заработает
MODEL_CANDIDATES = [
    "gemini-1.5-flash-002", # Самая стабильная новая версия
    "gemini-1.5-flash",     # Стандартная
    "gemini-1.5-flash-001", # Старая стабильная
    "gemini-1.5-pro",       # Мощная (резерв)
    "gemini-2.0-flash-exp"  # Экспериментальная
]

# --- 3. ИНИЦИАЛИЗАЦИЯ КЛИЕНТА И ВЫБОР МОДЕЛИ ---
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("Системная ошибка: Не найден API ключ (GEMINI_API_KEY). Добавьте его в Secrets.")
    st.stop()

# Создаем клиента
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Ошибка создания клиента AI: {e}")
    st.stop()

# Функция выбора рабочей модели (Кэшируем, чтобы не проверять каждый раз)
@st.cache_resource
def get_working_model():
    for model_name in MODEL_CANDIDATES:
        try:
            # Пробуем отправить пустой запрос ("Ping")
            client.models.generate_content(model=model_name, contents="Ping")
            return model_name
        except Exception:
            continue
    return None

# Определяем модель при запуске
active_model = get_working_model()

if not active_model:
    st.error("❌ ОШИБКА: Ни одна из моделей Gemini не отвечает. Попробуйте позже.")
    st.stop()

# --- 4. ДИСКЛЕЙМЕР ---
with st.expander("📜 ВАЖНО: Условия использования (Нажмите, чтобы прочитать)", expanded=True):
    st.warning("""
    **ВНИМАНИЕ:** Данный сервис работает на базе Искусственного Интеллекта.
    1. Ответы носят **исключительно информационный характер**.
    2. Движение ALMA не несет ответственности за действия, совершенные на основе ответов.
    3. Для судов обращайтесь к живому адвокату.
    """)
    agreement = st.checkbox("Я понимаю риски и согласен использовать сервис как справочник.")

if not agreement:
    st.info("Пожалуйста, примите условия выше, чтобы начать.")
    st.stop()

# --- 5. ЗАГРУЗКА БАЗЫ ЗНАНИЙ ---
@st.cache_resource
def load_knowledge():
    knowledge = ""
    folder_path = "laws" # Папка в репозитории
    
    if not os.path.exists(folder_path):
        return f"ОШИБКА: Папка '{folder_path}' не найдена."
    
    files = sorted(glob.glob(os.path.join(folder_path, "*.txt")))
    if not files:
        return f"ОШИБКА: В папке '{folder_path}' нет файлов."

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                filename = os.path.basename(file_path)
                knowledge += f"\n\n--- ДОКУМЕНТ: {filename} ---\n"
                knowledge += f.read()
        except Exception as e:
            knowledge += f"\n[Ошибка чтения {file_path}: {e}]\n"
    return knowledge

knowledge_base = load_knowledge()

if knowledge_base.startswith("ОШИБКА"):
    st.error(knowledge_base)
    st.stop()

# --- 6. ЧАТ ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"Здравствуйте! Я использую модель **{active_model}** для точности. Опишите проблему (например: *'Стройка на склоне'*, *'Срубили сад'*)."}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Введите ваш вопрос..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        
        # Системная инструкция
        system_instruction = f"""
        ТЫ — Виртуальный Юрист ALMA (Alma Zanger).
        ТВОЯ ЗАДАЧА: Защищать природу Алматы, используя ТОЛЬКО предоставленную Базу Знаний.
        
        ТВОЯ БАЗА ЗНАНИЙ:
        {knowledge_base}
        
        ИНСТРУКЦИЯ:
        1. Ссылайся на КОНКРЕТНЫЕ файлы, статьи и пункты законов (например: "Согласно ст. 324 УК РК из файла 05_crime_code.txt...").
        2. Если нарушение серьезное, предложи алгоритм действий.
        3. Если информации нет в базе, не выдумывай законы.
        4. Отвечай на языке пользователя (RU/KZ).
        """

        try:
            # Используем найденную active_model
            response = client.models.generate_content(
                model=active_model,
                contents=[system_instruction, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0, # Максимальная строгость фактов
                    max_output_tokens=2000,
                    # Добавляем настройки безопасности, как в main.py
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
            full_response = f"⚠️ Ошибка генерации: {e}"
            placeholder.error(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
from langchain.schema import HumanMessage
from ai.graphs.chat_graph import chat_graph
import av
import numpy as np
import tempfile
import os

import wave
import json
import re
from vosk import Model, KaldiRecognizer

# Путь к модели Vosk - при первом запуске модель будет скачана автоматически
MODEL_PATH = "vosk-model-ru-0.22"

# Функция для получения короткого имени репозитория
def get_short_repo_name(url: str) -> str:
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    return parts[-1] if parts else "unknown"

# Функция для получения пути к векторной базе данных
def get_vector_db_path():
    if "repositories" in st.session_state and "selected_repo_index" in st.session_state:
        selected_repo = st.session_state["repositories"][st.session_state["selected_repo_index"]]
        short_name = get_short_repo_name(selected_repo["url"])
        return f"storage/{short_name}/vectore_store/"
    elif "selected_repo" in st.session_state and st.session_state["selected_repo"]:
        # Для случая, когда есть selected_repo, но нет repositories
        repo_name = st.session_state["selected_repo"]["repo_name"]
        return f"storage/{repo_name}/vectore_store/"
    else:
        return "storage/default/vectore_store/"

# Аудио процессор для накопления аудиокадров
class AudioProcessor(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.recording = True
        self.sample_rate = None
        
    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        if self.recording:
            # Записываем частоту дискретизации при первом кадре
            if self.sample_rate is None:
                self.sample_rate = frame.sample_rate
            
            # Сохраняем аудиоданные
            self.frames.append(frame.to_ndarray())
        return frame

def download_vosk_model():
    """Функция для скачивания модели Vosk, если её нет"""
    if not os.path.exists(MODEL_PATH):
        st.info("Загрузка модели распознавания русской речи. Это может занять несколько минут...")
        import urllib.request
        import zipfile
        
        # URL для скачивания небольшой русской модели (~45 МБ)
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
        zip_path = "vosk-model.zip"
        
        # Скачиваем архив с моделью
        urllib.request.urlretrieve(model_url, zip_path)
        
        # Распаковываем архив
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("./")
        
        # Переименовываем папку с моделью
        os.rename("vosk-model-small-ru-0.22", MODEL_PATH)
        
        # Удаляем архив
        os.remove(zip_path)
        
        st.success("Модель распознавания успешно загружена!")

# Функция для сохранения и обработки аудио с использованием Vosk
def process_audio_frames(frames, sample_rate=16000):
    if not frames or len(frames) == 0:
        return "Не удалось записать аудио. Пожалуйста, попробуйте снова."
    
    try:
        # Проверяем наличие модели
        if not os.path.exists(MODEL_PATH):
            download_vosk_model()
        
        # Загружаем модель
        model = Model(MODEL_PATH)
        
        # Подготавливаем распознаватель
        rec = KaldiRecognizer(model, sample_rate)
        rec.SetWords(True)  # Получаем текст с временными метками
        
        # Объединяем аудиокадры
        audio_data = np.concatenate(frames, axis=0)
        audio_data = audio_data.flatten().astype(np.int16)
        
        # Сохраняем аудио во временный WAV файл для обработки
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            filepath = temp_file.name
            
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16 bits
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())
        
        # Открываем аудиофайл и распознаем
        with wave.open(filepath, 'rb') as wf:
            # Читаем данные блоками
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                
                # Подаем данные в распознаватель
                rec.AcceptWaveform(data)
            
            # Получаем финальный результат
            result_json = rec.FinalResult()
            result = json.loads(result_json)
            
            # Извлекаем распознанный текст
            recognized_text = result.get("text", "")
        
        # Удаляем временный файл
        os.unlink(filepath)
        
        if not recognized_text:
            return "Речь не распознана. Пожалуйста, попробуйте говорить четче."
        
        return recognized_text
        
    except Exception as e:
        return f"Произошла ошибка при обработке аудио: {str(e)}"

def show_chat_page():
    st.title("Чат по выбранному репозиторию")

    # Инициализация переменных сессии
    if "selected_repo" not in st.session_state:
        st.session_state.selected_repo = None
    if "chat1_messages" not in st.session_state:
        st.session_state.chat1_messages = [
            {"role": "assistant", "content": "Привет! Чем могу помочь?"}
        ]
    if "voice_chat_active" not in st.session_state:
        st.session_state.voice_chat_active = False
    if "recording" not in st.session_state:
        st.session_state.recording = False
    if "audio_processor" not in st.session_state:
        st.session_state.audio_processor = None
    if "webrtc_ctx" not in st.session_state:
        st.session_state.webrtc_ctx = None
    if "is_playing" not in st.session_state:
        st.session_state.is_playing = False
    
    # Проверяем наличие модели Vosk при запуске
    if not os.path.exists(MODEL_PATH):
        with st.sidebar:
            if st.button("Загрузить модель распознавания речи"):
                download_vosk_model()

    if not st.session_state.get("selected_repo"):
        # Временное решение для тестирования голосового интерфейса
        if "selected_repo" not in st.session_state:
            st.session_state.selected_repo = {"repo_name": "Тестовый репозиторий", "branch": "main"}
        else:
            st.info("Сначала выберите репозиторий в боковом меню.")
            return

    st.write(f"Текущий репозиторий: **{st.session_state['selected_repo']['repo_name']}**")
    st.write(f"Ветка: **{st.session_state['selected_repo']['branch']}**")

    # Получаем путь к векторной базе данных для текущего репозитория
    vector_db_path = get_vector_db_path()
    
    with st.sidebar:
        st.subheader("Информация о векторной базе данных")
        st.info(f"Путь к векторной базе данных: {vector_db_path}")

    # Отображаем историю сообщений
    for msg in st.session_state.chat1_messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # Функция для включения и настройки WebRTC
    def start_webrtc():
        def audio_processor_factory():
            st.session_state.audio_processor = AudioProcessor()
            return st.session_state.audio_processor
        
        webrtc_ctx = webrtc_streamer(
            key="speech_to_text",
            mode=WebRtcMode.SENDONLY,
            audio_processor_factory=audio_processor_factory,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
            media_stream_constraints={"video": False, "audio": True},
        )
        
        return webrtc_ctx

    # Обычный текстовый чат
    if not st.session_state.voice_chat_active:
        if prompt := st.chat_input(placeholder="Введите запрос"):
            st.session_state.chat1_messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            # Обработка текстового запроса
            process_text_query(prompt, vector_db_path)
            
        # Кнопка активации голосового чата
        if st.button("Голосовой чат"):
            # Проверяем наличие модели перед активацией голосового чата
            if not os.path.exists(MODEL_PATH):
                st.warning("Для голосового чата необходимо загрузить модель распознавания речи. Нажмите кнопку в боковом меню.")
            else:
                st.session_state.voice_chat_active = True
                st.rerun()
    else:
        # Стили для голосового интерфейса
        st.markdown(
            """
            <style>
            .circle-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                margin-top: 20px;
                margin-bottom: 20px;
            }
            .circle {
                width: 80px;
                height: 80px;
                border-radius: 50%;
                background: #ff4b4b;
                box-shadow: 0 0 0 rgba(255,75,75,0.7);
                animation: pulse 2s infinite;
                cursor: pointer;
            }
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(255,75,75,0.7); }
                70% { box-shadow: 0 0 0 20px rgba(255,75,75,0); }
                100% { box-shadow: 0 0 0 0 rgba(255,75,75,0); }
            }
            .voice-buttons {
                display: flex;
                gap: 15px;
                margin-top: 20px;
                justify-content: center;
            }
            .record-status {
                text-align: center;
                font-weight: bold;
                margin-top: 10px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Инициализация WebRTC контекста, если его нет
        if st.session_state.webrtc_ctx is None:
            st.session_state.webrtc_ctx = start_webrtc()
            
        # Проверка состояния WebRTC подключения
        webrtc_state = st.session_state.webrtc_ctx.state.playing if st.session_state.webrtc_ctx else False
        
        # Отображение статуса записи
        status_container = st.empty()
        if webrtc_state:
            status_container.markdown('<p class="record-status">🔴 Идет запись...</p>', unsafe_allow_html=True)
        else:
            status_container.markdown('<p class="record-status">⚪ Запись не активна</p>', unsafe_allow_html=True)
        
        # Анимированный круг для голосового режима
        st.markdown('<div class="circle-container"><div class="circle"></div></div>', unsafe_allow_html=True)
        
        # Контейнер для кнопок голосового интерфейса
        button_cols = st.columns(3)
        
        with button_cols[0]:
            # Кнопка для начала/остановки записи
            if not st.session_state.recording:
                if st.button("🎤 Начать запись", use_container_width=True):
                    st.session_state.recording = True
                    # Активируем WebRTC, если это не было сделано
                    if not webrtc_state and st.session_state.webrtc_ctx:
                        st.session_state.webrtc_ctx.state.playing = True
                    st.rerun()
            else:
                if st.button("⏹️ Остановить запись", use_container_width=True):
                    st.session_state.recording = False
                    
                    # Отключаем WebRTC
                    if webrtc_state and st.session_state.webrtc_ctx:
                        st.session_state.webrtc_ctx.state.playing = False
                    
                    # Обработка записанного аудио
                    if st.session_state.audio_processor and hasattr(st.session_state.audio_processor, "frames") and st.session_state.audio_processor.frames:
                        frames = st.session_state.audio_processor.frames
                        sample_rate = st.session_state.audio_processor.sample_rate or 16000
                        st.session_state.audio_processor.recording = False
                        
                        with st.spinner("Распознаю вашу речь..."):
                            # Получаем распознанный текст
                            recognized_text = process_audio_frames(frames, sample_rate)
                        
                        # Добавляем сообщение пользователя в чат
                        st.session_state.chat1_messages.append({"role": "user", "content": recognized_text})
                        st.chat_message("user").write(recognized_text)
                        
                        # Обрабатываем запрос
                        with st.spinner("Генерирую ответ..."):
                            response = process_text_query(recognized_text, vector_db_path)
                        
                        # Синтез речи с помощью компонента HTML
                        if response:
                            # Добавляем компонент для синтеза речи
                            st.markdown(f"""
                            <div id="speech-container">
                                <script>
                                    try {{
                                        // Функция для безопасного синтеза речи
                                        function speakText() {{
                                            const text = {json.dumps(response)};
                                            if ('speechSynthesis' in window) {{
                                                const utterance = new SpeechSynthesisUtterance(text);
                                                utterance.lang = 'ru-RU';
                                                utterance.rate = 1.0;
                                                speechSynthesis.speak(utterance);
                                                console.log("Speaking: " + text);
                                            }} else {{
                                                console.error("Speech synthesis not supported");
                                            }}
                                        }}
                                        
                                        // Запуск синтеза речи при загрузке
                                        if (document.readyState === 'complete') {{
                                            speakText();
                                        }} else {{
                                            window.addEventListener('load', speakText);
                                        }}
                                    }} catch (e) {{
                                        console.error("Speech synthesis error:", e);
                                    }}
                                </script>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Очищаем записанные фреймы
                        st.session_state.audio_processor.frames = []
                    
                    st.rerun()
                        
        with button_cols[1]:
            if st.button("🔄 Обновить", use_container_width=True):
                # Перезапускаем WebRTC контекст
                st.session_state.webrtc_ctx = None
                st.session_state.audio_processor = None
                st.rerun()
            
        with button_cols[2]:
            if st.button("✖️ Выйти из голосового чата", use_container_width=True):
                end_msg = "Голосовой чат окончен"
                st.session_state.chat1_messages.append({"role": "assistant", "content": end_msg})
                st.session_state.voice_chat_active = False
                st.session_state.recording = False
                st.session_state.audio_processor = None
                st.session_state.webrtc_ctx = None
                st.rerun()
                
        # Инструкции по использованию
        st.markdown("""
        ### Инструкция по использованию:
        1. Нажмите "🎤 Начать запись" и разрешите доступ к микрофону в браузере
        2. Говорите в микрофон
        3. Нажмите "⏹️ Остановить запись" для обработки вашей речи
        4. Если запись не работает, нажмите "🔄 Обновить"
        """)

def process_text_query(prompt, vector_db_path):
    """Обрабатывает текстовый запрос и возвращает ответ, используя графовый чат"""
    try:
        # Создаем сообщение в формате HumanMessage
        messages = [HumanMessage(content=prompt)]
        
        # Вызываем графовый чат
        with st.chat_message("assistant"):
            with st.spinner("Обрабатываю запрос..."):
                # Вызываем графовый чат с динамическим путем к векторной базе
                res = chat_graph.invoke({
                    "messages": messages,
                    "vector_db_path": vector_db_path
                }, config={"configurable": {"thread_id": "default"}})
                
                # Получаем ответ из результата
                response = res['messages'][-1].content
                
                # Добавляем ответ в историю сообщений
                st.session_state.chat1_messages.append({"role": "assistant", "content": response})
                st.write(response)
                return response
    except Exception as e:
        error_msg = f"Произошла ошибка при обработке запроса: {str(e)}"
        st.error(error_msg)
        st.session_state.chat1_messages.append({"role": "assistant", "content": error_msg})
        return error_msg
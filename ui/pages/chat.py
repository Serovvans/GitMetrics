import streamlit as st

from langchain.schema import HumanMessage
from ai.graphs.chat_graph import chat_graph
import re

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
        repo_name = st.session_state["selected_repo"]["repo_name"]
        return f"storage/{repo_name}/vectore_store/"
    else:
        return "storage/default/vectore_store/"

def show_chat_page():
    st.title("Чат по выбранному репозиторию")

    # Инициализация переменных сессии
    if "selected_repo" not in st.session_state:
        st.session_state.selected_repo = None
    if "chat1_messages" not in st.session_state:
        st.session_state.chat1_messages = [
            {"role": "assistant", "content": "Привет! Чем могу помочь?"}
        ]
    
    if not st.session_state.get("selected_repo"):
        # Временное решение для тестирования
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

    # Текстовый чат
    if prompt := st.chat_input(placeholder="Введите запрос"):
        st.session_state.chat1_messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # Обработка текстового запроса
        process_text_query(prompt, vector_db_path)

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
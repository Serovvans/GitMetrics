import streamlit as st
from ui.pages import add_repository, chat, metrics, complexity, mistakes, code_smells, custom, problem_mistakes
from ui.sidebar import draw_common_sidebar
from ui.pages.problem_mistakes import draw_problem_sidebar

def main():
    st.set_page_config(layout="wide")
    
    # Инициализация состояния сессии
    if "selected_main_tab" not in st.session_state:
        st.session_state["selected_main_tab"] = "Добавить репозиторий"
    if "repositories" not in st.session_state:
        st.session_state["repositories"] = []
    if "selected_repo_index" not in st.session_state:
        st.session_state["selected_repo_index"] = None

    if st.session_state["selected_repo_index"] is not None and st.session_state["repositories"]:
        st.session_state["selected_repo"] = st.session_state["repositories"][st.session_state["selected_repo_index"]]

    # Основной список вкладок без динамических вкладок
    all_tabs = [
        "Добавить репозиторий",
        "Чат",
        "Метрики",
        "Сложность кода",
        "Ошибки",
        "Code Smells",
        "Кастомные метрики",
        "Проблемные файлы",
    ]

    # Определение пропорций колонок
    col_ratios = [2, 0.7, 1.1, 1.5, 1.1, 1.2, 1.8, 2]

    # Оборачиваем колонки в контейнер для применения кастомного CSS при необходимости
    st.write('<div class="tabs-container">', unsafe_allow_html=True)
    cols = st.columns(col_ratios, gap="small")
    for idx, tab in enumerate(all_tabs):
        disabled = (tab == st.session_state["selected_main_tab"])
        if cols[idx].button(tab, key=f"tab_{tab}", disabled=disabled):
            st.session_state["selected_main_tab"] = tab
            st.rerun()
    st.write('</div>', unsafe_allow_html=True)

    selected_tab = st.session_state["selected_main_tab"]

    # Отрисовка боковой панели в зависимости от выбранной вкладки
    if selected_tab.startswith("Проблемные файлы"):
        draw_problem_sidebar(prefix="problem")
    else:
        draw_common_sidebar(prefix="common")

    # Отображение контента страницы
    page_mapping = {
        "Добавить репозиторий": add_repository.show_add_repository_page,
        "Чат": chat.show_chat_page,
        "Метрики": metrics.show_metrics_page,
        "Сложность кода": complexity.show_complexity_page,
        "Ошибки": mistakes.show_mistakes_page,
        "Code Smells": code_smells.show_code_smells_page,
        "Кастомные метрики": custom.show_custom_page,
        "Проблемные файлы": problem_mistakes.show_problem_file,
    }
    
    if selected_tab in page_mapping:
        # Если это вкладка с проблемными файлами, можно передавать необходимые данные или пустой словарь
        if selected_tab.startswith("Проблемные файлы"):
            page_mapping[selected_tab]({})
        else:
            page_mapping[selected_tab]()

if __name__ == "__main__":
    main()

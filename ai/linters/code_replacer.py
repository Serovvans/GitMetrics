import json

def replace_code_in_file(file_path, fragments):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Обрабатываем фрагменты в обратном порядке, чтобы сдвиги не ломали индексы
    for fragment in sorted(fragments, key=lambda x: x['start_line'], reverse=True):
        start = fragment['start_line'] - 1  # индексы в файле начинаются с 0
        end = fragment['end_line']
        replacement_lines = fragment['solve'].splitlines(keepends=True)
        lines[start:end] = replacement_lines

    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(lines)

# Загружаем данные из JSON
with open("analysis_result.json", "r", encoding="utf-8") as json_file:
    analysis_data = json.load(json_file)

replace_code_in_file(analysis_data["file_path"], analysis_data["fragments"])

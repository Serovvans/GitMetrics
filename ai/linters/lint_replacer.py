import json

with open("lint_result.json", "r", encoding="utf-8") as json_file:
    data = json.load(json_file)

file_path = data["file_path"]
fixed_code = data["fixed_code"]

with open(file_path, "w", encoding="utf-8") as file:
    file.write(fixed_code)

print(f"Файл {file_path} успешно обновлён.")

import subprocess

get_ids = '''ids=$(xinput list | grep -Ei "id=[0-9]+" | grep -oE "id=[0-9]+" | cut -d= -f2)
declare -A button_map
for id in $ids; do
    output=$(xinput get-button-map "$id" 2>&1)
    # Исключаем сообщения об ошибках
    if [[ $output != *"device has no buttons"* && $output != *"X Error of failed request:"* ]]; then
        button_map["$id"]="$output"
    fi
done
# Формируем вывод как строку словаря
for id in "${!button_map[@]}"; do
    echo "$id:${button_map[$id]}"
done'''


# Выполнение вышеуказанной команды shell в подпроцессе и декодирование результата в строку.
id_list = subprocess.check_output(['bash', '-c', get_ids]).decode().splitlines()
print(id_list)
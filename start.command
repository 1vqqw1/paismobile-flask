#!/bin/bash

cd "$(dirname "$0")"

PORT=5001

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 не найден. Установите Python 3 и запустите файл снова."
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

find_python_with_flask() {
    for PY in \
        "./venv/bin/python" \
        "./.venv/bin/python" \
        "../venv/bin/python" \
        "../.venv/bin/python" \
        ../*/venv/bin/python \
        ../*/.venv/bin/python \
        "$(command -v python3)"
    do
        if [ -x "$PY" ] && "$PY" -c "import flask" >/dev/null 2>&1; then
            echo "$PY"
            return 0
        fi
    done
    return 1
}

PYTHON_BIN="$(find_python_with_flask)"

if [ -z "$PYTHON_BIN" ]; then
    if [ ! -d "venv" ]; then
        echo "Создаю виртуальное окружение..."
        python3 -m venv venv
    fi
    PYTHON_BIN="./venv/bin/python"

    if "$PYTHON_BIN" -c "import flask" >/dev/null 2>&1; then
        :
    else
        echo "Flask не найден. Пробую установить зависимости один раз..."
        if "$PYTHON_BIN" -m pip install -r requirements.txt; then
            echo "Зависимости установлены."
        else
            echo ""
            echo "Не удалось установить Flask: сейчас нет доступа к PyPI/интернету."
            echo "Подключитесь к интернету и запустите start.command ещё раз."
            echo "Если Flask уже был установлен раньше, не удаляйте папку venv при замене файлов сайта."
            echo ""
            read -p "Нажмите Enter для выхода..."
            exit 1
        fi
    fi
fi

echo "Запускаю Flask-сайт на http://127.0.0.1:$PORT"
(sleep 2; open "http://127.0.0.1:$PORT") &

echo "Чтобы остановить сайт, нажмите Ctrl+C в этом окне."
"$PYTHON_BIN" app.py

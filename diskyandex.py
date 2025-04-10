import sys
import os
import time
import requests
from tqdm import tqdm
from urllib.parse import urlencode

YANDEX_TOKEN = ""
DEFAULT_REMOTE_DIR = "/veron"

def upload_file(local_file_path, remote_dir, chunk_size):
    try:
        file_size = os.path.getsize(local_file_path)
    except OSError as e:
        print("Ошибка доступа к файлу:", e)
        return False

    remote_file_path = f"{remote_dir}/{os.path.basename(local_file_path)}"
    print(f"\nПодготовка загрузки файла: {local_file_path}")
    num_chunks = (file_size + chunk_size - 1) // chunk_size
    print(f"Размер файла: {file_size} байт. Будет загружено {num_chunks} чанков по {chunk_size} байт.")

    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    params = {"path": remote_file_path, "overwrite": "true"}
    response = requests.get("https://cloud-api.yandex.net/v1/disk/resources/upload",
                            headers=headers, params=params)
    if response.status_code != 200:
        print("Ошибка получения URL для загрузки:", response.text)
        return False

    upload_url = response.json().get("href")
    if not upload_url:
        print("Ошибка: URL для загрузки не получен.")
        return False

    start_time = time.time()
    with open(local_file_path, "rb") as f, tqdm(total=file_size, unit='B', unit_scale=True,
                                                 desc=f"Загрузка {os.path.basename(local_file_path)}", miniters=1) as progress_bar:
        def data_generator():
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                progress_bar.update(len(chunk))
                yield chunk

        put_response = requests.put(upload_url, data=data_generator(),
                                    headers={"Content-Type": "application/octet-stream"})

    elapsed = time.time() - start_time
    if put_response.status_code in (200, 201):
        print(f"Файл '{os.path.basename(local_file_path)}' успешно загружен за {elapsed:.2f} секунд.")
        return True
    else:
        print(f"Ошибка при загрузке файла '{os.path.basename(local_file_path)}': {put_response.status_code} {put_response.text}")
        return False
        
def download_file(remote_file_path, local_file_path):
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    params = {"path": remote_file_path}
    response = requests.get("https://cloud-api.yandex.net/v1/disk/resources/download",
                            headers=headers, params=params)
    if response.status_code != 200:
        print("Ошибка получения URL для скачивания:", response.text)
        return False

    download_url = response.json().get("href")
    if not download_url:
        print("Ошибка: URL для скачивания не получен.")
        return False

    r = requests.get(download_url, stream=True)
    total_size = int(r.headers.get('Content-Length', 0))
    with open(local_file_path, "wb") as f, tqdm(total=total_size, unit='B', unit_scale=True,
                                                 desc="Скачивание", miniters=1) as progress:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                progress.update(len(chunk))
    print(f"Скачивание завершено. Файл сохранён как '{local_file_path}'.")
    return True

def create_remote_directory(remote_dir_path):
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    params = {"path": remote_dir_path}
    response = requests.put("https://cloud-api.yandex.net/v1/disk/resources", headers=headers, params=params)
    if response.status_code in (201, 409): 
        print("Каталог успешно создан или уже существует.")
        return True
    else:
        print("Ошибка при создании каталога:", response.status_code, response.text)
        return False

def list_local_directory():
    current_dir = os.getcwd()
    print(f"\nСодержимое каталога: {current_dir}")
    for item in os.listdir(current_dir):
        print(item)

def change_local_directory():
    new_dir = input("Введите путь к новому каталогу: ").strip()
    try:
        os.chdir(new_dir)
        print("Текущий каталог:", os.getcwd())
    except Exception as e:
        print("Ошибка при смене каталога:", e)

def create_local_directory():
    new_dir = input("Введите имя нового каталога: ").strip()
    try:
        os.makedirs(new_dir, exist_ok=True)
        print("Каталог создан:", os.path.join(os.getcwd(), new_dir))
    except Exception as e:
        print("Ошибка при создании каталога:", e)

def choose_file_dialog_upload():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("Tkinter не доступен, невозможно открыть диалог выбора файла.")
        return
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Выберите файл для загрузки")
    root.destroy()
    if file_path:
        chunk_size_input = input("Введите размер чанка в МБ (по умолчанию 4): ").strip()
        try:
            chunk_size_mb = float(chunk_size_input) if chunk_size_input else 4.0
        except ValueError:
            print("Неверный ввод. Используем 4 МБ.")
            chunk_size_mb = 4.0
        chunk_size = int(chunk_size_mb * 1024 * 1024)
        remote_dir = input(f"Введите путь на Яндекс.Диске для загрузки (по умолчанию {DEFAULT_REMOTE_DIR}): ").strip() or DEFAULT_REMOTE_DIR
        upload_file(file_path, remote_dir, chunk_size)
    else:
        print("Файл не выбран.")

def list_remote_files(remote_path="/"):
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    params = {"path": remote_path, "fields": "_embedded.items", "limit": 1000}
    response = requests.get("https://cloud-api.yandex.net/v1/disk/resources", headers=headers, params=params)
    if response.status_code != 200:
        print("Ошибка получения списка файлов:", response.text)
        return []
    data = response.json()
    items = data.get("_embedded", {}).get("items", [])
    if not items:
        print("Нет файлов в каталоге", remote_path)
    else:
        print(f"\nСодержимое Яндекс.Диска в каталоге {remote_path}:")
        for idx, item in enumerate(items, start=1):
            print(f"{idx}. {item.get('name')}  ({item.get('resource_type')})  - {item.get('path')}")
    return items

def download_remote_file_dialog():
    remote_dir = input("Введите путь на Яндекс.Диске для просмотра файлов (по умолчанию /): ").strip() or "/"
    items = list_remote_files(remote_dir)
    if not items:
        return
    choice = input("Введите номер файла для скачивания: ").strip()
    try:
        choice = int(choice)
        if choice < 1 or choice > len(items):
            print("Неверный номер файла.")
            return
    except ValueError:
        print("Нужно ввести число.")
        return
    selected = items[choice - 1]
    remote_file = selected.get("path")
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        local_save = input("Введите путь для сохранения файла: ").strip()
    else:
        root = tk.Tk()
        root.withdraw()
        local_save = filedialog.asksaveasfilename(title="Выберите место для сохранения загруженного файла",
                                                   initialfile=selected.get("name"))
        root.destroy()
        if not local_save:
            print("Файл не выбран для сохранения.")
            return
    download_file(remote_file, local_save)

def perform_download():
    remote_file = input("Введите путь к файлу на Яндекс.Диске (например, /veron/имя_файла): ").strip()
    local_file = input("Введите локальное имя файла для сохранения: ").strip()
    download_file(remote_file, local_file)

def perform_remote_create_directory():
    remote_dir_path = input("Введите путь для создания каталога на Яндекс.Диске: ").strip()
    create_remote_directory(remote_dir_path)

def perform_upload():
    local_file = input("Введите путь к файлу для загрузки: ").strip()
    if not os.path.isfile(local_file):
        print("Файл не найден.")
        return
    chunk_size_input = input("Введите размер чанка в МБ (по умолчанию 4): ").strip()
    try:
        chunk_size_mb = float(chunk_size_input) if chunk_size_input else 4.0
    except ValueError:
        print("Неверный ввод. Используем 4 МБ.")
        chunk_size_mb = 4.0
    chunk_size = int(chunk_size_mb * 1024 * 1024)
    remote_dir = input(f"Введите путь на Яндекс.Диске для загрузки (по умолчанию {DEFAULT_REMOTE_DIR}): ").strip() or DEFAULT_REMOTE_DIR
    upload_file(local_file, remote_dir, chunk_size)

def interactive_mode():
    while True:
        print("\nВыберите действие:")
        print("1. Показать содержимое текущего каталога (локальный)")
        print("2. Перейти в другой каталог (локальный)")
        print("3. Создать новый каталог (локальный)")
        print("4. Загрузить файл на Яндекс.Диск (ввод пути вручную)")
        print("5. Открыть диалог выбора файла для загрузки на Яндекс.Диск")
        print("6. Скачать файл с Яндекс.Диска (ввод пути вручную)")
        print("7. Создать каталог на Яндекс.Диске")
        print("8. Показать содержимое Яндекс.Диска")
        print("9. Скачать файл с Яндекс.Диска (с выбором через диалог)")
        print("10. Выход")
        choice = input("Введите номер операции: ").strip()
        if choice == "1":
            list_local_directory()
        elif choice == "2":
            change_local_directory()
        elif choice == "3":
            create_local_directory()
        elif choice == "4":
            perform_upload()
        elif choice == "5":
            choose_file_dialog_upload()
        elif choice == "6":
            perform_download()
        elif choice == "7":
            perform_remote_create_directory()
        elif choice == "8":
            remote_path = input("Введите путь на Яндекс.Диске для просмотра (по умолчанию /): ").strip() or "/"
            list_remote_files(remote_path)
        elif choice == "9":
            download_remote_file_dialog()
        elif choice == "10":
            print("Выход из программы.")
            break
        else:
            print("Неверный выбор. Повторите попытку.")

def main():
    if len(sys.argv) > 1:
        local_path = sys.argv[1]
        chunk_size_mb = 4.0
        chunk_size = int(chunk_size_mb * 1024 * 1024)
        if os.path.isdir(local_path):
            print(f"Обнаружена папка: {local_path}")
            files = [os.path.join(local_path, f) for f in os.listdir(local_path)
                     if os.path.isfile(os.path.join(local_path, f))]
            if not files:
                print("Папка не содержит файлов для загрузки.")
            else:
                print(f"Будет загружено {len(files)} файлов из папки '{local_path}'.")
                for file in files:
                    upload_file(file, DEFAULT_REMOTE_DIR, chunk_size)
        elif os.path.isfile(local_path):
            upload_file(local_path, DEFAULT_REMOTE_DIR, chunk_size)
        else:
            print(f"Ошибка: '{local_path}' не является файлом или папкой.")
    else:
        print("Запуск в интерактивном режиме.")
        interactive_mode()

if __name__ == "__main__":
    main()

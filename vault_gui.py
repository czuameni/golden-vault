import os
import base64
import hashlib
import shutil
import zipfile
from datetime import datetime
from cryptography.fernet import Fernet
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter.ttk import Progressbar, Combobox
from tkinter import ttk


CHECK_FILE = ".vault_check"
CHECK_TEXT = b"VAULT_OK"


vault_unlocked = False
idle_seconds = 60
idle_job = None
vault_map = {}

vault_checkboxes = {}

vault_max_size_gb = 5

BACKUP_DIR = "Backups"

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)


import json

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "vault_max_size_gb": 5,
    "idle_seconds": 60
}


def load_settings():

    global vault_max_size_gb
    global idle_seconds

    if not os.path.exists(SETTINGS_FILE):
        return

    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)

        vault_max_size_gb = data.get(
            "vault_max_size_gb", 5
        )

        idle_seconds = data.get(
            "idle_seconds", 60
        )

    except Exception as e:
        print("Load settings error:", e)


def save_settings(limit, idle):

    settings = {
        "vault_max_size_gb": limit,
        "idle_seconds": idle
    }

    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)


def generate_key(password: str) -> bytes:
    password = password.strip()

    return base64.urlsafe_b64encode(
        hashlib.sha256(password.encode()).digest()
    )


def encrypt_file(path, fernet):
    with open(path, "rb") as f:
        data = f.read()

    with open(path, "wb") as f:
        f.write(fernet.encrypt(data))


def decrypt_file(path, fernet):
    with open(path, "rb") as f:
        data = f.read()

    with open(path, "wb") as f:
        f.write(fernet.decrypt(data))


import random

def wipe_file(file_path, passes=3):
    """
    Secure overwrite pliku losowymi danymi.
    passes = ilość nadpisań.
    """

    if not os.path.isfile(file_path):
        return

    length = os.path.getsize(file_path)

    try:
        with open(file_path, "r+b") as f:

            for _ in range(passes):

                # losowe dane
                random_data = os.urandom(length)

                f.seek(0)
                f.write(random_data)
                f.flush()
                os.fsync(f.fileno())

    except Exception as e:
        print("Wipe error:", e)


def create_check_file(folder, fernet):
    path = os.path.join(folder, CHECK_FILE)

    with open(path, "wb") as f:
        f.write(fernet.encrypt(CHECK_TEXT))


def verify_password(folder, fernet):
    path = os.path.join(folder, CHECK_FILE)

    if not os.path.exists(path):
        print("Brak pliku kontrolnego!")
        return False

    try:
        with open(path, "rb") as f:
            data = f.read()

        if not data:
            print("Pusty plik kontrolny!")
            return False

        return fernet.decrypt(data) == CHECK_TEXT

    except Exception as e:
        print("Verify error:", e)
        return False


def is_folder_locked(folder, fernet):
    path = os.path.join(folder, CHECK_FILE)

    if not os.path.exists(path):
        return False

    try:
        with open(path, "rb") as f:
            data = f.read()

        return fernet.decrypt(data) == CHECK_TEXT
    except:
        return False

def get_vault_status(folder):
    unlocked_flag = os.path.join(folder, ".unlocked")

    if os.path.exists(unlocked_flag):
        return "🔓"
    else:
        return "🔒"


def get_status_color(folder):
    unlocked_flag = os.path.join(folder, ".unlocked")

    if os.path.exists(unlocked_flag):
        return "green"
    else:
        return "red"


def extract_vault_name(display_name):
    return display_name.rsplit(" ", 1)[0]


from datetime import datetime

LOG_FILE = "vault_log.txt"


def write_log(operation, vault_name, status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_line = (
        f"[{now}] | {operation} | {vault_name} | {status}\n"
    )

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)

    except Exception as e:
        print("Log write error:", e)


def backup_vault():
    display_name = vault_combo.get()

    if not display_name:
        messagebox.showerror(
            "Błąd",
            "Wybierz sejf do backupu!"
        )
        return

    vault_name = extract_vault_name(display_name)
    folder = vault_map.get(vault_name)

    if not folder or not os.path.isdir(folder):
        messagebox.showerror(
            "Błąd",
            "Folder sejfu nie istnieje!"
        )
        return

    try:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_name = f"{vault_name}_{now}"
        backup_path = os.path.join(
            BACKUP_DIR,
            backup_name
        )

        shutil.make_archive(
            backup_path,
            'zip',
            folder
        )

        write_log("BACKUP", vault_name, "SUCCESS")

        messagebox.showinfo(
            "Backup",
            f"Backup sejfu utworzony:\n{backup_name}.zip"
        )

    except Exception as e:
        write_log("BACKUP", vault_name, "FAILED")

        messagebox.showerror(
            "Błąd backupu",
            str(e)
        )


def restore_backup():

    zip_path = filedialog.askopenfilename(
        title="Wybierz backup sejfu",
        filetypes=[("ZIP files", "*.zip")]
    )

    if not zip_path:
        return

    display_name = vault_combo.get()

    if not display_name:
        messagebox.showerror(
            "Błąd",
            "Wybierz sejf do przywrócenia!"
        )
        return

    vault_name = extract_vault_name(display_name)
    folder = vault_map.get(vault_name)

    if not folder or not os.path.isdir(folder):
        messagebox.showerror(
            "Błąd",
            "Folder sejfu nie istnieje!"
        )
        return

    confirm = messagebox.askyesno(
        "Restore backup",
        "Czy na pewno przywrócić backup?\n"
        "Obecna zawartość sejfu zostanie NADPISANA."
    )

    if not confirm:
        return

    try:
        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)

            if os.path.isfile(item_path):
                os.remove(item_path)
            else:
                shutil.rmtree(item_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(folder)

        write_log(
            "RESTORE_BACKUP",
            vault_name,
            "SUCCESS"
        )

        refresh_vaults()
        update_vault_color()
        update_vault_info()

        messagebox.showinfo(
            "Gotowe",
            "Backup został przywrócony 🔄"
        )

    except Exception as e:

        write_log(
            "RESTORE_BACKUP",
            vault_name,
            "FAILED"
        )

        messagebox.showerror(
            "Błąd restore",
            str(e)
        )


def open_log_viewer():

    if not os.path.exists(LOG_FILE):
        messagebox.showinfo(
            "Log Viewer",
            "Brak pliku logów."
        )
        return

    viewer = tk.Toplevel(app)
    viewer.title("Vault Log Viewer")
    viewer.geometry("700x400")

    frame = tk.Frame(viewer)
    frame.pack(fill="both", expand=True)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")

    text_box = tk.Text(
        frame,
        yscrollcommand=scrollbar.set,
        wrap="none"
    )
    text_box.pack(fill="both", expand=True)

    scrollbar.config(command=text_box.yview)

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        text_box.insert("1.0", content)
        text_box.config(state="disabled")

    except Exception as e:
        messagebox.showerror(
            "Błąd",
            f"Nie udało się otworzyć logu:\n{e}"
        )


def open_settings():

    win = tk.Toplevel(app)
    win.title("Settings")
    win.geometry("300x200")

    tk.Label(
        win,
        text="Vault size limit (GB):"
    ).pack(pady=5)

    limit_var = tk.StringVar(
        value=str(vault_max_size_gb)
    )

    limit_entry_gui = tk.Entry(
        win,
        textvariable=limit_var
    )
    limit_entry_gui.pack()

    tk.Label(
        win,
        text="Idle auto-lock (seconds):"
    ).pack(pady=5)

    idle_var = tk.StringVar(
        value=str(idle_seconds)
    )

    idle_entry_gui = tk.Entry(
        win,
        textvariable=idle_var
    )
    idle_entry_gui.pack()

    def save():

        try:
            new_limit = float(limit_var.get())
            new_idle = int(idle_var.get())

            save_settings(new_limit, new_idle)

            load_settings()

            messagebox.showinfo(
                "Settings",
                "Ustawienia zapisane ✅"
            )

            win.destroy()

        except:
            messagebox.showerror(
                "Błąd",
                "Nieprawidłowe wartości!"
            )

    tk.Button(
        win,
        text="💾 Zapisz ustawienia",
        command=save
    ).pack(pady=15)


def create_vault():

    folder = filedialog.askdirectory(
        title="Wybierz folder do utworzenia sejfu"
    )

    if not folder:
        return

    password = entry_password.get()

    if not password:
        messagebox.showerror(
            "Błąd",
            "Podaj hasło do sejfu!"
        )
        return

    try:
        key = generate_key(password)
        fernet = Fernet(key)

        process_folder(folder, "lock", fernet)

        create_check_file(folder, fernet)

        write_log(
            "CREATE_VAULT",
            os.path.basename(folder),
            "SUCCESS"
        )

        messagebox.showinfo(
            "Gotowe",
            "Sejf został utworzony 🔐"
        )

        refresh_vaults()

    except Exception as e:
        print("Create vault error:", e)

        messagebox.showerror(
            "Błąd",
            "Nie udało się utworzyć sejfu!"
        )


def update_vault_info(event=None):
    selected = vault_combo.get()

    if not selected:
        info_label.config(text="📊 Brak danych o sejfie")
        return

    vault_name = extract_vault_name(selected)
    folder = vault_map.get(vault_name)

    if not folder or not os.path.isdir(folder):
        info_label.config(text="📊 Folder nie istnieje")
        return

    files = count_files(folder)
    size = get_folder_size(folder)

    fill_percent = get_vault_fill_percent(folder)

    vault_fill_bar["value"] = fill_percent
    vault_fill_label.config(
        text=f"Zapełnienie: {fill_percent}%"
    )

    if fill_percent < 60:
        style_name = "Green.Horizontal.TProgressbar"

    elif fill_percent < 85:
        style_name = "Orange.Horizontal.TProgressbar"

    else:
        style_name = "Red.Horizontal.TProgressbar"

    vault_fill_bar.configure(style=style_name)

    status = "OTWARTY 🔓" if os.path.exists(
        os.path.join(folder, ".unlocked")
    ) else "ZAMKNIĘTY 🔒"

    info_text = (
        f"📊 Sejf: {vault_name}\n"
        f"📁 Pliki: {files}\n"
        f"💾 Rozmiar: {size} MB\n"
        f"🔐 Status: {status}"
    )

    info_label.config(text=info_text)


def count_files(folder):
    total = 0

    SYSTEM_FILES = (
        CHECK_FILE,
        ".unlocked",
        "desktop.ini",
        "Thumbs.db",
    )

    for root, dirs, files in os.walk(folder):
        for name in files:

            if name in SYSTEM_FILES:
                continue

            total += 1

    return total


def get_folder_size(folder):
    total_size = 0

    SYSTEM_FILES = (
        CHECK_FILE,
        ".unlocked",
        "desktop.ini",
        "Thumbs.db",
    )

    for root, dirs, files in os.walk(folder):
        for name in files:

            if name in SYSTEM_FILES:
                continue

            path = os.path.join(root, name)
            total_size += os.path.getsize(path)

    return round(total_size / (1024 * 1024), 2)


def get_vault_fill_percent(folder):
    size_mb = get_folder_size(folder)

    max_mb = vault_max_size_gb * 1024

    percent = (size_mb / max_mb) * 100

    return min(round(percent, 2), 100)


def is_vault_over_limit(folder):
    size_mb = get_folder_size(folder)

    max_mb = vault_max_size_gb * 1024

    encrypted_estimate = size_mb * 1.15

    return encrypted_estimate >= max_mb


def update_vault_limit(event=None):
    global vault_max_size_gb

    try:
        value = float(limit_entry.get())

        if value <= 0:
            raise ValueError

        vault_max_size_gb = value

        update_vault_info()

    except:
        messagebox.showerror(
            "Błąd",
            "Podaj poprawny limit w GB!"
        )


def check_vault_fill_alert(folder):
    percent = get_vault_fill_percent(folder)

    if percent >= 80 and percent < 95:
        messagebox.showwarning(
            "Uwaga",
            f"⚠️ Sejf zaczyna się zapełniać\n"
            f"Obecne zapełnienie: {percent}%"
        )

    elif percent >= 95:
        messagebox.showerror(
            "Krytyczne zapełnienie",
            f"🚨 Sejf jest prawie pełny!\n"
            f"Obecne zapełnienie: {percent}%\n"
            f"Rozważ usunięcie plików."
        )


def process_folder(folder, mode, fernet):

    total_files = count_files(folder)
    processed = 0
    decrypted_any = False

    if total_files == 0:
        return True

    for root, dirs, files in os.walk(folder):
        for name in files:

            if name in (CHECK_FILE, ".unlocked"):
                continue

            full_path = os.path.join(root, name)

            try:
                if mode == "lock":
                    encrypt_file(full_path, fernet)

                elif mode == "unlock":
                    decrypt_file(full_path, fernet)
                    decrypted_any = True

            except Exception:
                pass

            processed += 1
            progress["value"] = (
                processed / total_files
            ) * 100
            app.update_idletasks()

    if mode == "unlock":
        return decrypted_any

    return True


def secure_wipe_folder(folder):

    SYSTEM_FILES = (
        CHECK_FILE,
        ".unlocked",
        "desktop.ini",
        "Thumbs.db",
    )

    total_files = count_files(folder)
    wiped = 0

    if total_files == 0:
        return True

    for root, dirs, files in os.walk(folder):

        for name in files:

            if name in SYSTEM_FILES:
                continue

            full_path = os.path.join(root, name)

            try:
                wipe_file(full_path)

                os.remove(full_path)

            except Exception as e:
                print("Wipe error:", e)

            wiped += 1

            progress["value"] = (
                wiped / total_files
            ) * 100

            app.update_idletasks()

    return True


def scan_for_vaults():

    global vault_map

    desktop = os.path.join(
        os.path.expanduser("~"),
        "Desktop"
    )

    vault_map.clear()
    vault_display = []

    if not os.path.exists(desktop):
        return []

    for item in os.listdir(desktop):

        full_path = os.path.join(desktop, item)

        if not os.path.isdir(full_path):
            continue

        check_file = os.path.join(
            full_path,
            CHECK_FILE
        )

        if not os.path.exists(check_file):
            continue

        status = get_vault_status(full_path)

        display_name = f"{item} {status}"

        vault_map[item] = full_path

        vault_display.append(display_name)

    return vault_display


def choose_folder():
    folder_selected = filedialog.askdirectory()

    if folder_selected:
        entry_folder.delete(0, tk.END)
        entry_folder.insert(0, folder_selected)


def reset_idle_timer(event=None):
    global idle_job

    if idle_job:
        app.after_cancel(idle_job)

    idle_job = app.after(idle_seconds * 1000, idle_lock)


def idle_lock():
    global vault_unlocked

    if vault_unlocked:
        display_name = vault_combo.get()
        vault_name = extract_vault_name(display_name)
        folder = vault_map.get(vault_name)
        password = entry_password.get()

        if not folder or not isinstance(folder, str):
            print("Idle lock: brak poprawnego folderu")
            return

        if os.path.isdir(folder) and password:

            if is_vault_over_limit(folder):
                messagebox.showwarning(
                    "Limit sejfu",
                    "⚠️ Sejf przekroczył limit.\n"
                    "Auto-lock został zablokowany."
                )
                return

            try:
                key = generate_key(password)
                fernet = Fernet(key)

                process_folder(folder, "lock", fernet)
                create_check_file(folder, fernet)

                vault_unlocked = False

                write_log("IDLE_LOCK", vault_name, "SUCCESS")

                flag = os.path.join(folder, ".unlocked")
                if os.path.exists(flag):
                    os.remove(flag)

                refresh_vaults()
                update_vault_color()
                update_vault_info()

                check_vault_fill_alert(folder)

                messagebox.showinfo(
                    "Idle lock",
                    "Sejf zamknięty z powodu bezczynności ⏱️"
                )

            except Exception as e:
                print("Idle auto-lock failed:", e)


def batch_lock_unlock(mode):

    selected_vaults = [
        (name, data[1])
        for name, data in vault_checkboxes.items()
        if data[0].get()
    ]

    if not selected_vaults:
        messagebox.showwarning(
            "Batch",
            "Zaznacz przynajmniej jeden sejf!"
        )
        return

    password = entry_password.get()

    if not password:
        messagebox.showerror(
            "Błąd",
            "Podaj hasło!"
        )
        return

    for vault_name, folder in selected_vaults:

        if not os.path.isdir(folder):
            print("Batch: folder missing →", folder)
            continue

        try:
            key = generate_key(password)
            fernet = Fernet(key)

            if mode == "lock":

                process_folder(folder, "lock", fernet)
                create_check_file(folder, fernet)

                flag = os.path.join(folder, ".unlocked")
                if os.path.exists(flag):
                    os.remove(flag)

                write_log("BATCH_LOCK", vault_name, "SUCCESS")

            elif mode == "unlock":

                if not verify_password(folder, fernet):
                    write_log(
                        "BATCH_UNLOCK",
                        vault_name,
                        "WRONG_PASSWORD"
                    )
                    continue

                process_folder(folder, "unlock", fernet)

                flag = os.path.join(folder, ".unlocked")
                with open(flag, "w") as f:
                    f.write("open")

                write_log("BATCH_UNLOCK", vault_name, "SUCCESS")

        except Exception as e:
            print("Batch error:", e)

    refresh_vaults()

    messagebox.showinfo(
        "Batch",
        "Operacja zakończona ✅"
    )


def refresh_multi_vault_panel():

    for widget in multi_vault_frame.winfo_children():
        widget.destroy()

    vault_checkboxes.clear()

    for vault_name, folder in vault_map.items():

        var = tk.BooleanVar()

        cb = tk.Checkbutton(
            multi_vault_frame,
            text=vault_name,
            variable=var,
            anchor="w"
        )

        cb.pack(fill="x")

        vault_checkboxes[vault_name] = (var, folder)


def lock_folder():
    global vault_unlocked

    display_name = vault_combo.get()
    vault_name = extract_vault_name(display_name)
    folder = vault_map.get(vault_name)
    password = entry_password.get()

    if not folder or not isinstance(folder, str) or not os.path.isdir(folder):
        messagebox.showerror("Błąd", "Folder nie istnieje!")
        return

    if is_vault_over_limit(folder):
        messagebox.showerror(
            "Limit sejfu",
            "❌ Sejf przekroczył maksymalny rozmiar!\n"
            "Usuń część plików przed zamknięciem."
        )
        return

    key = generate_key(password)
    fernet = Fernet(key)

    progress["value"] = 0
    process_folder(folder, "lock", fernet)

    create_check_file(folder, fernet)

    vault_unlocked = False

    write_log("LOCK", vault_name, "SUCCESS")
    

    flag = os.path.join(folder, ".unlocked")
    if os.path.exists(flag):
        os.remove(flag)

    refresh_vaults()
    update_vault_color()
    update_vault_info()

    check_vault_fill_alert(folder)

    messagebox.showinfo("Gotowe", "Folder został ZAMKNIĘTY 🔒")


def unlock_folder():
    global vault_unlocked

    display_name = vault_combo.get()
    vault_name = extract_vault_name(display_name)
    folder = vault_map.get(vault_name)
    password = entry_password.get()

    if not password:
        messagebox.showerror(
            "Błąd",
            "Podaj hasło do sejfu!"
        )
        return

    if not folder or not isinstance(folder, str) or not os.path.isdir(folder):
        messagebox.showerror("Błąd", "Folder nie istnieje!")
        return

    key = generate_key(password)
    fernet = Fernet(key)

    if not verify_password(folder, fernet):
        messagebox.showerror(
            "Błąd",
            "❌ Nieprawidłowe hasło!"
        )
        write_log("OPEN", vault_name, "WRONG_PASSWORD")
        return

    progress["value"] = 0

    success = process_folder(folder, "unlock", fernet)

    if not success:
        messagebox.showerror(
            "Błąd",
            "❌ Nie udało się odszyfrować plików!"
        )
        write_log("OPEN", vault_name, "DECRYPT_FAILED")
        return

    vault_unlocked = True

    flag = os.path.join(folder, ".unlocked")
    with open(flag, "w") as f:
        f.write("open")

    reset_idle_timer()

    refresh_vaults()
    update_vault_color()
    update_vault_info()

    write_log("OPEN", vault_name, "SUCCESS")
    

    messagebox.showinfo(
        "Gotowe",
        "Folder został OTWARTY 🔓"
    )

def change_password():
    display_name = vault_combo.get()
    vault_name = extract_vault_name(display_name)
    folder = vault_map.get(vault_name)

    unlocked_flag = os.path.join(folder, ".unlocked")

    if os.path.exists(unlocked_flag):
        messagebox.showerror(
            "Błąd",
            "❌ Zamknij sejf przed zmianą hasła!"
        )
        return

    old_password = entry_password.get()
    new_password = entry_new_password.get()

    if not folder or not os.path.isdir(folder):
        messagebox.showerror("Błąd", "Folder nie istnieje!")
        return

    if not new_password:
        messagebox.showerror("Błąd", "Podaj nowe hasło!")
        return

    old_key = generate_key(old_password)
    old_fernet = Fernet(old_key)

    if not verify_password(folder, old_fernet):
        messagebox.showerror(
            "Błąd",
            "❌ Stare hasło nieprawidłowe!"
        )
        write_log(
            "CHANGE_PASSWORD",
            vault_name,
            "WRONG_PASSWORD"
        )
        return

    progress["value"] = 0

    for root, dirs, files in os.walk(folder):
        for name in files:

            if name in (CHECK_FILE, ".unlocked"):
                continue

            full_path = os.path.join(root, name)

            try:
                decrypt_file(full_path, old_fernet)
            except:
                pass

    check_path = os.path.join(folder, CHECK_FILE)

    if os.path.exists(check_path):
        os.remove(check_path)

    new_key = generate_key(new_password)
    new_fernet = Fernet(new_key)

    process_folder(folder, "lock", new_fernet)
    create_check_file(folder, new_fernet)

    write_log(
        "CHANGE_PASSWORD",
        vault_name,
        "SUCCESS"
    )

    messagebox.showinfo(
        "Gotowe",
        "Hasło zostało zmienione 🔑"
    )


def secure_wipe_vault():

    display_name = vault_combo.get()

    if not display_name:
        messagebox.showerror(
            "Błąd",
            "Wybierz sejf do usunięcia!"
        )
        return

    vault_name = extract_vault_name(display_name)
    folder = vault_map.get(vault_name)

    if not folder or not os.path.isdir(folder):
        messagebox.showerror(
            "Błąd",
            "Folder nie istnieje!"
        )
        return

    confirm = messagebox.askyesno(
        "SECURE WIPE",
        "Czy na pewno chcesz TRWALE usunąć dane sejfu?\n\n"
        "Operacja NADPISZE wszystkie pliki.\n"
        "Nie ma możliwości odzyskania."
    )

    if not confirm:
        return

    confirm2 = messagebox.askyesno(
        "OSTATECZNE POTWIERDZENIE",
        "To jest NIEODWRACALNE.\n\n"
        "Kontynuować secure wipe?"
    )

    if not confirm2:
        return

    try:
        progress["value"] = 0

        secure_wipe_folder(folder)

        write_log(
            "SECURE_WIPE",
            vault_name,
            "SUCCESS"
        )

        refresh_vaults()
        update_vault_color()
        update_vault_info()

        messagebox.showwarning(
            "SECURE WIPE",
            "Dane sejfu zostały trwale usunięte 💀"
        )

    except Exception as e:

        write_log(
            "SECURE_WIPE",
            vault_name,
            "FAILED"
        )

        messagebox.showerror(
            "Błąd wipe",
            str(e)
        )


def panic_lock_all():
    global vault_unlocked

    confirm = messagebox.askyesno(
        "PANIC",
        "Czy na pewno zamknąć WSZYSTKIE sejfy?\n"
        "Operacja natychmiastowa."
    )

    if not confirm:
        return

    for vault_name, folder in vault_map.items():

        if not os.path.isdir(folder):
            continue

        password = entry_password.get()

        if not password:
            continue

        try:
            key = generate_key(password)
            fernet = Fernet(key)

            process_folder(folder, "lock", fernet)
            create_check_file(folder, fernet)

            flag = os.path.join(folder, ".unlocked")
            if os.path.exists(flag):
                os.remove(flag)

            write_log("PANIC_LOCK", vault_name, "SUCCESS")

        except Exception as e:
            print("Panic lock error:", e)
            write_log("PANIC_LOCK", vault_name, "FAILED")

    vault_unlocked = False

    refresh_vaults()
    update_vault_color()
    update_vault_info()

    messagebox.showwarning(
        "PANIC",
        "🚨 Wszystkie sejfy zostały zamknięte!"
    )

    app.destroy()


def smart_panic():

    locked_any = False

    for vault_name, folder in vault_map.items():

        if not os.path.isdir(folder):
            continue

        unlocked_flag = os.path.join(folder, ".unlocked")

        if not os.path.exists(unlocked_flag):
            continue

        password = entry_password.get()

        if not password:
            continue

        try:
            key = generate_key(password)
            fernet = Fernet(key)

            process_folder(folder, "lock", fernet)
            create_check_file(folder, fernet)

            os.remove(unlocked_flag)

            write_log("SMART_PANIC", vault_name, "SUCCESS")

            locked_any = True

        except Exception as e:
            print("Smart panic error:", e)
            write_log("SMART_PANIC", vault_name, "FAILED")

    vault_unlocked = False

    refresh_vaults()
    update_vault_color()
    update_vault_info()

    if locked_any:
        messagebox.showwarning(
            "SMART PANIC",
            "🚨 Otwarte sejfy zostały zamknięte!"
        )
    else:
        messagebox.showinfo(
            "SMART PANIC",
            "Brak otwartych sejfów."
        )


def on_close():
    global vault_unlocked

    if vault_unlocked:
        display_name = vault_combo.get()
        vault_name = extract_vault_name(display_name)
        folder = vault_map.get(vault_name)
        password = entry_password.get()

        if not folder or not isinstance(folder, str):
            print("On close: brak poprawnego folderu")
            app.destroy()
            return

        if os.path.isdir(folder) and password:

            if is_vault_over_limit(folder):
                print(
                    "Auto-lock przy zamknięciu zablokowany — limit przekroczony"
                )
                app.destroy()
                return

            try:
                key = generate_key(password)
                fernet = Fernet(key)

                process_folder(folder, "lock", fernet)
                create_check_file(folder, fernet)

                write_log("AUTO_LOCK", vault_name, "SUCCESS")
                

                flag = os.path.join(folder, ".unlocked")
                if os.path.exists(flag):
                    os.remove(flag)

                print("Auto-lock przy zamknięciu wykonany 🔒")

            except Exception as e:
                print(
                    "Auto-lock przy zamknięciu nie powiódł się:",
                    e
                )

    app.destroy()


def refresh_vaults():

    global vault_list

    current_selection = vault_combo.get()

    vault_list = scan_for_vaults()
    vault_combo["values"] = vault_list

    if current_selection in vault_list:
        vault_combo.set(current_selection)

    refresh_multi_vault_panel()


def update_vault_color(event=None):
    selected = vault_combo.get()

    if not selected:
        return

    vault_name = extract_vault_name(selected)
    folder = vault_map.get(vault_name)

    if not folder:
        return

    color = get_status_color(folder)

    status_label.config(fg=color)


def clean_unlocked_flags():

    desktop = os.path.join(
        os.path.expanduser("~"),
        "Desktop"
    )

    if not os.path.exists(desktop):
        return

    for item in os.listdir(desktop):

        folder = os.path.join(desktop, item)

        if not os.path.isdir(folder):
            continue

        flag = os.path.join(folder, ".unlocked")

        if os.path.exists(flag):
            os.remove(flag)




load_settings()


app = tk.Tk()
app.title("Golden Vault")
app.geometry("420x260")

app.iconbitmap("vault.ico")

style = ttk.Style()
style.theme_use("clam")


style.configure("Vault.TCombobox", foreground="black")


style.configure(
    "Green.Horizontal.TProgressbar",
    troughcolor="white",
    background="green"
)

style.configure(
    "Orange.Horizontal.TProgressbar",
    troughcolor="white",
    background="orange"
)

style.configure(
    "Red.Horizontal.TProgressbar",
    troughcolor="white",
    background="red"
)

tk.Label(app, text="Sejf:").pack(pady=5)

status_label = tk.Label(app, text="●", font=("Arial", 14))
status_label.pack()

info_label = tk.Label(
    app,
    text="📊 Brak danych o sejfie",
    justify="left"
)
info_label.pack(pady=5)

vault_fill_bar = Progressbar(
    app,
    orient="horizontal",
    length=250,
    mode="determinate",
    style="Green.Horizontal.TProgressbar"
)
vault_fill_bar.pack(pady=5)

vault_fill_label = tk.Label(app, text="Zapełnienie: 0%")
vault_fill_label.pack()


limit_label = tk.Label(app, text="Limit sejfu (GB):")
limit_label.pack()

limit_entry = tk.Entry(app, width=10)
limit_entry.pack()

limit_entry.bind("<Return>", update_vault_limit)

vault_list = []

vault_combo = Combobox(
    app,
    values=vault_list,
    width=50,
    style="Vault.TCombobox",
    state="readonly"
)
vault_combo.pack()


multi_vault_frame = tk.LabelFrame(
    app,
    text="Batch Operations",
    padx=5,
    pady=5
)
multi_vault_frame.pack(pady=5)

vault_checkboxes = {}


vault_combo.bind("<<ComboboxSelected>>", update_vault_color)
vault_combo.bind("<<ComboboxSelected>>", update_vault_info)


limit_entry.delete(0, tk.END)
limit_entry.insert(0, str(vault_max_size_gb))

app.after(100, refresh_vaults)


load_settings()

limit_entry.delete(0, tk.END)
limit_entry.insert(0, str(vault_max_size_gb))


app.after(100, refresh_vaults)


tk.Button(app, text="🔄 Odśwież listę", command=refresh_vaults).pack(pady=5)

tk.Label(app, text="Hasło:").pack(pady=5)

entry_password = tk.Entry(app, show="*", width=30)
entry_password.pack()

tk.Label(app, text="Nowe hasło:").pack(pady=5)

entry_new_password = tk.Entry(app, show="*", width=30)
entry_new_password.pack()


buttons_frame = tk.Frame(app)
buttons_frame.pack(pady=5)


tk.Button(
    buttons_frame,
    text="🔓 Otwórz sejf",
    command=unlock_folder,
    width=18
).grid(row=0, column=0, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="🔒 Zamknij sejf",
    command=lock_folder,
    width=18
).grid(row=0, column=1, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="🔑 Zmień hasło",
    command=change_password,
    width=18
).grid(row=1, column=0, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="➕ Utwórz sejf",
    command=create_vault,
    width=18
).grid(row=1, column=1, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="🔒 Batch Lock",
    command=lambda: batch_lock_unlock("lock"),
    width=18
).grid(row=2, column=0, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="🔓 Batch Unlock",
    command=lambda: batch_lock_unlock("unlock"),
    width=18
).grid(row=2, column=1, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="🚨 PANIC LOCK",
    command=panic_lock_all,
    bg="red",
    fg="white",
    width=18
).grid(row=3, column=0, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="💾 Backup sejfu",
    command=backup_vault,
    width=18
).grid(row=3, column=1, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="♻️ Restore backup",
    command=restore_backup,
    width=18
).grid(row=4, column=0, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="📜 Podgląd logów",
    command=open_log_viewer,
    width=18
).grid(row=4, column=1, padx=5, pady=5)


tk.Button(
    buttons_frame,
    text="💀 SECURE WIPE",
    command=secure_wipe_vault,
    bg="black",
    fg="white",
    width=40
).grid(
    row=5,
    column=0,
    columnspan=2,
    padx=5,
    pady=10,
    sticky="ew"
)


tk.Button(
    buttons_frame,
    text="⚙️ Settings",
    command=open_settings,
    width=18
).grid(row=6, column=0, padx=5, pady=5)


progress = Progressbar(
    app, orient="horizontal", length=300, mode="determinate"
)
progress.pack(pady=15)

app.protocol("WM_DELETE_WINDOW", on_close)

app.bind_all("<Key>", reset_idle_timer)
app.bind_all("<Button>", reset_idle_timer)

app.bind_all("<Control-Alt-p>", lambda e: smart_panic())

app.mainloop()

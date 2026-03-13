import os
import base64
import hashlib
from cryptography.fernet import Fernet

CHECK_FILE = ".vault_check"
CHECK_TEXT = b"VAULT_OK"


# ===== KLUCZ =====
def generate_key(password: str) -> bytes:
    return base64.urlsafe_b64encode(
        hashlib.sha256(password.encode()).digest()
    )


# ===== SZYFROWANIE =====
def encrypt_file(path, fernet):
    with open(path, "rb") as f:
        data = f.read()

    with open(path, "wb") as f:
        f.write(fernet.encrypt(data))


# ===== DESZYFROWANIE =====
def decrypt_file(path, fernet):
    with open(path, "rb") as f:
        data = f.read()

    with open(path, "wb") as f:
        f.write(fernet.decrypt(data))


# ===== PLIK KONTROLNY =====
def create_check_file(folder, fernet):
    path = os.path.join(folder, CHECK_FILE)

    with open(path, "wb") as f:
        f.write(fernet.encrypt(CHECK_TEXT))


def verify_password(folder, fernet):
    path = os.path.join(folder, CHECK_FILE)

    if not os.path.exists(path):
        return True

    try:
        with open(path, "rb") as f:
            data = f.read()

        return fernet.decrypt(data) == CHECK_TEXT
    except:
        return False


# ===== OPERACJA NA FOLDERZE =====
def process_folder(folder, mode, fernet):
    for root, dirs, files in os.walk(folder):
        for name in files:
            if name == CHECK_FILE:
                continue

            full_path = os.path.join(root, name)

            try:
                if mode == "lock":
                    encrypt_file(full_path, fernet)
                elif mode == "unlock":
                    decrypt_file(full_path, fernet)
            except Exception as e:
                print(f"Błąd przy pliku: {full_path}")
                print(e)


# ===== PROGRAM =====
print("=== FOLDER VAULT ===")

folder = input("Ścieżka do folderu-sejfu: ").strip()

if not os.path.isdir(folder):
    print("Folder nie istnieje.")
    exit()

password = input("Podaj hasło: ").strip()
key = generate_key(password)
fernet = Fernet(key)

mode = input("Zamknąć czy otworzyć folder? (z/o): ").lower()

if mode == "z":
    process_folder(folder, "lock", fernet)
    create_check_file(folder, fernet)
    print("Folder został ZAMKNIĘTY 🔒")

elif mode == "o":
    if not verify_password(folder, fernet):
        print("❌ Nieprawidłowe hasło!")
        exit()

    process_folder(folder, "unlock", fernet)
    print("Folder został OTWARTY 🔓")

else:
    print("Nieznana opcja.")

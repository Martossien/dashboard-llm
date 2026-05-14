#!/usr/bin/env python3
"""
Script securise pour modifier le mot de passe admin du Dashboard LLM.
Ne passe JAMAIS par le web. Modifie directement config.yaml.
"""

import getpass
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.yaml")
BAK_SUFFIX = ".backup.change_password"

def read_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERREUR: Fichier config introuvable: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()

def write_config(content):
    # Sauvegarde
    bak_path = CONFIG_PATH + BAK_SUFFIX
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            original = f.read()
        with open(bak_path, "w", encoding="utf-8") as f:
            f.write(original)
    except Exception as exc:
        print(f"AVERTISSEMENT: impossible de creer la sauvegarde {bak_path}: {exc}")
    # Ecriture
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)

def update_password_hash(new_hash):
    content = read_config()
    lines = content.splitlines()
    found = False
    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("password_hash:"):
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f'{indent}password_hash: "{new_hash}"')
            found = True
        else:
            new_lines.append(line)
    if not found:
        print("ERREUR: impossible de trouver 'password_hash:' dans config.yaml")
        sys.exit(1)
    write_config("\n".join(new_lines))

def restart_service():
    if os.path.exists("/etc/systemd/system/dashboard-llm.service"):
        print("Redemarrage via systemctl...")
        ret = os.system("sudo systemctl restart dashboard-llm.service")
        if ret != 0:
            print("AVERTISSEMENT: systemctl restart a retourne un code != 0.")
            return False
        print("Service dashboard-llm redemarre via systemctl.")
        return True
    else:
        print("Pas de service systemd, redemarrage manuel...")
        ret = os.system("pkill -f 'python -m llm_dashboard'; sleep 2; "
                         "cd " + SCRIPT_DIR + " && "
                         "nohup conda run -n dashboard-llm python -m llm_dashboard > /tmp/dashboard-llm.log 2>&1 &")
        if ret != 0:
            print("AVERTISSEMENT: erreur lors du redemarrage manuel.")
            return False
        print("Dashboard redemarre manuellement.")
        return True

def main():
    print("=" * 60)
    print("  Modification du mot de passe Admin — Dashboard LLM")
    print("=" * 60)
    print("")
    print("Ce script met a jour le hash du mot de passe dans")
    print(f"{CONFIG_PATH}")
    print("")

    # Lire mot de passe (masque)
    pwd1 = getpass.getpass("Entrez le NOUVEAU mot de passe admin: ")
    if not pwd1:
        print("ERREUR: le mot de passe ne peut pas etre vide.")
        sys.exit(1)
    if len(pwd1) < 8:
        print("AVERTISSEMENT: mot de passe de moins de 8 caracteres (non recommande).")

    pwd2 = getpass.getpass("Confirmez le nouveau mot de passe:    ")
    if pwd1 != pwd2:
        print("ERREUR: les mots de passe ne correspondent pas.")
        sys.exit(1)

    # Generer le hash
    try:
        from werkzeug.security import generate_password_hash
    except ImportError:
        conda_python = os.path.expanduser("~/.conda/envs/dashboard-llm/bin/python")
        if os.path.exists(conda_python):
            print("Re-execution dans conda env dashboard-llm...")
            os.execv(conda_python, [conda_python, __file__])
        print("ERREUR: werkzeug non installe.")
        sys.exit(1)
    new_hash = generate_password_hash(pwd1)

    # Mettre a jour le fichier
    update_password_hash(new_hash)
    print("")
    print(f"OK: config.yaml mis a jour. Sauvegarde: {CONFIG_PATH}{BAK_SUFFIX}")

    # Demander redemarrage
    print("")
    try:
        ans = input("Redemarrer le service dashboard-llm maintenant ? [O/n]: ").strip().lower()
    except EOFError:
        ans = ""
    if ans in ("", "o", "y", "yes", "oui", "o/n"):
        restart_service()
    else:
        print("Redemarrage saute. Relancez avec: sudo systemctl restart dashboard-llm")

    print("")
    print("Termine.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrompu.")
        sys.exit(130)

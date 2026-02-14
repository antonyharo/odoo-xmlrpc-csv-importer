import os
import sys

def start():
    print("Subindo ambiente...")
    os.system("docker run -d --name odoo-db --rm -e POSTGRES_DB=postgres -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo postgres:15")
    os.system("docker run -d --name odoo --rm --link odoo-db:db -p 8069:8069 odoo:16")
    print("\nOdoo rodando em http://localhost:8069")

def stop():
    print("Limpando tudo...")
    os.system("docker stop odoo odoo-db")
    print("Pronto! Odoo foi removido.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop()
    else:
        start()
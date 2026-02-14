import csv
from faker import Faker
import random

fake = Faker(['pt_BR', 'en_US']) # Diversidade de dados

def generate_stress_test_csv(file_name, total_records):
    headers = [
        "Nome completo", "E-mail", "Cargo", "Nome da empresa", 
        "Cidade", "País", "Estado", "Localização", "LinkedIn"
    ]
    
    # Lista para simular duplicatas
    generated_emails = []

    print(f"Gerando {total_records} registros em {file_name}...")

    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()

        for i in range(total_records):
            # Propositalmente gera duplicatas a cada 10 registros para testar seu código
            if i > 0 and i % 10 == 0:
                email = random.choice(generated_emails)
                name = fake.name() # Nome diferente, email igual (duplicata)
            else:
                name = fake.name()
                email = fake.unique.email()
                generated_emails.append(email)
                # Limpa a lista de cache local para não estourar a RAM do gerador
                if len(generated_emails) > 100:
                    generated_emails.pop(0)

            writer.writerow({
                "Nome completo": name,
                "E-mail": email,
                "Cargo": fake.job(),
                "Nome da empresa": fake.company(),
                "Cidade": fake.city(),
                "País": fake.country(),
                "Estado": fake.state(),
                "Localização": fake.address().replace("\n", ", "),
                "LinkedIn": f"https://www.linkedin.com/in/{fake.user_name()}"
            })
            
            if i % 10000 == 0:
                print(f"{i} registros criados...")

    print(f"\nSucesso! Arquivo {file_name} pronto para o massacre.")

if __name__ == "__main__":
    generate_stress_test_csv("stress_test.csv", 20000)
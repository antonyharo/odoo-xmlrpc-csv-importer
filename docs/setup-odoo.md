# ✅ Rodar Odoo 100% descartável (sem volumes, sem persistência)

## Conceito (importante)

* **Sem volumes** → nada é salvo em disco
* **Sem docker-compose**
* **Sem bind de pasta**
* Se parar/remover o container → **acabou tudo**

Nada fica no seu PC além da imagem (que também pode ser apagada).

---

## 1️⃣ Subir PostgreSQL descartável

```powershell
docker run -d ^
  --name odoo-db ^
  --rm ^
  -e POSTGRES_DB=postgres ^
  -e POSTGRES_USER=odoo ^
  -e POSTGRES_PASSWORD=odoo ^
  postgres:15
```

### O que esse comando faz

* `--rm` → **apaga o container automaticamente ao parar**
* ❌ Sem volume
* ❌ Sem persistência
* ❌ Sem lixo

---

## 2️⃣ Subir Odoo descartável

```powershell
docker run -d ^
  --name odoo ^
  --rm ^
  --link odoo-db:db ^
  -p 8069:8069 ^
  odoo:16
```

### Resultado

* Odoo rodando em:

  ```
  http://localhost:8069
  ```
* Você cria o banco
* Testa XML-RPC
* Importa CSV
* Faz o que quiser

👉 **Nada será salvo depois**.

---

## 3️⃣ Usar normalmente

* Crie banco
* Usuário: `admin`
* Senha: você define
* Teste seu script XML-RPC

Tudo funciona como produção, só que descartável.

---

## 4️⃣ Apagar TUDO (em 2 comandos)

Quando terminar:

```powershell
docker stop odoo
docker stop odoo-db
```

E pronto.

Por causa do `--rm`:

* Containers são destruídos automaticamente
* Banco some
* Odoo some
* Dados somem
* Zero rastro

---

## 5️⃣ Quer apagar até as imagens? (opcional)

Se quiser voltar ao **zero absoluto**:

```powershell
docker rmi odoo:16 postgres:15
```

Depois disso:

* Nem Odoo
* Nem Postgres
* Nem imagem
* Só Docker instalado

---

## 6️⃣ Como verificar que não ficou nada

```powershell
docker ps -a
```

Resultado esperado:

```
CONTAINER ID   IMAGE   COMMAND   STATUS   PORTS   NAMES
```

Lista vazia.

---

## 7️⃣ Por que esse modo é o melhor para você

* Você quer **testar**
* Não quer bagunçar o PC
* Não quer “me comprometer” com Odoo
* Quer aprender integração

👉 **Esse é exatamente o setup certo.**

---

## Resumo seco

* ✔️ Sem volumes
* ✔️ Sem persistência
* ✔️ Sem lixo
* ✔️ Apagou = acabou
* ✔️ Ambiente real

Se quiser, próximo passo posso:

* testar seu **script XML-RPC contra esse Odoo**
* ou te passar **um checklist de testes** (login, search, create, import)
* ou te ajudar a **documentar isso como case técnico no GitHub**, do jeito certo

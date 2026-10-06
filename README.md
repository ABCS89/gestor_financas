# 💰 Gestor de Finanças Pessoais

Aplicativo moderno, intuitivo e completo para gestão de finanças pessoais, com suporte a **importação de extratos bancários (OFX / CSV)** e **anexo de comprovantes de pagamento (imagens e PDFs)**.

Construído em ambiente isolado (**Python Virtualenv**), salvando seus dados 100% de forma local e privada com **SQLite**.

---

## 🚀 Como Executar

O ambiente virtual `.venv` já está configurado com todas as dependências instaladas.

Para iniciar o aplicativo, abra o PowerShell nesta pasta e execute:

```powershell
.\.venv\Scripts\python.exe run.py
```

Ou, se preferir ativar o ambiente virtual antes:

```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```

O aplicativo estará disponível no seu navegador em:
👉 **[http://localhost:8000](http://localhost:8000)**

> 📱 **Uso no Celular / Mobile:**
> Se o seu computador e celular estiverem na mesma rede Wi-Fi, você pode acessar pelo navegador do celular usando `http://SEU_IP_LOCAL:8000` (ex: `http://192.168.1.50:8000`) e tocar em **"Adicionar à tela de início"** para usar como um app nativo!

---

## ✨ Principais Funcionalidades

### 1. 📊 Visão Geral & Dashboard
- **Cards Dinâmicos:** Saldo consolidado, total de receitas e total de despesas do mês selecionado.
- **Gráfico Interativo:** Gráfico em rosca (Doughnut) com a distribuição de gastos por categoria e percentuais.
- **Navegação por Período:** Seletor de mês/ano com atualização instantânea de saldo e lançamentos.
- **Modo Escuro / Claro:** Alternância rápida com 1 clique.

### 2. 🏦 Integração Bancária Fácil (OFX e CSV)
- **Zero burocracia:** Exporte o extrato do seu banco favorito (Nubank, Inter, Itaú, Bradesco, Santander, C6, etc.) em formato `.ofx` ou `.csv`.
- **Importação por Arraste:** Solte o arquivo na aba de importação.
- **Auto-Categorização Inteligente:** O sistema reconhece nomes de estabelecimentos (iFood, Uber, Enel, Mercado Livre, etc.) e sugere as categorias certas automaticamente.
- **Anti-Duplicação:** Se você importar o mesmo arquivo mais de uma vez, transações repetidas são detectadas e desativadas automaticamente.

### 3. 📄 Envio e Anexo de Comprovantes
- **Envio no Lançamento:** Anexe foto do comprovante de Pix, boleto ou recibo diretamente ao cadastrar uma transação.
- **Galeria de Comprovantes:** Visualize todos os comprovantes enviados na aba **"Comprovantes"**.
- **Suporte Multiformato:** Aceita fotos e imagens (`.jpg`, `.jpeg`, `.png`, `.webp`) e documentos `.pdf`.
- **Visualizador Integrado:** Abra em tamanho real ou faça download direto pela tela do app.

### 4. ☁️ Sincronização Automática com Google Drive
- **Leitura de Pasta na Nuvem:** Conecte o ID ou link de uma pasta do seu Google Drive.
- **Sincronização com 1 Clique:** Baixa fotos e PDFs salvos na pasta direto para a galeria de comprovantes, evitando arquivos repetidos.
- **Link Direto:** Cada comprovante sincronizado ganha um botão para abrir diretamente no seu Google Drive.

### 5. 🏷️ Categorias Pré-configuradas
- Alimentação, Moradia & Contas, Transporte, Saúde, Lazer & Streaming, Compras, Educação, Salário & Renda, Investimentos, etc.

---

## 🛠️ Tecnologias Utilizadas
- **Backend:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy.
- **Banco de Dados:** SQLite local (`financas.db` criado automaticamente).
- **Leitor Bancário:** `ofxparse` + parser CSV resiliente.
- **Frontend:** HTML5 responsivo mobile-first, Tailwind CSS, Lucide Icons, Chart.js.

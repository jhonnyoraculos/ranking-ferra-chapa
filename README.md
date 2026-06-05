# ranking-ferra-chapa

Dashboard Streamlit para analisar separacao, conferencia, peso por colaborador, produtos e enderecos mais movimentados.

## Como rodar

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

O app carrega automaticamente a planilha `.xls` ou `.xlsx` mais recente na pasta do projeto.

## Como atualizar os dados

Depois de alterar ou substituir a planilha, clique duas vezes em `atualizar_dados.bat`.
Ele cria um commit com a planilha atualizada e envia para o GitHub automaticamente.

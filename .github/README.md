# 🧠 ALM Platform Backend (API FastAPI)

## 🎯 Visão Geral do Projeto

O Backend da Plataforma ALM é o serviço central de análise de dados e Machine Learning.

### Funções Principais:

- **Ingestão de Dados**: Coleta de preços históricos e notícias financeiras.
- **Modelagem**: Execução de modelos LSTM para previsão de tendências e FinBERT para análise de sentimento.
- **Backtesting**: Simulação de estratégias de investimento e cálculo de métricas (Sharpe Ratio, Retorno Total).
- **API REST**: Disponibilização de todos os dados, previsões e resultados de simulação via FastAPI.

O objetivo é fornecer o motor de inteligência por trás do dashboard de gestão de ativos e passivos.

## 🚀 Como Rodar o Serviço Rapidamente (Docker)

Este projeto é totalmente containerizado para garantir uma inicialização rápida e um ambiente consistente.

### 1. Pré-requisitos

Você precisa ter o **Docker** e o **Docker Compose** instalados e em execução em sua máquina.

### 2. Inicialização

No diretório raiz do projeto (onde o arquivo `docker-compose.yml` está):

```bash
# Este comando constrói a imagem e inicia o serviço em segundo plano.
sudo docker compose up -d
```

### 3. Acesso

Após a inicialização (aguarde alguns segundos):

- **Endereço do Serviço:** http://localhost:8000
- **Documentação Interativa da API (Swagger UI):** http://localhost:8000/docs

### 4. Parada do Serviço

Para derrubar e remover os contêineres e a rede do projeto:

```bash
sudo docker compose down
```

"""
Serviço para buscar dados de mercado de ações usando Brapi (API brasileira) e CoinGecko para cripto.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import requests

from app.services.database_service import database_service
from app.services.cache_service import cache_service
from app.services.rate_limiter import brapi_rate_limiter


class MarketDataService:
    """Serviço para obter dados reais de ações via Brapi e CoinGecko."""

    # URLs das APIs
    BRAPI_BASE_URL = "https://brapi.dev/api"
    COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

    # API Key da Brapi (lida do ambiente)
    BRAPI_API_KEY = os.getenv("BRAPI_API_KEY", "")

    # Mapeamento de tickers brasileiros + Bitcoin
    # Usando apenas ações gratuitas da Brapi (sem necessidade de token)
    TICKERS = {
        "PETR4.SA": "Petrobras PN",
        "VALE3.SA": "Vale ON",
        "ITUB4.SA": "Itaú Unibanco PN",
        "BTC-USD": "Bitcoin",
    }

    # Alocações fictícias (usado quando não há banco de dados)
    # Total: 100% distribuído entre 4 ativos
    MOCK_ALLOCATIONS = {
        "PETR4.SA": 0.40,  # 40%
        "VALE3.SA": 0.30,  # 30% (era 25%, ganhou +5%)
        "ITUB4.SA": 0.20,  # 20% (era 15%, ganhou +5%)
        "BTC-USD": 0.10,   # 10%
    }

    @staticmethod
    def get_stock_data(
        ticker: str, period: str = "1y", retries: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        Busca dados históricos de uma ação usando Brapi (ações BR) ou CoinGecko (cripto).
        Utiliza cache e rate limiting para otimizar requisições.

        Args:
            ticker: Código da ação (ex: "PETR4.SA" ou "BTC-USD")
            period: Período de dados (não usado atualmente, Brapi retorna 1 ano)
            retries: Número de tentativas em caso de falha

        Returns:
            DataFrame com dados históricos ou None em caso de erro
        """
        import time

        # Verifica cache primeiro
        cache_key = f"stock_data:{ticker}:{period}"
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            print(f"✓ Cache hit para {ticker}")
            return cached_data

        # Detecta se é Bitcoin ou ação brasileira
        is_crypto = ticker == "BTC-USD"

        # Aguarda rate limit se necessário (apenas para Brapi)
        if not is_crypto:
            while not brapi_rate_limiter.is_allowed():
                wait_time = brapi_rate_limiter.time_until_next_call()
                if wait_time and wait_time > 0:
                    print(f"⏳ Rate limit: aguardando {wait_time:.1f}s para {ticker}")
                    time.sleep(wait_time + 0.1)
                else:
                    break

        for attempt in range(retries):
            try:
                if is_crypto:
                    # Usa CoinGecko para Bitcoin (365 dias)
                    url = f"{MarketDataService.COINGECKO_BASE_URL}/coins/bitcoin/market_chart"
                    params = {
                        "vs_currency": "usd",
                        "days": "365",
                        "interval": "daily"
                    }
                    response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    # Converte para DataFrame no formato esperado
                    prices = data.get("prices", [])
                    if prices:
                        df = pd.DataFrame(prices, columns=["timestamp", "Close"])
                        df["Date"] = pd.to_datetime(df["timestamp"], unit='ms')
                        df.set_index("Date", inplace=True)
                        df.drop("timestamp", axis=1, inplace=True)
                        # Adiciona colunas fictícias para compatibilidade
                        df["Open"] = df["Close"]
                        df["High"] = df["Close"]
                        df["Low"] = df["Close"]
                        df["Volume"] = 0

                        # Armazena em cache (1 hora)
                        cache_service.set(cache_key, df, ttl=3600)
                        return df

                else:
                    # Remove .SA do ticker para Brapi
                    brapi_ticker = ticker.replace(".SA", "")

                    # Usa Brapi para ações brasileiras
                    url = f"{MarketDataService.BRAPI_BASE_URL}/quote/{brapi_ticker}"
                    params = {"range": "1y", "interval": "1d"}

                    # Adiciona header de autenticação se API key estiver disponível
                    headers = {}
                    if MarketDataService.BRAPI_API_KEY:
                        headers["Authorization"] = f"Bearer {MarketDataService.BRAPI_API_KEY}"

                    # Registra chamada no rate limiter
                    brapi_rate_limiter.record_call()

                    response = requests.get(url, params=params, headers=headers, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    results = data.get("results", [])
                    if results and len(results) > 0:
                        historical = results[0].get("historicalDataPrice", [])

                        if historical:
                            df = pd.DataFrame(historical)
                            df["date"] = pd.to_datetime(df["date"], unit='s')
                            df.set_index("date", inplace=True)
                            df.rename(columns={
                                "open": "Open",
                                "high": "High",
                                "low": "Low",
                                "close": "Close",
                                "volume": "Volume"
                            }, inplace=True)

                            result_df = df[["Open", "High", "Low", "Close", "Volume"]]

                            # Armazena em cache (1 hora)
                            cache_service.set(cache_key, result_df, ttl=3600)

                            return result_df

                print(f"Tentativa {attempt + 1}/{retries}: Dados vazios para {ticker}")

            except Exception as e:
                print(f"Tentativa {attempt + 1}/{retries} falhou para {ticker}: {e}")

            # Aguarda antes de tentar novamente
            if attempt < retries - 1:
                time.sleep(2 ** attempt)

        print(f"Todas as {retries} tentativas falharam para {ticker}")
        return None

    @staticmethod
    def calculate_returns_and_volatility(
        hist: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Calcula retorno e volatilidade anualizados.

        Args:
            hist: DataFrame com histórico de preços

        Returns:
            Dict com retorno e volatilidade anualizados
        """
        if hist is None or hist.empty:
            return {
                "annual_return": 0.0,
                "annual_volatility": 0.0,
            }

        # Calcula retornos diários
        returns = hist["Close"].pct_change().dropna()

        # Anualiza (252 dias úteis por ano)
        annual_return = returns.mean() * 252
        annual_volatility = returns.std() * (252**0.5)

        return {
            "annual_return": round(annual_return, 4),
            "annual_volatility": round(annual_volatility, 4),
        }

    @staticmethod
    def get_current_price(ticker: str) -> Optional[float]:
        """
        Busca o preço atual de uma ação usando Brapi ou CoinGecko.

        Args:
            ticker: Código da ação

        Returns:
            Preço atual ou None
        """
        try:
            is_crypto = ticker == "BTC-USD"

            if is_crypto:
                # CoinGecko para Bitcoin
                url = f"{MarketDataService.COINGECKO_BASE_URL}/simple/price"
                params = {"ids": "bitcoin", "vs_currencies": "usd"}
                response = requests.get(url, params=params, timeout=5)
                response.raise_for_status()
                data = response.json()
                return float(data.get("bitcoin", {}).get("usd", 0))

            else:
                # Brapi para ações brasileiras
                brapi_ticker = ticker.replace(".SA", "")
                url = f"{MarketDataService.BRAPI_BASE_URL}/quote/{brapi_ticker}"

                # Adiciona header de autenticação se API key estiver disponível
                headers = {}
                if MarketDataService.BRAPI_API_KEY:
                    headers["Authorization"] = f"Bearer {MarketDataService.BRAPI_API_KEY}"

                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if results and len(results) > 0:
                    return float(results[0].get("regularMarketPrice", 0))

            return None

        except Exception as e:
            print(f"Erro ao buscar preço de {ticker}: {e}")
            return None

    @classmethod
    def get_portfolio_data(cls, user_id: Optional[int] = None, use_database: bool = True) -> List[Dict]:
        """
        Busca dados atualizados de todas as ações do portfólio.

        Args:
            user_id: ID do usuário para buscar portfólio personalizado.
                    Se None, usa portfólio padrão.
            use_database: Se True, busca ações do banco de dados.
                         Se False, usa TICKERS estático.

        Returns:
            Lista com dados de cada ação
        """
        portfolio = []

        # Inicializa banco de dados se necessário
        if use_database:
            database_service.initialize_stocks()

        # Busca alocações do usuário ou usa padrão
        if use_database and user_id:
            # Busca portfólio do usuário no banco
            user_portfolio = database_service.get_user_portfolio(user_id)
            allocations = {item["stock_ticker"]: item["allocation"] for item in user_portfolio}
            tickers_dict = {item["stock_ticker"]: item["stock_name"] for item in user_portfolio}
        elif use_database:
            # Usa dados do banco mas com alocações padrão
            stocks_from_db = database_service.get_all_stocks()
            tickers_dict = {stock["ticker"]: stock["name"] for stock in stocks_from_db}
            allocations = cls.MOCK_ALLOCATIONS
        else:
            # Usa dados estáticos
            tickers_dict = cls.TICKERS
            allocations = cls.MOCK_ALLOCATIONS

        # Busca dados de mercado para cada ativo
        for ticker, name in tickers_dict.items():
            hist = cls.get_stock_data(ticker, period="1y")
            if hist is not None and not hist.empty:
                current_price = hist["Close"].iloc[-1]

                # Calcula métricas históricas
                metrics = cls.calculate_returns_and_volatility(hist)

                # Para previsão, usa uma estimativa simples (pode ser melhorado)
                forecast_return = metrics["annual_return"] * 1.05  # +5% otimista
                forecast_volatility = (
                    metrics["annual_volatility"] * 0.95
                )  # -5% menos volátil

                portfolio.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "allocation": allocations.get(ticker, 0.0),
                        "currentPrice": round(current_price, 2),
                        "historicalAnnualReturn": metrics["annual_return"],
                        "historicalAnnualVolatility": metrics["annual_volatility"],
                        "forecastAnnualReturn": round(forecast_return, 4),
                        "forecastAnnualVolatility": round(forecast_volatility, 4),
                    }
                )

        return portfolio


# Instância global do serviço
market_data_service = MarketDataService()

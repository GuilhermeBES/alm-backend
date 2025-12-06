"""
Endpoints para previsões de séries temporais.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import warnings

import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.market_data_service import market_data_service

# Suppress warnings from statsmodels
warnings.filterwarnings('ignore')

router = APIRouter()


# ==================== SCHEMAS ====================

class ForecastRequest(BaseModel):
    """Schema para requisição de previsão."""
    ticker: str = Field(..., description="Ticker da ação (ex: PETR4.SA)")
    n_steps: int = Field(7, ge=1, le=30, description="Número de dias a prever")
    order: Optional[Tuple[int, int, int]] = Field(None, description="Ordem SARIMA (p, d, q)")
    seasonal_order: Optional[Tuple[int, int, int, int]] = Field(None, description="Ordem sazonal (P, D, Q, s)")
    days: int = Field(365, ge=30, le=730, description="Dias de histórico para treinar")


class ForecastResponse(BaseModel):
    """Schema para resposta de previsão."""
    ticker: str
    forecast_dates: List[str]
    forecast_values: List[float]
    plot_base64: Optional[str] = None
    metrics: Optional[dict] = None


# ==================== ENDPOINTS ====================

@router.post("/forecast/sarima", response_model=ForecastResponse)
async def forecast_sarima(request: ForecastRequest):
    """
    Gera previsão SARIMA para uma ação.

    Args:
        request: Dados da requisição

    Returns:
        Previsão com datas e valores futuros

    Example:
        POST /forecast/sarima
        {
            "ticker": "PETR4.SA",
            "n_steps": 7,
            "order": [2, 1, 2],
            "seasonal_order": [1, 1, 1, 5],
            "days": 365
        }
    """
    try:
        # Busca dados históricos
        hist = market_data_service.get_stock_data(
            request.ticker,
            period="1y",
            retries=3
        )

        if hist is None or hist.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Não foi possível obter dados históricos para {request.ticker}"
            )

        # Filtra últimos N dias
        if len(hist) > request.days:
            hist = hist.tail(request.days)

        # Prepara série temporal
        prices = hist["Close"].values
        dates = hist.index

        # Parâmetros SARIMA
        order = request.order or (2, 1, 2)
        seasonal_order = request.seasonal_order or (1, 1, 1, 5)

        # Treina modelo SARIMA
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX

            model = SARIMAX(
                prices,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False
            )

            results = model.fit(disp=False, maxiter=200)

            # Gera previsão
            forecast = results.forecast(steps=request.n_steps)

            # Calcula datas futuras
            last_date = dates[-1]
            forecast_dates = []
            for i in range(1, request.n_steps + 1):
                future_date = last_date + timedelta(days=i)
                forecast_dates.append(future_date.strftime("%Y-%m-%d"))

            # Calcula métricas
            metrics = {
                "aic": float(results.aic),
                "bic": float(results.bic),
                "last_price": float(prices[-1]),
                "mean_forecast": float(forecast.mean()),
                "std_forecast": float(forecast.std())
            }

            return ForecastResponse(
                ticker=request.ticker,
                forecast_dates=forecast_dates,
                forecast_values=[float(v) for v in forecast],
                metrics=metrics
            )

        except Exception as e:
            # Fallback: previsão simples usando média móvel
            print(f"SARIMA falhou, usando fallback: {e}")

            # Média móvel simples dos últimos 7 dias
            ma = pd.Series(prices).rolling(window=7).mean().iloc[-1]

            # Gera previsão constante com pequena variação
            forecast_values = []
            for i in range(request.n_steps):
                noise = np.random.normal(0, prices.std() * 0.01)
                forecast_values.append(float(ma + noise))

            # Datas futuras
            last_date = dates[-1]
            forecast_dates = []
            for i in range(1, request.n_steps + 1):
                future_date = last_date + timedelta(days=i)
                forecast_dates.append(future_date.strftime("%Y-%m-%d"))

            return ForecastResponse(
                ticker=request.ticker,
                forecast_dates=forecast_dates,
                forecast_values=forecast_values,
                metrics={
                    "method": "moving_average_fallback",
                    "last_price": float(prices[-1]),
                    "mean_forecast": float(np.mean(forecast_values))
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar previsão: {str(e)}"
        )

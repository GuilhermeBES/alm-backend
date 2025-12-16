"""
Endpoints para gerenciamento de portfólios de usuários.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.database_service import database_service
from app.services.market_data_service import market_data_service


router = APIRouter()


# ==================== SCHEMAS ====================

class AllocationUpdate(BaseModel):
    """Schema para atualizar alocação de um ativo."""
    stock_ticker: str = Field(..., description="Ticker da ação (ex: PETR4.SA)")
    allocation: float = Field(..., ge=0, le=1, description="Alocação (0.0 a 1.0)")


class PortfolioItem(BaseModel):
    """Item do portfólio com dados de mercado."""
    ticker: str
    name: str
    allocation: float
    currentPrice: float
    historicalAnnualReturn: float
    historicalAnnualVolatility: float
    forecastAnnualReturn: float
    forecastAnnualVolatility: float


class PortfolioResponse(BaseModel):
    """Resposta com portfólio completo."""
    user_id: int
    portfolio: List[PortfolioItem]
    total_allocation: float


# ==================== ENDPOINTS ====================

@router.get("/{user_id}", response_model=PortfolioResponse)
async def get_user_portfolio(user_id: int):
    """
    Busca portfólio completo de um usuário com dados de mercado atualizados.

    Args:
        user_id: ID do usuário

    Returns:
        Portfólio com alocações e dados de mercado em tempo real

    Example:
        GET /api/v1/portfolio/1
    """
    try:
        # Busca portfólio com dados de mercado
        portfolio_data = market_data_service.get_portfolio_data(user_id=user_id)

        if not portfolio_data:
            raise HTTPException(
                status_code=404,
                detail="Portfólio não encontrado ou usuário sem alocações"
            )

        # Calcula alocação total
        total_allocation = sum(item["allocation"] for item in portfolio_data)

        return {
            "user_id": user_id,
            "portfolio": portfolio_data,
            "total_allocation": round(total_allocation, 4)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar portfólio: {str(e)}"
        )


@router.put("/{user_id}/allocation", status_code=200)
async def update_portfolio_allocation(user_id: int, allocation: AllocationUpdate):
    """
    Atualiza a alocação de um ativo no portfólio do usuário.

    Args:
        user_id: ID do usuário
        allocation: Dados da nova alocação

    Returns:
        Mensagem de sucesso

    Example:
        PUT /api/v1/portfolio/1/allocation
        {
            "stock_ticker": "PETR4.SA",
            "allocation": 0.35
        }
    """
    try:
        # Verifica se o ativo existe
        stock = database_service.get_stock_by_ticker(allocation.stock_ticker)
        if not stock:
            raise HTTPException(
                status_code=404,
                detail=f"Ação '{allocation.stock_ticker}' não encontrada"
            )

        # Atualiza alocação
        success = database_service.update_allocation(
            user_id=user_id,
            stock_ticker=allocation.stock_ticker,
            allocation=allocation.allocation
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Erro ao atualizar alocação"
            )

        return {
            "message": "Alocação atualizada com sucesso",
            "user_id": user_id,
            "stock_ticker": allocation.stock_ticker,
            "new_allocation": allocation.allocation
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar alocação: {str(e)}"
        )


@router.delete("/{user_id}/stock/{ticker}", status_code=200)
async def remove_stock_from_portfolio(user_id: int, ticker: str):
    """
    Remove um ativo do portfólio do usuário.

    Args:
        user_id: ID do usuário
        ticker: Ticker da ação a remover

    Returns:
        Mensagem de sucesso

    Example:
        DELETE /api/v1/portfolio/1/stock/PETR4.SA
    """
    try:
        success = database_service.remove_from_portfolio(
            user_id=user_id,
            stock_ticker=ticker
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Ação '{ticker}' não encontrada no portfólio do usuário"
            )

        return {
            "message": f"Ação '{ticker}' removida do portfólio",
            "user_id": user_id,
            "stock_ticker": ticker
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover ação: {str(e)}"
        )


@router.get("/{user_id}/summary")
async def get_portfolio_summary(user_id: int):
    """
    Retorna resumo estatístico do portfólio do usuário.

    Args:
        user_id: ID do usuário

    Returns:
        Resumo com métricas agregadas

    Example:
        GET /api/v1/portfolio/1/summary
    """
    try:
        portfolio_data = market_data_service.get_portfolio_data(user_id=user_id)

        if not portfolio_data:
            raise HTTPException(
                status_code=404,
                detail="Portfólio não encontrado"
            )

        # Calcula métricas agregadas
        total_allocation = sum(item["allocation"] for item in portfolio_data)

        # Retorno médio ponderado
        weighted_return = sum(
            item["allocation"] * item["historicalAnnualReturn"]
            for item in portfolio_data
        )

        # Volatilidade média ponderada
        weighted_volatility = sum(
            item["allocation"] * item["historicalAnnualVolatility"]
            for item in portfolio_data
        )

        return {
            "user_id": user_id,
            "total_assets": len(portfolio_data),
            "total_allocation": round(total_allocation, 4),
            "weighted_annual_return": round(weighted_return, 4),
            "weighted_annual_volatility": round(weighted_volatility, 4),
            "is_fully_allocated": abs(total_allocation - 1.0) < 0.01,  # Margem de 1%
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao calcular resumo: {str(e)}"
        )

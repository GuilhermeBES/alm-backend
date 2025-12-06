"""
Endpoints de autenticação.
"""

import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from app.services.database_service import database_service
from app.services.auth_service import auth_service


# ==================== SCHEMAS ====================

class LoginRequest(BaseModel):
    """Schema para requisição de login."""
    email: str = Field(..., description="Email do usuário")
    password: str = Field(..., min_length=6, description="Senha do usuário")


class User(BaseModel):
    """Schema para dados do usuário."""
    id: str
    name: str
    email: str
    role: str
    createdAt: str | None = None


class LoginResponse(BaseModel):
    """Schema para resposta de login."""
    user: User
    token: str
    refreshToken: str
    message: str


class RegisterRequest(BaseModel):
    """Schema para registro de novo usuário."""
    email: str
    name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6)


router = APIRouter()


# Dependency to get current user from token
async def get_current_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="api/v1/auth/login"))) -> User:
    """
    Valida o token JWT e retorna o usuário autenticado.
    """
    try:
        # Verifica e decodifica o token JWT
        payload = auth_service.verify_token(token, token_type="access")

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extrai user_id do payload
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: user_id não encontrado"
            )

        # Busca usuário no banco de dados
        user_from_db = database_service.get_user_by_id(user_id)

        if not user_from_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )

        # Retorna objeto User
        return User(
            id=str(user_from_db["id"]),
            name=user_from_db["name"],
            email=user_from_db["email"],
            role=user_from_db["role"],
            createdAt=user_from_db.get("created_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Erro de autenticação: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== ENDPOINTS ====================

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    Endpoint de login.

    Args:
        credentials: Email e senha do usuário

    Returns:
        Dados do usuário autenticado

    Example:
        POST /api/v1/auth/login
        {
            "email": "demo@alm.com",
            "password": "demo123"
        }
    """
    try:
        # Busca usuário por email
        user = database_service.get_user_by_email(credentials.email)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Email ou senha inválidos"
            )

        # Verifica senha (hash SHA-256)
        password_hash = hashlib.sha256(credentials.password.encode()).hexdigest()

        if password_hash != user["password_hash"]:
            raise HTTPException(
                status_code=401,
                detail="Email ou senha inválidos"
            )

        # Gera tokens JWT (access token e refresh token)
        from datetime import datetime

        token_data = {
            "user_id": user["id"],
            "email": user["email"],
            "role": user["role"]
        }

        access_token = auth_service.create_access_token(token_data)
        refresh_token = auth_service.create_refresh_token(token_data)

        # Verifica se o usuário tem portfólio, senão cria um padrão
        user_id_int = user["id"] # user["id"] is already int from database
        existing_portfolio = database_service.get_user_portfolio(user_id_int)
        if not existing_portfolio:
            database_service.create_default_portfolio(user_id_int)

        # Retorna dados do usuário (sem o hash da senha) no formato esperado pelo frontend
        created_at = user.get("created_at")
        if isinstance(created_at, (int, float)):
            created_at = datetime.fromtimestamp(created_at).isoformat()
        elif created_at is None:
            created_at = datetime.utcnow().isoformat()

        return {
            "user": {
                "id": str(user["id"]),
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "createdAt": created_at
            },
            "token": access_token,
            "refreshToken": refresh_token,
            "message": "Login realizado com sucesso"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao realizar login: {str(e)}"
        )


@router.post("/register", status_code=201)
async def register(user_data: RegisterRequest):
    """
    Endpoint para registro de novo usuário.

    Args:
        user_data: Dados do novo usuário

    Returns:
        Confirmação de registro

    Example:
        POST /api/v1/auth/register
        {
            "email": "novo@alm.com",
            "name": "Novo Usuario",
            "password": "senha123"
        }
    """
    try:
        # Verifica se email já existe
        existing_user = database_service.get_user_by_email(user_data.email)

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email já cadastrado"
            )

        # Hash da senha
        password_hash = hashlib.sha256(user_data.password.encode()).hexdigest()

        # Cria usuário
        user_id = database_service.create_user(
            email=user_data.email,
            name=user_data.name,
            password_hash=password_hash,
            role="user"  # Sempre cria como user comum
        )

        if not user_id:
            raise HTTPException(
                status_code=500,
                detail="Erro ao criar usuário"
            )

        return {
            "message": "Usuário criado com sucesso",
            "user_id": user_id,
            "email": user_data.email
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao registrar usuário: {str(e)}"
        )


@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Endpoint para obter informações do usuário atualmente autenticado.
    Requer token de autenticação no cabeçalho 'Authorization: Bearer <token>'.
    """
    return current_user


class RefreshTokenRequest(BaseModel):
    """Schema para requisição de refresh token."""
    refreshToken: str = Field(..., description="Refresh token válido")


class RefreshTokenResponse(BaseModel):
    """Schema para resposta de refresh token."""
    token: str = Field(..., description="Novo access token")
    message: str


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Endpoint para renovar access token usando refresh token.

    Args:
        request: Refresh token válido

    Returns:
        Novo access token

    Example:
        POST /api/v1/auth/refresh
        {
            "refreshToken": "eyJ..."
        }
    """
    try:
        new_access_token = auth_service.refresh_access_token(request.refreshToken)

        if not new_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido ou expirado"
            )

        return {
            "token": new_access_token,
            "message": "Token renovado com sucesso"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao renovar token: {str(e)}"
        )


@router.get("/users/{user_id}")
async def get_user_info(user_id: int):
    """
    Busca informações de um usuário (sem senha).

    Args:
        user_id: ID do usuário

    Returns:
        Dados do usuário
    """
    try:
        user = database_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar usuário: {str(e)}"
        )
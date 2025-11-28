"""
Endpoints de autenticação.
"""

import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from app.services.database_service import database_service


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
    message: str


class RegisterRequest(BaseModel):
    """Schema para registro de novo usuário."""
    email: str
    name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6)


router = APIRouter()


# Dependency to get current user from token
async def get_current_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="api/v1/auth/login"))) -> User:
    try:
        # Decode the token (assuming it's base64 encoded JSON)
        import base64
        import json
        from datetime import datetime

        decoded_payload = base64.b64decode(token).decode()
        token_data = json.loads(decoded_payload)

        # Check token expiration
        if token_data.get("exp") < datetime.utcnow().timestamp():
            raise HTTPException(status_code=401, detail="Token expirado")

        # Fetch user from DB using user_id from token
        user_id = token_data.get("user_id")
        user_from_db = database_service.get_user_by_id(user_id)

        if not user_from_db:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        # Return user object conforming to the User schema
        return User(
            id=str(user_from_db["id"]),
            name=user_from_db["name"],
            email=user_from_db["email"],
            role=user_from_db["role"],
            createdAt=user_from_db.get("created_at")
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token inválido ou erro de autenticação: {str(e)}")


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

        # Gera um token simples (em produção usar JWT)
        import base64
        import json
        from datetime import datetime, timedelta

        token_data = {
            "user_id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "exp": (datetime.utcnow() + timedelta(days=7)).timestamp()
        }
        token = base64.b64encode(json.dumps(token_data).encode()).decode()

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
            "token": token,
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
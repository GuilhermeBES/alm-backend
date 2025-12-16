"""
Serviço de autenticação com JWT.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-secret-key-change-this")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


class AuthService:
    """Serviço para gerenciar autenticação JWT."""

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Cria um access token JWT.

        Args:
            data: Dados a serem codificados no token
            expires_delta: Tempo de expiração customizado

        Returns:
            Token JWT assinado
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """
        Cria um refresh token JWT.

        Args:
            data: Dados a serem codificados no token

        Returns:
            Refresh token JWT assinado
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
        """
        Verifica e decodifica um token JWT.

        Args:
            token: Token JWT a ser verificado
            token_type: Tipo do token ("access" ou "refresh")

        Returns:
            Payload do token se válido, None caso contrário
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            # Verifica o tipo do token
            if payload.get("type") != token_type:
                return None

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        """
        Cria um novo access token a partir de um refresh token válido.

        Args:
            refresh_token: Refresh token válido

        Returns:
            Novo access token se o refresh token for válido, None caso contrário
        """
        payload = AuthService.verify_token(refresh_token, token_type="refresh")

        if not payload:
            return None

        # Cria novo access token com os mesmos dados do usuário
        new_token_data = {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role")
        }

        return AuthService.create_access_token(new_token_data)


# Instância global do serviço
auth_service = AuthService()

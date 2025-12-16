"""
Serviço para gerenciar conexão e operações com o banco de dados SQLite.
"""

import sqlite3
from typing import Dict, List, Optional
from pathlib import Path


class DatabaseService:
    """Serviço para interagir com o banco de dados ALM."""

    # Caminho para o banco de dados
    # Verifica se está rodando no Docker ou local
    if Path("/alm-banco-de-dados/scripts/database.db").exists():
        # Rodando no Docker
        DB_PATH = Path("/alm-banco-de-dados/scripts/database.db")
    else:
        # Rodando localmente
        DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "alm-banco-de-dados" / "scripts" / "database.db"

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        """
        Retorna uma conexão com o banco de dados.

        Returns:
            sqlite3.Connection: Conexão com o banco
        """
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
        return conn

    @classmethod
    def get_all_stocks(cls) -> List[Dict[str, str]]:
        """
        Busca todas as ações cadastradas no banco.

        Returns:
            Lista de dicionários com dados das ações
        """
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT ticker, name, sector FROM Stock")
        rows = cursor.fetchall()

        stocks = [dict(row) for row in rows]

        conn.close()
        return stocks

    @classmethod
    def get_stock_by_ticker(cls, ticker: str) -> Optional[Dict[str, str]]:
        """
        Busca uma ação específica por ticker.

        Args:
            ticker: Código da ação (ex: "PETR4.SA")

        Returns:
            Dicionário com dados da ação ou None se não encontrada
        """
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT ticker, name, sector FROM Stock WHERE ticker = ?",
            (ticker,)
        )
        row = cursor.fetchone()

        stock = dict(row) if row else None

        conn.close()
        return stock

    @classmethod
    def create_stock(cls, ticker: str, name: str, sector: str) -> bool:
        """
        Cria uma nova ação no banco.

        Args:
            ticker: Código da ação
            name: Nome da empresa
            sector: Setor

        Returns:
            True se criado com sucesso
        """
        try:
            conn = cls.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO Stock (ticker, name, sector) VALUES (?, ?, ?)",
                (ticker, name, sector)
            )

            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # Já existe
            return False

    @classmethod
    def update_stock(cls, ticker: str, name: str = None, sector: str = None) -> bool:
        """
        Atualiza dados de uma ação.

        Args:
            ticker: Código da ação
            name: Novo nome (opcional)
            sector: Novo setor (opcional)

        Returns:
            True se atualizado com sucesso
        """
        conn = cls.get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if sector is not None:
            updates.append("sector = ?")
            params.append(sector)

        if not updates:
            return False

        params.append(ticker)
        query = f"UPDATE Stock SET {', '.join(updates)} WHERE ticker = ?"

        cursor.execute(query, params)
        conn.commit()

        rows_affected = cursor.rowcount
        conn.close()

        return rows_affected > 0

    @classmethod
    def delete_stock(cls, ticker: str) -> bool:
        """
        Remove uma ação do banco.

        Args:
            ticker: Código da ação

        Returns:
            True se removido com sucesso
        """
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM Stock WHERE ticker = ?", (ticker,))
        conn.commit()

        rows_affected = cursor.rowcount
        conn.close()

        return rows_affected > 0

    @classmethod
    def initialize_stocks(cls) -> None:
        """
        Popula o banco com as ações iniciais se estiver vazio.
        """
        stocks = cls.get_all_stocks()

        if len(stocks) == 0:
            print("Banco vazio. Populando com ações iniciais...")

            initial_stocks = [
                ("PETR4.SA", "Petrobras PN", "Petróleo e Gás"),
                ("VALE3.SA", "Vale ON", "Mineração"),
                ("ITUB4.SA", "Itaú Unibanco PN", "Bancos"),
                ("WEGE3.SA", "Weg ON", "Energia"),
                ("BTC-USD", "Bitcoin", "Criptomoedas"),
            ]

            for ticker, name, sector in initial_stocks:
                cls.create_stock(ticker, name, sector)

            print(f"OK: {len(initial_stocks)} acoes adicionadas ao banco.")
        else:
            print(f"Banco já possui {len(stocks)} ações cadastradas.")

    # ==================== MÉTODOS DE USUÁRIO ====================

    @classmethod
    def get_user_by_id(cls, user_id: int) -> Optional[Dict]:
        """Busca usuário por ID."""
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email, name, role, created_at FROM User WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        user = dict(row) if row else None

        conn.close()
        return user

    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[Dict]:
        """Busca usuário por email."""
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email, name, password_hash, role, created_at FROM User WHERE email = ?",
            (email,)
        )
        row = cursor.fetchone()
        user = dict(row) if row else None

        conn.close()
        return user

    @classmethod
    def create_user(cls, email: str, name: str, password_hash: str, role: str = 'user') -> Optional[int]:
        """Cria novo usuário."""
        try:
            conn = cls.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO User (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
                (email, name, password_hash, role)
            )

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except Exception as e:
            print(f"Erro ao criar usuario: {e}")
            return None

    # ==================== MÉTODOS DE PORTFÓLIO ====================

    @classmethod
    def get_user_portfolio(cls, user_id: int) -> List[Dict]:
        """
        Busca portfólio completo do usuário.

        Returns:
            Lista com {stock_ticker, allocation, quantity, purchase_price, etc}
        """
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                p.id,
                p.stock_ticker,
                p.allocation,
                p.quantity,
                p.purchase_price,
                p.purchase_date,
                s.name as stock_name,
                s.sector
            FROM Portfolio p
            LEFT JOIN Stock s ON p.stock_ticker = s.ticker
            WHERE p.user_id = ?
            ORDER BY p.allocation DESC
        """, (user_id,))

        rows = cursor.fetchall()
        portfolio = [dict(row) for row in rows]

        conn.close()
        return portfolio

    @classmethod
    def create_default_portfolio(cls, user_id: int) -> None:
        """
        Cria um portfólio padrão para um usuário.
        """
        default_assets = [
            ("PETR4.SA", 0.40),
            ("VALE3.SA", 0.30),
            ("ITUB4.SA", 0.20),
            ("WEGE3.SA", 0.05),
            ("BTC-USD", 0.05),
        ]

        conn = cls.get_connection()
        cursor = conn.cursor()

        for ticker, allocation in default_assets:
            cursor.execute("""
                INSERT INTO Portfolio (user_id, stock_ticker, allocation)
                VALUES (?, ?, ?)
            """, (user_id, ticker, allocation))

        conn.commit()
        conn.close()
        print(f"Portfólio padrão criado para o usuário {user_id}")

    @classmethod
    def update_allocation(cls, user_id: int, stock_ticker: str, allocation: float) -> bool:
        """
        Atualiza alocação de um ativo no portfólio do usuário.

        Args:
            user_id: ID do usuário
            stock_ticker: Ticker da ação
            allocation: Nova alocação (0.0 a 1.0)

        Returns:
            True se atualizado com sucesso
        """
        try:
            conn = cls.get_connection()
            cursor = conn.cursor()

            # Verifica se já existe
            cursor.execute(
                "SELECT id FROM Portfolio WHERE user_id = ? AND stock_ticker = ?",
                (user_id, stock_ticker)
            )
            existing = cursor.fetchone()

            if existing:
                # Atualizar
                cursor.execute("""
                    UPDATE Portfolio
                    SET allocation = ?
                    WHERE user_id = ? AND stock_ticker = ?
                """, (allocation, user_id, stock_ticker))
            else:
                # Inserir
                cursor.execute("""
                    INSERT INTO Portfolio (user_id, stock_ticker, allocation)
                    VALUES (?, ?, ?)
                """, (user_id, stock_ticker, allocation))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erro ao atualizar alocacao: {e}")
            return False

    @classmethod
    def remove_from_portfolio(cls, user_id: int, stock_ticker: str) -> bool:
        """Remove um ativo do portfólio."""
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM Portfolio WHERE user_id = ? AND stock_ticker = ?",
            (user_id, stock_ticker)
        )
        conn.commit()

        rows_affected = cursor.rowcount
        conn.close()

        return rows_affected > 0


# Instância global
database_service = DatabaseService()
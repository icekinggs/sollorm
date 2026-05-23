"""
Script CLI para criar usuários do sistema.

Uso (dentro do container):
    docker compose exec backend python -m scripts.create_user

Ou direto na pasta backend:
    python -m scripts.create_user
"""
import asyncio
import getpass
import re
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal, Base, engine
from app.models import User
from app.security import hash_password


def validate_username(username: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_.-]{3,50}$", username))


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


async def create_user_interactive():
    print("=" * 50)
    print("SolloRMM - Criação de usuário")
    print("=" * 50)

    # Garante que as tabelas existem
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    while True:
        username = input("Username (3-50 chars, letras/números/_.-): ").strip()
        if validate_username(username):
            break
        print("Username inválido. Tente novamente.")

    while True:
        email = input("Email: ").strip()
        if validate_email(email):
            break
        print("Email inválido. Tente novamente.")

    full_name = input("Nome completo (opcional): ").strip() or None

    while True:
        password = getpass.getpass("Senha (mín 8 chars): ")
        if len(password) < 8:
            print("Senha muito curta.")
            continue
        password2 = getpass.getpass("Confirme a senha: ")
        if password == password2:
            break
        print("As senhas não conferem. Tente novamente.")

    is_superuser_input = input("É administrador? [s/N]: ").strip().lower()
    is_superuser = is_superuser_input in ("s", "sim", "y", "yes")

    async with AsyncSessionLocal() as db:
        # Verifica duplicidade
        existing = await db.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        if existing.scalar_one_or_none():
            print(f"\n❌ Já existe usuário com esse username ou email.")
            return False

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            is_superuser=is_superuser,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"\n✅ Usuário '{user.username}' criado com sucesso!")
        print(f"   ID: {user.id}")
        print(f"   Admin: {'Sim' if user.is_superuser else 'Não'}")
        return True


if __name__ == "__main__":
    try:
        result = asyncio.run(create_user_interactive())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nCancelado.")
        sys.exit(130)

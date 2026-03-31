"""Renovação automática do token Meta de longa duração.

O token expira em ~60 dias. Este script renova e atualiza o .env.
Rode via cron a cada 50 dias ou manualmente.

Uso:
    python refresh_token.py
    python refresh_token.py --check  # Apenas verificar validade
"""

import argparse
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"


def check_token_validity() -> dict:
    """Verifica validade do token atual."""
    settings = get_settings()

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{GRAPH_API}/debug_token",
            params={
                "input_token": settings.meta_access_token,
                "access_token": f"{settings.meta_app_id}|{settings.meta_app_secret}",
            },
        )

    if resp.status_code != 200:
        logger.error(f"Erro ao verificar token: {resp.text}")
        return {"valid": False, "error": resp.text}

    data = resp.json().get("data", {})
    is_valid = data.get("is_valid", False)
    expires_at = data.get("expires_at", 0)

    if expires_at > 0:
        expiry = datetime.fromtimestamp(expires_at)
        days_left = (expiry - datetime.now()).days
    else:
        expiry = None
        days_left = -1

    return {
        "valid": is_valid,
        "expires_at": expiry,
        "days_left": days_left,
        "scopes": data.get("scopes", []),
        "app_id": data.get("app_id"),
    }


def refresh_token() -> str | None:
    """Troca token atual por um novo de longa duração."""
    settings = get_settings()

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{GRAPH_API}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "fb_exchange_token": settings.meta_access_token,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Erro ao renovar token: {resp.text}")
        return None

    data = resp.json()
    new_token = data.get("access_token")

    if not new_token:
        logger.error(f"Resposta sem token: {data}")
        return None

    return new_token


def update_env_file(new_token: str):
    """Atualiza META_ACCESS_TOKEN no .env."""
    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        logger.error(".env não encontrado")
        return False

    content = env_path.read_text()
    lines = content.split("\n")
    updated = False

    for i, line in enumerate(lines):
        if line.startswith("META_ACCESS_TOKEN="):
            old_token = line.split("=", 1)[1]
            lines[i] = f"META_ACCESS_TOKEN={new_token}"
            updated = True
            logger.info(f"Token atualizado: ...{old_token[-8:]} → ...{new_token[-8:]}")
            break

    if updated:
        env_path.write_text("\n".join(lines))
        return True

    logger.error("META_ACCESS_TOKEN não encontrado no .env")
    return False


def main():
    parser = argparse.ArgumentParser(description="Renovar token Meta")
    parser.add_argument("--check", action="store_true", help="Apenas verificar validade")
    args = parser.parse_args()

    # Verificar token atual
    info = check_token_validity()

    if args.check:
        print(f"\n🔑 Status do token Meta:")
        print(f"   Válido:    {'✅ Sim' if info['valid'] else '❌ Não'}")
        if info.get("expires_at"):
            print(f"   Expira em: {info['expires_at'].strftime('%d/%m/%Y %H:%M')}")
            print(f"   Dias restantes: {info['days_left']}")
            if info['days_left'] < 10:
                print(f"\n   ⚠️  Token expira em breve! Rode: python refresh_token.py")
        print(f"   Permissões: {', '.join(info.get('scopes', []))}")
        return

    # Renovar
    if info["valid"] and info.get("days_left", 0) > 15:
        logger.info(f"Token ainda válido por {info['days_left']} dias.")
        confirm = input("Renovar mesmo assim? (s/n) ").strip().lower()
        if confirm != "s":
            print("Cancelado.")
            return

    print("\n🔄 Renovando token...")
    new_token = refresh_token()

    if not new_token:
        print("❌ Falha ao renovar. Verifique APP_ID e APP_SECRET no .env.")
        sys.exit(1)

    # Verificar novo token
    # Temporariamente sobrescreve para testar
    import os
    os.environ["META_ACCESS_TOKEN"] = new_token

    # Atualizar .env
    if update_env_file(new_token):
        print("✅ Token renovado e .env atualizado!")
        print("   Reinicie o serviço: sudo systemctl restart pbev-instagram-bot")
    else:
        print(f"⚠️  Novo token gerado mas .env não foi atualizado.")
        print(f"   Token: {new_token[:20]}...{new_token[-8:]}")
        print(f"   Atualize manualmente no .env")


if __name__ == "__main__":
    main()

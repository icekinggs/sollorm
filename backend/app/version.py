"""
Mantém em memória a última versão do agente publicada no GitHub Releases.

O backend consulta a API do GitHub a cada hora em background.
Assim, basta publicar uma release no GitHub — o sistema detecta
automaticamente e exibe o badge de atualização nos agentes desatualizados.

Fallback: se a API não estiver acessível, usa settings.agent_current_version.
"""
import asyncio
import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Versão mais recente conhecida — atualizada em background
_latest: str | None = None

POLL_INTERVAL = 3600  # 1 hora


def get_latest_version() -> str:
    """Retorna a versão mais recente conhecida (GitHub ou fallback do .env)."""
    return _latest or settings.agent_current_version


async def _poll_once() -> str | None:
    url = f"https://api.github.com/repos/{settings.github_repo}/releases/latest"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "SolloRMM",
            })
            if resp.status_code == 200:
                return resp.json().get("tag_name")
            if resp.status_code == 404:
                log.debug("Nenhuma release publicada no GitHub ainda")
            else:
                log.warning("GitHub releases API retornou %d", resp.status_code)
    except Exception as exc:
        log.debug("Falha ao consultar GitHub releases: %s", exc)
    return None


async def start_version_poller() -> None:
    """Loop em background: atualiza _latest a cada POLL_INTERVAL segundos."""
    global _latest
    while True:
        version = await _poll_once()
        if version:
            if version != _latest:
                log.info("Nova versão do agente detectada no GitHub: %s", version)
            _latest = version
        await asyncio.sleep(POLL_INTERVAL)

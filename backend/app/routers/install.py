"""
Router que serve scripts de instalação.

IMPORTANTE: Estes endpoints são PÚBLICOS (sem autenticação) porque os scripts
precisam ser baixados pelas máquinas-alvo via curl/iwr antes de qualquer auth.

A segurança vem do TOKEN que o script recebe via variável de ambiente -
sem o token, o agente instalado não consegue se autenticar no backend.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.config import settings

router = APIRouter(prefix="/install", tags=["install"])

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "install_templates"


def _render_template(filename: str) -> str:
    """Carrega template e substitui variáveis."""
    template_path = TEMPLATES_DIR / filename
    if not template_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template {filename} não encontrado no servidor",
        )

    content = template_path.read_text(encoding="utf-8")

    replacements = {
        "{{SOLLORM_SERVER}}": settings.public_backend_url,
        "{{GITHUB_REPO}}": settings.github_repo,
        "{{AGENT_VERSION}}": settings.agent_current_version,
        "{{MESHCENTRAL_AGENT_LINUX_URL}}": settings.meshcentral_agent_linux_url,
        "{{MESHCENTRAL_AGENT_WINDOWS_URL}}": settings.meshcentral_agent_windows_url,
    }

    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)

    return content


@router.get("/windows.ps1", response_class=PlainTextResponse)
async def install_windows():
    """Script de instalação para Windows (PowerShell)."""
    content = _render_template("windows.ps1")
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="install-sollorm.ps1"'},
    )


@router.get("/linux.sh", response_class=PlainTextResponse)
async def install_linux():
    """Script de instalação para Linux (bash)."""
    content = _render_template("linux.sh")
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="install-sollorm.sh"'},
    )

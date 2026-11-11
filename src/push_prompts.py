"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

Uso:
    python src/push_prompts.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header, validate_prompt_structure

load_dotenv()

PROMPT_NAME = "bug_to_user_story_v2"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / f"{PROMPT_NAME}.yml"

# Chave de entrada usada no dataset de avaliação
REQUIRED_VARIABLE = "bug_report"


def build_prompt(prompt_data: dict) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", prompt_data["system_prompt"]),
        ("user", prompt_data["user_prompt"]),
    ])


def build_tags(prompt_data: dict) -> list:
    """Tags do YAML mais uma tag por técnica, para filtrar no Hub."""
    tags = list(prompt_data.get("tags", []))
    for technique in prompt_data.get("techniques_applied", []):
        tag = f"technique:{technique}"
        if tag not in tags:
            tags.append(tag)
    version = prompt_data.get("version")
    if version and version not in tags:
        tags.append(version)
    return tags


def build_readme(prompt_data: dict) -> str:
    techniques = "\n".join(f"- {t}" for t in prompt_data.get("techniques_applied", []))
    return (
        f"# {PROMPT_NAME}\n\n"
        f"{prompt_data.get('description', '')}\n\n"
        f"## Técnicas aplicadas\n\n{techniques}\n\n"
        f"Variável de entrada: `{{{REQUIRED_VARIABLE}}}`.\n"
    )


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    username = os.getenv("USERNAME_LANGSMITH_HUB")
    identifier = f"{username}/{prompt_name}"
    print(f"Fazendo push de {identifier}...")

    client = Client()
    try:
        url = client.push_prompt(
            identifier,
            object=build_prompt(prompt_data),
            is_public=True,
            description=prompt_data.get("description", ""),
            readme=build_readme(prompt_data),
            tags=build_tags(prompt_data),
        )
    except Exception as e:
        # O Hub recusa commit idêntico ao último: o prompt publicado já é este.
        if "nothing to commit" in str(e).lower() or "409" in str(e):
            print("   ✓ Nenhuma mudança desde o último push, o Hub já tem esta versão")
            return True
        print(f"❌ Falha no push de {identifier}: {e}")
        return False

    print(f"   ✓ Publicado (público): {url}")
    print(f"   ✓ Técnicas: {', '.join(prompt_data.get('techniques_applied', []))}")
    return True


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    _, errors = validate_prompt_structure(prompt_data)

    user_prompt = (prompt_data.get("user_prompt") or "").strip()
    if not user_prompt:
        errors.append("user_prompt está vazio")

    try:
        variables = set(build_prompt(prompt_data).input_variables)
    except Exception as e:
        errors.append(f"Template inválido (chaves soltas precisam ser escapadas com {{{{ }}}}): {e}")
        return (False, errors)

    if REQUIRED_VARIABLE not in variables:
        errors.append(f"O template precisa usar a variável {{{REQUIRED_VARIABLE}}}")
    extra = variables - {REQUIRED_VARIABLE}
    if extra:
        errors.append(f"Variáveis que o dataset não fornece: {', '.join(sorted(extra))}")

    # O v1 repetia {bug_report} no system e no user; aqui o relato entra uma vez só.
    if f"{{{REQUIRED_VARIABLE}}}" in prompt_data.get("system_prompt", ""):
        errors.append(f"{{{REQUIRED_VARIABLE}}} deve ficar só no user_prompt")

    return (len(errors) == 0, errors)


def main():
    """Função principal"""
    print_section_header("PUSH DE PROMPTS OTIMIZADOS")

    if not check_env_vars(["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]):
        return 1

    data = load_yaml(str(PROMPT_PATH))
    if not data or PROMPT_NAME not in data:
        print(f"❌ {PROMPT_PATH.name} precisa ter a chave '{PROMPT_NAME}' na raiz")
        return 1

    prompt_data = data[PROMPT_NAME]
    is_valid, errors = validate_prompt(prompt_data)
    if not is_valid:
        print("❌ Prompt inválido:")
        for error in errors:
            print(f"   - {error}")
        return 1
    print("   ✓ Prompt válido")

    return 0 if push_prompt_to_langsmith(PROMPT_NAME, prompt_data) else 1


if __name__ == "__main__":
    sys.exit(main())

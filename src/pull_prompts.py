"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull do prompt semente do desafio
3. Salva localmente em prompts/bug_to_user_story_v1.yml

Uso:
    python src/pull_prompts.py
"""

import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()


def _str_presenter(dumper, value):
    """Grava strings multilinha como bloco literal (|), legível no diff."""
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


# save_yaml (utils.py) usa yaml.dump, que passa a usar este representer
yaml.add_representer(str, _str_presenter)

SOURCE_PROMPT = "leonanluppi/bug_to_user_story_v1"
PROMPT_KEY = "bug_to_user_story_v1"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "prompts" / f"{PROMPT_KEY}.yml"

# Tipo da mensagem no LangChain -> campo no YAML
ROLE_TO_FIELD = {
    "system": "system_prompt",
    "human": "user_prompt",
}


def prompt_to_dict(prompt: ChatPromptTemplate) -> dict:
    """
    Converte o ChatPromptTemplate puxado do Hub no formato YAML do projeto.

    Cada mensagem do template vira um campo (system_prompt, user_prompt). Os
    metadados que o Hub anexa ao objeto (lc_hub_owner, lc_hub_repo, lc_hub_commit_hash)
    são preservados para rastrear de qual commit o arquivo local veio.
    """
    data = {"description": "Prompt para converter relatos de bugs em User Stories"}

    for message in prompt.messages:
        role = getattr(message, "_msg_class", None)
        role_name = role.__name__.replace("Message", "").lower() if role else ""
        if not role_name:
            # Fallback: SystemMessagePromptTemplate -> "system"
            role_name = type(message).__name__.replace("MessagePromptTemplate", "").lower()

        field = ROLE_TO_FIELD.get(role_name, f"{role_name}_prompt")
        data[field] = message.prompt.template

    hub_meta = prompt.metadata or {}
    data["version"] = "v1"
    data["input_variables"] = sorted(prompt.input_variables)
    data["source"] = {
        "hub": SOURCE_PROMPT,
        "commit": hub_meta.get("lc_hub_commit_hash"),
    }
    data["tags"] = ["bug-analysis", "user-story", "product-management"]
    return data


def pull_prompts_from_langsmith() -> bool:
    print(f"Puxando {SOURCE_PROMPT} do LangSmith Hub...")

    try:
        client = Client()
        # O identificador tem dono explícito ("owner/nome"), então o LangSmith exige
        # o opt-in: o prompt é um objeto LangChain serializado vindo de terceiros.
        # Aqui é o prompt semente do desafio, o risco é conhecido.
        prompt = client.pull_prompt(SOURCE_PROMPT, dangerously_pull_public_prompt=True)
    except Exception as e:
        print(f"❌ Falha no pull de {SOURCE_PROMPT}: {e}")
        return False

    data = prompt_to_dict(prompt)
    print(f"   ✓ {len(prompt.messages)} mensagens, variáveis: {', '.join(data['input_variables'])}")

    if not save_yaml({PROMPT_KEY: data}, str(OUTPUT_PATH)):
        return False

    print(f"   ✓ Salvo em {OUTPUT_PATH.relative_to(OUTPUT_PATH.parent.parent)}")
    return True


def main():
    """Função principal"""
    print_section_header("PULL DE PROMPTS DO LANGSMITH HUB")

    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1

    return 0 if pull_prompts_from_langsmith() else 1


if __name__ == "__main__":
    sys.exit(main())

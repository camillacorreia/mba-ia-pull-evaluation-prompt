"""
Testes automatizados para validação de prompts.
"""
import re
import pytest
import yaml
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def load_prompts(file_path: str):
    """Carrega prompts do arquivo YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def prompt():
    return load_prompts(PROMPT_PATH)[PROMPT_KEY]


@pytest.fixture(scope="module")
def system_prompt(prompt):
    return prompt.get("system_prompt") or ""


class TestPrompts:
    def test_prompt_has_system_prompt(self, prompt):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        assert "system_prompt" in prompt
        assert prompt["system_prompt"].strip()

    def test_prompt_has_role_definition(self, system_prompt):
        """Verifica se o prompt define uma persona (ex: "Você é um Product Manager")."""
        assert re.search(r"Você é (um|uma) .+", system_prompt), "Falta a frase de persona 'Você é um ...'"
        assert "Product Manager" in system_prompt

    def test_prompt_mentions_format(self, system_prompt):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        for part in ("Como um", "eu quero", "para que"):
            assert part in system_prompt, f"Formato de User Story sem '{part}'"
        assert "Critérios de Aceitação" in system_prompt
        for keyword in ("Dado que", "Quando", "Então"):
            assert keyword in system_prompt, f"Critérios sem o padrão Given/When/Then ('{keyword}')"

    def test_prompt_has_few_shot_examples(self, system_prompt):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        inputs = re.findall(r"^Relato:\s*$", system_prompt, flags=re.MULTILINE)
        outputs = re.findall(r"^Resposta:\s*$", system_prompt, flags=re.MULTILINE)
        assert len(inputs) >= 2, f"Few-shot precisa de pelo menos 2 exemplos, achei {len(inputs)}"
        assert len(inputs) == len(outputs), "Todo exemplo de entrada precisa de uma saída"

        # Cada resposta de exemplo precisa seguir o próprio formato que o prompt exige
        answers = re.split(r"^Resposta:\s*$", system_prompt, flags=re.MULTILINE)[1:]
        for answer in answers:
            assert answer.strip().startswith("Como um"), "Exemplo de saída fora do formato de User Story"

    def test_prompt_no_todos(self):
        """Garante que você não esqueceu nenhum `[TODO]` no texto."""
        text = PROMPT_PATH.read_text(encoding="utf-8")
        assert "[TODO]" not in text
        assert "TODO" not in text, "utils.validate_prompt_structure também barra 'TODO' sem colchetes"

    def test_minimum_techniques(self, prompt):
        """Verifica (através dos metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        techniques = prompt.get("techniques_applied", [])
        assert isinstance(techniques, list)
        assert len(techniques) >= 2
        assert "few-shot-learning" in techniques, "Few-shot é obrigatório no desafio"

    def test_prompt_passes_structure_validation(self, prompt):
        """A mesma validação de utils.py que o push usa."""
        is_valid, errors = validate_prompt_structure(prompt)
        assert is_valid, errors

    def test_bug_report_only_in_user_prompt(self, prompt, system_prompt):
        """O v1 repetia {bug_report} no system e no user; o v2 manda o relato uma vez só."""
        assert "{bug_report}" in prompt["user_prompt"]
        assert "{bug_report}" not in system_prompt

    def test_system_prompt_has_no_unescaped_braces(self, system_prompt):
        """Chave solta no system prompt vira variável no ChatPromptTemplate e quebra o invoke."""
        from langchain_core.prompts import ChatPromptTemplate

        template = ChatPromptTemplate.from_messages([("system", system_prompt)])
        assert template.input_variables == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

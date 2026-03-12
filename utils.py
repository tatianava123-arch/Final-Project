from typing import Iterator

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


# =========================
# Autocomplete
# =========================
class CommandCompleter(Completer):
    """Підказує команди і аргументи залежно від того в якому модулі знаходиться користувач."""

    NAME_COMMANDS: set[str] = {"edit", "delete", "show-birthday"}
    TITLE_COMMANDS: set[str] = {"edit", "delete"}
    SEARCH_COMMANDS: set[str] = {"search", "sort"}

    def __init__(self, commands: list[str], context: dict) -> None:
        """Зберігає команди і контекст, щоб підказки були актуальні на момент вводу."""
        self.commands = commands
        self.context = context

    def get_completions(self, document: Document, complete_event: object) -> Iterator[Completion]:
        """Визначає що підказувати — команду чи аргумент — залежно від позиції курсора."""
        text = document.text_before_cursor
        parts = text.split()

        if not parts or (len(parts) == 1 and not text.endswith(" ")):
            word = parts[0].lower() if parts else ""
            for command in self.commands:
                if command.startswith(word):
                    yield Completion(command, start_position=-len(word))
            return

        cmd = parts[0].lower()
        current_word = parts[1] if len(
            parts) > 1 and not text.endswith(" ") else ""

        if cmd in self.NAME_COMMANDS and "names" in self.context:
            for name in self.context["names"]():
                if name.lower().startswith(current_word.lower()):
                    yield Completion(name, start_position=-len(current_word))

        elif cmd in self.TITLE_COMMANDS and "titles" in self.context:
            for title in self.context["titles"]():
                if title.lower().startswith(current_word.lower()):
                    yield Completion(title, start_position=-len(current_word))

        elif cmd in self.SEARCH_COMMANDS and "titles" in self.context:
            seen: set[str] = set()
            for title in self.context["titles"]():
                if title.lower().startswith(current_word.lower()) and title not in seen:
                    seen.add(title)
                    yield Completion(title, start_position=-len(current_word), display=f"📝 {title}")
            for tag in self.context["tags"]():
                if tag.lower().startswith(current_word.lower()) and tag not in seen:
                    seen.add(tag)
                    yield Completion(tag, start_position=-len(current_word), display=f"🏷  {tag}")


# =========================
# Helpers
# =========================
def ask_yes_no(text: str) -> bool:
    """Повторює запит поки користувач не введе валідну відповідь."""
    while True:
        answer = input(f"{text} (y/n): ").lower()
        if answer in ["y", "n"]:
            return answer == "y"
        print("Введіть y або n")

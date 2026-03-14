import pickle
from datetime import datetime
from collections import UserDict
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import box
from prompt_toolkit import PromptSession

from utils import CommandCompleter, ask_yes_no

console = Console()


# =========================
# Fields
# =========================


class Field:
    """Спільна основа для всіх полів нотатки."""

    def __init__(self, value: str | list) -> None:
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


class Title(Field):
    """Зберігає заголовок нотатки."""

    pass


class Content(Field):
    """Зберігає вміст нотатки."""

    pass


class Tags(Field):
    """Нормалізує теги до списку рядків незалежно від формату вводу."""

    def __init__(self, value: Optional[str | list]) -> None:
        if isinstance(value, str):
            value = [tag.strip() for tag in value.split(",") if tag.strip()]
        elif not isinstance(value, list):
            value = []
        super().__init__(value)


# =========================
# Note
# =========================


class Note:
    """Представляє одну нотатку з автоматичним відстеженням дат змін."""

    def __init__(
        self,
        title: str,
        content: str,
        tags: Optional[str] = None,
    ) -> None:
        self.title = Title(title)
        self.content = Content(content)
        self.tags = Tags(tags)
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

    def edit(
        self,
        new_content: Optional[str] = None,
        new_tags: Optional[str] = None,
    ) -> None:
        """Оновлює лише передані поля і фіксує час змін."""
        if new_content is not None:
            self.content = Content(new_content)
        if new_tags is not None:
            self.tags = Tags(new_tags)
        self.updated_at = datetime.now()


# =========================
# Notebook
# =========================


class Notebook(UserDict):
    """Зберігає нотатки за заголовком як ключем."""

    def add_note(self, note: Note) -> None:
        """Використовує заголовок як ключ, бо він унікальний для нотаток."""
        self.data[note.title.value] = note

    def find(self, title: str) -> Optional[Note]:
        """Потрібен для перевірки існування перед редагуванням."""
        return self.data.get(title)

    def delete(self, title: str) -> bool:
        """Повертає False якщо нотатку не знайдено."""
        if title in self.data:
            del self.data[title]
            return True
        return False

    def search(self, query: Optional[str] = None) -> list[Note]:
        """Шукає одночасно по заголовку і тегах."""
        result = []
        for note in self.data.values():
            if not query:
                result.append(note)
                continue
            q = query.lower()
            if (
                q in note.title.value.lower()
                or any(q in t.lower() for t in note.tags.value)
            ):
                result.append(note)
        return result

    def sort_notes_by_tag(self, tag: str) -> list[Note]:
        """Виносить нотатки з потрібним тегом вгору."""
        tag_lower = tag.lower()
        notes_with_tag = [
            n
            for n in self.data.values()
            if any(tag_lower in t.lower() for t in n.tags.value)
        ]
        others = [n for n in self.data.values() if n not in notes_with_tag]
        return notes_with_tag + others


# =========================
# Save / Load
# =========================


def save_data(book: Notebook) -> None:
    """Зберігає стан нотатника між сесіями."""
    with open("notebook.pkl", "wb") as f:
        pickle.dump(book, f)


def load_data() -> Notebook:
    """Відновлює збережений стан або створює порожній нотатник."""
    try:
        with open("notebook.pkl", "rb") as f:
            return pickle.load(f)
    except (FileNotFoundError, EOFError, pickle.UnpicklingError):
        return Notebook()


# =========================
# CLI
# =========================


def create_note(book: Notebook) -> None:
    """Забороняє створення дублікату заголовку."""
    title = input("Заголовок нотатки: ").strip()
    if not title:
        print("Заголовок не може бути порожнім")
        return
    if book.find(title):
        print("Нотатка з таким заголовком вже існує")
        return
    content = input("Вміст: ")
    tags = input("Теги (через кому, необов'язково): ")
    note = Note(title, content, tags)
    book.add_note(note)
    print("Нотатку створено")


def edit_note(book: Notebook, title: str = "") -> None:
    """Редагує лише вибрані поля."""
    if not title:
        title = input("Заголовок нотатки: ").strip()
    note = book.find(title)
    if not note:
        print("Нотатку не знайдено")
        return

    content: Optional[str] = None
    tags: Optional[str] = None

    if ask_yes_no("Редагувати вміст"):
        content = input("Новий вміст: ")
    if ask_yes_no("Редагувати теги"):
        tags = input("Нові теги (через кому): ")

    note.edit(content, tags)
    print("Нотатку оновлено")


def delete_note(book: Notebook, title: str = "") -> None:
    """Видаляє нотатку за заголовком."""
    if not title:
        title = input("Заголовок нотатки: ").strip()
    if book.delete(title):
        print("Нотатку видалено")
    else:
        print("Нотатку не знайдено")


def show_notes(book: Notebook, query: Optional[str] = None) -> None:
    """Виводить таблицю з нотатками."""
    notes = book.search(query)
    if not notes:
        print("Нотаток не знайдено")
        return

    table = Table(title="Нотатки", box=box.ROUNDED)
    table.add_column("Заголовок", style="cyan")
    table.add_column("Вміст")
    table.add_column("Теги", style="magenta")
    table.add_column("Створено", style="dim")
    table.add_column("Оновлено", style="dim")

    for note in notes:
        table.add_row(
            str(note.title.value),
            str(note.content.value),
            ", ".join(str(tag) for tag in note.tags.value),
            note.created_at.strftime("%d.%m.%Y %H:%M"),
            note.updated_at.strftime("%d.%m.%Y %H:%M"),
        )
    console.print(table)


def run(book: Notebook) -> None:
    """Запускає інтерактивний цикл нотатника."""
    commands = ["add", "edit", "delete", "all", "search", "sort", "help", "back"]
    session = PromptSession()

    # Винесено в окрему змінну для кращої читабельності PEP 8
    def get_tags():
        return list({tag for n in book.data.values() for tag in n.tags.value})

    completer = CommandCompleter(
        commands,
        {
            "titles": lambda: list(book.data.keys()),
            "tags": lambda: list({tag for n in book.data.values() for tag in n.tags.value}),
        },
    )

    console.print(
        "\n[cyan]📓 Нотатник[/cyan] — введіть [bold]help[/bold] "
        "для списку команд\n"
    )

    while True:
        try:
            user_input = session.prompt("Нотатник › ", completer=completer).strip()
            if not user_input:
                continue

            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) == 2 else ""

            if cmd == "back":
                save_data(book)
                break
            elif cmd == "help":
                table = Table(title="Команди нотатника", box=box.ROUNDED)
                table.add_column("Команда", style="yellow")
                table.add_column("Опис")
                table.add_row("add", "Створити нотатку")
                table.add_row("edit [заголовок]", "Редагувати нотатку")
                table.add_row("delete [заголовок]", "Видалити нотатку")
                table.add_row("all", "Показати всі нотатки")
                table.add_row("search [запит]", "Пошук за заголовком/тегом")
                table.add_row("sort [тег]", "Сортувати за тегом")
                table.add_row("help", "Список команд")
                table.add_row("back", "Назад до меню")
                console.print(table)
            elif cmd == "add":
                create_note(book)
            elif cmd == "edit":
                edit_note(book, args)
            elif cmd == "delete":
                delete_note(book, args)
            elif cmd == "all":
                show_notes(book)
            elif cmd == "search":
                show_notes(book, args if args else None)
            elif cmd == "sort":
                if args:
                    sorted_notes = book.sort_notes_by_tag(args)
                    show_notes(Notebook({n.title.value: n for n in sorted_notes}))
                else:
                    print("Використання: sort ТЕГ")
            else:
                print("Невідома команда")
        except KeyboardInterrupt:
            continue

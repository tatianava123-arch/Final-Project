from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import contacts as ab
import notebook as nb

console = Console()


def show_menu() -> None:
    """Виводить головне меню у вигляді панелі."""
    text = Text()
    text.append("1", style="bold cyan")
    text.append("  📒 Адресна книга\n")
    text.append("2", style="bold cyan")
    text.append("  📓 Нотатник\n")
    text.append("3", style="bold cyan")
    text.append("  👋 Вийти")
    console.print(Panel(
        text,
        title="[bold green]Персональний асистент[/bold green]",
        padding=(1, 4)
    ))


def main() -> None:
    """
    Завантажує дані, показує головне меню і направляє до потрібного модуля.
    Зберігає дані при виході.
    """
    address_book = ab.load_data()
    notebook = nb.load_data()

    while True:
        show_menu()
        choice = input("Оберіть: ").strip()

        if choice == "1":
            ab.run(address_book)
        elif choice == "2":
            nb.run(notebook)
        elif choice == "3":
            ab.save_data(address_book)
            nb.save_data(notebook)
            console.print("[yellow]До побачення![/yellow]")
            break
        else:
            console.print("[red]Оберіть 1, 2 або 3[/red]")


if __name__ == "__main__":
    main()

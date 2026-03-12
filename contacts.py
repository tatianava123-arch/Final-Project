from __future__ import annotations

import pickle
import re
import uuid
from collections import UserDict
from datetime import date, datetime, timedelta
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import box

from prompt_toolkit import PromptSession

from utils import CommandCompleter, ask_yes_no

console = Console()


# =========================
# Валідація
# =========================

def normalize_ua_phone(phone: str) -> str:
    """Приводить різні формати українських номерів до єдиного +380XXXXXXXXX."""
    cleaned = re.sub(r"[^0-9+]", "", phone.strip())

    if cleaned.startswith("+380"):
        normalized = cleaned
    elif cleaned.startswith("380"):
        normalized = "+" + cleaned
    elif cleaned.startswith("0"):
        normalized = "+38" + cleaned
    else:
        raise ValueError("Невалідний український номер телефону")

    if not re.fullmatch(r"\+380\d{9}", normalized):
        raise ValueError("Невалідний український номер телефону")

    return normalized


def validate_email(email: str) -> str:
    """Захищає від збереження некоректних email-адрес."""
    email = email.strip()
    if not re.fullmatch(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
        raise ValueError("Невалідний email")
    return email


# =========================
# Fields
# =========================

class Field:
    """Спільна основа для всіх полів запису."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


class Name(Field):
    """Зберігає ім'я контакту."""
    pass


class Phone(Field):
    """Гарантує що номер завжди зберігається у нормалізованому форматі."""

    def __init__(self, value: str) -> None:
        super().__init__(normalize_ua_phone(value))


class Email(Field):
    """Гарантує що email зберігається лише після перевірки формату."""

    def __init__(self, value: str) -> None:
        super().__init__(validate_email(value))


class Address(Field):
    """Зберігає довільну адресу контакту."""
    pass


class Birthday(Field):
    """Зберігає дату як рядок і як date-об'єкт для обчислень."""

    def __init__(self, value: str) -> None:
        try:
            self.date_value: date = datetime.strptime(
                value.strip(), "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Використовуйте формат DD.MM.YYYY")
        super().__init__(value.strip())


# =========================
# Record
# =========================

class Record:
    """Представляє один контакт із uuid як ключем, щоб дозволити однакові імена."""

    def __init__(self, name: str) -> None:
        self.id: str = str(uuid.uuid4())
        self.name = Name(name.strip())
        self.phones: list[Phone] = []
        self.email: Optional[Email] = None
        self.address: Optional[Address] = None
        self.birthday: Optional[Birthday] = None

    def add_phone(self, phone: str) -> None:
        """Уникає дублікатів перед додаванням нового номера."""
        new_phone = Phone(phone)
        if any(p.value == new_phone.value for p in self.phones):
            return
        self.phones.append(new_phone)

    def find_phone(self, phone: str) -> Optional[Phone]:
        """Шукає за нормалізованим значенням, щоб формат вводу не мав значення."""
        normalized = normalize_ua_phone(phone)
        return next((p for p in self.phones if p.value == normalized), None)

    def remove_phone(self, phone: str) -> bool:
        """Повертає False якщо номер не існує, щоб CLI міг повідомити користувача."""
        found = self.find_phone(phone)
        if found is None:
            return False
        self.phones.remove(found)
        return True

    def edit_phone(self, old_phone: str, new_phone: str) -> bool:
        """Замінює номер на місці, щоб зберегти порядок у списку."""
        found = self.find_phone(old_phone)
        if found is None:
            return False
        found.value = Phone(new_phone).value
        return True

    def add_email(self, email: str) -> None:
        """Перезаписує email, бо контакт може мати лише одну адресу."""
        self.email = Email(email)

    def add_address(self, address: str) -> None:
        """Перезаписує адресу, бо контакт може мати лише одну."""
        self.address = Address(address.strip())

    def add_birthday(self, birthday: str) -> None:
        """Перезаписує день народження після валідації формату."""
        self.birthday = Birthday(birthday)

    def matches(self, query: str) -> bool:
        """Дозволяє шукати контакт за будь-яким з його полів."""
        q = query.lower().strip()
        if q in self.name.value.lower():
            return True
        if self.email and q in self.email.value.lower():
            return True
        if self.address and q in self.address.value.lower():
            return True
        return any(q in p.value for p in self.phones)


# =========================
# AddressBook
# =========================

class AddressBook(UserDict):
    """Зберігає контакти за uuid, щоб підтримувати однакові імена."""

    def add_record(self, record: Record) -> None:
        """Використовує id запису як ключ для унікальності."""
        self.data[record.id] = record

    def find_by_id(self, record_id: str) -> Optional[Record]:
        """Потрібен для прямого доступу коли id вже відомий."""
        return self.data.get(record_id)

    def find(self, name: str) -> Optional[Record]:
        """Повертає перший збіг — для випадків коли дублікати малоймовірні."""
        name = name.strip()
        return next((r for r in self.data.values() if r.name.value == name), None)

    def find_all_by_name(self, name: str) -> list[Record]:
        """Потрібен для коректної обробки кількох контактів з однаковим іменем."""
        name = name.strip()
        return [r for r in self.data.values() if r.name.value == name]

    def delete(self, record_id: str) -> bool:
        """Видаляє за id, а не за іменем, щоб не зачепити однофамільців."""
        if record_id not in self.data:
            return False
        del self.data[record_id]
        return True

    def search(self, query: str) -> list[Record]:
        """Делегує перевірку збігу самому запису через matches()."""
        return [r for r in self.data.values() if r.matches(query)]

    def get_upcoming_birthdays(self, days: int = 7) -> list[dict]:
        """Переносить привітання з вихідних на понеділок і сортує за датою."""
        today = date.today()
        end_date = today + timedelta(days=days)
        result: list[dict] = []

        for record in self.data.values():
            if record.birthday is None:
                continue

            bday = record.birthday.date_value
            try:
                congrats = bday.replace(year=today.year)
            except ValueError:
                congrats = date(today.year, 2, 28)

            if congrats < today:
                try:
                    congrats = bday.replace(year=today.year + 1)
                except ValueError:
                    congrats = date(today.year + 1, 2, 28)

            if congrats.weekday() == 5:
                congrats += timedelta(days=2)
            elif congrats.weekday() == 6:
                congrats += timedelta(days=1)

            if today <= congrats <= end_date:
                result.append({
                    "name": record.name.value,
                    "congratulation_date": congrats.strftime("%d.%m.%Y"),
                })

        result.sort(key=lambda x: datetime.strptime(
            x["congratulation_date"], "%d.%m.%Y"))
        return result


# =========================
# Save / Load
# =========================

def save_data(book: AddressBook) -> None:
    """Зберігає стан книги між сесіями."""
    with open("contacts.pkl", "wb") as f:
        pickle.dump(book, f)


def load_data() -> AddressBook:
    """Відновлює збережений стан або створює порожню книгу при першому запуску."""
    try:
        with open("contacts.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return AddressBook()


# =========================
# CLI helpers
# =========================

def _pick_record(book: AddressBook, name: str) -> Optional[Record]:
    """Дає користувачу вибрати конкретний запис коли є кілька з однаковим іменем."""
    matches = book.find_all_by_name(name)

    if not matches:
        print("Контакт не знайдено")
        return None

    if len(matches) == 1:
        return matches[0]

    print(f"Знайдено {len(matches)} контакти з іменем '{name}':")
    for i, record in enumerate(matches, 1):
        phones = ", ".join(p.value for p in record.phones) or "—"
        email = record.email.value if record.email else "—"
        print(f"  {i}. Телефони: {phones} | Email: {email}")

    while True:
        choice = input(f"Оберіть номер (1-{len(matches)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(matches):
            return matches[int(choice) - 1]
        print("Невірний вибір")


# =========================
# CLI
# =========================

def create_contact(book: AddressBook) -> None:
    """Попереджає про дублікат імені, але дозволяє створити контакт."""
    name = input("Ім'я: ").strip()
    if not name:
        print("Ім'я не може бути порожнім")
        return

    existing = book.find_all_by_name(name)
    if existing:
        print(f"Увага: контакт '{name}' вже існує ({len(existing)} шт.)")
        if not ask_yes_no("Все одно створити новий?"):
            return

    record = Record(name)

    while ask_yes_no("Додати телефон"):
        try:
            record.add_phone(input("Телефон: "))
        except ValueError as e:
            print(e)

    if ask_yes_no("Додати день народження"):
        try:
            record.add_birthday(input("День народження DD.MM.YYYY: "))
        except ValueError as e:
            print(e)

    if ask_yes_no("Додати email"):
        try:
            record.add_email(input("Email: "))
        except ValueError as e:
            print(e)

    if ask_yes_no("Додати адресу"):
        record.add_address(input("Адреса: "))

    book.add_record(record)
    print("\n\033[1mКонтакт створено\033[0m\n")


def edit_contact(book: AddressBook, name: str = "") -> None:
    """Обирає потрібний запис через _pick_record якщо є однофамільці."""
    if not name:
        name = input("Ім'я контакту: ").strip()

    record = _pick_record(book, name)
    if not record:
        return

    if ask_yes_no("Редагувати телефони"):
        phones_str = ", ".join(p.value for p in record.phones) or "—"
        print("Телефони:", phones_str)
        print("1 — додати  2 — видалити  3 — замінити")
        option = input("Опція: ")

        if option == "1":
            try:
                record.add_phone(input("Новий телефон: "))
            except ValueError as e:
                print(e)
        elif option == "2":
            if not record.remove_phone(input("Телефон для видалення: ")):
                print("Телефон не знайдено")
        elif option == "3":
            old = input("Старий телефон: ")
            new = input("Новий телефон: ")
            try:
                if not record.edit_phone(old, new):
                    print("Телефон не знайдено")
            except ValueError as e:
                print(e)

    if ask_yes_no("Редагувати день народження"):
        try:
            record.add_birthday(input("День народження: "))
        except ValueError as e:
            print(e)

    if ask_yes_no("Редагувати email"):
        try:
            record.add_email(input("Email: "))
        except ValueError as e:
            print(e)

    if ask_yes_no("Редагувати адресу"):
        record.add_address(input("Адреса: "))

    print("Контакт оновлено")


def delete_contact(book: AddressBook, name: str = "") -> None:
    """Видаляє за id запису, щоб не зачепити однофамільців."""
    if not name:
        name = input("Ім'я контакту: ").strip()

    record = _pick_record(book, name)
    if not record:
        return

    if book.delete(record.id):
        print("Видалено")
    else:
        print("Контакт не знайдено")


def show_contacts(book: AddressBook) -> None:
    """Виводить таблицю для швидкого огляду всіх контактів."""
    if not book.data:
        print("Немає контактів")
        return

    table = Table(title="Контакти", box=box.ROUNDED)
    table.add_column("Ім'я")
    table.add_column("Телефони")
    table.add_column("День народження")
    table.add_column("Email")
    table.add_column("Адреса")

    for record in book.data.values():
        phones = ", ".join(p.value for p in record.phones)
        birthday = record.birthday.value if record.birthday else ""
        email = record.email.value if record.email else ""
        address = record.address.value if record.address else ""
        table.add_row(record.name.value, phones, birthday, email, address)

    console.print(table)


def show_upcoming_birthdays(book: AddressBook, days_range: int = 30) -> None:
    """Нагадує про дні народження заздалегідь, щоб не пропустити."""
    upcoming = book.get_upcoming_birthdays(days_range)

    if not upcoming:
        print(f"Немає днів народження у найближчі {days_range} днів")
        return

    table = Table(
        title=f"Дні народження (наступні {days_range} днів)", box=box.ROUNDED)
    table.add_column("Ім'я")
    table.add_column("Дата привітання")

    for item in upcoming:
        table.add_row(item["name"], item["congratulation_date"])

    console.print(table)


def show_birthday(book: AddressBook, name: str) -> None:
    """Показує скільки днів залишилось до наступного дня народження контакту."""
    record = _pick_record(book, name)
    if not record:
        return

    if not record.birthday:
        print(f"{name} не має дня народження")
        return

    today = date.today()
    bday = record.birthday.date_value
    try:
        next_bd = bday.replace(year=today.year)
    except ValueError:
        next_bd = date(today.year, 2, 28)
    if next_bd < today:
        try:
            next_bd = bday.replace(year=today.year + 1)
        except ValueError:
            next_bd = date(today.year + 1, 2, 28)

    days_left = (next_bd - today).days
    print(
        f"День народження {name}: {record.birthday.value} (через {days_left} днів)")


def run(book: AddressBook) -> None:
    """Запускає інтерактивний цикл адресної книги."""
    commands = ["add", "edit", "delete", "all", "search",
                "birthdays", "show-birthday", "help", "back"]
    session = PromptSession()
    completer = CommandCompleter(commands, {
        "names": lambda: list({r.name.value for r in book.data.values()}),
    })

    console.print(
        "\n[cyan]📒 Адресна книга[/cyan] — введіть [bold]help[/bold] для списку команд, або [bold]back[/bold] для повернення до головного меню\n")

    while True:
        user_input = session.prompt(
            "Адресна книга › ", completer=completer).strip()
        cmd = user_input.lower()

        if cmd == "back":
            save_data(book)
            break
        elif cmd == "help":
            table = Table(title="Команди адресної книги", box=box.ROUNDED)
            table.add_column("Команда")
            table.add_column("Опис")
            table.add_row("add", "Створити контакт")
            table.add_row("edit [ім'я]", "Редагувати контакт")
            table.add_row("delete [ім'я]", "Видалити контакт")
            table.add_row("all", "Показати всі контакти")
            table.add_row("search [запит]",
                          "Пошук за іменем, телефоном, email")
            table.add_row("birthdays", "Найближчі дні народження")
            table.add_row("show-birthday [ім'я]", "День народження контакту")
            table.add_row("help", "Список команд")
            table.add_row("back", "Повернутись до головного меню")
            console.print(table)
        elif cmd == "add":
            create_contact(book)
        elif cmd.startswith("edit"):
            parts = user_input.split(maxsplit=1)
            edit_contact(book, parts[1] if len(parts) == 2 else "")
        elif cmd.startswith("delete"):
            parts = user_input.split(maxsplit=1)
            delete_contact(book, parts[1] if len(parts) == 2 else "")
        elif cmd == "all":
            show_contacts(book)
        elif cmd.startswith("search"):
            parts = user_input.split(maxsplit=1)
            if len(parts) == 2:
                results = book.search(parts[1])
                if results:
                    tmp = AddressBook({r.id: r for r in results})
                    show_contacts(tmp)
                else:
                    print("Нічого не знайдено")
            else:
                print("Використання: search ЗАПИТ")
        elif cmd == "birthdays":
            show_upcoming_birthdays(book)
        elif cmd.startswith("show-birthday"):
            parts = user_input.split(maxsplit=1)
            if len(parts) == 2:
                show_birthday(book, parts[1])
            else:
                print("Використання: show-birthday ІМ'Я")
        else:
            print("Невідома команда")

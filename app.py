"""Simple Library Management System.

The application intentionally uses three separate SQLite files:
  * authentication.db - users, passwords and roles
  * catalog.db - the current book catalogue and rental status
  * transactions.db - immutable history records for important actions

Tkinter and SQLite are part of Python's standard library, so no third-party
packages are required.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import tkinter as tk
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from collections.abc import Iterator


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AUTH_DB = DATA_DIR / "authentication.db"
BOOK_DB = DATA_DIR / "catalog.db"
HISTORY_DB = DATA_DIR / "transactions.db"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_databases() -> None:
    """Create/migrate each independent database and add assignment dummy data."""
    DATA_DIR.mkdir(exist_ok=True)

    # DATABASE 1: authentication database.
    with connect(AUTH_DB) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Admin', 'User'))
            )"""
        )
        admin = db.execute("SELECT id, password_hash FROM users WHERE username='admin'").fetchone()
        if admin is None:
            db.execute(
                "INSERT INTO users(username, password_hash, role) VALUES (?, ?, 'Admin')",
                ("admin", hash_password("admin123")),
            )
        elif not verify_password("admin123", admin["password_hash"]):
            # The supplied starter database used a different hash format.
            # Convert only the seeded admin so the documented account works.
            db.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (hash_password("admin123"), admin["id"]),
            )
        if db.execute("SELECT 1 FROM users WHERE username='librarian'").fetchone() is None:
            db.execute(
                "INSERT INTO users(username, password_hash, role) VALUES (?, ?, 'User')",
                ("librarian", hash_password("library123")),
            )

    # DATABASE 2: current book information database.  Migrate the starter
    # catalogue's columns to the clearer assignment names without losing data.
    with connect(BOOK_DB) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT UNIQUE NOT NULL,
                year INTEGER NOT NULL,
                category TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1,
                release_date TEXT,
                status TEXT NOT NULL DEFAULT 'Available',
                rented_by TEXT
            )"""
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(books)")}
        for name, definition in (
            ("release_date", "TEXT"),
            ("status", "TEXT NOT NULL DEFAULT 'Available'"),
            ("rented_by", "TEXT"),
        ):
            if name not in columns:
                db.execute(f"ALTER TABLE books ADD COLUMN {name} {definition}")
        db.execute(
            "UPDATE books SET release_date=COALESCE(release_date, CAST(year AS TEXT)), "
            "status=CASE WHEN available=1 THEN 'Available' ELSE 'Rented' END "
            "WHERE release_date IS NULL OR status IS NULL"
        )
        count = db.execute("SELECT COUNT(*) AS count FROM books").fetchone()["count"]
        if count == 0:
            db.executemany(
                """INSERT INTO books(title, author, isbn, year, category, available,
                   release_date, status) VALUES (?, ?, ?, ?, ?, 1, ?, 'Available')""",
                [
                    ("The Pragmatic Programmer", "David Thomas", "9780135957059", 2019, "Technology", "2019-10-30"),
                    ("Pride and Prejudice", "Jane Austen", "9780141439518", 1813, "Classic", "1813-01-28"),
                    ("Project Hail Mary", "Andy Weir", "9780593135204", 2021, "Science Fiction", "2021-05-04"),
                    ("Atomic Habits", "James Clear", "9780735211292", 2018, "Self-help", "2018-10-16"),
                ],
            )

    # DATABASE 3: history database. Other legacy transaction tables are kept,
    # but the application uses only this history table.
    with connect(HISTORY_DB) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                username TEXT NOT NULL,
                book_name TEXT,
                timestamp TEXT NOT NULL
            )"""
        )


def record_history(action: str, username: str, book_name: str = "") -> None:
    with connect(HISTORY_DB) as db:
        db.execute(
            "INSERT INTO history(action_type, username, book_name, timestamp) VALUES (?, ?, ?, ?)",
            (action, username, book_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


class LibraryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Simple Library Management System")
        self.geometry("1050x650")
        self.minsize(900, 560)
        self.user: sqlite3.Row | None = None
        self.show_login()

    def clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def show_login(self) -> None:
        self.clear()
        frame = ttk.Frame(self, padding=35)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(frame, text="Library Management System", font=("Segoe UI", 22, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 25)
        )
        ttk.Label(frame, text="Username").grid(row=1, column=0, sticky="w", pady=6)
        username = ttk.Entry(frame, width=32)
        username.grid(row=1, column=1, pady=6)
        ttk.Label(frame, text="Password").grid(row=2, column=0, sticky="w", pady=6)
        password = ttk.Entry(frame, show="*", width=32)
        password.grid(row=2, column=1, pady=6)

        def login() -> None:
            with connect(AUTH_DB) as db:
                row = db.execute(
                    "SELECT id, username, role, password_hash FROM users WHERE username=?",
                    (username.get().strip(),),
                ).fetchone()
            if row and verify_password(password.get(), row["password_hash"]):
                self.user = row
                self.show_main_menu()
            else:
                messagebox.showerror("Login failed", "Invalid username or password.")

        ttk.Button(frame, text="Login", command=login).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(18, 6))
        ttk.Button(frame, text="Register as normal user", command=self.register_dialog).grid(
            row=4, column=0, columnspan=2, sticky="ew"
        )
        ttk.Label(
            frame, text="Default admin: admin / admin123\nDemo user: librarian / library123",
            foreground="#555555", justify="center",
        ).grid(row=5, column=0, columnspan=2, pady=(22, 0))
        username.focus_set()
        password.bind("<Return>", lambda _event: login())

    def register_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Register user")
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=20)
        frame.pack()
        ttk.Label(frame, text="Username").grid(row=0, column=0, sticky="w", pady=5)
        name = ttk.Entry(frame, width=28)
        name.grid(row=0, column=1, pady=5)
        ttk.Label(frame, text="Password").grid(row=1, column=0, sticky="w", pady=5)
        pwd = ttk.Entry(frame, show="*", width=28)
        pwd.grid(row=1, column=1, pady=5)

        def save() -> None:
            username = name.get().strip()
            if not username or not pwd.get():
                messagebox.showwarning("Missing data", "Username and password are required.", parent=dialog)
                return
            try:
                with connect(AUTH_DB) as db:
                    db.execute(
                        "INSERT INTO users(username, password_hash, role) VALUES (?, ?, 'User')",
                        (username, hash_password(pwd.get())),
                    )
                messagebox.showinfo("Registered", "The user account was created.", parent=dialog)
                dialog.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Registration failed", "That username is already in use.", parent=dialog)

        ttk.Button(frame, text="Create account", command=save).grid(row=2, column=0, columnspan=2, pady=(12, 0))
        name.focus_set()

    def show_main_menu(self) -> None:
        self.clear()
        top = ttk.Frame(self, padding=(20, 15))
        top.pack(fill="x")
        ttk.Label(top, text=f"Signed in as {self.user['username']} ({self.user['role']})",
                  font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Button(top, text="Log out", command=self.logout).pack(side="right")
        body = ttk.Frame(self, padding=30)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Choose a database", font=("Segoe UI", 18, "bold")).pack(pady=(35, 25))
        ttk.Button(body, text="Authentication Database\nUsers and roles", command=self.show_users).pack(fill="x", pady=7)
        ttk.Button(body, text="Book Database\nCurrent catalogue and rentals", command=self.show_books).pack(fill="x", pady=7)
        history_state = "normal" if self.user["role"] == "Admin" else "disabled"
        ttk.Button(body, text="History Database\nRead-only action history", command=self.show_history,
                   state=history_state).pack(fill="x", pady=7)
        ttk.Label(body, text="Only administrators can open the History Database.", foreground="#666666").pack(pady=18)

    def logout(self) -> None:
        self.user = None
        self.show_login()

    def page(self, title: str) -> ttk.Frame:
        self.clear()
        header = ttk.Frame(self, padding=(15, 12))
        header.pack(fill="x")
        ttk.Button(header, text="Main menu", command=self.show_main_menu).pack(side="left")
        ttk.Label(header, text=title, font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)
        content = ttk.Frame(self, padding=15)
        content.pack(fill="both", expand=True)
        return content

    def make_tree(self, parent: ttk.Frame, columns: list[tuple[str, str]]) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings")
        for key, heading in columns:
            tree.heading(key, text=heading)
            tree.column(key, width=130, anchor="w")
        tree.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def show_users(self) -> None:
        content = self.page("Authentication Database")
        tree = self.make_tree(content, [("id", "ID"), ("username", "Username"), ("role", "Role")])
        with connect(AUTH_DB) as db:
            rows = db.execute("SELECT id, username, role FROM users ORDER BY id").fetchall()
        for row in rows:
            tree.insert("", "end", values=tuple(row))
        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(10, 0))
        if self.user["role"] == "Admin":
            ttk.Button(buttons, text="Add user", command=self.user_dialog).pack(side="left", padx=3)
            ttk.Button(buttons, text="Edit selected", command=lambda: self.user_dialog(tree)).pack(side="left", padx=3)
            ttk.Button(buttons, text="Delete selected", command=lambda: self.delete_user(tree)).pack(side="left", padx=3)
        else:
            ttk.Label(buttons, text="Only administrators can modify user accounts.", foreground="#666666").pack(side="left")

    def user_dialog(self, tree: ttk.Treeview | None = None) -> None:
        selected = tree.selection()[0] if tree and tree.selection() else None
        values = tree.item(selected, "values") if selected else ()
        dialog = tk.Toplevel(self)
        dialog.title("Edit user" if selected else "Add user")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack()
        ttk.Label(frame, text="Username").grid(row=0, column=0, sticky="w", pady=5)
        name = ttk.Entry(frame, width=28)
        name.grid(row=0, column=1, pady=5)
        if values:
            name.insert(0, values[1])
        ttk.Label(frame, text="Password (leave blank to keep)").grid(row=1, column=0, sticky="w", pady=5)
        pwd = ttk.Entry(frame, show="*", width=28)
        pwd.grid(row=1, column=1, pady=5)
        role = ttk.Combobox(frame, values=("User", "Admin"), state="readonly", width=25)
        role.set(values[2] if values else "User")
        ttk.Label(frame, text="Role").grid(row=2, column=0, sticky="w", pady=5)
        role.grid(row=2, column=1, pady=5)

        def save() -> None:
            username = name.get().strip()
            if not username:
                messagebox.showwarning("Missing data", "Username is required.", parent=dialog)
                return
            try:
                with connect(AUTH_DB) as db:
                    if selected:
                        user_id = int(values[0])
                        if user_id == self.user["id"] and role.get() != "Admin":
                            messagebox.showwarning("Not allowed", "You cannot remove your own admin role.", parent=dialog)
                            return
                        if pwd.get():
                            db.execute("UPDATE users SET username=?, password_hash=?, role=? WHERE id=?",
                                       (username, hash_password(pwd.get()), role.get(), user_id))
                        else:
                            db.execute("UPDATE users SET username=?, role=? WHERE id=?", (username, role.get(), user_id))
                    else:
                        db.execute("INSERT INTO users(username, password_hash, role) VALUES (?, ?, ?)",
                                   (username, hash_password(pwd.get()), role.get()))
                dialog.destroy()
                self.show_users()
            except sqlite3.IntegrityError:
                messagebox.showerror("Save failed", "Username is already in use.", parent=dialog)

        ttk.Button(frame, text="Save", command=save).grid(row=3, column=0, columnspan=2, pady=(12, 0))

    def delete_user(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select a user", "Select a user first.")
            return
        user_id, username, role = tree.item(selected[0], "values")
        if int(user_id) == self.user["id"] or username == "admin":
            messagebox.showwarning("Not allowed", "The signed-in account and default admin cannot be deleted.")
            return
        if messagebox.askyesno("Delete user", f"Delete {username}?"):
            with connect(AUTH_DB) as db:
                db.execute("DELETE FROM users WHERE id=?", (user_id,))
            self.show_users()

    def show_books(self) -> None:
        content = self.page("Book Database")
        tree = self.make_tree(content, [("id", "ID"), ("title", "Book name"), ("author", "Author"),
                                        ("release", "Release date"), ("status", "Status"), ("rented", "Rented by")])
        with connect(BOOK_DB) as db:
            rows = db.execute("SELECT id, title, author, COALESCE(release_date, year), status, COALESCE(rented_by, '') FROM books ORDER BY id").fetchall()
        for row in rows:
            tree.insert("", "end", values=tuple(row))
        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(10, 0))
        if self.user["role"] == "Admin":
            ttk.Button(buttons, text="Add book", command=self.book_dialog).pack(side="left", padx=3)
            ttk.Button(buttons, text="Edit selected", command=lambda: self.book_dialog(tree)).pack(side="left", padx=3)
            ttk.Button(buttons, text="Delete selected", command=lambda: self.delete_book(tree)).pack(side="left", padx=3)
        ttk.Button(buttons, text="Rent selected", command=lambda: self.rent_book(tree)).pack(side="left", padx=3)
        ttk.Button(buttons, text="Return selected", command=lambda: self.return_book(tree)).pack(side="left", padx=3)
        ttk.Label(buttons, text="Admin" if self.user["role"] == "Admin" else "User view", foreground="#666666").pack(side="right")

    def book_dialog(self, tree: ttk.Treeview | None = None) -> None:
        selected = tree.selection()[0] if tree and tree.selection() else None
        values = tree.item(selected, "values") if selected else ()
        dialog = tk.Toplevel(self)
        dialog.title("Edit book" if selected else "Add book")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack()
        entries: dict[str, ttk.Entry] = {}
        labels = ["Book name", "Author", "ISBN", "Release date", "Category"]
        old = [values[1], values[2], "", values[3], "General"] if values else ["", "", "", "", ""]
        with connect(BOOK_DB) as db:
            if selected:
                row = db.execute("SELECT isbn, category FROM books WHERE id=?", (values[0],)).fetchone()
                old[2], old[4] = row["isbn"], row["category"]
        for index, label in enumerate(labels):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky="w", pady=4)
            entry = ttk.Entry(frame, width=30)
            entry.insert(0, old[index])
            entry.grid(row=index, column=1, pady=4)
            entries[label] = entry

        def save() -> None:
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not all(data.values()):
                messagebox.showwarning("Missing data", "Complete every field.", parent=dialog)
                return
            try:
                with connect(BOOK_DB) as db:
                    if selected:
                        db.execute("""UPDATE books SET title=?, author=?, isbn=?, release_date=?,
                                      year=?, category=? WHERE id=?""",
                                   (data["Book name"], data["Author"], data["ISBN"], data["Release date"],
                                    int(data["Release date"][:4]), data["Category"], values[0]))
                        action = None
                    else:
                        db.execute("""INSERT INTO books(title, author, isbn, year, category, release_date,
                                      status) VALUES (?, ?, ?, ?, ?, ?, 'Available')""",
                                   (data["Book name"], data["Author"], data["ISBN"], int(data["Release date"][:4]),
                                    data["Category"], data["Release date"]))
                        action = "BOOK_ADDED"
                if action:
                    record_history(action, self.user["username"], data["Book name"])
                dialog.destroy()
                self.show_books()
            except (sqlite3.IntegrityError, ValueError):
                messagebox.showerror("Save failed", "ISBN must be unique and release date must start with a year.", parent=dialog)

        ttk.Button(frame, text="Save", command=save).grid(row=len(labels), column=0, columnspan=2, pady=(12, 0))

    def delete_book(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select a book", "Select a book first.")
            return
        values = tree.item(selected[0], "values")
        if values[4] == "Rented":
            messagebox.showwarning("Cannot delete", "Return the book before deleting it.")
            return
        if messagebox.askyesno("Delete book", f"Delete {values[1]}?"):
            with connect(BOOK_DB) as db:
                db.execute("DELETE FROM books WHERE id=?", (values[0],))
            record_history("BOOK_DELETED", self.user["username"], values[1])
            self.show_books()

    def rent_book(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select a book", "Select a book first.")
            return
        values = tree.item(selected[0], "values")
        if values[4] != "Available":
            messagebox.showwarning("Unavailable", "That book is already rented.")
            return
        with connect(BOOK_DB) as db:
            db.execute("UPDATE books SET status='Rented', available=0, rented_by=? WHERE id=?",
                       (self.user["username"], values[0]))
        record_history("BOOK_RENTED", self.user["username"], values[1])
        self.show_books()

    def return_book(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select a book", "Select a book first.")
            return
        values = tree.item(selected[0], "values")
        if values[4] != "Rented" or values[5] != self.user["username"]:
            messagebox.showwarning("Cannot return", "You can return only a book rented by your account.")
            return
        with connect(BOOK_DB) as db:
            db.execute("UPDATE books SET status='Available', available=1, rented_by=NULL WHERE id=?", (values[0],))
        record_history("BOOK_RETURNED", self.user["username"], values[1])
        self.show_books()

    def show_history(self) -> None:
        if self.user["role"] != "Admin":
            messagebox.showerror("Access denied", "Only administrators may access history.")
            return
        content = self.page("History Database (read-only)")
        tree = self.make_tree(content, [("id", "ID"), ("action", "Action type"), ("user", "Username"),
                                        ("book", "Book name"), ("time", "Timestamp")])
        with connect(HISTORY_DB) as db:
            rows = db.execute("SELECT id, action_type, username, COALESCE(book_name, ''), timestamp FROM history ORDER BY id DESC").fetchall()
        for row in rows:
            tree.insert("", "end", values=tuple(row))
        ttk.Label(content, text="History records are automatically created for book actions.", foreground="#666666").pack(pady=10)


if __name__ == "__main__":
    initialize_databases()
    LibraryApp().mainloop()
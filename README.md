# Simple Library Management System

A small school-assignment application built with Python, Tkinter, and SQLite.
It demonstrates reading and modifying **three separate database files** through
a graphical user interface.

## Databases

The `data` folder contains:

1. `authentication.db` - user accounts, password hashes, and roles.
2. `catalog.db` - the current book catalogue, availability, and renter.
3. `transactions.db` - the history database. The `history` table records
   important actions and timestamps. The file name is retained from the
   supplied starter project.

The application creates or migrates these databases automatically on startup.
The standalone SQL reference is in [`database_schema.sql`](database_schema.sql).

## Running

Python 3.10 or newer is recommended. Tkinter and SQLite are included with
standard Python installations.

```text
python app.py
```

Run the command from this folder. No package installation is required.

## Login accounts

The first startup creates:

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `admin123` | Admin |
| `librarian` | `library123` | User |

Normal users can also register from the login window. Passwords are stored as
salted PBKDF2-SHA256 hashes for a safer demonstration; this project is not
intended to be production authentication software.

## Application workflow

1. Log in and choose a database from the main menu.
2. The Authentication Database screen lets administrators add, edit, delete,
   and view users. The default admin account cannot be deleted.
3. The Book Database screen displays all books. Administrators can add, edit,
   and delete books. Users can rent available books and return books rented by
   their own account.
4. The History Database is read-only and administrator-only. Adding/deleting a
   book and renting/returning a book automatically creates a history row.

Existing starter records are preserved when the app migrates `catalog.db`.
The old transaction tables in `transactions.db` are left intact, while the
application uses the new `history` table.
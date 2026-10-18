-- Reference schema for the three independent SQLite database files.
-- The Python application also creates/migrates these schemas automatically.

-- DATABASE 1: data/authentication.db
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Admin', 'User'))
);

-- DATABASE 2: data/catalog.db
CREATE TABLE IF NOT EXISTS books (
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
);

-- DATABASE 3: data/transactions.db
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    username TEXT NOT NULL,
    book_name TEXT,
    timestamp TEXT NOT NULL
);

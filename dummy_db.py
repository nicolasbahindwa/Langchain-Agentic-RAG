import sqlite3
import random
import datetime

# Connect to SQLite (in-memory for demo; use 'dummy.db' for a file)
conn = sqlite3.connect("dummy.db")
cursor = conn.cursor()

# Drop tables if exist (for reruns)
cursor.executescript("""
DROP TABLE IF EXISTS Products;
DROP TABLE IF EXISTS Prices;
DROP TABLE IF EXISTS Inventory;
DROP TABLE IF EXISTS Sales;
""")

# Create tables
cursor.execute("""
CREATE TABLE Products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL
);
""")

cursor.execute("""
CREATE TABLE Prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    price REAL NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    FOREIGN KEY(product_id) REFERENCES Products(product_id)
);
""")

cursor.execute("""
CREATE TABLE Inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity INTEGER NOT NULL,
    last_updated DATE NOT NULL,
    FOREIGN KEY(product_id) REFERENCES Products(product_id)
);
""")

cursor.execute("""
CREATE TABLE Sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity INTEGER NOT NULL,
    sale_date DATE NOT NULL,
    FOREIGN KEY(product_id) REFERENCES Products(product_id)
);
""")

# Sample categories and product base names
categories = ["Electronics", "Books", "Clothing", "Toys", "Food", "Home", "Sports", "Beauty"]
product_basenames = [
    "Laptop", "Smartphone", "Headphones", "Tablet", "Camera", "Monitor", "Keyboard", "Mouse",
    "Novel", "Cookbook", "T-Shirt", "Jeans", "Jacket", "Sneakers", "Action Figure", "Board Game",
    "Chocolate Bar", "Coffee", "Blender", "Shampoo"
]

# Insert 20 Products
for name in product_basenames:
    category = random.choice(categories)
    cursor.execute("INSERT INTO Products (name, category) VALUES (?, ?)", (name, category))

# Insert Prices (current price for each product)
product_ids = [row[0] for row in cursor.execute("SELECT product_id FROM Products").fetchall()]
for pid in product_ids:
    price = round(random.uniform(5, 1000), 2)
    start_date = datetime.date(2024, 1, 1)
    cursor.execute("INSERT INTO Prices (product_id, price, start_date) VALUES (?, ?, ?)", (pid, price, start_date))

# Insert Inventory
for pid in product_ids:
    quantity = random.randint(10, 500)
    last_updated = datetime.date.today()
    cursor.execute("INSERT INTO Inventory (product_id, quantity, last_updated) VALUES (?, ?, ?)", (pid, quantity, last_updated))

# Insert Sales (random historical sales)
for _ in range(200):  # 200 random sales for more data
    pid = random.choice(product_ids)
    quantity = random.randint(1, 10)
    sale_date = datetime.date(2024, 1, 1) + datetime.timedelta(days=random.randint(0, 365))
    cursor.execute("INSERT INTO Sales (product_id, quantity, sale_date) VALUES (?, ?, ?)", (pid, quantity, sale_date))

# Commit changes
conn.commit()

print("Dummy SQLite database created with 20 Products, Prices, Inventory, and Sales tables!")

# Optional: preview some data
print("\nSample Products:")
for row in cursor.execute("SELECT * FROM Products LIMIT 5").fetchall():
    print(row)

print("\nSample Sales:")
for row in cursor.execute("SELECT * FROM Sales LIMIT 5").fetchall():
    print(row)

# Close connection
conn.close()

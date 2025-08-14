import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG
import bcrypt

import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG
import bcrypt
import time
import sys

_connection = None

def get_db_connection():
    """Gets a new database connection."""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"\nError connecting to MySQL: {e}")
        print("\nTroubleshooting tips:")
        print(f"1. Check if MySQL server is running on {DB_CONFIG['host']}")
        print(f"2. Verify the username '{DB_CONFIG['user']}' and password in config.py")
        sys.exit(1)

def initialize_database():
    """Creates tables and populates them if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    print("Database connected. Initializing tables...")


    db_name = DB_CONFIG['database']

    tables = {
        'users': """
            CREATE TABLE users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE
            )
        """,
        'item_codes': """
            CREATE TABLE item_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo VARCHAR(50) UNIQUE NOT NULL,
                tipo VARCHAR(50),
                descripcion TEXT
            )
        """,
        'inventory_items': """
            CREATE TABLE inventory_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                fecha_ingreso DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                sn VARCHAR(255) NOT NULL UNIQUE,
                item_code_id INT NOT NULL,
                tipo_servicio VARCHAR(50) NOT NULL,
                estado_actual VARCHAR(50) NOT NULL DEFAULT 'En Bodega',
                asignado_a_id INT NULL,
                terminal_comercio VARCHAR(255) NULL,
                FOREIGN KEY (item_code_id) REFERENCES item_codes(id),
                FOREIGN KEY (asignado_a_id) REFERENCES users(id)
            )
        """
    }

    for table_name, create_stmt in tables.items():
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (db_name, table_name))
        if cursor.fetchone()[0] == 0:
            print(f"Creating table '{table_name}'...")
            cursor.execute(create_stmt)
        else:
            print(f"Table '{table_name}' already exists.")

    # Populate users with a default admin if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if cursor.fetchone() is None:
        hashed_password = bcrypt.hashpw(b'admin', bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, is_admin) VALUES (%s, %s, %s, %s)",
            ('admin', hashed_password.decode('utf-8'), 'Admin User', True)
        )
        print("Default admin user created.")
    else:
        print("Admin user already exists.")

    # Pre-populate item_codes if the table is empty
    cursor.execute("SELECT COUNT(*) FROM item_codes")
    if cursor.fetchone()[0] == 0:
        print("Populating item_codes table...")
        item_codes_to_add = [
            ('POS', 'Punto de Venta', 'Terminal para transacciones comerciales'),
            ('PINPAD', 'Pinpad', 'Dispositivo para ingreso de PIN'),
            ('SIM', 'Tarjeta SIM', 'Tarjeta para conectividad celular')
        ]
        cursor.executemany("INSERT INTO item_codes (codigo, tipo, descripcion) VALUES (%s, %s, %s)", item_codes_to_add)
        print(f"{cursor.rowcount} item codes inserted.")

    # Commit all changes and close the connection
    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialization complete.")

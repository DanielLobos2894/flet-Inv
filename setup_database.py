import mysql.connector
from mysql.connector import Error

def setup_database():
    try:
        # First, connect as root to create the database and user if they don't exist
        print("Connecting to MySQL server...")
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='root'
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create database if it doesn't exist
            cursor.execute("CREATE DATABASE IF NOT EXISTS flet_login_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print("Database 'flet_login_app' is ready")
            
            # Create user if it doesn't exist
            try:
                cursor.execute("CREATE USER IF NOT EXISTS 'flet_user'@'localhost' IDENTIFIED BY 'flet_password'")
                print("User 'flet_user' created")
            except Exception as e:
                print(f"Note: Could not create user (might already exist): {e}")
            
            # Grant privileges
            cursor.execute("GRANT ALL PRIVILEGES ON flet_login_app.* TO 'flet_user'@'localhost'")
            cursor.execute("FLUSH PRIVILEGES")
            print("Privileges granted")
            
            # Switch to the database
            cursor.execute("USE flet_login_app")
            
            # Create users table if it doesn't exist
            create_table = """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_table)
            print("Users table is ready")
            
            # Close cursor and connection
            cursor.close()
            connection.close()
            
            # Test the new user connection
            test_connection()
            
    except Error as e:
        print(f"Error: {e}")
        print("\nTroubleshooting steps:")
        print("1. Make sure MySQL server is running")
        print("2. Verify the root password (we're using 'root' as password)")
        print("3. Try connecting with MySQL Workbench or MySQL Shell to verify credentials")

def test_connection():
    try:
        print("\nTesting connection with flet_user...")
        connection = mysql.connector.connect(
            host='localhost',
            user='flet_user',
            password='flet_password',
            database='flet_login_app'
        )
        
        if connection.is_connected():
            print("✅ Successfully connected with flet_user!")
            print("\nDatabase setup is complete! You can now run the application.")
            print("Run: python main.py")
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ Connection test failed: {e}")
        print("\nTrying to continue with root user...")
        return False

if __name__ == "__main__":
    setup_database()

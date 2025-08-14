import mysql.connector
from mysql.connector import Error

def test_connection():
    print("Testing MySQL connection...")
    
    # Try with different combinations of credentials
    configs = [
        {'user': 'root', 'password': ''},  # No password
        {'user': 'root', 'password': 'root'},  # Common default
        {'user': 'root', 'password': 'password'},  # Another common default
    ]
    
    for config in configs:
        try:
            print(f"\nTrying with user: {config['user']}")
            connection = mysql.connector.connect(
                host='localhost',
                **config
            )
            
            if connection.is_connected():
                db_info = connection.get_server_info()
                print(f"Successfully connected to MySQL Server version {db_info}")
                
                # Try to create the database if it doesn't exist
                cursor = connection.cursor()
                cursor.execute("CREATE DATABASE IF NOT EXISTS flet_login_app")
                print("Database 'flet_login_app' is ready")
                
                # Create a dedicated user
                try:
                    cursor.execute("CREATE USER IF NOT EXISTS 'flet_user'@'localhost' IDENTIFIED BY 'flet_password'")
                    cursor.execute("GRANT ALL PRIVILEGES ON flet_login_app.* TO 'flet_user'@'localhost'")
                    cursor.execute("FLUSH PRIVILEGES")
                    print("Created user 'flet_user' with necessary permissions")
                except Exception as e:
                    print(f"Note: Could not create user (might already exist): {e}")
                
                cursor.close()
                connection.close()
                return True
                
        except Error as e:
            print(f"Connection failed: {e}")
    
    print("\nCould not connect to MySQL with any of the tested credentials.")
    print("\nPlease try these steps:")
    print("1. Make sure MySQL server is running")
    print("2. Try connecting with MySQL Workbench or MySQL Shell to find your credentials")
    print("3. If you've forgotten the root password, you may need to reset it")
    return False

if __name__ == "__main__":
    test_connection()

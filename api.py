from __future__ import annotations
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import bcrypt
import mysql.connector
from fastapi.security import OAuth2PasswordBearer
from database import initialize_database, get_db_connection
from mysql.connector import Error

app = FastAPI()

@app.on_event("startup")
def on_startup():
    initialize_database()

# Dependency to get the database session
def get_db():
    db = get_db_connection()
    try:
        yield db
    finally:
        db.close()

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    is_admin: bool = False

class UserAuth(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    is_admin: bool

class ItemCode(BaseModel):
    id: int
    codigo: str
    tipo: str
    descripcion: str

class InventoryItemBase(BaseModel):
    sn: str
    item_code_id: int
    tipo_servicio: str
    estado_actual: str = 'En Bodega'
    asignado_a_id: Optional[int] = None
    terminal_comercio: Optional[str] = None

class InventoryItemCreate(InventoryItemBase):
    sn: str
    item_code_id: int
    tipo_servicio: str = "implementacion"
    estado_actual: str = "En Bodega"
    asignado_a_id: Optional[int] = None
    terminal_comercio: Optional[str] = None

class InventoryItemUpdate(InventoryItemBase):
    pass

class ItemStatusUpdate(BaseModel):
    estado_actual: str
    terminal_comercio: Optional[str] = None

class InventoryItemOut(InventoryItemBase):
    id: int
    fecha_ingreso: datetime
    item_code: ItemCode
    asignado_a: Optional[UserOut] = None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user_from_token(token: str = Depends(oauth2_scheme), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (token,))
    user = cursor.fetchone()
    cursor.close()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_admin_user(current_user: dict = Depends(get_current_user_from_token)):
    if not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Operation not permitted")
    return current_user

@app.post("/auth")
def authenticate_user(data: UserAuth, db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    # This is insecure and for demo purposes. In production, you'd compare password hashes.
    cursor.execute(
        "SELECT id, username, full_name, is_admin FROM users WHERE username = %s",
        (data.username,)
    )
    user = cursor.fetchone()
    cursor.close()

    if not user:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    # A placeholder for password verification
    # In a real app: if not bcrypt.checkpw(data.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
    # For this demo, we are not checking password hash. The simplified token (username) is the auth.
    # This endpoint is just to simulate a login flow.
    # We add the access_token to the user dictionary to be used by the client.
    user["access_token"] = user['username']
    return user

@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, admin: dict = Depends(get_current_admin_user), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor()
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, is_admin) VALUES (%s, %s, %s, %s)",
            (user.username, hashed_password.decode('utf-8'), user.full_name, user.is_admin)
        )
        db.commit()
    except mysql.connector.Error as err:
        raise HTTPException(status_code=400, detail=f"Error creating user: {err}")
    finally:
        cursor.close()
    return {"message": "User created successfully"}

@app.get("/item-codes", response_model=List[ItemCode])
def get_item_codes(current_user: dict = Depends(get_current_user_from_token), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, codigo, tipo, descripcion FROM item_codes ORDER BY codigo")
    codes = cursor.fetchall()
    cursor.close()
    return codes

@app.get("/users/technicians", response_model=List[UserOut])
def get_technicians(admin: dict = Depends(get_current_admin_user), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, username, full_name, is_admin FROM users ORDER BY full_name")
    technicians = cursor.fetchall()
    cursor.close()
    return technicians

@app.post("/inventory", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
def create_inventory_item(item: InventoryItemCreate, current_user: dict = Depends(get_current_user_from_token), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    print(f"Creating inventory item with data: {item.dict()}")  # Log de depuración
    cursor = db.cursor(dictionary=True)
    try:
        # Verificar si ya existe un ítem con el mismo SN
        cursor.execute("SELECT id FROM inventory_items WHERE sn = %s", (item.sn,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Ya existe un ítem con el número de serie: {item.sn}")
            
        # Verificar que el item_code_id existe
        cursor.execute("SELECT id FROM item_codes WHERE id = %s", (item.item_code_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"El código de ítem {item.item_code_id} no existe")
        
        # Insertar el nuevo ítem
        cursor.execute(
            """
            INSERT INTO inventory_items 
            (sn, item_code_id, tipo_servicio, estado_actual, asignado_a_id, terminal_comercio) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (item.sn, item.item_code_id, item.tipo_servicio, item.estado_actual, item.asignado_a_id, item.terminal_comercio)
        )
        db.commit()
        item_id = cursor.lastrowid
        print(f"Item created successfully with ID: {item_id}")  # Log de depuración
        
        # Obtener el ítem recién creado
        new_item = get_inventory_item_by_id(item_id, db)
        if not new_item:
            raise HTTPException(status_code=500, detail="Error al recuperar el ítem recién creado")
            
        return new_item
        
    except mysql.connector.Error as err:
        db.rollback()
        print(f"Database error: {err}")  # Log de depuración
        raise HTTPException(status_code=400, detail=f"Error al crear el ítem: {err}")
    except HTTPException:
        # Re-lanzar las excepciones HTTP que ya manejamos
        raise
    except Exception as e:
        db.rollback()
        print(f"Unexpected error: {e}")  # Log de depuración
        raise HTTPException(status_code=500, detail=f"Error inesperado al crear el ítem: {str(e)}")
    finally:
        cursor.close()

@app.get("/inventory", response_model=List[InventoryItemOut])
def get_all_inventory_items(current_user: dict = Depends(get_current_user_from_token), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT 
            i.id, i.fecha_ingreso, i.sn, i.tipo_servicio, i.estado_actual, i.terminal_comercio,
            i.item_code_id, i.asignado_a_id,
            ic.codigo as item_code_codigo, ic.tipo as item_code_tipo, ic.descripcion as item_code_descripcion,
            u.username as user_username, u.full_name as user_full_name, u.is_admin as user_is_admin
        FROM inventory_items i
        JOIN item_codes ic ON i.item_code_id = ic.id
        LEFT JOIN users u ON i.asignado_a_id = u.id
        ORDER BY i.fecha_ingreso DESC
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    items = []
    for row in results:
        item = InventoryItemOut(
            id=row['id'],
            fecha_ingreso=row['fecha_ingreso'],
            sn=row['sn'],
            tipo_servicio=row['tipo_servicio'],
            estado_actual=row['estado_actual'],
            terminal_comercio=row['terminal_comercio'],
            item_code_id=row['item_code_id'],
            asignado_a_id=row['asignado_a_id'],
            item_code=ItemCode(
                id=row['item_code_id'],
                codigo=row['item_code_codigo'],
                tipo=row['item_code_tipo'],
                descripcion=row['item_code_descripcion']
            ),
            # Correctly handle cases where 'asignado_a_id' is None.
            # The check must be done on the existence of the key in the row.
            asignado_a=UserOut(
                id=row['asignado_a_id'],
                username=row['user_username'],
                full_name=row['user_full_name'],
                is_admin=row['user_is_admin']
            ) if row.get('asignado_a_id') else None
        )
        items.append(item)
    return items

def get_inventory_item_by_id(item_id: int, db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    try:
        # Primero, obtener los datos básicos del ítem
        query = """
            SELECT * FROM inventory_items WHERE id = %s
        """
        cursor.execute(query, (item_id,))
        item_row = cursor.fetchone()
        
        if not item_row:
            return None
            
        # Obtener la información del código de ítem
        cursor.execute("""
            SELECT id, codigo, tipo, descripcion 
            FROM item_codes 
            WHERE id = %s
        """, (item_row['item_code_id'],))
        item_code_row = cursor.fetchone()
        
        if not item_code_row:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró el código de ítem con ID {item_row['item_code_id']}"
            )
            
        # Construir el objeto ItemCode
        item_code = ItemCode(
            id=item_code_row['id'],
            codigo=item_code_row['codigo'],
            tipo=item_code_row['tipo'],
            descripcion=item_code_row['descripcion']
        )
        
        # Obtener información del usuario asignado si existe
        asignado_a = None
        if item_row.get('asignado_a_id'):
            cursor.execute("""
                SELECT id, username, full_name, is_admin 
                FROM users 
                WHERE id = %s
            """, (item_row['asignado_a_id'],))
            
            user_row = cursor.fetchone()
            if user_row:
                asignado_a = UserOut(
                    id=user_row['id'],
                    username=user_row['username'],
                    full_name=user_row['full_name'],
                    is_admin=bool(user_row['is_admin'])
                )
        
        # Construir y retornar el objeto InventoryItemOut
        return InventoryItemOut(
            id=item_row['id'],
            fecha_ingreso=item_row['fecha_ingreso'],
            sn=item_row['sn'],
            item_code_id=item_row['item_code_id'],
            tipo_servicio=item_row['tipo_servicio'],
            estado_actual=item_row['estado_actual'],
            asignado_a_id=item_row.get('asignado_a_id'),
            terminal_comercio=item_row.get('terminal_comercio'),
            item_code=item_code,
            asignado_a=asignado_a
        )
        
    except Exception as e:
        print(f"Error en get_inventory_item_by_id: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al recuperar el ítem: {str(e)}"
        )
    finally:
        cursor.close()

@app.put("/inventory/{item_id}", response_model=InventoryItemOut)
def update_inventory_item(item_id: int, item: InventoryItemUpdate, current_user: dict = Depends(get_current_user_from_token), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    try:
        # Verificar si el ítem existe y el usuario tiene permiso para editarlo
        cursor.execute(
            "SELECT * FROM inventory_items WHERE id = %s",
            (item_id,)
        )
        existing_item = cursor.fetchone()
        
        if not existing_item:
            raise HTTPException(status_code=404, detail="Item no encontrado")
            
        # Solo el admin o el usuario asignado pueden editar
        if not current_user.get('is_admin') and existing_item.get('asignado_a_id') != current_user.get('id'):
            raise HTTPException(status_code=403, detail="No tiene permiso para editar este ítem")
        
        # Si el usuario no es admin, solo puede modificar ciertos campos
        update_fields = []
        update_values = []
        
        # Campos que todos pueden modificar
        update_fields.append("estado_actual = %s")
        update_values.append(item.estado_actual)
        
        # Solo admin puede modificar estos campos
        if current_user.get('is_admin'):
            update_fields.extend([
                "sn = %s", "item_code_id = %s", "tipo_servicio = %s",
                "asignado_a_id = %s", "terminal_comercio = %s"
            ])
            update_values.extend([
                item.sn, item.item_code_id, item.tipo_servicio,
                item.asignado_a_id, item.terminal_comercio
            ])
        
        # Construir y ejecutar la consulta dinámica
        update_query = """
            UPDATE inventory_items 
            SET """ + ", ".join(update_fields) + """
            WHERE id = %s
        """
        update_values.append(item_id)
        
        cursor.execute(update_query, update_values)
        db.commit()
    except mysql.connector.Error as err:
        raise HTTPException(status_code=400, detail=f"Error updating item: {err}")
    finally:
        cursor.close()
    return get_inventory_item_by_id(item_id, db)

@app.delete("/inventory/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(item_id: int, current_user: dict = Depends(get_current_user_from_token), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    try:
        # Verificar si el ítem existe
        cursor.execute("SELECT * FROM inventory_items WHERE id = %s", (item_id,))
        item = cursor.fetchone()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item no encontrado")
            
        # Solo el admin puede eliminar ítems
        if not current_user.get('is_admin'):
            raise HTTPException(status_code=403, detail="Solo los administradores pueden eliminar ítems")
            
        cursor.execute("DELETE FROM inventory_items WHERE id = %s", (item_id,))
        db.commit()
    except mysql.connector.Error as err:
        raise HTTPException(status_code=400, detail=f"Error deleting item: {err}")
    finally:
        cursor.close()
    return

@app.get("/inventory/my-items", response_model=List[InventoryItemOut])
def get_my_inventory_items(current_user: dict = Depends(get_current_user_from_token), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    user_id = current_user['id']
    query = """
        SELECT 
            i.id, i.fecha_ingreso, i.sn, i.tipo_servicio, i.estado_actual, i.terminal_comercio,
            ic.id as item_code_id, ic.codigo as item_code_codigo, ic.tipo as item_code_tipo, ic.descripcion as item_code_descripcion,
            u.id as user_id, u.username as user_username, u.full_name as user_full_name, u.is_admin as user_is_admin
        FROM inventory_items i
        JOIN item_codes ic ON i.item_code_id = ic.id
        LEFT JOIN users u ON i.asignado_a_id = u.id
        WHERE i.asignado_a_id = %s
        ORDER BY i.fecha_ingreso DESC
    """
    cursor.execute(query, (user_id,))
    results = cursor.fetchall()
    cursor.close()

    items = []
    for row in results:
        item = InventoryItemOut(
            id=row['id'],
            fecha_ingreso=row['fecha_ingreso'],
            sn=row['sn'],
            tipo_servicio=row['tipo_servicio'],
            estado_actual=row['estado_actual'],
            terminal_comercio=row['terminal_comercio'],
            item_code_id=row['item_code_id'],
            asignado_a_id=row['user_id'],
            item_code=ItemCode(
                id=row['item_code_id'],
                codigo=row['item_code_codigo'],
                tipo=row['item_code_tipo'],
                descripcion=row['item_code_descripcion']
            ),
            asignado_a=UserOut(
                id=row['user_id'],
                username=row['user_username'],
                full_name=row['user_full_name'],
                is_admin=row['user_is_admin']
            ) if row['user_id'] else None
        )
        items.append(item)
    return items

@app.patch("/inventory/{item_id}/status", response_model=InventoryItemOut)
def update_item_status(item_id: int, status_update: ItemStatusUpdate, current_user: dict = Depends(get_current_user_from_token), db: mysql.connector.connection.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    user_id = current_user['id']

    # Primero, verificar que el item pertenece al usuario
    cursor.execute("SELECT id FROM inventory_items WHERE id = %s AND asignado_a_id = %s", (item_id, user_id))
    if cursor.fetchone() is None:
        cursor.close()
        raise HTTPException(status_code=403, detail="Not authorized to update this item")

    # Si pertenece, actualizar el estado
    try:
        cursor.execute(
            "UPDATE inventory_items SET estado_actual = %s, terminal_comercio = %s WHERE id = %s",
            (status_update.estado_actual, status_update.terminal_comercio, item_id)
        )
        db.commit()
    except mysql.connector.Error as err:
        raise HTTPException(status_code=400, detail=f"Error updating status: {err}")
    finally:
        cursor.close()
    
    return get_inventory_item_by_id(item_id, db)

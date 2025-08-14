# Aplicación de Login con Flet y MySQL

Aplicación móvil básica con sistema de autenticación y gestión de usuarios.

## Características

- Inicio de sesión de usuarios
- Usuario administrador por defecto (MTOadmin/admin)
- Creación de nuevos usuarios (solo administradores)
- Interfaz amigable y responsiva
- Almacenamiento de usuarios en memoria

## Requisitos

- Python 3.7 o superior
- pip (gestor de paquetes de Python)

## Instalación

1. Clona este repositorio o descarga los archivos
2. Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Uso

1. Ejecuta la aplicación:

```bash
python main.py
```

2. Inicia sesión con las credenciales por defecto:
   - Usuario: MTOadmin
   - Contraseña: admin

3. Una vez autenticado, podrás:
   - Ver tu nombre de bienvenida
   - Si eres administrador, crear nuevos usuarios
   - Cerrar sesión

## Credenciales por defecto

- **Usuario administrador:**
  - Usuario: MTOadmin
  - Contraseña: admin

## Notas

- Los usuarios se almacenan en memoria, por lo que se perderán al cerrar la aplicación.
- Solo los usuarios con permisos de administrador pueden crear nuevos usuarios.

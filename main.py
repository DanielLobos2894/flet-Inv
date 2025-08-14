import flet as ft
import httpx
from typing import Optional
import time
import threading

# La URL base de la API. Se usa 127.0.0.1 (localhost) para desarrollo local.
API_BASE_URL = "http://127.0.0.1:8000"


def main(page: ft.Page):
    page.title = "Sistema de Login"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 400
    page.window_height = 700
    page.window_resizable = False

    def show_message(message, color="red"):
        for msg in page.controls:
            if isinstance(msg, ft.SnackBar):
                page.controls.remove(msg)
        page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def httpx_request(method: str, endpoint: str, token: Optional[str] = None, json_data: Optional[dict] = None):
        # Obtener el token de la sesión si no se proporciona
        if token is None:
            token = page.client_storage.get("auth_token")
            
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Log de depuración
        print(f"\n=== Solicitud HTTP ===")
        print(f"Método: {method.upper()}")
        print(f"URL: {API_BASE_URL}{endpoint}")
        print(f"Headers: {headers}")
        if json_data:
            print(f"Datos: {json_data}")

        try:
            with httpx.Client() as client:
                if method.lower() == 'get':
                    response = client.get(f"{API_BASE_URL}{endpoint}", headers=headers, timeout=30.0)
                elif method.lower() == 'post':
                    response = client.post(f"{API_BASE_URL}{endpoint}", headers=headers, json=json_data, timeout=30.0)
                elif method.lower() == 'put':
                    response = client.put(f"{API_BASE_URL}{endpoint}", headers=headers, json=json_data, timeout=30.0)
                elif method.lower() == 'patch':
                    response = client.patch(f"{API_BASE_URL}{endpoint}", headers=headers, json=json_data, timeout=30.0)
                elif method.lower() == 'delete':
                    response = client.delete(f"{API_BASE_URL}{endpoint}", headers=headers, timeout=30.0)
                else:
                    error_msg = f"Método HTTP no válido: {method}"
                    print(f"Error: {error_msg}")
                    show_message(error_msg)
                    return None

                # Log de la respuesta
                print(f"\n=== Respuesta HTTP ===")
                print(f"Status: {response.status_code}")
                print(f"Headers: {dict(response.headers)}")
                try:
                    print(f"Body: {response.json()}")
                except:
                    print(f"Body: {response.text}")

                response.raise_for_status()  # Lanza una excepción para respuestas 4xx/5xx

                if response.status_code == 204:  # Éxito sin contenido
                    return response
                
                return response.json()
                
        except httpx.HTTPStatusError as e:
            print(f"\n=== Error HTTP {e.response.status_code} ===")
            try:
                error_detail = e.response.json().get("detail", e.response.text)
                print(f"Detalles: {error_detail}")
                show_message(f"Error {e.response.status_code}: {error_detail}")
            except:
                print(f"Error al procesar la respuesta: {e}")
                show_message(f"Error {e.response.status_code}: {e.response.text}")
            return None
            
        except httpx.RequestError as e:
            error_msg = f"Error de conexión: No se pudo conectar a la API en {API_BASE_URL}"
            print(f"\n=== Error de conexión ===\n{error_msg}\nDetalles: {e}")
            show_message(error_msg)
            return None
            
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            print(f"\n=== Error inesperado ===\n{error_msg}")
            show_message(error_msg)
            return None

    # --- VISTAS / PANELES ---
    def get_login_view():
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Iniciar Sesión", size=30, weight="bold"),
                    username_field,
                    password_field,
                    ft.ElevatedButton("Ingresar", on_click=login_clicked, width=200),
                    error_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )

    def get_welcome_view(user):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(f"Bienvenido, {user.get('full_name')}!", size=30, weight="bold"),
                    ft.Text("Selecciona una opción del menú lateral para comenzar.")
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        )

    # --- Lógica y UI de Inventario ---

    # Variables para almacenar el estado de la UI de inventario
    inventory_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("S/N")),
            ft.DataColumn(ft.Text("Código")),
            ft.DataColumn(ft.Text("Descripción")),
            ft.DataColumn(ft.Text("Estado")),
            ft.DataColumn(ft.Text("Asignado a")),
            ft.DataColumn(ft.Text("Acciones")),
        ],
        rows=[]
    )
    # Almacenaremos los datos completos para no tener que pedirlos de nuevo
    all_inventory_items = []
    all_item_codes = []
    all_technicians = []
    my_assigned_items = []
    user_items_list = ft.ListView(expand=True, spacing=10)
    
    # Inicializar el botón de añadir en el ámbito de la función main
    add_button = None
    
    # Crear indicador de carga
    loading_indicator = ft.ProgressBar(
        visible=False,
        width=400,
        color="blue"
    )

    def get_inventory_view():
        user = page.client_storage.get("current_user")
        if not user:
            return ft.Text("Error: No se pudo identificar al usuario.")
            
        is_admin = user.get("is_admin") == 1
        
        # Cargar datos apropiados según el rol
        if is_admin:
            load_admin_data()
        else:
            load_user_data()
        
        # Crear el título
        title = ft.Text("Inventario General" if is_admin else "Mis Artículos Asignados", 
                       size=24, weight="bold")
        
        # Obtener códigos existentes de la base de datos
        token = page.client_storage.get("auth_token")
        item_codes = httpx_request("get", "/item-codes", token=token) or []
        
        # Crear opciones para el menú desplegable
        code_options = [
            ft.dropdown.Option(
                text=code['codigo'],
                key=str(code['id']),
                data=code
            ) for code in item_codes
        ]
        
        # Crear campos del formulario de ingreso rápido (solo para admin)
        serial_number_field = ft.TextField(
            label="S/N",
            width=200,
            autofocus=True
        )
        
        # Menú desplegable para seleccionar el código
        code_dropdown = ft.Dropdown(
            label="Código",
            width=250,
            options=code_options,
            autofocus=False,
            hint_text="Seleccione un código",
            text_size=14,
            border_radius=8
        )
        
        # Campo para agregar un nuevo código (opcional)
        new_code_field = ft.TextField(
            label="O ingrese un código nuevo",
            width=200,
            visible=False
        )
        
        # Función para alternar entre seleccionar y agregar código
        def toggle_code_input(e):
            if code_dropdown.value == "nuevo":
                new_code_field.visible = True
                code_dropdown.width = 200
            else:
                new_code_field.visible = False
                code_dropdown.width = 250
            page.update()
        
        # Agregar opción para nuevo código
        code_dropdown.options.append(ft.dropdown.Option("nuevo", text="➕ Agregar código nuevo"))
        code_dropdown.on_change = toggle_code_input
        
        description_field = ft.TextField(
            label="Descripción",
            width=400,
            multiline=True,
            min_lines=1,
            max_lines=2
        )
        
        def save_quick_item(e):
            # Mostrar indicador de carga
            loading_indicator.visible = True
            page.update()
            
            try:
                # Validar campos obligatorios
                if not serial_number_field.value or not description_field.value:
                    show_message("Por favor complete los campos obligatorios (S/N y Descripción)", color="red")
                    loading_indicator.visible = False
                    page.update()
                    return
                    
                # Obtener el token de autenticación
                token = page.client_storage.get("auth_token")
                if not token:
                    show_message("Error de autenticación. Por favor, inicie sesión nuevamente.", color="red")
                    loading_indicator.visible = False
                    page.update()
                    return
                
                # Determinar el código seleccionado o el nuevo código
                item_code = None
                selected_code = None
                
                if code_dropdown.value == "nuevo":
                    if not new_code_field.value:
                        show_message("Por favor ingrese un código nuevo", color="red")
                        loading_indicator.visible = False
                        page.update()
                        return
                    item_code = {
                        "codigo": new_code_field.value,
                        "descripcion": description_field.value
                    }
                else:
                    # Buscar el código seleccionado
                    selected_code = next((code for code in item_codes if str(code['id']) == code_dropdown.value), None)
                    if not selected_code:
                        show_message("Por favor seleccione un código válido", color="red")
                        loading_indicator.visible = False
                        page.update()
                        return
                    item_code = {
                        "codigo": selected_code['codigo'],
                        "descripcion": selected_code.get('descripcion', '')
                    }
                
                # Crear el nuevo ítem con la estructura que espera la API
                new_item = {
                    "sn": serial_number_field.value.strip(),
                    "item_code_id": int(selected_code['id']) if selected_code else None,
                    "tipo_servicio": "implementacion",  # Valor por defecto
                    "estado_actual": "En Bodega",  # Valor por defecto que coincide con la base de datos
                    "asignado_a_id": None,  # Se asignará después
                    "terminal_comercio": None  # Opcional
                }
                
                # Enviar a la API
                response = httpx_request(
                    method="post",
                    endpoint="/inventory",
                    json_data=new_item
                )
                
                if response is None:
                    show_message("Error al guardar el artículo. Intente nuevamente.", color="red")
                    return
                
                # Limpiar los campos
                serial_number_field.value = ""
                code_dropdown.value = None
                new_code_field.value = ""
                new_code_field.visible = False
                code_dropdown.width = 250
                description_field.value = ""
                
                # Mostrar mensaje de éxito
                show_message("Artículo agregado exitosamente.", color="green")
                
                # Actualizar la vista
                load_admin_data()
                
            except Exception as ex:
                print(f"Error al guardar el artículo: {str(ex)}")
                show_message(f"Error al guardar el artículo: {str(ex)}", color="red")
            finally:
                loading_indicator.visible = False
                page.update()
        
        # Crear el formulario de ingreso rápido (solo para admin)
        quick_add_form = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Agregar Artículo Rápido", weight="bold"),
                        ft.Column(
                            [
                                # Primera fila: S/N y Código
                                ft.Row(
                                    [
                                        serial_number_field,
                                        code_dropdown,
                                        new_code_field,
                                    ],
                                    spacing=10,
                                    wrap=True
                                ),
                                # Segunda fila: Descripción
                                ft.Row(
                                    [
                                        description_field,
                                        ft.ElevatedButton(
                                            "Guardar",
                                            on_click=save_quick_item,
                                            icon="save",
                                            height=50,
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=8)
                                            )
                                        )
                                    ],
                                    spacing=10,
                                    wrap=True
                                )
                            ],
                            spacing=10
                        )
                    ],
                    spacing=15
                ),
                padding=20
            ),
            elevation=3,
            margin=10
        ) if is_admin else None
        
        # Crear la vista
        view = ft.Column(controls=[])
        view.controls.append(title)
        
        # Agregar el formulario de ingreso rápido si es admin
        if is_admin and quick_add_form:
            view.controls.append(quick_add_form)
        
        # Añadir el indicador de carga
        view.controls.append(
            ft.Container(
                content=loading_indicator,
                alignment=ft.alignment.center,
                padding=10
            )
        )
            
        # Añadir la tabla o lista de items
        view.controls.append(
            ft.Container(
                content=inventory_table if is_admin else user_items_list,
                expand=True
            )
        )
        
        return view

    def load_admin_data():
        # Limpiar la tabla
        inventory_table.rows.clear()
        
        # Mostrar indicador de carga
        loading_indicator.visible = True
        page.update()
        
        # Obtener datos de la API
        token = page.client_storage.get("auth_token")
        items = httpx_request("get", "/inventory", token=token)
        
        if items is None:
            show_message("Error al cargar el inventario")
            loading_indicator.visible = False
            page.update()
            return
            
        # Llenar la tabla con los datos
        for item in items:
            # Crear acciones
            actions = []
            
            # Botón para ver detalles (temporalmente deshabilitado)
            view_button = ft.IconButton(
                icon="info_outline",
                on_click=lambda e, item_id=item['id']: print(f"Ver detalles del ítem {item_id}")
            )
            actions.append(view_button)
            
            # Botón para editar
            edit_button = ft.IconButton(
                icon="edit",
                data=item,  # Almacenar el ítem completo en el botón
                on_click=open_edit_item_dialog
            )
            actions.append(edit_button)
            
            # Botón para eliminar (solo para admin)
            delete_button = ft.IconButton(
                icon="delete",
                data=item,  # Pasar el objeto completo del ítem
                on_click=open_delete_item_dialog,
                tooltip="Eliminar artículo",
                icon_color="red"
            )
            actions.append(delete_button)
            
            # Crear fila de la tabla
            inventory_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item['sn'])),
                        ft.DataCell(ft.Text(item['item_code']['codigo'])),
                        ft.DataCell(ft.Text(item['item_code']['descripcion'])),
                        ft.DataCell(ft.Text(item['estado_actual'])),
                        ft.DataCell(ft.Text(item['asignado_a']['full_name'] if item.get('asignado_a') else 'No asignado')),
                        ft.DataCell(ft.Row(actions, spacing=5))
                    ]
                )
            )
            
        loading_indicator.visible = False
        page.update()
        
    def load_user_data():
        # Limpiar la lista de items del usuario
        user_items_list.controls.clear()
        
        # Mostrar indicador de carga
        loading_indicator.visible = True
        page.update()
        
        # Obtener datos de la API
        token = page.client_storage.get("auth_token")
        items = httpx_request("get", "/inventory/my-items", token=token)
        
        if items is None:
            show_message("Error al cargar tus artículos")
            loading_indicator.visible = False
            page.update()
            return
            
        # Llenar la lista con los datos
        for item in items:
            # Crear tarjeta para cada ítem
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"S/N: {item['sn']}", weight="bold"),
                                    ft.Text(f"Estado: {item['estado_actual']}", 
                                           color={"Activo": "green", "Inactivo": "red"}.get(item['estado_actual'], "orange"))
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            ),
                            ft.Text(f"Tipo: {item['item_code']['descripcion']}"),
                            ft.Text(f"Código: {item['item_code']['codigo']}"),
                            ft.Row(
                                [
                                    ft.ElevatedButton(
                                        "Actualizar Estado",
                                        on_click=lambda e, item_id=item['id']: open_update_status_dialog(item_id)
                                    ),
                                    ft.IconButton(
                                        icon="info",
                                        on_click=lambda e, item_id=item['id']: show_item_details(item_id)
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.END
                            )
                        ],
                        spacing=5
                    ),
                    padding=10
                )
            )
            
            user_items_list.controls.append(card)
            
        loading_indicator.visible = False
        page.update()
    
    def load_inventory_data():
        # Limpiar la tabla
        inventory_table.rows.clear()
        
        # Mostrar indicador de carga
        loading_indicator.visible = True
        page.update()
        
        # Determinar qué endpoint usar según el rol del usuario
        current_user = page.client_storage.get("current_user") or {}
        is_admin = current_user.get("is_admin", False)
        endpoint = "/inventory" if is_admin else "/inventory/my-items"
        
        # Obtener datos de la API
        items = httpx_request("get", endpoint, token=current_user.get("access_token"))
        
        if items is None:
            show_message("Error al cargar el inventario")
            loading_indicator.visible = False
            page.update()
            return
            
        # Llenar la tabla con los datos
        for item in items:
            # Crear acciones según permisos
            actions = []
            
            # Todos los usuarios pueden ver el estado
            status_action = ft.IconButton(
                icon="info",
                tooltip="Ver detalles",
                on_click=lambda e, item_id=item['id']: show_item_details(item_id)
            )
            actions.append(status_action)
            
            # Solo admin puede editar/eliminar cualquier ítem
            # Los usuarios regulares solo pueden editar sus propios ítems
            can_edit = is_admin or (item.get('asignado_a') and item['asignado_a'].get('id') == current_user.get('id'))
            
            if can_edit:
                edit_btn = ft.IconButton(
                    icon="edit",
                    tooltip="Editar",
                    on_click=lambda e, item_id=item['id']: open_edit_item_dialog(item_id)
                )
                actions.append(edit_btn)
            
            # Solo admin puede eliminar
            if is_admin:
                delete_btn = ft.IconButton(
                    icon="delete",
                    tooltip="Eliminar",
                    on_click=lambda e, item_id=item['id']: delete_item_confirm(item_id)
                )
                actions.append(delete_btn)
            
            # Crear fila de la tabla
            inventory_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item['sn'])),
                        ft.DataCell(ft.Text(item['item_code']['codigo'])),
                        ft.DataCell(ft.Text(item['item_code']['descripcion'])),
                        ft.DataCell(ft.Text(item['estado_actual'])),
                        ft.DataCell(ft.Text(item['asignado_a']['full_name'] if item.get('asignado_a') else 'No asignado')),
                        ft.DataCell(ft.Row(actions, spacing=5))
                    ]
                )
            )
        
        # Ocultar indicador de carga
        loading_indicator.visible = False
        page.update()

    def get_user_inventory_view():
        load_user_data()
        return ft.Column([
            ft.Text("Mis Artículos Asignados", size=30, weight="bold"),
            user_items_list
        ])

    def load_user_data():
        token = page.client_storage.get("auth_token")
        response = httpx_request("get", "/inventory/my-items", token=token)
        if response:
            global my_assigned_items
            my_assigned_items = response
            user_items_list.controls.clear()
            for item in my_assigned_items:
                user_items_list.controls.append(create_item_card(item))
            page.update()
        else:
            show_message("Error al cargar tus artículos.")

    def create_item_card(item):
        status_dropdown = ft.Dropdown(
            label="Cambiar Estado",
            value=item['estado_actual'],
            options=[
                ft.dropdown.Option("Asignado a Tecnico"),
                ft.dropdown.Option("En Comercio"),
                ft.dropdown.Option("Reversa lista"),
                ft.dropdown.Option("Reversado"),
            ]
        )
        terminal_field = ft.TextField(label="Nº Terminal", value=item.get('terminal_comercio'), visible=(item['estado_actual'] == 'En Comercio'))

        def on_status_change(e):
            terminal_field.visible = (e.control.value == 'En Comercio')
            page.update()
        
        status_dropdown.on_change = on_status_change

        def save_status_change(e):
            item_id_to_update = e.control.data
            update_data = {
                "estado_actual": status_dropdown.value,
                "terminal_comercio": terminal_field.value if terminal_field.visible else None
            }
            token = page.client_storage.get("auth_token")
            response = httpx_request("patch", f"/inventory/{item_id_to_update}/status", token=token, json_data=update_data)
            if response:
                show_message("Estado actualizado correctamente", color="green")
                load_user_data() # Recargar para ver los cambios
            
        return ft.Card(
            content=ft.Container(
                padding=10,
                content=ft.Column([
                    ft.Text(f"S/N: {item['sn']}", weight="bold"),
                    ft.Text(f"{item['item_code']['codigo']} - {item['item_code']['descripcion']}"),
                    ft.Divider(),
                    status_dropdown,
                    terminal_field,
                    ft.ElevatedButton("Guardar Cambio", data=item['id'], on_click=save_status_change)
                ])
            )
        )

    def open_add_item_dialog(e):
        current_user = page.client_storage.get("current_user")
        token = current_user.get("access_token") if current_user else None

        # Obtener datos para los dropdowns
        all_item_codes = httpx_request("get", "/item-codes", token=token)
        all_technicians = httpx_request("get", "/users/technicians", token=token)

        if all_item_codes is None or all_technicians is None:
            show_message("Error de comunicación con la API. No se pudieron cargar los datos.")
            return
        if not all_item_codes:
            show_message("No hay 'Códigos de Artículo' definidos en el sistema. Añada algunos primero.")
            return

        # Campos del formulario
        sn_field = ft.TextField(
            label="Número de Serie (S/N)*",
            hint_text="Ingrese el número de serie único",
            autofocus=True,
            width=400
        )
        
        code_dropdown = ft.Dropdown(
            label="Código de Artículo*",
            hint_text="Seleccione un código de artículo",
            options=[ft.dropdown.Option(
                key=str(code['id']), 
                text=f"{code['codigo']} - {code['descripcion']}"
            ) for code in all_item_codes],
            width=400
        )
        
        service_type_dropdown = ft.Dropdown(
            label="Tipo de Servicio*",
            hint_text="Seleccione el tipo de servicio",
            options=[
                ft.dropdown.Option("implementacion", text="Implementación"),
                ft.dropdown.Option("falla", text="Falla"),
                ft.dropdown.Option("entrega_insumos", text="Entrega de Insumos"),
                ft.dropdown.Option("reemplazo", text="Reemplazo"),
                ft.dropdown.Option("mantenimiento", text="Mantenimiento")
            ],
            width=400
        )
        
        status_dropdown = ft.Dropdown(
            label="Estado Actual*",
            hint_text="Seleccione el estado del artículo",
            options=[
                ft.dropdown.Option("En Bodega", text="En Bodega"),
                ft.dropdown.Option("Asignado a Tecnico", text="Asignado a Técnico"),
                ft.dropdown.Option("En Comercio", text="En Comercio"),
                ft.dropdown.Option("En Reversa", text="En Reversa"),
                ft.dropdown.Option("Reversado", text="Reversado")
            ],
            value="En Bodega",
            width=400
        )
        
        tech_options = [ft.dropdown.Option(key='None', text="No asignado")] + [
            ft.dropdown.Option(key=str(tech['id']), text=tech['full_name']) 
            for tech in all_technicians
        ]
        
        tech_dropdown = ft.Dropdown(
            label="Asignar a Técnico",
            hint_text="Seleccione un técnico (opcional)",
            options=tech_options,
            value='None',
            width=400
        )
        
        terminal_field = ft.TextField(
            label="Número de Terminal de Comercio",
            hint_text="Opcional - Solo si aplica",
            width=400,
            visible=False  # Inicialmente oculto
        )
        
        # Mostrar/ocultar campo de terminal según el estado seleccionado
        def on_status_change(e):
            terminal_field.visible = (status_dropdown.value == "En Comercio")
            page.update()
            
        status_dropdown.on_change = on_status_change

        def add_item_confirm(e):
            # Validar campos obligatorios
            required_fields = [
                (sn_field, "Número de Serie"),
                (code_dropdown, "Código de Artículo"),
                (service_type_dropdown, "Tipo de Servicio"),
                (status_dropdown, "Estado Actual")
            ]
            
            missing_fields = [name for field, name in required_fields if not field.value]
            if missing_fields:
                show_message(f"Por favor complete los campos obligatorios: {', '.join(missing_fields)}", color="red")
                return
                
            # Validar que si el estado es "En Comercio", se proporcione el número de terminal
            if status_dropdown.value == "En Comercio" and not terminal_field.value:
                show_message("Por favor ingrese el número de terminal para artículos en comercio", color="red")
                return

            try:
                # Obtener el ID del código de artículo seleccionado
                selected_item_code_id = int(code_dropdown.value)
                
                # Obtener el código y descripción del artículo seleccionado
                selected_item = next((code for code in all_item_codes if code['id'] == selected_item_code_id), None)
                
                # Preparar datos para enviar a la API
                new_item_data = {
                    "sn": sn_field.value.strip(),
                    "item_code_id": selected_item_code_id,
                    "tipo_servicio": service_type_dropdown.value,  # Asegurar que este campo esté incluido
                    "estado_actual": status_dropdown.value,
                    "asignado_a_id": int(tech_dropdown.value) if tech_dropdown.value and tech_dropdown.value != 'None' else None,
                    "terminal_comercio": terminal_field.value if status_dropdown.value == "En Comercio" else None
                }
                
                print("\n=== Datos a enviar a la API ===")
                print(f"Tipo de servicio: {type(service_type_dropdown.value)}")
                print(f"Valor de tipo_servicio: {service_type_dropdown.value!r}")
                print(f"Datos completos: {new_item_data}")
                
                # Validar que los datos requeridos no sean cadenas vacías
                required_fields = {
                    "sn": "Número de Serie",
                    "tipo_servicio": "Tipo de Servicio",
                    "estado_actual": "Estado Actual"
                }
                
                for field, name in required_fields.items():
                    if not new_item_data.get(field):
                        show_message(f"El campo {name} no puede estar vacío", color="red")
                        return
                
                # Mostrar indicador de carga
                save_button.text = "Guardando..."
                save_button.disabled = True
                page.update()
                
                # Obtener el token de autenticación
                token = page.client_storage.get("auth_token")
                if not token:
                    show_message("Error: No se encontró el token de autenticación", color="red")
                    return
                
                # Enviar solicitud a la API
                print(f"\n=== Enviando solicitud a la API ===")
                print(f"Token: {token}")
                print(f"Datos: {new_item_data}")
                
                response = httpx_request(
                    "post", 
                    "/inventory", 
                    token=token, 
                    json_data=new_item_data
                )

                if response:
                    print("\n=== Respuesta exitosa de la API ===")
                    print(f"Respuesta: {response}")
                    add_dialog.open = False
                    show_message("✅ Artículo añadido exitosamente", color="green")
                    load_admin_data()  # Recargar la tabla
                
            except (ValueError, AttributeError) as e:
                print(f"\n=== Error en los datos del formulario ===")
                print(f"Error: {str(e)}")
                show_message(f"Error en los datos del formulario: {str(e)}", color="red")
            except Exception as e:
                print(f"\n=== Error inesperado ===")
                print(f"Tipo de error: {type(e).__name__}")
                print(f"Error: {str(e)}")
                show_message(f"Error inesperado: {str(e)}", color="red")
            finally:
                # Restaurar estado del botón
                save_button.text = "Guardar"
                save_button.disabled = False
                page.update()

        # Crear el diálogo con todos los campos
        add_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("➕ Añadir Nuevo Artículo", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Complete la información del artículo", size=14, color="#757575"),
                        ft.Divider(height=10, color="transparent"),
                        sn_field,
                        code_dropdown,
                        service_type_dropdown,
                        status_dropdown,
                        tech_dropdown,
                        terminal_field,
                        ft.Text("* Campos obligatorios", size=12, color="#9E9E9E", italic=True)
                    ],
                    spacing=15,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                ),
                width=450,
                padding=20
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(add_dialog, 'open', False) or page.update()),
                ft.ElevatedButton(
                    text="Guardar",
                    on_click=add_item_confirm,
                    icon="save",
                    style=ft.ButtonStyle(
                        padding=20,
                        bgcolor="#1E88E5",
                        color="white"
                    )
                )
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        # Guardar referencia al botón para actualizar su estado
        save_button = add_dialog.actions[1]

        # Asignar el diálogo a la página y mostrarlo
        page.dialog = add_dialog
        add_dialog.open = True
        page.update()

    def open_edit_item_dialog(e):
        item_to_edit = e.control.data

        # --- Definición de los campos del formulario con datos existentes ---
        sn_field = ft.TextField(label="Número de Serie (S/N)", value=item_to_edit['sn'])
        code_dropdown = ft.Dropdown(
            label="Código de Artículo",
            options=[ft.dropdown.Option(key=code['id'], text=f"{code['codigo']} - {code['descripcion']}") for code in all_item_codes],
            value=item_to_edit['item_code']['id']
        )
        service_type_dropdown = ft.Dropdown(
            label="Tipo de Servicio",
            options=[
                ft.dropdown.Option("implementacion"),
                ft.dropdown.Option("falla"),
                ft.dropdown.Option("entrega de insumos"),
            ],
            value=item_to_edit['tipo_servicio']
        )
        status_dropdown = ft.Dropdown(
            label="Estado Actual",
            options=[
                ft.dropdown.Option("En Bodega"),
                ft.dropdown.Option("Asignado a Tecnico"),
                ft.dropdown.Option("En Comercio"),
                ft.dropdown.Option("Reversa lista"),
                ft.dropdown.Option("Reversado"),
            ],
            value=item_to_edit['estado_actual']
        )
        tech_options = [ft.dropdown.Option(key=None, text="Nadie")] + [ft.dropdown.Option(key=tech['id'], text=tech['full_name']) for tech in all_technicians]
        tech_dropdown = ft.Dropdown(
            label="Asignar a Técnico", 
            options=tech_options, 
            value=item_to_edit.get('asignado_a')['id'] if item_to_edit.get('asignado_a') else None
        )
        terminal_field = ft.TextField(label="Nº Terminal (si aplica)", value=item_to_edit.get('terminal_comercio'))

        def edit_item_confirm(e):
            updated_item_data = {
                "sn": sn_field.value,
                "item_code_id": int(code_dropdown.value),
                "tipo_servicio": service_type_dropdown.value,
                "estado_actual": status_dropdown.value,
                "asignado_a_id": tech_dropdown.value,
                "terminal_comercio": terminal_field.value if terminal_field.value else None
            }

            token = page.client_storage.get("auth_token")
            response = httpx_request("put", f"/inventory/{item_to_edit['id']}", token=token, json_data=updated_item_data)

            if response:
                page.dialog.open = False
                show_message("Artículo actualizado exitosamente", color="green")
                load_admin_data()
            page.update()

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar Artículo"),
            content=ft.Column([sn_field, code_dropdown, service_type_dropdown, status_dropdown, tech_dropdown, terminal_field], tight=True, scroll=ft.ScrollMode.ADAPTIVE),
            actions=[
                ft.ElevatedButton("Guardar Cambios", on_click=edit_item_confirm),
                ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, 'open', False) or page.update()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog.open = True
        page.update()

    def open_delete_item_dialog(e):
        item_to_delete = e.control.data
        
        # Obtener el ID del ítem, ya sea directamente o desde un diccionario
        if isinstance(item_to_delete, dict):
            item_id = item_to_delete['id']
            sn = item_to_delete.get('sn', 'desconocido')
            item_code = item_to_delete.get('item_code', {})
            description = item_code.get('descripcion', 'sin descripción') if isinstance(item_code, dict) else 'sin descripción'
            display_text = f"{sn} - {description}"
        else:
            # Asumimos que es el ID directamente
            item_id = item_to_delete
            display_text = f"ID: {item_id}"
        
        def delete_item_confirm(e):
            try:
                token = page.client_storage.get("auth_token")
                if not token:
                    show_message("Error: No se encontró el token de autenticación", color="red")
                    return
                    
                # Mostrar mensaje de carga
                page.dialog.content = ft.Column([
                    ft.ProgressRing(),
                    ft.Text("Eliminando artículo...")
                ])
                page.update()
                
                # Realizar la petición DELETE
                response = httpx_request("delete", f"/inventory/{item_id}", token=token)
                
                # Cerrar el diálogo de confirmación
                page.dialog.open = False
                
                # Mostrar mensaje de éxito o error
                if response is not None:  # DELETE exitoso (código 204)
                    show_message("✅ Artículo eliminado exitosamente", color="green")
                    # Recargar los datos del inventario
                    if 'load_admin_data' in globals():
                        load_admin_data()
                    elif 'load_inventory_data' in globals():
                        load_inventory_data()
                else:
                    # El mensaje de error ya fue mostrado por httpx_request
                    pass
                    
            except Exception as ex:
                page.dialog.open = False
                show_message(f"Error al eliminar el artículo: {str(ex)}", color="red")
                
            page.update()

        # Crear diálogo de confirmación
        # Usando colores directos como cadenas para mayor compatibilidad
        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Confirmar Eliminación"),
            content=ft.Text(f"¿Estás seguro de que quieres eliminar el siguiente artículo?\n\n{display_text}"),
            actions=[
                ft.ElevatedButton(
                    "Eliminar", 
                    on_click=delete_item_confirm, 
                    style=ft.ButtonStyle(
                        color="white",
                        bgcolor="#d32f2f"  # Rojo oscuro
                    ),
                    # Usando una cadena de texto para el ícono para mayor compatibilidad
                    icon="delete_forever"
                ),
                ft.TextButton(
                    "Cancelar", 
                    on_click=lambda e: setattr(page.dialog, 'open', False) or page.update(),
                    style=ft.ButtonStyle(
                        color="#1976d2"  # Azul
                    )
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog.open = True
        page.update()


    def get_admin_view():
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Panel de Administrador", size=20, weight="bold"),
                    new_username,
                    new_password,
                    full_name,
                    is_admin_checkbox,
                    ft.ElevatedButton("Crear Usuario", on_click=create_user_clicked, width=200),
                    admin_message_text, # Mensaje específico para el panel de admin
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
            ),
            alignment=ft.alignment.center,
            expand=True,
            padding=20
        )

    # --- LÓGICA DE NAVEGACIÓN Y ACCIONES ---
    def show_view(view):
        main_content.controls.clear()
        main_content.controls.append(view)
        page.update()

    def nav_drawer_changed(e):
        selected_index = e.control.selected_index
        page.drawer.open = False
        
        current_user = page.client_storage.get("current_user") or {}
        is_admin = current_user.get("is_admin") == 1
        
        if selected_index == 0:  # Inicio
            show_view(get_welcome_view(current_user))
        elif selected_index == 1:  # Inventario
            show_view(get_inventory_view())
        elif selected_index == 2 and is_admin:  # Administración (solo para admin)
            show_view(get_admin_view())
        
        page.update()

    def show_message(message, color="red", target_text=None):
        if target_text is None:
            target_text = error_text
        target_text.value = message
        target_text.color = color
        target_text.visible = True
        page.update()

    def login_clicked(e):
        user_data = {"username": username_field.value, "password": password_field.value}
        try:
            with httpx.Client() as client:
                # Hacer la petición de autenticación
                response = client.post(
                    f"{API_BASE_URL}/auth", 
                    json=user_data, 
                    timeout=10.0
                )
                response.raise_for_status()
                
                # Obtener la respuesta del servidor
                user = response.json()
                print("Datos de autenticación recibidos:", user)  # Para depuración
                
                # Verificar que el token está presente en la respuesta
                if not user.get("access_token"):
                    show_message("Error: No se recibió token de autenticación")
                    return
                
                # Asegurarse de que los campos requeridos estén presentes
                if not all(key in user for key in ["username", "full_name", "is_admin"]):
                    show_message("Error: Datos de usuario incompletos en la respuesta")
                    return
                
                # Almacenar el token y los datos del usuario
                page.client_storage.set("auth_token", user["access_token"])
                page.client_storage.set("current_user", user)
                
                # Limpiar campos de login
                username_field.value = ""
                password_field.value = ""
                
                # Inicializar la interfaz principal
                setup_main_layout(user)
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                show_message("Usuario o contraseña incorrectos")
            else:
                show_message(f"Error del servidor: {e.response.text}")
            print(f"Error en login: {e}")
            
        except httpx.RequestError as e:
            show_message("Error de conexión: No se pudo conectar al servidor.")
            print(f"Error de conexión: {e}")
            
        except Exception as e:
            show_message("Error inesperado. Por favor, intente nuevamente.")
            print(f"Error inesperado: {e}")

    def create_user_clicked(e):
        if not new_username.value or not new_password.value or not full_name.value:
            show_message("Todos los campos son obligatorios", target_text=admin_message_text)
            return

        user_data = {
            "username": new_username.value, "password": new_password.value,
            "full_name": full_name.value, "is_admin": is_admin_checkbox.value
        }
        
        current_user = page.client_storage.get("current_user")
        token = current_user.get("access_token") if current_user else None

        response = httpx_request("post", "/users", token=token, json_data=user_data)
        
        if response:
            new_username.value, new_password.value, full_name.value = "", "", ""
            is_admin_checkbox.value = False
            show_message("✅ Usuario creado exitosamente", color="green", target_text=admin_message_text)

    def logout_clicked(e):
        page.client_storage.remove("current_user")
        setup_login_layout()

    def open_drawer(e):
        page.drawer.open = True
        page.update()

    # --- CONFIGURACIÓN DE LAYOUTS ---
    def setup_main_layout(user):
        page.appbar = ft.AppBar(
            title=ft.Text("Mi Aplicación"),
            leading=ft.IconButton(ft.Icons.MENU, on_click=open_drawer),
            actions=[ft.IconButton(ft.Icons.LOGOUT, on_click=logout_clicked)]
        )
        drawer_items = [
            ft.NavigationDrawerDestination(icon=ft.Icons.HOME, label="Inicio"),
            ft.NavigationDrawerDestination(icon=ft.Icons.INVENTORY, label="Inventario")
        ]
        if user.get("is_admin"):
            drawer_items.append(ft.NavigationDrawerDestination(icon=ft.Icons.ADMIN_PANEL_SETTINGS, label="Panel de Administrador"))
        page.drawer = ft.NavigationDrawer(controls=drawer_items, on_change=nav_drawer_changed)
        
        page.clean()
        page.add(main_content)
        show_view(get_welcome_view(user))

    def setup_login_layout():
        page.appbar = None
        page.drawer = None
        page.clean()
        page.add(get_login_view())
        page.update()

    # --- COMPONENTES DE UI ---
    username_field = ft.TextField(label="Usuario", width=300)
    password_field = ft.TextField(label="Contraseña", password=True, width=300)
    error_text = ft.Text("", color="red", visible=False)
    
    new_username = ft.TextField(label="Nuevo Usuario", width=300)
    new_password = ft.TextField(label="Nueva Contraseña", password=True, width=300)
    full_name = ft.TextField(label="Nombre Completo", width=300)
    is_admin_checkbox = ft.Checkbox(label="Es Administrador", value=False)
    admin_message_text = ft.Text("", color="red", visible=False)

    main_content = ft.Column(expand=True, alignment=ft.MainAxisAlignment.CENTER)

    # --- INICIO DE LA APP ---
    stored_user = page.client_storage.get("current_user")
    if stored_user:
        setup_main_layout(stored_user)
    else:
        setup_login_layout()

if __name__ == "__main__":
    ft.app(target=main)


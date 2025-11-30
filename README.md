# CocinAI

Sistema de gestión para restaurantes desarrollado con Django que incluye gestión de inventario, compras, producción, ventas y predicciones usando Machine Learning.

## Características

- 📦 **Gestión de Inventario**: Control de insumos, lotes, mermas y movimientos
- 🛒 **Compras**: Gestión de órdenes de compra y proveedores
- 🍳 **Producción**: Control de producción de platos
- 💰 **Ventas**: Gestión de mesas, comandas y ventas
- 🤖 **Predicciones ML**: Modelos de Machine Learning para predecir ventas
- 👥 **Usuarios**: Sistema de roles y permisos

## Requisitos

- Python 3.8+
- MySQL 5.7+ o MariaDB
- Django 4.2+

## Instalación

1. Clona el repositorio:
```bash
git clone https://github.com/JuanBaeza95/Proyecto-de-Titulo-Cocinai.git
cd Proyecto-de-Titulo-Cocinai
```

2. Crea un entorno virtual:
```bash
python -m venv venv
```

3. Activa el entorno virtual:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

4. Instala las dependencias:
```bash
pip install -r requirements.txt
```

5. Configura la base de datos:
   - Crea una base de datos MySQL llamada `cocinai`
   - Copia `cocinAI/settings.example.py` a `cocinAI/settings.py`
   - Edita `cocinAI/settings.py` con tus credenciales de base de datos

6. Ejecuta las migraciones:
```bash
python manage.py migrate
```

7. Crea un superusuario:
```bash
python manage.py createsuperuser
```

8. Ejecuta el servidor de desarrollo:
```bash
python manage.py runserver
```

## Estructura del Proyecto

```
CocinAI/
├── cocinAI/          # Configuración principal de Django
├── inventario/       # App de gestión de inventario
├── compras/          # App de gestión de compras
├── produccion/       # App de gestión de producción
├── ventas/           # App de gestión de ventas
├── prediccion/       # App de predicciones ML
├── usuarios/         # App de gestión de usuarios
└── models_ml/        # Modelos de Machine Learning entrenados
```

## Modelos de Machine Learning

El proyecto incluye modelos entrenados para predecir ventas:
- Random Forest para platos individuales
- Gradient Boosting para ventas generales

Los modelos se encuentran en la carpeta `models_ml/` (no incluidos en el repositorio por tamaño).

## Notas de Seguridad

⚠️ **IMPORTANTE**: 
- No subas `settings.py` con credenciales reales
- Usa `settings.example.py` como plantilla
- Cambia el `SECRET_KEY` en producción
- No subas archivos `.sql` con datos reales

## Licencia

Este proyecto es privado.

## Autor

Desarrollado para gestión de restaurantes.


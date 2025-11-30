# Guía para Subir el Proyecto a GitHub

## ✅ Pasos Completados

1. ✅ Repositorio Git inicializado
2. ✅ `.gitignore` configurado (protege `settings.py`, `db.sqlite3`, `*.sql`, etc.)
3. ✅ `README.md` creado
4. ✅ `settings.example.py` creado (archivo de ejemplo sin información sensible)
5. ✅ Archivos agregados al staging area

## 📋 Pasos Pendientes

### 1. Configurar tu identidad en Git

Ejecuta estos comandos (reemplaza con tu información):

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu-email@ejemplo.com"
```

O solo para este repositorio (sin --global):

```bash
git config user.name "Juan Baeza"
git config user.email "juancarlosbm95@hotmail.com"
```

### 2. Hacer el commit inicial

```bash
git commit -m "Commit inicial: Sistema CocinAI - Gestión de restaurantes con Django y ML"
```

### 3. Crear el repositorio en GitHub

1. Ve a [GitHub](https://github.com) e inicia sesión
2. Haz clic en el botón "+" (arriba a la derecha) y selecciona "New repository"
3. Nombre del repositorio: `CocinAI` (o el que prefieras)
4. Descripción: "Sistema de gestión para restaurantes con Django y Machine Learning"
5. **NO** marques "Initialize this repository with a README" (ya tenemos uno)
6. Haz clic en "Create repository"

### 4. Conectar tu repositorio local con GitHub

Después de crear el repositorio en GitHub, ejecuta estos comandos (reemplaza `TU-USUARIO` con tu usuario de GitHub):

```bash
git remote add origin https://github.com/JuanBaeza95/Proyecto-de-Titulo-Cocinai.git
git branch -M main
git push -u origin main
```

Si GitHub te muestra una URL diferente (SSH o HTTPS), usa esa.

### 5. Si usas autenticación

- **HTTPS**: GitHub puede pedirte un token de acceso personal en lugar de tu contraseña
- **SSH**: Necesitarás configurar una clave SSH

## 🔒 Seguridad

✅ **Archivos protegidos** (no se subirán a GitHub):
- `cocinAI/settings.py` (contiene SECRET_KEY y credenciales)
- `db.sqlite3` (base de datos local)
- `*.sql` (archivos SQL)
- `models_ml/*.pkl` (modelos ML grandes)
- `venv/` (entorno virtual)
- `__pycache__/` (archivos compilados)

✅ **Archivos incluidos**:
- `cocinAI/settings.example.py` (plantilla para configuración)
- Todo el código fuente
- `requirements.txt`
- `README.md`

## 📝 Notas

- Si necesitas cambiar algo después del primer push, simplemente:
  ```bash
  git add .
  git commit -m "Descripción del cambio"
  git push
  ```

- Para verificar qué archivos se subirán:
  ```bash
  git status
  ```


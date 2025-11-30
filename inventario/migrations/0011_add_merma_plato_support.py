# Generated manually for Merma model changes

from django.db import migrations, models
import django.db.models.deletion


def verificar_y_agregar_campos(apps, schema_editor):
    """Verifica qué columnas existen y agrega solo las que faltan"""
    db_alias = schema_editor.connection.alias
    
    with schema_editor.connection.cursor() as cursor:
        # Verificar qué columnas existen en la tabla MERMA
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'MERMA'
        """)
        columnas_existentes = [row[0] for row in cursor.fetchall()]
        
        # Agregar tipo_merma si no existe
        if 'tipo_merma' not in columnas_existentes:
            cursor.execute("""
                ALTER TABLE MERMA 
                ADD COLUMN tipo_merma VARCHAR(10) NOT NULL DEFAULT 'lote'
            """)
        
        # Modificar id_lote para permitir NULL si aún no lo permite
        cursor.execute("""
            SELECT IS_NULLABLE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'MERMA' 
            AND COLUMN_NAME = 'id_lote'
        """)
        resultado = cursor.fetchone()
        if resultado and resultado[0] == 'NO':
            cursor.execute("""
                ALTER TABLE MERMA 
                MODIFY COLUMN id_lote INT NULL
            """)
        
        # Agregar id_plato_producido si no existe
        if 'id_plato_producido' not in columnas_existentes:
            cursor.execute("""
                ALTER TABLE MERMA 
                ADD COLUMN id_plato_producido INT NULL,
                ADD CONSTRAINT fk_merma_plato_producido 
                FOREIGN KEY (id_plato_producido) 
                REFERENCES PLATO_PRODUCIDO(id_plato_producido) 
                ON DELETE RESTRICT
            """)


def revertir_campos(apps, schema_editor):
    """Revertir los cambios"""
    db_alias = schema_editor.connection.alias
    
    with schema_editor.connection.cursor() as cursor:
        # Eliminar id_plato_producido si existe
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'MERMA' 
            AND COLUMN_NAME = 'id_plato_producido'
        """)
        if cursor.fetchone():
            cursor.execute("""
                ALTER TABLE MERMA 
                DROP FOREIGN KEY fk_merma_plato_producido,
                DROP COLUMN id_plato_producido
            """)
        
        # Revertir id_lote a NOT NULL si es necesario
        cursor.execute("""
            ALTER TABLE MERMA 
            MODIFY COLUMN id_lote INT NOT NULL
        """)
        
        # Eliminar tipo_merma si existe
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'MERMA' 
            AND COLUMN_NAME = 'tipo_merma'
        """)
        if cursor.fetchone():
            cursor.execute("""
                ALTER TABLE MERMA 
                DROP COLUMN tipo_merma
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0010_update_origen_movimiento_enum'),
    ]

    operations = [
        migrations.RunPython(verificar_y_agregar_campos, revertir_campos),
    ]


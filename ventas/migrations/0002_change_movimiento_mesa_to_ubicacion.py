# Generated manually to change MovimientoMesa from Mesa to Ubicacion

from django.db import migrations, models
import django.db.models.deletion


def migrar_datos_mesa_a_ubicacion(apps, schema_editor):
    """
    Migra los datos de id_mesa a id_ubicacion.
    Si hay registros existentes, intenta encontrar una ubicación de tipo mesa.
    Si no hay registros, no hace nada.
    """
    MovimientoMesa = apps.get_model('ventas', 'MovimientoMesa')
    Ubicacion = apps.get_model('inventario', 'Ubicacion')
    
    # Buscar una ubicación de tipo mesa para usar como default
    ubicacion_mesa_default = None
    try:
        ubicacion_mesa_default = Ubicacion.objects.filter(
            tipo_ubicacion__iexact='mesa'
        ).first()
        
        if not ubicacion_mesa_default:
            ubicacion_mesa_default = Ubicacion.objects.filter(
                tipo_ubicacion__icontains='mesa'
            ).first()
        
        if not ubicacion_mesa_default:
            ubicacion_mesa_default = Ubicacion.objects.filter(
                nombre_ubicacion__icontains='mesa'
            ).first()
    except:
        pass
    
    # Si hay movimientos existentes y encontramos una ubicación, migrar
    if ubicacion_mesa_default:
        MovimientoMesa.objects.filter(id_ubicacion__isnull=True).update(
            id_ubicacion=ubicacion_mesa_default
        )


def revertir_migracion(apps, schema_editor):
    """Revertir la migración (no se puede hacer completamente sin perder datos)"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0001_initial_mesas'),
        ('inventario', '0011_add_merma_plato_support'),
    ]

    operations = [
        # Agregar id_ubicacion como nullable primero
        migrations.AddField(
            model_name='movimientomesa',
            name='id_ubicacion',
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_column='id_ubicacion',
                on_delete=django.db.models.deletion.RESTRICT,
                to='inventario.ubicacion',
                verbose_name='Ubicación (Mesa)'
            ),
        ),
        # Agregar numero_mesa
        migrations.AddField(
            model_name='movimientomesa',
            name='numero_mesa',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Número de Mesa'),
        ),
        # Migrar datos si existen
        migrations.RunPython(migrar_datos_mesa_a_ubicacion, revertir_migracion),
        # Hacer id_ubicacion no nullable
        migrations.AlterField(
            model_name='movimientomesa',
            name='id_ubicacion',
            field=models.ForeignKey(
                db_column='id_ubicacion',
                on_delete=django.db.models.deletion.RESTRICT,
                to='inventario.ubicacion',
                verbose_name='Ubicación (Mesa)'
            ),
        ),
        # Eliminar id_mesa
        migrations.RemoveField(
            model_name='movimientomesa',
            name='id_mesa',
        ),
    ]


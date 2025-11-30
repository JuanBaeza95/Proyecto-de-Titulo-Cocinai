# Generated manually for Mesa and MovimientoMesa models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventario', '0011_add_merma_plato_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='Mesa',
            fields=[
                ('id_mesa', models.AutoField(primary_key=True, serialize=False)),
                ('numero_mesa', models.CharField(max_length=10, unique=True, verbose_name='Número de Mesa')),
                ('capacidad', models.IntegerField(default=4, verbose_name='Capacidad')),
                ('estado', models.CharField(
                    choices=[
                        ('disponible', 'Disponible'),
                        ('ocupada', 'Ocupada'),
                        ('reservada', 'Reservada'),
                        ('mantenimiento', 'En Mantenimiento'),
                    ],
                    default='disponible',
                    max_length=20,
                    verbose_name='Estado'
                )),
                ('ubicacion', models.CharField(blank=True, max_length=100, null=True, verbose_name='Ubicación')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('activa', models.BooleanField(default=True, verbose_name='Activa')),
            ],
            options={
                'verbose_name': 'Mesa',
                'verbose_name_plural': 'Mesas',
                'db_table': 'MESA',
                'ordering': ['numero_mesa'],
            },
        ),
        migrations.CreateModel(
            name='MovimientoMesa',
            fields=[
                ('id_movimiento_mesa', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_movimiento', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Movimiento')),
                ('observaciones', models.TextField(blank=True, null=True, verbose_name='Observaciones')),
                ('id_mesa', models.ForeignKey(
                    db_column='id_mesa',
                    on_delete=django.db.models.deletion.RESTRICT,
                    to='ventas.mesa',
                    verbose_name='Mesa'
                )),
                ('id_plato_producido', models.ForeignKey(
                    db_column='id_plato_producido',
                    on_delete=django.db.models.deletion.RESTRICT,
                    related_name='movimientos_mesa',
                    to='inventario.platoproducido',
                    verbose_name='Plato Producido'
                )),
                ('id_usuario', models.ForeignKey(
                    db_column='id_usuario',
                    on_delete=django.db.models.deletion.RESTRICT,
                    to='inventario.usuario',
                    verbose_name='Usuario'
                )),
            ],
            options={
                'verbose_name': 'Movimiento a Mesa',
                'verbose_name_plural': 'Movimientos a Mesas',
                'db_table': 'MOVIMIENTO_MESA',
                'ordering': ['-fecha_movimiento'],
            },
        ),
    ]


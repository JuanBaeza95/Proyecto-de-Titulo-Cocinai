# Generated manually for Comanda and DetalleComanda models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0002_change_movimiento_mesa_to_ubicacion'),
        ('inventario', '0011_add_merma_plato_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='Comanda',
            fields=[
                ('id_comanda', models.AutoField(primary_key=True, serialize=False)),
                ('estado', models.CharField(
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('en_preparacion', 'En Preparación'),
                        ('parcialmente_lista', 'Parcialmente Lista'),
                        ('lista', 'Lista'),
                        ('entregada', 'Entregada'),
                        ('cancelada', 'Cancelada'),
                    ],
                    default='pendiente',
                    max_length=20,
                    verbose_name='Estado'
                )),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')),
                ('observaciones', models.TextField(blank=True, null=True, verbose_name='Observaciones')),
                ('id_mesa', models.ForeignKey(
                    db_column='id_mesa',
                    on_delete=django.db.models.deletion.RESTRICT,
                    related_name='comandas',
                    to='ventas.mesa',
                    verbose_name='Mesa'
                )),
                ('id_usuario', models.ForeignKey(
                    db_column='id_usuario',
                    on_delete=django.db.models.deletion.RESTRICT,
                    related_name='comandas_creadas',
                    to='inventario.usuario',
                    verbose_name='Usuario (Garzón)'
                )),
            ],
            options={
                'verbose_name': 'Comanda',
                'verbose_name_plural': 'Comandas',
                'db_table': 'COMANDA',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='DetalleComanda',
            fields=[
                ('id_detalle_comanda', models.AutoField(primary_key=True, serialize=False)),
                ('cantidad', models.IntegerField(default=1, verbose_name='Cantidad')),
                ('estado', models.CharField(
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('en_preparacion', 'En Preparación'),
                        ('listo', 'Listo'),
                        ('entregado', 'Entregado'),
                        ('cancelado', 'Cancelado'),
                    ],
                    default='pendiente',
                    max_length=20,
                    verbose_name='Estado'
                )),
                ('observaciones', models.TextField(blank=True, null=True, verbose_name='Observaciones')),
                ('id_comanda', models.ForeignKey(
                    db_column='id_comanda',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='detalles',
                    to='ventas.comanda',
                    verbose_name='Comanda'
                )),
                ('id_plato', models.ForeignKey(
                    db_column='id_plato',
                    on_delete=django.db.models.deletion.RESTRICT,
                    to='inventario.plato',
                    verbose_name='Plato'
                )),
                ('id_plato_producido', models.ForeignKey(
                    blank=True,
                    db_column='id_plato_producido',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='detalles_comanda',
                    to='inventario.platoproducido',
                    verbose_name='Plato Producido'
                )),
            ],
            options={
                'verbose_name': 'Detalle de Comanda',
                'verbose_name_plural': 'Detalles de Comanda',
                'db_table': 'DETALLE_COMANDA',
                'ordering': ['id_comanda', 'id_plato'],
            },
        ),
    ]

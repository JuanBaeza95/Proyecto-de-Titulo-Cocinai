# Generated manually to add 'venta' state to PlatoProducido

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0011_add_merma_plato_support'),
    ]

    operations = [
        migrations.AlterField(
            model_name='platoproducido',
            name='estado',
            field=models.CharField(
                choices=[
                    ('en_cocina', 'En Cocina'),
                    ('en_mesa', 'En Mesa'),
                    ('venta', 'Vendido'),
                    ('entregado', 'Entregado')
                ],
                default='en_cocina',
                max_length=20,
                verbose_name='Estado'
            ),
        ),
    ]


# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('inventario', '0012_add_venta_estado_plato_producido'),
    ]

    operations = [
        migrations.CreateModel(
            name='PreferenciaUsuarioVencidos',
            fields=[
                ('id_preferencia', models.AutoField(primary_key=True, serialize=False)),
                ('no_mostrar_alertas', models.BooleanField(default=False, verbose_name='No Mostrar Alertas')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')),
                ('lotes_mostrados', models.JSONField(blank=True, default=list, verbose_name='Lotes Ya Mostrados')),
                ('id_usuario', models.ForeignKey(db_column='id_usuario', on_delete=django.db.models.deletion.CASCADE, related_name='preferencias_vencidos', to='auth.user', verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Preferencia de Usuario - Vencidos',
                'verbose_name_plural': 'Preferencias de Usuarios - Vencidos',
                'db_table': 'PREFERENCIA_USUARIO_VENCIDOS',
                'unique_together': {('id_usuario',)},
            },
        ),
    ]


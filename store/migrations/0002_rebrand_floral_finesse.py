from django.db import migrations, models

OLD_NAME = 'Al Rayan'
NEW_NAME = 'Floral Finesse'


def rename_store(apps, schema_editor):
    # Only touch the untouched default — a name set by hand in the admin wins.
    StoreSetting = apps.get_model('store', 'StoreSetting')
    StoreSetting.objects.filter(store_name=OLD_NAME).update(store_name=NEW_NAME)


def restore_store(apps, schema_editor):
    StoreSetting = apps.get_model('store', 'StoreSetting')
    StoreSetting.objects.filter(store_name=NEW_NAME).update(store_name=OLD_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storesetting',
            name='store_name',
            field=models.CharField(default=NEW_NAME, max_length=120),
        ),
        migrations.RunPython(rename_store, restore_store),
    ]

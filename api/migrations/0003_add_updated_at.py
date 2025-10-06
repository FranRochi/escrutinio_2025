from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_adherente"),  # 👈 cambia esto al último número de tu app
    ]

    operations = [
        migrations.RunSQL(
            """
            ALTER TABLE padron
            ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP;
            """,
            reverse_sql="""
            ALTER TABLE padron DROP COLUMN updated_at;
            """
        ),
        migrations.RunSQL(
            """
            ALTER TABLE adherentes
            ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP;
            """,
            reverse_sql="""
            ALTER TABLE adherentes DROP COLUMN updated_at;
            """
        ),
    ]

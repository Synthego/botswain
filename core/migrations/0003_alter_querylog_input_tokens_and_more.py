# Generated manually to change IntegerField to PositiveIntegerField for token fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_querylog_input_tokens_querylog_output_tokens_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="querylog",
            name="input_tokens",
            field=models.PositiveIntegerField(
                blank=True, help_text="Number of input tokens used", null=True
            ),
        ),
        migrations.AlterField(
            model_name="querylog",
            name="output_tokens",
            field=models.PositiveIntegerField(
                blank=True, help_text="Number of output tokens used", null=True
            ),
        ),
        migrations.AlterField(
            model_name="querylog",
            name="total_tokens",
            field=models.PositiveIntegerField(
                blank=True, help_text="Total tokens (input + output)", null=True
            ),
        ),
    ]

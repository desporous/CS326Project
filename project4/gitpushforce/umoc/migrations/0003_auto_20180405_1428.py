# Generated by Django 2.0.2 on 2018-04-05 18:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('umoc', '0002_auto_20180405_1416'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comment',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='umoc.UserProfile'),
        ),
        migrations.AlterField(
            model_name='notification',
            name='recipient',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='umoc.UserProfile'),
        ),
        migrations.AlterField(
            model_name='trip',
            name='leader',
            field=models.ForeignKey(help_text='Select a user to be in charge of organizing and leading this trip', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='trip_leader', to='umoc.UserProfile', verbose_name='Trip Leader/Organizer'),
        ),
        migrations.AlterField(
            model_name='trip',
            name='participants',
            field=models.ManyToManyField(help_text='Select users who are signed up to go on the trip', to='umoc.UserProfile'),
        ),
    ]

import uuid
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0002_table_is_active_table_section_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DiningArea',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Dining Area',
                'verbose_name_plural': 'Dining Areas',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='ReservationSchedule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')], unique=True)),
                ('lunch_start', models.TimeField(blank=True, default='12:00:00', null=True)),
                ('lunch_end', models.TimeField(blank=True, default='15:00:00', null=True)),
                ('dinner_start', models.TimeField(blank=True, default='17:00:00', null=True)),
                ('dinner_end', models.TimeField(blank=True, default='23:00:00', null=True)),
                ('is_closed', models.BooleanField(default=False, help_text='Mark entire day closed for reservations')),
            ],
            options={
                'verbose_name': 'Reservation Schedule',
                'verbose_name_plural': 'Reservation Schedules',
                'ordering': ['day_of_week'],
            },
        ),
        migrations.CreateModel(
            name='ReservationSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('standard_duration_minutes', models.PositiveIntegerField(default=90, help_text='Default table sitting duration for 1-4 guests (e.g. 90 minutes)')),
                ('large_party_duration_minutes', models.PositiveIntegerField(default=120, help_text='Sitting duration for large parties 5+ guests (e.g. 120 minutes)')),
                ('min_party_size', models.PositiveIntegerField(default=1)),
                ('max_party_size', models.PositiveIntegerField(default=16, help_text='Maximum party size allowed via online booking')),
                ('min_advance_minutes', models.PositiveIntegerField(default=30, help_text='Minimum advance notice in minutes required to book')),
                ('max_advance_days', models.PositiveIntegerField(default=60, help_text='How many days in advance guests can book')),
                ('auto_confirm_max_guests', models.PositiveIntegerField(default=6, help_text='Parties up to this size are confirmed automatically; larger parties require staff review')),
                ('cancellation_deadline_hours', models.PositiveIntegerField(default=2, help_text='Hours before reservation when free online cancellation is allowed')),
            ],
            options={
                'verbose_name': 'Reservation Setting',
                'verbose_name_plural': 'Reservation Settings',
            },
        ),
        migrations.AddField(
            model_name='table',
            name='dining_area',
            field=models.ForeignKey(blank=True, help_text='Optional linked dining area / room', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tables', to='reservations.diningarea'),
        ),
        migrations.AddField(
            model_name='table',
            name='min_capacity',
            field=models.PositiveSmallIntegerField(default=1, help_text='Minimum party size suitable for this table', validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='table',
            name='max_capacity',
            field=models.PositiveSmallIntegerField(default=4, help_text='Maximum party size accommodated by this table', validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='table',
            name='shape',
            field=models.CharField(choices=[('SQUARE', 'Square Table'), ('RECTANGULAR', 'Rectangular Table'), ('ROUND', 'Round Table'), ('BOOTH', 'Cozy Booth'), ('HIGH_TOP', 'High Top / Bar Table')], default='SQUARE', max_length=20),
        ),
        migrations.AddField(
            model_name='table',
            name='is_combinable',
            field=models.BooleanField(default=False, help_text='Can be combined with adjacent tables for large parties'),
        ),
        migrations.AddField(
            model_name='table',
            name='priority',
            field=models.PositiveIntegerField(default=0, help_text='Higher priority tables are assigned first'),
        ),
        migrations.AddField(
            model_name='table',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='table',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='table',
            name='number',
            field=models.CharField(help_text='Table identifier (e.g. T-1, T-2, Booth 4)', max_length=30, unique=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='guest_token',
            field=models.UUIDField(blank=True, db_index=True, help_text='Guest token allowing guest users to view or cancel reservation', null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='reservation_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='duration_minutes',
            field=models.PositiveIntegerField(default=90),
        ),
        migrations.AddField(
            model_name='reservation',
            name='end_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='dining_area',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reservations', to='reservations.diningarea'),
        ),
        migrations.AddField(
            model_name='reservation',
            name='seating_preference',
            field=models.CharField(choices=[('NO_PREFERENCE', 'No Preference'), ('WINDOW', 'Window Table'), ('BOOTH', 'Cozy Booth'), ('TERRACE', 'Conservatory / Garden Terrace'), ('QUIET_CORNER', 'Quiet Corner'), ('HIGH_TOP', 'High Top / Bar Area')], default='NO_PREFERENCE', max_length=30),
        ),
        migrations.AddField(
            model_name='reservation',
            name='occasion',
            field=models.CharField(choices=[('NONE', 'Regular Dining'), ('BIRTHDAY', 'Birthday Celebration'), ('ANNIVERSARY', 'Anniversary'), ('DATE_NIGHT', 'Date Night'), ('BUSINESS', 'Business Lunch / Dinner'), ('FAMILY_GATHERING', 'Family Gathering'), ('OTHER', 'Other Special Occasion')], default='NONE', max_length=30),
        ),
        migrations.AddField(
            model_name='reservation',
            name='dietary_notes',
            field=models.TextField(blank=True, help_text='e.g. 1 vegetarian, 1 nut allergy'),
        ),
        migrations.AddField(
            model_name='reservation',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='seated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='guest_name',
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='guest_email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='reference_code',
            field=models.CharField(blank=True, db_index=True, help_text='Unique booking reference code (e.g. RES-20261114-AB12CD)', max_length=36, unique=True),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='time_slot',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.CreateModel(
            name='ReservationNotification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('recipient', models.CharField(max_length=255)),
                ('notification_type', models.CharField(choices=[('CONFIRMATION', 'Booking Confirmation'), ('REMINDER', 'Booking Reminder'), ('STATUS_UPDATE', 'Status Update'), ('CANCELLATION', 'Cancellation Confirmation')], max_length=30)),
                ('channel', models.CharField(choices=[('SMS', 'SMS'), ('EMAIL', 'Email'), ('IN_APP', 'In-App')], default='SMS', max_length=15)),
                ('title', models.CharField(max_length=150)),
                ('message', models.TextField()),
                ('is_sent', models.BooleanField(default=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='reservations.reservation')),
            ],
            options={
                'verbose_name': 'Reservation Notification',
                'verbose_name_plural': 'Reservation Notifications',
                'ordering': ['-sent_at'],
            },
        ),
    ]


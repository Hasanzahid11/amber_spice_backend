import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('staff', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='staffmember',
            options={'ordering': ['name'], 'verbose_name': 'Staff Member', 'verbose_name_plural': 'Staff Members'},
        ),
        migrations.AddField(
            model_name='staffmember',
            name='email',
            field=models.EmailField(blank=True, help_text='Contact email address', max_length=254),
        ),
        migrations.AddField(
            model_name='staffmember',
            name='emergency_contact_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='staffmember',
            name='emergency_contact_phone',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='staffmember',
            name='hire_date',
            field=models.DateField(blank=True, help_text='Date joined restaurant team', null=True),
        ),
        migrations.AddField(
            model_name='staffmember',
            name='hourly_rate',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Hourly pay rate in EUR', max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='staffmember',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Active employee status (uncheck when staff member leaves)'),
        ),
        migrations.AddField(
            model_name='staffmember',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='staffmember',
            name='assigned_section',
            field=models.CharField(default='Main Floor', help_text='Floor zone, kitchen station, or delivery hub', max_length=100),
        ),
        migrations.AlterField(
            model_name='staffmember',
            name='phone',
            field=models.CharField(blank=True, help_text='Irish mobile or contact phone', max_length=30),
        ),
        migrations.AlterField(
            model_name='staffmember',
            name='role',
            field=models.CharField(choices=[('Head Chef', 'Head Chef'), ('Sous Chef', 'Sous Chef'), ('Station Cook', 'Station Cook'), ('Floor Manager', 'Floor Manager'), ('Host', 'Host'), ('Server', 'Server'), ('Cashier', 'Cashier'), ('Delivery Driver', 'Delivery Driver'), ('Bartender', 'Bartender / Barista'), ('Kitchen Porter', 'Kitchen Porter / Cleaner'), ('Staff', 'General Staff')], default='Server', max_length=50),
        ),
        migrations.AlterField(
            model_name='staffmember',
            name='shift',
            field=models.CharField(choices=[('Morning (10:00 - 16:00)', 'Morning (10:00 - 16:00)'), ('Evening (16:00 - 23:00)', 'Evening (16:00 - 23:00)'), ('Full Day', 'Full Day'), ('Custom Shift', 'Custom Shift')], default='Morning (10:00 - 16:00)', max_length=50),
        ),
        migrations.AlterField(
            model_name='staffmember',
            name='status',
            field=models.CharField(choices=[('active', 'Active (On Duty)'), ('break', 'On Break'), ('off-duty', 'Off Duty')], default='active', max_length=30),
        ),
        migrations.CreateModel(
            name='StaffShift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shift_date', models.DateField(db_index=True)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('title', models.CharField(blank=True, help_text='e.g. Lunch Service, Dinner Rush, Kitchen Prep', max_length=100)),
                ('station', models.CharField(blank=True, help_text='Specific station (e.g. Biryani & Grill, Front POS)', max_length=100)),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('confirmed', 'Confirmed'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('sick_leave', 'Sick Leave / Absent')], default='scheduled', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('staff_member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shifts', to='staff.staffmember')),
            ],
            options={
                'verbose_name': 'Staff Shift',
                'verbose_name_plural': 'Staff Shifts',
                'ordering': ['shift_date', 'start_time'],
            },
        ),
        migrations.CreateModel(
            name='StaffAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clock_in', models.DateTimeField(default=django.utils.timezone.now)),
                ('clock_out', models.DateTimeField(blank=True, null=True)),
                ('break_minutes', models.PositiveIntegerField(default=0)),
                ('total_hours', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('status', models.CharField(choices=[('on_duty', 'On Duty'), ('on_break', 'On Break'), ('completed', 'Completed')], default='on_duty', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('staff_member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='staff.staffmember')),
            ],
            options={
                'verbose_name': 'Staff Attendance',
                'verbose_name_plural': 'Staff Attendance Records',
                'ordering': ['-clock_in'],
            },
        ),
    ]


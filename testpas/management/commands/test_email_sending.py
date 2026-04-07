"""
Management command to test email sending and diagnose email issues.
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from testpas.models import Participant, EmailTemplate
from testpas.tasks import daily_timeline_check
from testpas.models import User

class Command(BaseCommand):
    help = 'Test email sending and diagnose email issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--participant-id',
            type=str,
            help='Test email for a specific participant ID',
        )
        parser.add_argument(
            '--template',
            type=str,
            help='Test a specific email template',
        )
        parser.add_argument(
            '--run-timeline-check',
            action='store_true',
            help='Run the daily timeline check for all users',
        )

    def handle(self, *args, **options):
        participant_id = options.get('participant_id')
        template_name = options.get('template')
        run_timeline_check = options.get('run_timeline_check')
        
        # Check email configuration
        self.stdout.write('\n' + '='*60)
        self.stdout.write('EMAIL CONFIGURATION CHECK')
        self.stdout.write('='*60)
        self.stdout.write(f'EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'EMAIL_HOST: {getattr(settings, "EMAIL_HOST", "NOT SET")}')
        self.stdout.write(f'EMAIL_PORT: {getattr(settings, "EMAIL_PORT", "NOT SET")}')
        self.stdout.write(f'EMAIL_USE_TLS: {getattr(settings, "EMAIL_USE_TLS", "NOT SET")}')
        self.stdout.write(f'EMAIL_HOST_USER: {getattr(settings, "EMAIL_HOST_USER", None) or "NOT SET"}')
        self.stdout.write(f'EMAIL_HOST_PASSWORD: {"SET" if getattr(settings, "EMAIL_HOST_PASSWORD", None) else "NOT SET"}')
        self.stdout.write(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        
        # Check if email templates exist
        self.stdout.write('\n' + '='*60)
        self.stdout.write('EMAIL TEMPLATES CHECK')
        self.stdout.write('='*60)
        templates = EmailTemplate.objects.all()
        if templates.exists():
            self.stdout.write(f'Found {templates.count()} email templates:')
            for template in templates:
                self.stdout.write(f'  - {template.name}')
        else:
            self.stdout.write(self.style.ERROR('No email templates found! Run: python manage.py seed_email_template'))
        
        # Test email sending
        if participant_id and template_name:
            try:
                participant = Participant.objects.get(participant_id=participant_id)
                self.stdout.write(f'\nTesting email sending for participant {participant_id}...')
                participant.send_email(template_name)
                self.stdout.write(self.style.SUCCESS(f'Successfully sent {template_name} email to {participant_id}'))
            except Participant.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Participant {participant_id} not found'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send email: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())
        
        # Run timeline check
        if run_timeline_check:
            self.stdout.write('\n' + '='*60)
            self.stdout.write('RUNNING DAILY TIMELINE CHECK')
            self.stdout.write('='*60)
            users = User.objects.all()
            self.stdout.write(f'Processing {users.count()} users...')
            for user in users:
                try:
                    daily_timeline_check(user)
                    self.stdout.write(f'  ✓ Processed user {user.id} ({user.username})')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Error processing user {user.id}: {str(e)}'))
        
        # Test basic email sending
        if not participant_id and not run_timeline_check:
            self.stdout.write('\n' + '='*60)
            self.stdout.write('TESTING BASIC EMAIL SENDING')
            self.stdout.write('='*60)
            try:
                send_mail(
                    'Test Email',
                    'This is a test email from the PAS project.',
                    settings.DEFAULT_FROM_EMAIL,
                    ['vuleson59@gmail.com'],
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS('✓ Test email sent successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed to send test email: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())
        
        self.stdout.write('\n' + '='*60 + '\n')


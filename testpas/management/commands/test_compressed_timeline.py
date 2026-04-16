from django.core.management.base import BaseCommand
from django.utils import timezone
from testpas.models import UserSurveyProgress, Participant
from testpas.utils import get_current_time
from testpas.timeline import get_study_day
from testpas import settings
import time

class Command(BaseCommand):
    help = 'Test the compressed timeline functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=5,
            help='Number of days to simulate (default: 5)'
        )
        parser.add_argument(
            '--participant',
            type=str,
            help='Specific participant ID to test'
        )

    def handle(self, *args, **options):
        days_to_simulate = options['days']
        participant_id = options['participant']
        
        self.stdout.write(f"Testing compressed timeline for {days_to_simulate} days...")
        
        # Get participants to test
        if participant_id:
            participants = Participant.objects.filter(participant_id=participant_id)
        else:
            participants = Participant.objects.all()
        
        if not participants.exists():
            self.stdout.write(self.style.WARNING("No participants found to test."))
            return
        
        for participant in participants:
            self.stdout.write(f"\nTesting participant: {participant.participant_id}")
            
            # Get user progress
            user_progress = UserSurveyProgress.objects.filter(
                user=participant.user, 
                survey__title="Eligibility Criteria"
            ).first()
            
            if not user_progress or not user_progress.day_1:
                self.stdout.write(f"  No valid progress found for {participant.participant_id}")
                continue
            
            # Simulate timeline progression
            for day in range(1, days_to_simulate + 1):
                current_time = get_current_time()
                study_day = get_study_day(
                    user_progress.day_1,
                    now=current_time,
                    compressed=settings.TIME_COMPRESSION,
                    seconds_per_day=settings.SECONDS_PER_DAY
                )
                
                self.stdout.write(f"  Day {day}: Study Day {study_day}")
                
                # Check what should happen on this study day
                if study_day == 1:
                    self.stdout.write(f"    → Should send Wave 1 survey email")
                elif study_day == 11:
                    self.stdout.write(f"    → Should send Wave 1 monitoring email")
                elif study_day == 21:
                    self.stdout.write(f"    → Should send Wave 1 missing code email (if applicable)")
                elif study_day == 29:
                    self.stdout.write(f"    → Should randomize participant")
                elif study_day == 57:
                    self.stdout.write(f"    → Should send Wave 2 survey email")
                elif study_day == 67:
                    self.stdout.write(f"    → Should send Wave 2 no monitoring email")
                elif study_day == 85:
                    self.stdout.write(f"    → Should send Wave 3 survey email (Day 85)")
                elif study_day == 92:
                    self.stdout.write(f"    → Should send Wave 3 monitoring email (Day 92)")
                elif study_day == 106:
                    self.stdout.write(f"    → Should send Wave 3 missing code email (if applicable) (Day 106)")
                
                # Wait for the compressed time to pass
                if settings.TIME_COMPRESSION:
                    time.sleep(settings.SECONDS_PER_DAY)
        
        self.stdout.write(self.style.SUCCESS(f"\nCompressed timeline test completed for {days_to_simulate} days")) 
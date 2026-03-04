# testpas/management/commands/seed_email_templates.py
from django.core.management.base import BaseCommand
from testpas.models import EmailTemplate

def to_html(body: str) -> str:
    """Preserve original line breaks while allowing HTML tags like <b> and <u>."""
    if not body:
        return ""
    # If it already looks like HTML, keep as-is.
    if "<p" in body or "<br" in body or "<div" in body:
        return body
    return f"<div style=\"white-space: pre-line;\">{body}</div>"

EMAIL_TEMPLATES = [
    {
        "name": "account_confirmation",
        "subject": "Confirm to Activate Your Account (Confident Moves Research)",
        # "body": "Dear {participant_id},\n\nPlease confirm your email by clicking the following link:\n{confirmation_link}\n\nThank you,\nPAS 2.0 Team"
        "body": "Hi {username},\n\nPlease click the following link to confirm your registration and activate your account:\n{confirmation_link}\n\n"
        "If you need any assistance or have any questions at any time, please contact Seungmin (“Seung”) Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n"
        "Sincerely,\nThe Confident Moves Research Team"
    },
    {
        "name": "wave1_survey_ready",
        "subject": "Wave 1 Online Survey Set – Ready",
        "body": "Hi {username},\n\nCongratulations! You are now enrolled as a participant in the study."
        "\n\nYour next task is to complete the Wave 1 Online Survey Set within 7 days. You will earn $5 in your Amazon electronic gift card account for completing this task. You will receive the accrued incentives after this study ends. <b>After 7 days</b>, this task will expire (i.e., no Amazon gift card for this task)."
        "\n\n· Link: {survey_link}\n\nYou may need to remember your username to complete the survey. Your username is: {username}."
        "\n\nYou may click the following link to view and download the consent document for your records:[a link that will be updated by researchers]\n\nIf you need any assistance or have any questions at any time, please contact Seungmin (“Seung”) Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\nSincerely,\n\nThe Confident Moves Research Team"
    },
    {
        "name": "wave1_monitor_ready",
        "subject": "Wave 1 Physical Activity Monitoring – Ready",
        "body": (
            "Hi {username},\n\n"
            "Your next task is to complete Wave 1 Physical Activity Monitoring.\n\n"
            "You need to enter a code on the website within 14 days to complete the physical activity monitoring. "
            "The code can be found in the mail package that will arrive at your address (the one you provided) in a few days.\n\n"
            "You will earn an additional $25 in your Amazon electronic gift card account for completing this task. "
            "You will receive the accrued incentives after this study ends. After 14 days, this task will expire (i.e., no Amazon gift card for this task).\n\n"
            "If you need any assistance or have any questions at any time, please contact Seungmin (“Seung”) Lee (Principal Investigator) "
            "at seunglee@iastate.edu or 517-898-0020.\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
        {
            'name': 'wave1_code_entry',
            'subject': 'Physical Activity Monitoring Tomorrow (Wave 1)',
            'body': (
                'Hi {username},\n\n'
                'You have successfully entered the access code for physical activity monitoring. Thank you!\n\n'
                'Please start wearing the monitor tomorrow for seven consecutive days. For example, if you enter the code on {code_date} (Fri), please wear the monitor starting on {start_date} (Sat) and continue wearing it until {end_date} (Fri).\n\n'
                'Please wear the monitor as much as possible during the seven consecutive days. To earn $25 in Amazon gift cards, please wear the monitor for at least 3 days with at least 10 hours each day. If this requirement is not met, we may not be able to provide the incentive.\n\n'
                'Please keep the yellow prepaid envelope. You will use it to return the monitor after the 7 days.\n\n'
                'If you need any assistance or have any questions at any time, please contact Seungmin (“Seung”) Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n'
                'Sincerely,\n\n'
                'The Confident Moves Research Team'
            )
        },
        {
            'name': 'wave1_survey_return',
            'subject': 'Return Monitor (Wave 1)',
            'body': (
                'Hi {username},\n\n'
                'The timeline for wearing the physical activity monitor is complete for this wave.\n\n'
                'Please return the monitor using the yellow prepaid envelope that was included in the mail package. If possible, within 3 days, visit a nearby USPS office or drop it in a USPS dropbox. The monitor is expensive and important to us.\n\n'
                'If you need any assistance or have any questions at any time, please contact Seungmin (“Seung”) Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n'
                'Sincerely,\n\n'
                'The Confident Moves Research Team'
            )
        },
        {
            'name': 'wave1_missing_code',
            'subject': 'Missing Code Entry (Wave 1)',
            'body': (
                'Hi {username},\n\n'
                'You missed the code entry (i.e., no $25 worth of Amazon electronic gift cards). However, you will still have more tasks now and in the future.\n\n'
                'You may have received our mail package—please check your mailbox. Please (a) open the package and (b) return the monitor using the yellow prepaid envelope. If possible, within 3 days, visit a nearby USPS office or drop it in a USPS dropbox. The monitor is expensive and important to us.\n\n'
                'If you need any assistance or have any questions at any time, please contact Seungmin (“Seung”) Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n'
                'Sincerely,\n\n'
                'The Confident Moves Research Team'
            )
        },
    {
        "name": "intervention_access_later",
        "subject": "Next Task in Approximately 4 week",
        "body": "Hi {username},\n\nWe recommend that you maintain your usual daily routines. We will email you again in approximately 4 weeks for the next task (i.e., completing an online survey set). Please regularly check your inbox. You will receive the accrued incentives after this study ends.\n\nIf you need any assistance or have any questions at any time, please contact Seungmin (\"Seung\") Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\nSincerely,\n\nThe Confident Moves Research Team"
    },
    {
        "name": "intervention_access_immediate",  # Information 17
        "subject": "Intervention Access Immediately",  # Information 17
        "body": (
            "Hi {username},\n\n"
            "Your access to the online physical activity intervention will begin immediately."
            "You may access the online physical activity intervention whenever you wish throughout approximately 4 weeks.\n\n"
            "· Please log in from the following website: (***Login link placeholder, will be updated in production***)\n"
            "· Your ID is: {username}. If you forgot your password, you may reset it on the website.\n\n"
            "If you complete at least 24 post-introductory challenges during the 4 weeks, you will earn an additional $20 "
            "in your Amazon electronic gift card account. Thoughtfully completing at least 24 post-introductory challenges "
            "may take approximately 2 hours. You will receive the accrued incentives after this study ends.\n\n"
            "We will also email you again in approximately 4 weeks for the next task (i.e., completing an online survey set). "
            "Please regularly check your inbox. You will receive the accrued incentives after this study ends.\n\n"
            "If you need any assistance or have any questions at any time, please contact Seungmin (\"Seung\") Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
    {
        "name": "wave2_survey_ready",
        "subject": "Wave 2 Online Survey Set – Ready",
        "body": (
            "Hi {username},\n\n"
            "Your next task is to complete the Wave 2 Online Survey Set within 7 days. You will earn $5 in your Amazon electronic gift card account for completing this task. "
            "You will receive the accrued incentives after this study ends. <b>After 7 days</b>, this task will expire (i.e., no Amazon gift card for this task).\n"
            "· Link: {survey_link}\n\n"
            "If you need any assistance or have any questions at any time, please contact Seungmin Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
    {
        "name": "wave2_no_monitoring",
        "subject": "No Wave 2 Physical Activity Monitoring",
        "body": (
            "Hi {username},\n\n"
            "There is no Wave 2 Physical Activity Monitoring.\n\n"
            "We will email you again in approximately 4 weeks for the next task (i.e., completing an online survey set). Please regularly check your inbox. You will receive the accrued incentives after this study ends.\n\n"
            "If you need any assistance or have any questions at any time, please contact Seungmin (“Seung”) Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },

    {
        "name": "wave3_survey_ready",
        "subject": "Wave 3 Online Survey Set – Ready",
        "body": (
            "Hi {username},\n\n"
            "Your next task is to complete the Wave 3 Online Survey Set within 7 days. You will earn $5 in your Amazon electronic gift card account for completing this task. "
            "You will receive the accrued incentives after this study ends. <b>After 7 days</b>, this task will expire (i.e., no Amazon gift card for this task).\n"
            "· Link: {survey_link}\n\n"
            "If you need any assistance or have any questions at any time, please contact Seungmin Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
    {
        "name": "wave3_monitoring_ready",
        "subject": "Wave 3 Physical Activity Monitoring – Ready",
        "body": (
            "Hi {username},\n\n"
            "Your next task is to complete Wave 3 Physical Activity Monitoring.\n"
            "You need to enter a code on the website within 14 days to complete the physical activity monitoring. The code can be found in the mail package that will arrive at your address (the one you provided) in a few days.\n\n"
            "You will earn an additional $30 in your Amazon electronic gift card account for completing this task. You will receive the accrued incentives after this study ends. After 14 days, this task will expire (i.e., no Amazon gift card for this task).\n\n"
            "If you need any assistance or have any questions at any time, please contact Seungmin Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
    {
        "name": "wave3_code_entry",
        "subject": "Physical Activity Monitoring Tomorrow (Wave 3)",
        "body": (
            "Hi {username},\n\n"
            "You have successfully entered the access code for physical activity monitoring. Thank you!\n\n"
            "Please start wearing the monitor tomorrow for seven consecutive days. For example, if you enter the code on {code_date} (Fri), please wear the monitor starting on {start_date} (Sat) and continue wearing it until {end_date} (Fri).\n\n"
            "Please wear the monitor as much as possible during the seven consecutive days. To earn $30 in Amazon gift cards, please wear the monitor for at least 3 days with at least 10 hours each day. If this requirement is not met, we may not be able to provide the incentive.\n\n"
            "Please keep the yellow prepaid envelope. You will use it to return the monitor after the 7 days.\n\n"
            "If you need any assistance or have any questions at any time, please contact Seungmin Lee (Principal Investigator) at seunglee@iastate.edu or 517-898-0020.\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
    {
        "name": "wave3_survey_monitor_return",
        "subject": "Return Monitor (Study End)",
        "body": (
            "Hi {username},\n\n"
            "The timeline for wearing the physical activity monitor is complete for this wave.\n\n"
            "Please return the monitor using the yellow prepaid envelope that was included in the mail package. If possible, within 3 days, visit a nearby USPS office or drop it in a USPS dropbox. The monitor is expensive and important to us.\n\n"
            "If you complete the above tasks, no further action is required for this study.\n\n"
            "Any funds earned on your Amazon electronic gift card account will be sent to you as soon as possible via your email. Thank you for the time you have contributed to this study!\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
    {
        "name": "wave3_missing_code",
        "subject": "Missing Code Entry (Study End)",
        "body": (
            "Hi {username},\n\n"
            "You missed the code entry (i.e., no $30 worth of Amazon electronic gift cards).\n\n"
            "You may have received our mail package—please check your mailbox. Please (a) open the package and (b) return the monitor using the yellow prepaid envelope. If possible, within 3 days, visit a nearby USPS office or drop it in a USPS dropbox. The monitor is expensive and important to us.\n\n"
            "If you complete the above tasks, no further action is required for this study.\n\n"
            "Any funds earned on your Amazon electronic gift card account will be sent to you as soon as possible via your email. Thank you for the time you have contributed to this study!\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
    {
        "name": "study_end",
        "subject": "Return Monitor (Study End)",
        "body": (
            "Hi {username},\n\n"
            "The timeline for wearing the physical activity monitor is complete for this wave.\n\n"
            "Please return the monitor using the yellow prepaid envelope that was included in the mail package. If possible, within 3 days, visit a nearby USPS office or drop it in a USPS dropbox. The monitor is expensive and important to us.\n\n"
            "If you complete the above tasks, no further action is required for this study.\n\n"
            "Any funds earned on your Amazon electronic gift card account will be sent to you as soon as possible via your email. Thank you for the time you have contributed to this study!\n\n"
            "Sincerely,\n\n"
            "The Confident Moves Research Team"
        )
    },
]

class Command(BaseCommand):
    help = "Seeds the database with default email templates."

    def handle(self, *args, **kwargs):
        for template in EMAIL_TEMPLATES:
            html_body = to_html(template["body"])
            obj, created = EmailTemplate.objects.get_or_create(
                name=template["name"],
                defaults={'subject': template["subject"], 'body': html_body}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Added email template: {template['name']}"))
            else:
                # Update existing template to ensure correct subject and body
                obj.subject = template["subject"]
                obj.body = html_body
                obj.save()
                self.stdout.write(self.style.WARNING(f"Updated template: {template['name']}"))
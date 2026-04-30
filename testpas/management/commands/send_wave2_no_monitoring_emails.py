from django.core.management.base import BaseCommand, CommandError

from testpas.models import Participant


class Command(BaseCommand):
    help = "Send Wave 2 no monitoring email (manual testing helper)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Send to one participant by Django username.",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Send to one participant by user email.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Send to all participants who have not already been marked as sent.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show who would receive the email without sending anything.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore wave2_monitoring_notice_sent flag and send anyway.",
        )

    def handle(self, *args, **options):
        username = options.get("username")
        email = options.get("email")
        send_all = options.get("all")
        dry_run = options.get("dry_run")
        force = options.get("force")

        selected_filters = [bool(username), bool(email), bool(send_all)]
        if sum(selected_filters) != 1:
            raise CommandError("Choose exactly one target option: --username, --email, or --all.")

        participants = Participant.objects.select_related("user")
        if username:
            participants = participants.filter(user__username=username)
        elif email:
            participants = participants.filter(user__email=email)
        elif send_all and not force:
            participants = participants.filter(wave2_monitoring_notice_sent=False)

        participants = list(participants)
        if not participants:
            self.stdout.write(self.style.WARNING("No matching participants found."))
            return

        self.stdout.write(f"Matched {len(participants)} participant(s).")
        sent_count = 0

        for participant in participants:
            already_sent = participant.wave2_monitoring_notice_sent
            if already_sent and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP {participant.participant_id} ({participant.user.username}) - already marked sent."
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"DRY RUN -> would send to {participant.participant_id} ({participant.user.username}, {participant.user.email})"
                )
                continue

            participant.send_email(
                "wave2_no_monitoring",
                extra_context={"username": participant.user.username},
            )
            if not already_sent:
                participant.wave2_monitoring_notice_sent = True
                participant.save(update_fields=["wave2_monitoring_notice_sent"])

            sent_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"SENT to {participant.participant_id} ({participant.user.username}, {participant.user.email})"
                )
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No emails were sent."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. Sent {sent_count} email(s)."))
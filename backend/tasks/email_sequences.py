"""Scheduled task — process due email sequences."""

from backend.services.sequence_service import SequenceService


async def scheduled_email_sequences():
    """Process all due email sequences."""
    sent = await SequenceService.process_due_sequences()
    if sent:
        print(f"[EmailSequences] Sent {len(sent)} emails")
    else:
        print("[EmailSequences] No due sequences")

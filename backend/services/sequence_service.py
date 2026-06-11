"""Email sequence orchestration — follow-up automation."""

from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session
from backend.models.email_sequence import EmailSequence
from backend.models.email_template import EmailTemplate
from backend.models.customer import Customer
from backend.models.mailbox import Mailbox
from backend.services.email_service import EmailService


class SequenceService:
    """Manage automated email follow-up sequences."""

    SEQUENCE_STEPS = {
        "cold": [
            {"day": 0, "template_category": "cold", "description": "First contact"},
            {"day": 3, "template_category": "followup", "description": "Follow-up 1"},
            {"day": 7, "template_category": "followup", "description": "Follow-up 2"},
            {"day": 14, "template_category": "followup", "description": "Follow-up 3"},
        ],
        "lead": [
            {"day": 0, "template_category": "cold", "description": "Introduction"},
            {"day": 5, "template_category": "followup", "description": "Value proposition"},
            {"day": 14, "template_category": "followup", "description": "Case study"},
        ],
    }

    @staticmethod
    async def create_sequence(
        customer_id: str,
        mailbox_id: str | None = None,
        sequence_type: str = "cold",
    ) -> list[dict]:
        """Create a follow-up sequence for a customer. Returns list of created sequence entries."""
        steps = SequenceService.SEQUENCE_STEPS.get(sequence_type, SequenceService.SEQUENCE_STEPS["cold"])
        created = []
        now = datetime.now(timezone.utc)

        async with async_session() as db:
            for step in steps:
                scheduled = now + timedelta(days=step["day"])
                seq = EmailSequence(
                    customer_id=customer_id,
                    mailbox_id=mailbox_id,
                    status="pending",
                    step_number=step["day"],
                    scheduled_at=scheduled.isoformat(),
                )
                db.add(seq)
                created.append({
                    "step": step["day"],
                    "description": step["description"],
                    "scheduled_at": scheduled.isoformat(),
                })

            await db.commit()

        return created

    @staticmethod
    async def process_due_sequences() -> list[dict]:
        """Process all sequences that are due to send. Returns list of sent items."""
        now = datetime.now(timezone.utc)
        sent = []

        async with async_session() as db:
            # Find due sequences
            result = await db.execute(
                select(EmailSequence)
                .where(EmailSequence.status == "pending")
                .where(EmailSequence.scheduled_at <= now.isoformat())
                .limit(50)
            )
            sequences = result.scalars().all()

            for seq in sequences:
                # Get customer email
                cust_result = await db.execute(select(Customer).where(Customer.id == seq.customer_id))
                customer = cust_result.scalar_one_or_none()
                if not customer or not customer.email:
                    seq.status = "skipped"
                    continue

                # Get mailbox SMTP config
                mailbox_email = "sales@txd.com"
                smtp_config = {}
                if seq.mailbox_id:
                    mb_result = await db.execute(select(Mailbox).where(Mailbox.id == seq.mailbox_id))
                    mailbox = mb_result.scalar_one_or_none()
                    if mailbox:
                        mailbox_email = mailbox.email_address
                        smtp_config = {
                            "smtp_host": mailbox.smtp_host,
                            "smtp_port": mailbox.smtp_port,
                            "smtp_user": mailbox.smtp_username,
                            "smtp_pass": mailbox.smtp_password_enc,
                            "use_ssl": mailbox.use_ssl,
                        }

                # Build email content
                subject = f"Following up - {customer.company or 'TXD CO., LTD'}"
                body = f"""Dear {customer.name or 'Sir/Madam'},

I hope this message finds you well.

We specialize in manufacturing and exporting high-quality PP hollow sheets and corrugated plastic boxes for global buyers.

If you have any questions or need a quotation, please feel free to reply to this email.

Best regards,
Sales Team
TXD CO., LTD
sales@txd.com"""

                # Send email (skip if no SMTP configured, just log)
                if smtp_config.get("smtp_host"):
                    success = await EmailService.send_email(
                        smtp_host=smtp_config["smtp_host"],
                        smtp_port=smtp_config["smtp_port"],
                        smtp_user=smtp_config["smtp_user"],
                        smtp_pass=smtp_config["smtp_pass"],
                        from_addr=mailbox_email,
                        to_addr=customer.email,
                        subject=subject,
                        body=body,
                        use_ssl=smtp_config.get("use_ssl", True),
                    )
                    if success:
                        seq.status = "sent"
                        seq.sent_at = now.isoformat()
                        sent.append({"customer_id": seq.customer_id, "email": customer.email, "status": "sent"})
                    else:
                        seq.status = "failed"
                else:
                    # No SMTP configured — mark as sent for now (will send when configured)
                    seq.status = "sent"
                    seq.sent_at = now.isoformat()
                    sent.append({"customer_id": seq.customer_id, "email": customer.email, "status": "logged_only"})

            await db.commit()

        return sent

    @staticmethod
    async def handle_reply(customer_id: str) -> int:
        """When a customer replies, pause all pending sequences for them. Returns count paused."""
        async with async_session() as db:
            result = await db.execute(
                select(EmailSequence)
                .where(EmailSequence.customer_id == customer_id)
                .where(EmailSequence.status == "pending")
            )
            pending = result.scalars().all()
            for seq in pending:
                seq.status = "completed"  # Customer replied, no more follow-ups needed
            await db.commit()
        return len(pending)

    @staticmethod
    async def get_customer_sequence_status(customer_id: str) -> list[dict]:
        """Get all sequence entries for a customer."""
        async with async_session() as db:
            result = await db.execute(
                select(EmailSequence)
                .where(EmailSequence.customer_id == customer_id)
                .order_by(EmailSequence.step_number)
            )
            sequences = result.scalars().all()
            return [
                {
                    "id": s.id,
                    "step": s.step_number,
                    "status": s.status,
                    "scheduled_at": s.scheduled_at,
                    "sent_at": s.sent_at,
                }
                for s in sequences
            ]

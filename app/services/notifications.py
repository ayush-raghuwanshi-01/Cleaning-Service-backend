"""
Notification engine for SMS, WhatsApp, and Email.

Currently uses console logging as a fallback. In production, integrate with:
- Twilio for SMS/WhatsApp
- SendGrid / SMTP for email
- WhatsApp Business API for richer messages
"""

import logging
from typing import Protocol

logger = logging.getLogger("notifications")


class NotificationChannel(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> bool: ...


class ConsoleChannel:
    """Fallback channel that logs to console."""

    def send(self, recipient: str, subject: str, body: str) -> bool:
        logger.info(
            "\n--- NOTIFICATION ---\nTo: %s\nSubject: %s\nBody:\n%s\n-------------------",
            recipient,
            subject,
            body,
        )
        return True


# Active channel(s) - swap with real implementations in production
channels: list[NotificationChannel] = [ConsoleChannel()]


def send_notification(
    recipient: str, subject: str, body: str, channel_type: str = "any"
) -> bool:
    """
    Send a notification through all available channels.

    Args:
        recipient: Phone number, email, or WhatsApp ID
        subject: Short subject line
        body: Message body
        channel_type: 'sms', 'email', 'whatsapp', or 'any'

    Returns:
        True if at least one channel succeeded
    """
    success = False
    for channel in channels:
        try:
            if channel.send(recipient, subject, body):
                success = True
        except Exception as e:
            logger.error("Notification channel failed: %s", e)
    return success


# --- Convenience templates ---

def notify_order_confirmed(customer_phone: str, customer_name: str, order_code: str, service_name: str, scheduled_date: str, scheduled_slot: str) -> None:
    send_notification(
        customer_phone,
        "Booking Confirmed",
        f"Hi {customer_name}! Your {service_name} booking ({order_code}) is confirmed for {scheduled_date} at {scheduled_slot}. Our team will arrive on time. - {__import__('app.core.config', fromlist=['get_settings']).get_settings().brand_name or 'Home Shine'}",
    )


def notify_cleaner_dispatched(customer_phone: str, customer_name: str, cleaner_name: str, order_code: str, scheduled_slot: str) -> None:
    send_notification(
        customer_phone,
        "Cleaner on the Way",
        f"Hi {customer_name}! {cleaner_name} is on the way for your booking {order_code}, scheduled for {scheduled_slot}. - Home Shine",
    )


def notify_payment_received(customer_phone: str, customer_name: str, amount: str, order_code: str) -> None:
    send_notification(
        customer_phone,
        "Payment Received",
        f"Hi {customer_name}! Payment of ₹{amount} for order {order_code} has been received. Thank you! - Home Shine",
    )


def notify_order_completed(customer_phone: str, customer_name: str, order_code: str) -> None:
    send_notification(
        customer_phone,
        "Service Completed",
        f"Hi {customer_name}! Your cleaning service ({order_code}) is complete. We'd love your feedback! - Home Shine",
    )


def notify_receipt(customer_email: str, customer_name: str, order_code: str, amount: str, pdf_link: str) -> None:
    send_notification(
        customer_email,
        "Invoice Receipt",
        f"Hi {customer_name}! Your invoice for order {order_code} (₹{amount}) is ready. Download: {pdf_link}",
    )
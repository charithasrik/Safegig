import os
import smtplib
from email.message import EmailMessage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_otp_email(user_email, otp):
    """
    Function to send a 6-digit OTP for password reset using SMTP.
    ALWAYS logs the OTP securely to console so active developers can use it without relying natively on email.
    """
    logger.info(f"\n==========================================")
    logger.info(f"PASSWORD RESET OTP for {user_email}")
    logger.info(f"Dev OTP: {otp}")
    logger.info(f"==========================================\n")
    
    mail_server = os.getenv('MAIL_SERVER')
    mail_port = os.getenv('MAIL_PORT')
    mail_username = os.getenv('MAIL_USERNAME')
    mail_password = os.getenv('MAIL_PASSWORD')
    mail_use_tls = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
    
    if not all([mail_server, mail_port, mail_username, mail_password]):
        logger.warning("SMTP configuration is incomplete. Falling back to console simulation.")
        return True

    try:
        msg = EmailMessage()
        msg['Subject'] = "Password Reset OTP - SafeGig"
        msg['From'] = mail_username
        msg['To'] = user_email
        msg.set_content(f"You have requested a password reset. Your 6-digit OTP is:\n\n{otp}\n\nThis OTP will expire in 15 minutes. If you did not request this, please ignore this email.")
        
        # Determine whether to use standard SMTP or SMTP_SSL based on TLS
        port = int(mail_port)
        if port == 465:
            server = smtplib.SMTP_SSL(mail_server, port)
        else:
            server = smtplib.SMTP(mail_server, port)
            if mail_use_tls:
                server.starttls()
                
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"Password reset OTP sent to {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {user_email}: {e}")
        return False

def send_reset_link_email(user_email, reset_url):
    """
    Function to send password reset link using SMTP.
    ALWAYS logs the link securely to console so active developers can use it without relying natively on email.
    """
    logger.info(f"\n==========================================")
    logger.info(f"PASSWORD RESET LINK for {user_email}")
    logger.info(f"{reset_url}")
    logger.info(f"==========================================\n")
    
    mail_server = os.getenv('MAIL_SERVER')
    mail_port = os.getenv('MAIL_PORT')
    mail_username = os.getenv('MAIL_USERNAME')
    mail_password = os.getenv('MAIL_PASSWORD')
    mail_use_tls = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
    
    if not all([mail_server, mail_port, mail_username, mail_password]):
        logger.warning("SMTP configuration is incomplete. Falling back to console simulation.")
        return True

    try:
        msg = EmailMessage()
        msg['Subject'] = "Password Reset Link - SafeGig"
        msg['From'] = mail_username
        msg['To'] = user_email
        msg.set_content(f"You have requested a password reset. Please click the following link to reset your password:\n\n{reset_url}\n\nThis link will expire in 1 hour. If you did not request this, please ignore this email.")
        
        # Determine whether to use standard SMTP or SMTP_SSL based on TLS
        port = int(mail_port)
        if port == 465:
            server = smtplib.SMTP_SSL(mail_server, port)
        else:
            server = smtplib.SMTP(mail_server, port)
            if mail_use_tls:
                server.starttls()
                
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"Password reset link sent to {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {user_email}: {e}")
        return False

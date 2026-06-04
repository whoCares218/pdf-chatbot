import os
import random
import smtplib

from datetime import datetime, timedelta

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash


def generate_otp():

    return str(random.randint(100000, 999999))


def send_otp_email(email, otp):

    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")

    message = MIMEMultipart()

    message["From"] = sender_email
    message["To"] = email
    message["Subject"] = "AskPDF Email Verification"

    body = f"""
Your AskPDF verification code is:

{otp}

This code expires in 10 minutes.
"""

    message.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP("smtp.gmail.com", 587)

    server.starttls()

    server.login(
        sender_email,
        sender_password
    )

    server.send_message(message)

    server.quit()


def create_user(cursor, connection, email, password):

    password_hash = generate_password_hash(password)

    cursor.execute(
        """
        INSERT INTO users
        (
            email,
            password_hash
        )
        VALUES
        (
            %s,
            %s
        )
        RETURNING id
        """,
        (
            email,
            password_hash
        )
    )

    user_id = cursor.fetchone()[0]

    connection.commit()

    return user_id


def get_user_by_email(cursor, email):

    cursor.execute(
        """
        SELECT
            id,
            email,
            password_hash,
            is_verified
        FROM users
        WHERE email = %s
        """,
        (email,)
    )

    return cursor.fetchone()


def save_otp(cursor, connection, user_id):

    otp = generate_otp()

    expires_at = datetime.now() + timedelta(minutes=10)

    cursor.execute(
        """
        INSERT INTO otp_codes
        (
            user_id,
            otp,
            expires_at
        )
        VALUES
        (
            %s,
            %s,
            %s
        )
        """,
        (
            user_id,
            otp,
            expires_at
        )
    )

    connection.commit()

    return otp


def verify_otp(
    cursor,
    connection,
    user_id,
    entered_otp
):

    cursor.execute(
        """
        SELECT
            otp,
            expires_at
        FROM otp_codes
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    if not result:

        return False

    otp, expires_at = result

    if datetime.now() > expires_at:

        return False

    if otp != entered_otp:

        return False

    cursor.execute(
        """
        UPDATE users
        SET is_verified = TRUE
        WHERE id = %s
        """,
        (user_id,)
    )

    connection.commit()

    return True


def login_user(
    cursor,
    email,
    password
):

    user = get_user_by_email(
        cursor,
        email
    )

    if not user:

        return None

    user_id = user[0]

    password_hash = user[2]

    is_verified = user[3]

    if not is_verified:

        return None

    if not check_password_hash(
        password_hash,
        password
    ):

        return None

    return user_id
import imaplib, email, os
from email.header import decode_header
from django.conf import settings

def download_resumes():
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login("your-email@gmail.com", "your-app-password")
    imap.select("inbox")

    status, messages = imap.search(None, '(SUBJECT "applying for job")')
    email_ids = messages[0].split()

    for num in email_ids:
        _, msg_data = imap.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()
            if filename and filename.endswith(".pdf"):
                filepath = os.path.join(settings.MEDIA_ROOT, "resumes", filename)
                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))
    imap.logout()

import imaplib

email_user = 'hr.bharatcrest@gmail.com'
email_pass = 'simp ewmn rnhc ezup'  # e.g., "abcd efgh ijkl mnop"

try:
    mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    mail.login(email_user, email_pass)
    mail.select('INBOX')
    print("Connection successful!")
except Exception as e:
    print(f"Error: {e}")

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict
from dotenv import load_dotenv
load_dotenv()

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

def send_email_with_file(to_email: str, subject: str, body: str, files_to_attach: list[str]) -> dict:

    # Validate required fields
    if not subject or not body:
        return {"error": "Subject and body are required"}

    # Validate final email
    if not to_email:
        return {"error": "Email address is required"}

    # Basic email format validation
    if '@' not in to_email or '.' not in to_email:
        return {"error": "Invalid email format"}

    # Add footer to the body
    final_body = body

    try:

        if not all([DEFAULT_FROM_EMAIL, EMAIL_HOST_PASSWORD]):
            raise ValueError("DEFAULT_FROM_EMAIL and EMAIL_HOST_PASSWORD must be set in the environment variables")

        # Create multipart message
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = f"NAIA Uninorte <{DEFAULT_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Reply-To"] = "naia@uninorte.edu.co"

        # Attach body text
        msg.attach(MIMEText(final_body, 'plain'))

        # Attach files from docs folder
        docs_folder = "docs"
        if files_to_attach:
            for filename in files_to_attach:
                file_path = os.path.join(docs_folder, filename)

                # Check if file exists in docs folder
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    try:
                        with open(file_path, 'rb') as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())

                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename={filename}')
                        msg.attach(part)
                        print(f"Archivo adjunto: {filename}")
                    except Exception as e:
                        print(f"Error al adjuntar {filename}: {str(e)}")
                else:
                    print(f"Archivo no encontrado en docs/: {filename}")

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            print("Iniciando conexión con el servidor de correo")
            server.login(DEFAULT_FROM_EMAIL, EMAIL_HOST_PASSWORD)
            print("Login exitoso")
            server.send_message(msg)
            print(f"Email enviado a {to_email}")
        return {"success": 'Email enviado correctamente'}
    
    except smtplib.SMTPAuthenticationError as e:
        error_msg = "Error de autenticación del correo"
        print(f"{error_msg}: {str(e)}")
        return {"error": error_msg}
    except smtplib.SMTPException as e:
        error_msg = "Error en el servidor de correo"
        print(f"{error_msg}: {str(e)}")
        return {"error": error_msg}
    except Exception as e:
        print(f"Error al enviar el email: {str(e)}")
        return {"error": str(e)}
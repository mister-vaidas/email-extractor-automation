from flask import Flask, request, render_template_string
from dotenv import load_dotenv
import psycopg2
import os

# Load environment variables
load_dotenv()

# Database credentials
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')

app = Flask(__name__)

@app.route('/unsubscribe')
def unsubscribe():
    email = request.args.get('email')

    if not email:
        return "Invalid request. Email parameter is missing.", 400

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cursor = conn.cursor()

        # Insert into unsubscribe table
        cursor.execute(
            "INSERT INTO unsubscribe_emails (email) VALUES (%s) ON CONFLICT (email) DO NOTHING;",
            (email.lower(),)
        )

        conn.commit()
        cursor.close()
        conn.close()

        print(f"Unsubscribed: {email}")

        # Simple confirmation page
        html = """
        <h2>You have been unsubscribed.</h2>
        <p>We're sorry to see you go.</p>
        """
        return render_template_string(html)

    except Exception as e:
        print(f"Error unsubscribing email {email}: {e}")
        return "An error occurred while processing your request.", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

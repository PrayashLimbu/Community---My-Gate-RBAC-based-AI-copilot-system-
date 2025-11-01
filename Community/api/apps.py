# Community/api/apps.py
from django.apps import AppConfig
from django.conf import settings
import firebase_admin
from firebase_admin import credentials
import os

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # --- NEW EXPLICIT INITIALIZATION ---
        # We will explicitly load the key file that we know works for Gemini.
        # This path is the one from your docker-compose.yml
        cred_path = '/app/firebase-key.json' 

        if os.path.exists(cred_path):
            try:
                if not firebase_admin._apps:
                    # Explicitly create credential object from the file
                    cred = credentials.Certificate(cred_path) 

                    firebase_admin.initialize_app(cred, {
                        # Ensure it uses the correct project ID from the key
                        'projectId': 'gen-lang-client-0431862828', 
                    })
                    print("Firebase Admin SDK initialized EXPLICITLY from gcp-key.json.")
                else:
                    print("Firebase Admin SDK already initialized.")
            except Exception as e:
                print(f"Error initializing Firebase Admin SDK from {cred_path}: {e}")
        else:
            print(f"CRITICAL: Key file {cred_path} not found. FCM will fail.")
        # --- END NEW INITIALIZATION ---
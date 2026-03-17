from google.oauth2 import id_token
from google.auth.transport import requests
from app.config import GOOGLE_CLIENT_ID
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class GoogleAuthService:
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verifies a Google ID token.
        Returns the decoded payload if valid and email is verified, None otherwise.
        """
        if not GOOGLE_CLIENT_ID:
            logger.error("GOOGLE_CLIENT_ID is not configured.")
            return None

        try:
            # Specify the CLIENT_ID of the app that accesses the backend:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)

            # ID token is valid. Verify that the email is verified.
            # This prevents spoofing with unverified Google accounts.
            if not idinfo.get('email_verified'):
                logger.warning(f"Google token verification failed: email not verified for sub {idinfo.get('sub')}")
                return None

            return idinfo
        except Exception as e:
            logger.error(f"Google token verification failed: {str(e)}")
            return None

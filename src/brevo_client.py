"""
Brevo API Client Module - FINAL FIX with Attachments
Handles all interactions with Brevo API for email templates and sending
Properly handles both {{ ATTRIBUTE }} and {{ contact.ATTRIBUTE }} templates
"""
import os
from typing import Dict, List, Optional
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import streamlit as st  # ✅ added for secrets


class BrevoClient:
    """Client for interacting with Brevo API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Brevo client with API key
        
        Args:
            api_key: Brevo API key (if None, loads from Streamlit secrets)
        """
        # 🔁 replaced dotenv + os.getenv with st.secrets
        self.api_key = api_key or st.secrets["BREVO_API_KEY"]
        
        if not self.api_key:
            raise ValueError("BREVO_API_KEY not found in secrets")
        
        # Load sender email from secrets
        self.default_sender_email = st.secrets["BREVO_SENDER_EMAIL"]
        self.default_sender_name = st.secrets.get("BREVO_SENDER_NAME", 'AppWeave Labs')
        
        # Configure Brevo API client
        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = self.api_key
        self.api_client = brevo_python.ApiClient(configuration)
        self.email_api = brevo_python.TransactionalEmailsApi(self.api_client)
        
    def send_template_email(
        self,
        to_email: str,
        template_id: int,
        params: Dict[str, str],
        to_name: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_name: Optional[str] = None,
        attachments: Optional[list] = None
    ) -> bool:
        """
        Send email using a template with dynamic parameters
        
        Args:
            to_email: Recipient email address
            template_id: Brevo template ID to use
            params: Dictionary of placeholder parameters
            to_name: Recipient name (optional)
            sender_email: Sender email (optional, uses .env default)
            sender_name: Sender name (optional, uses .env default)
            attachments: List of attachment dicts with 'name' and 'content' (base64) keys
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Prepare recipient
            recipient = {"email": to_email}
            if to_name:
                recipient["name"] = to_name
            
            # Prepare email object
            email_data = brevo_python.SendSmtpEmail(
                to=[recipient],
                template_id=template_id
            )
            
            # Add params - Brevo requires params field even if empty for some templates
            if params and len(params) > 0:
                email_data.params = params
                print(f"📝 Sending with parameters: {list(params.keys())}")
            else:
                # Send minimal params to avoid "params is blank" error
                # For templates using {{ contact.* }}, pass empty dict or minimal placeholder
                email_data.params = {}
                print("📝 No custom parameters (template may use contact attributes)")
            
            # Add attachments if provided
            if attachments:
                email_data.attachment = attachments
                print(f"📎 Attaching {len(attachments)} file(s)")
            
            # Use sender from secrets or provided parameter
            final_sender_email = sender_email or self.default_sender_email
            final_sender_name = sender_name or self.default_sender_name
            
            if final_sender_email:
                email_data.sender = {"email": final_sender_email, "name": final_sender_name}
                print(f"📤 Sending from: {final_sender_name} <{final_sender_email}>")
            else:
                print("⚠️  Warning: No sender email specified. Using template default.")
            
            # Send email
            response = self.email_api.send_transac_email(email_data)
            print(f"✅ Email sent successfully! Message ID: {response.message_id}")
            return True
            
        except ApiException as e:
            error_message = str(e)
            print(f"❌ Exception when sending email: {e}")
            
            # Provide helpful debugging information
            if "params is blank" in error_message:
                print("\n💡 TROUBLESHOOTING:")
                print("   Your template uses {{ contact.ATTRIBUTE }} syntax (e.g., {{ contact.FIRSTNAME }})")
                print("   This means:")
                print("   1. The recipient must exist in your Brevo Contacts")
                print("   2. The contact must have those attributes (FIRSTNAME, JOB_TITLE, etc.) set")
                print("\n   TO FIX:")
                print("   Option A: Add recipient to Brevo contacts with required attributes")
                print("   Option B: Edit template to use {{ FIRSTNAME }} instead of {{ contact.FIRSTNAME }}")
            
            return False

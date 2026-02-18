"""
Brevo API Client Module - FINAL FIX with Attachments
Handles all interactions with Brevo API for email templates and sending
Properly handles both {{ ATTRIBUTE }} and {{ contact.ATTRIBUTE }} templates
"""
import os
from typing import Dict, List, Optional
import brevo_python
from brevo_python.rest import ApiException
from dotenv import load_dotenv


class BrevoClient:
    """Client for interacting with Brevo API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Brevo client with API key
        
        Args:
            api_key: Brevo API key (if None, loads from environment)
        """
        load_dotenv()
        self.api_key = api_key or os.getenv('BREVO_API_KEY')
        
        if not self.api_key:
            raise ValueError("BREVO_API_KEY not found in environment or provided")
        
        # Load sender email from environment
        self.default_sender_email = os.getenv('BREVO_SENDER_EMAIL')
        self.default_sender_name = os.getenv('BREVO_SENDER_NAME', 'AppWeave Labs')
        
        # Configure Brevo API client
        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = self.api_key
        self.api_client = brevo_python.ApiClient(configuration)
        self.email_api = brevo_python.TransactionalEmailsApi(self.api_client)
    
    def get_all_templates(self) -> List[Dict]:
        """
        Fetch all email templates from Brevo
        
        Returns:
            List of template dictionaries with id, name, and subject
        """
        try:
            response = self.email_api.get_smtp_templates()
            templates = []
            
            for template in response.templates:
                templates.append({
                    'id': template.id,
                    'name': template.name,
                    'subject': template.subject,
                    'is_active': template.is_active
                })
            
            return templates
        except ApiException as e:
            print(f"Exception when calling get_smtp_templates: {e}")
            return []
    
    def get_template_by_id(self, template_id: int) -> Optional[Dict]:
        """
        Get specific template details by ID
        
        Args:
            template_id: Template ID to fetch
            
        Returns:
            Template details or None if not found
        """
        try:
            response = self.email_api.get_smtp_template(template_id)
            return {
                'id': response.id,
                'name': response.name,
                'subject': response.subject,
                'html_content': response.html_content,
                'is_active': response.is_active
            }
        except ApiException as e:
            print(f"Exception when calling get_smtp_template: {e}")
            return None
    
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
            
            # Use sender from .env or provided parameter
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
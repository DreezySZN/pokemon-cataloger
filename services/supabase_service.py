import logging
from typing import Dict
from supabase import create_client, Client


class SupabaseService:
    """Service for real-time Supabase database integration."""
    
    def __init__(self, settings):
        self.settings = settings
        self.enabled = settings.supabase_enabled
        self.client: Client = None
        self.table_name = settings.supabase_table_name
        
        if not settings.supabase_enabled:
            logging.warning("Supabase integration requested but supabase-py not available")
            return
        
        if self.enabled:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client."""

        try:
            if not self.settings.supabase_url or not self.settings.supabase_key:
                logging.error("SUPABASE: Missing URL or service role key in configuration")
                self.enabled = False
                return
            
            self.client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_key
            )
            
            logging.info("SUPABASE: Successfully connected to database")
            
        except Exception as e:
            logging.error("SUPABASE: Failed to initialize client: %s", e)
            self.enabled = False
    
    def insert_detection(self, detection_data: Dict):
        """Insert a card detection into Supabase.."""

        if not self.enabled or not self.client:
            return False
        
        try:
            supabase_data = {
                "account": detection_data.get("deviceAccount"),
                "password": detection_data.get("devicePassword"), 
                "timestamp": detection_data.get("timestamp"),
                "card_name": detection_data.get("card_name"),
                "rarity": detection_data.get("rarity"),
                "card_id": detection_data.get("card_id")
            }
            
            supabase_data = {k: v for k, v in supabase_data.items() if v is not None}
            
            result = self.client.table(self.table_name).insert(supabase_data).execute()
            
            if result.data:
                logging.info("SUPABASE: Successfully inserted detection for card: %s", 
                           detection_data.get("card_name"))
                return True
            else:
                logging.error("SUPABASE: Failed to insert detection - no data returned")
                return False
                
        except Exception as e:
            logging.error("SUPABASE: Failed to insert detection: %s", e, exc_info=True)
            return False
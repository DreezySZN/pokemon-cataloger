import discord
import logging
import os
import sys
from typing import Optional

from config.settings import Settings
from core.models import ModelManager
from handlers.message_handler import MessageHandler
from services.google_sheets import GoogleSheetsService
from utils.logger_stream import LoggerStream


class CardDetectionBot:
    """Main Discord bot class."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.is_fully_ready = False
        
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        
        self.model_manager = ModelManager(settings)
        self.message_handler = MessageHandler(settings, self.model_manager)
        self.google_sheets_service = GoogleSheetsService(settings) if settings.gsheets_enabled else None
        
        self._setup_logging()
        
        self._register_events()
    
    def _setup_logging(self):
        """Setup logging stream redirection."""

        sys.stdout = LoggerStream(logging.getLogger('STDOUT'), logging.INFO)
        sys.stderr = LoggerStream(logging.getLogger('STDERR'), logging.ERROR)
    
    def _register_events(self):
        """Register Discord event handlers."""
        
        @self.client.event
        async def on_ready():
            await self._on_ready()
        
        @self.client.event
        async def on_message(message):
            await self._on_message(message)
    
    async def _on_ready(self):
        """Handle bot ready event."""
        logging.info('Bot is ready and logged in as %s', self.client.user)
        
        os.makedirs(self.settings.temp_dir, exist_ok=True)
        
        if self.google_sheets_service:
            self.google_sheets_service.start_sync_thread()

        if self.settings.parse_history:
            await self.message_handler.parse_historical_messages(self.client, self.settings.target_channel_id)
        
        self.is_fully_ready = True
        logging.info("--- Bot is fully initialized and ready for new messages. ---")
    
    async def _on_message(self, message):
        """Handle new message event."""

        if not self.is_fully_ready:
            return
        
        # Skip if message the is from the bot, wrong channel, or has no attachments
        if (message.author == self.client.user or 
            message.channel.id != self.settings.target_channel_id or 
            not message.attachments):
            return
        
        await self.message_handler.process_message(message)
    
    def run(self):
        """Start the bot."""
        
        if not self.settings.bot_token:
            logging.critical('FATAL ERROR: Please set your bot_token in data/config.ini')
            return
        
        try:
            self.client.run(self.settings.bot_token)
        except discord.errors.LoginFailure:
            logging.critical("FATAL ERROR: Login failed. The bot token in data/config.ini is likely invalid.")
        except Exception as e:
            logging.critical("An unexpected error occurred at the top level: %s", e, exc_info=True)
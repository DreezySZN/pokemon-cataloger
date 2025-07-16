import asyncio
import discord
import logging
import os
from datetime import datetime

from services.logging_service import LoggingService
from services.vision_pipeline import VisionPipelineService
from services.supabase_service import SupabaseService
from utils.xml_parser import parse_device_account_from_xml
from config.settings import Settings


class MessageHandler:
    """Handles Discord message processing."""
    
    def __init__(self, settings, model_manager):
        self.settings = settings
        self.model_manager = model_manager
        self.vision_pipeline = VisionPipelineService(model_manager, settings)
        self.logging_service = LoggingService(settings)

        self.supabase_service = SupabaseService(settings) if settings.supabase_enabled else None
    
    async def process_message(self, message):
        """Process a Discord message with attachments."""

        image_attachments = [
            att for att in message.attachments 
            if att.filename.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        
        if not image_attachments:
            return None
        
        image_att = image_attachments[0]
        
        # Skip friend code images
        if "FRIENDCODE" in image_att.filename:
            return f"Skipping friend code image: `{image_att.filename}`"
        
        # Send processing message
        processing_msg = await message.channel.send(
            f"Analyzing attachments in message `{message.id}`..."
        )
        
        # Setup temp file paths
        image_path = os.path.join(self.settings.temp_dir, image_att.filename)
        temp_files_to_delete = [image_path]
        device_account = None
        device_password = None

        try:
            await image_att.save(image_path)
            
            xml_att = next(
                (att for att in message.attachments if att.filename.lower().endswith('.xml')), 
                None
            )
            
            if xml_att:
                xml_path = os.path.join(self.settings.temp_dir, xml_att.filename)
                await xml_att.save(xml_path)
                temp_files_to_delete.append(xml_path)
                device_account, device_password = parse_device_account_from_xml(xml_path)
            
            loop = asyncio.get_running_loop()
            analysis_reports = await loop.run_in_executor(
                None, self.vision_pipeline.run_vision_pipeline, image_path, image_att.filename
            )
            
            report = await self._generate_report(
                image_att.filename, message.id, analysis_reports, 
                message.created_at, device_account, device_password
            )
            
            if report:
                await processing_msg.edit(content=report)
            else:
                await processing_msg.delete()
            
            return report
            
        except Exception as e:
            logging.error("ERROR processing %s: %s", image_att.filename, e, exc_info=True)
            error_msg = f"An error occurred while processing `{image_att.filename}`: {type(e).__name__}"
            await processing_msg.edit(content=error_msg)
            return error_msg
            
        finally:
            for path in temp_files_to_delete:
                if os.path.exists(path):
                    os.remove(path)
    
    async def _generate_report(self, filename: str, message_id: int, analysis_reports: list, 
                             created_at: datetime, device_account: str, device_password: str):
        """Generate analysis report for a message."""

        report = f"**Analysis for `{filename}` (MSG ID: {message_id}):**\n"
        
        if not analysis_reports:
            report += "YOLO did not detect any cards."
        else:
            for i, data in enumerate(analysis_reports):
                report += f"\n--- **Detected Card #{i + 1}** ---\n"
                
                winning_algo, final_result = self.vision_pipeline.feature_matching.get_best_identification(data)
                
                if winning_algo and final_result:
                    card_id = final_result.get('card_id')
                    card_info = self.model_manager.get_card_info(card_id)
                    card_name = card_info.get('card_name', 'Unknown')
                    rarity = card_info.get('rarity', 'Unknown')
                    
                    report += f"Identified as **{card_name}** (Rarity: {rarity}) via `{winning_algo.upper()}`"
                    
                    log_entry = {
                        "timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "deviceAccount": device_account,
                        "devicePassword": device_password,
                        "card_name": card_name,
                        "rarity": rarity,
                        "card_id": card_id
                    }
                    
                    logging.info("CSV_LOG: Writing -> Time: %s, Card: %s, Rarity: %s", 
                               log_entry['timestamp'], card_name, rarity)
                    self.logging_service.log_detection(log_entry)

                    if self.settings.supabase_enabled and self.supabase_service:
                        logging.info("SUPABASE: Inserting detection for %s", card_name)
                        self.supabase_service.insert_detection(log_entry)
                else:
                    report += "Could not identify this card."
        
        return report
    
    async def parse_historical_messages(self, client, target_channel_id: int):
        """Parse historical messages in the target channel."""

        if not self.settings.parse_history:
            return
        
        logging.info("--- Starting historical message parsing. ---")
        target_channel = client.get_channel(target_channel_id)
        
        if not target_channel:
            logging.error("Could not find target channel with ID %s.", target_channel_id)
            return
        
        start_point = int(self.settings.last_message_id) if self.settings.last_message_id and self.settings.last_message_id.isdigit() else None
        
        try:
            await target_channel.send(
                f"`Starting historical data population. Will only process messages with XML files. "
                f"Resuming from message ID: {start_point or 'Beginning'}`"
            )
            
            messages_processed = 0
            final_message_id = start_point
            
            async for message in target_channel.history(
                limit=None, 
                after=discord.Object(id=start_point) if start_point else None, 
                oldest_first=True
            ):
                final_message_id = message.id
                
                has_xml = any(att.filename.lower().endswith('.xml') for att in message.attachments)
                
                if (message.author == client.user or 
                    not message.attachments or 
                    not has_xml):
                    
                    if not has_xml and message.attachments:
                        logging.info("HISTORICAL: Skipping message %s (no XML file found).", message.id)
                    
                    # Save progress and continue
                    self.settings.update_last_message_id(final_message_id)
                    continue
                
                try:
                    logging.info("HISTORICAL: Processing message %s (XML found)...", message.id)
                    await self.process_message(message)
                    messages_processed += 1
                    
                except Exception as e:
                    logging.error("Failed to process historical message %s: %s", message.id, e, exc_info=True)
                finally:
                    # Update progress
                    self.settings.update_last_message_id(final_message_id)
            
            # Disable historical parsing for next run
            logging.info("Historical parse complete. Disabling for next bot start.")
            self.settings.disable_historical_parsing()
            
            await target_channel.send(
                f"`Historical data population complete. Processed {messages_processed} new messages containing XML files.`"
            )
            
        except Exception as e:
            logging.error("An error occurred during historical message parsing: %s", e, exc_info=True)
            await target_channel.send(
                f"`An error occurred during historical data population. Check logs. Progress has been saved.`"
            )
        finally:
            logging.info("--- Finished historical message parsing. ---")
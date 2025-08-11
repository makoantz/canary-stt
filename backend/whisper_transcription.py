import asyncio
import gc
import torch
import librosa
import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from hardware_config import hardware_optimizer

logger = logging.getLogger(__name__)

class WhisperTranscriptionService:
    """Working transcription service using OpenAI Whisper as a fallback"""
    
    def __init__(self):
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.config = hardware_optimizer.optimize_for_hardware()
        hardware_optimizer.setup_cuda_optimizations()
        logger.info(f"Whisper service using device: {self.device}")
        
    async def load_model(self):
        """Load the Whisper model"""
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            logger.info("Loading OpenAI Whisper model...")
            
            import whisper
            # Use largest available Whisper model with RTX 3080 setup
            total_vram = self.config.get('total_vram_gb', 0)
            if total_vram > 18:
                model_size = "large-v3"  # Best quality, ~10GB VRAM needed
                logger.info(f"Using Whisper Large-v3 (highest quality) - {total_vram:.1f}GB VRAM available")
            elif total_vram > 10:
                model_size = "large-v2"  # Second best, ~6GB VRAM needed  
                logger.info(f"Using Whisper Large-v2 - {total_vram:.1f}GB VRAM available")
            elif total_vram > 4:
                model_size = "medium"    # Good balance, ~2GB VRAM needed
                logger.info(f"Using Whisper Medium - {total_vram:.1f}GB VRAM available")
            else:
                model_size = "base"      # Fallback for low VRAM
                logger.info(f"Using Whisper Base - {total_vram:.1f}GB VRAM available")
            
            self.model = whisper.load_model(
                model_size, 
                device=self.device
            )
            
            logger.info(f"Whisper {model_size} model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            return False
    
    async def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe audio file using Whisper"""
        try:
            if self.model is None:
                success = await self.load_model()
                if not success:
                    raise Exception("Failed to load transcription model")
            
            logger.info(f"Starting Whisper transcription: {audio_path}")
            
            # Check file exists and get duration
            if not os.path.exists(audio_path):
                raise Exception(f"Audio file not found: {audio_path}")
            
            # Get duration for progress estimation
            audio_data, sr = librosa.load(audio_path, sr=16000)
            duration = len(audio_data) / sr
            logger.info(f"Audio file duration: {duration:.2f}s")
            
            # Transcribe with Whisper
            logger.info("Running Whisper transcription...")
            
            # Run transcription in thread pool to avoid blocking
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            def transcribe_sync():
                # Load audio with librosa and pass numpy array instead of file path
                audio_array, _ = librosa.load(audio_path, sr=16000)
                
                return self.model.transcribe(
                    audio_array,
                    language=None,  # Auto-detect language with powerful hardware
                    fp16=torch.cuda.is_available()
                )
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, transcribe_sync)
            
            logger.info("Whisper transcription completed")
            
            return {
                "transcription": result["text"].strip(),
                "confidence": self._estimate_confidence(result.get("segments", [])),
                "duration": duration,
                "model": f"whisper-{self.model.__class__.__name__ if hasattr(self.model, '__class__') else 'base'}",
                "language": result.get("language", "en")
            }
            
        except Exception as e:
            logger.error(f"Whisper transcription failed: {str(e)}")
            return {
                "transcription": "",
                "error": str(e),
                "confidence": 0.0,
                "duration": 0.0
            }
        finally:
            # Hardware memory cleanup
            if self.config.get('clear_cache_after_inference', False):
                hardware_optimizer.cleanup_memory()
    
    def _estimate_confidence(self, segments) -> float:
        """Estimate confidence from Whisper segments"""
        if not segments:
            return 0.8  # Default reasonable confidence
        
        # Average the segment probabilities if available
        confidences = []
        for segment in segments:
            if 'avg_logprob' in segment:
                # Convert log prob to rough confidence (0-1)
                conf = min(1.0, max(0.0, (segment['avg_logprob'] + 1.0) / 1.0))
                confidences.append(conf)
        
        if confidences:
            return sum(confidences) / len(confidences)
        else:
            return 0.85  # Default confidence if no segment info

# Global service instance
whisper_transcription_service = WhisperTranscriptionService()
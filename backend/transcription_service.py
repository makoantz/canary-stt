import asyncio
import gc
import torch
import librosa
import soundfile as sf
import numpy as np
import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from hardware_config import hardware_optimizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CanaryTranscriptionService:
    def __init__(self):
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.config = hardware_optimizer.optimize_for_hardware()
        hardware_optimizer.setup_cuda_optimizations()
        hardware_optimizer.setup_multi_gpu()
        logger.info(f"Using device: {self.device}")
        logger.info(f"Hardware config: {self.config}")
        
    async def load_model(self):
        """Load the best available transcription model"""
        try:
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            logger.info("Loading transcription models (priority: Canary > Whisper > Mock)...")
            
            # First try to load real Canary-Qwen-2.5B model
            try:
                logger.info("Attempting to load Canary-Qwen-2.5B model...")
                from canary_transcription import canary_transcription_service
                
                success = await canary_transcription_service.load_model()
                if success:
                    logger.info("✅ Using Canary-Qwen-2.5B model")
                    self.model = "canary"
                    self.canary_service = canary_transcription_service
                    return True
                else:
                    logger.warning("Canary model loading failed, trying alternatives...")
                    
            except Exception as canary_error:
                logger.warning(f"Canary model not available: {canary_error}")
            
            # Fallback to Whisper (real speech-to-text)
            try:
                logger.info("Loading Whisper as speech-to-text service...")
                from whisper_transcription import whisper_transcription_service
                
                success = await whisper_transcription_service.load_model()
                if success:
                    logger.info("✅ Using Whisper model")
                    self.model = "whisper"
                    self.whisper_service = whisper_transcription_service
                    return True
                else:
                    raise Exception("Whisper loading failed")
                    
            except Exception as whisper_error:
                logger.warning(f"Whisper loading failed: {whisper_error}")
            
            # Last resort: mock service (for development only)
            logger.warning("⚠️  Using mock transcription service - no real models available")
            logger.warning("Install 'openai-whisper' or ensure Canary model access for real transcription")
            self.model = "mock"
            return True
            
        except Exception as e:
            logger.error(f"Failed to load any transcription model: {str(e)}")
            return False
    
    
    async def preprocess_audio(self, audio_path: str) -> Optional[str]:
        """Convert audio to required format (16kHz mono WAV)"""
        try:
            logger.info(f"preprocess_audio called with: {audio_path}")
            logger.info(f"audio_path type: {type(audio_path)}")
            logger.info(f"audio_path exists: {os.path.exists(audio_path) if audio_path else 'audio_path is None/empty'}")
            
            if not audio_path or not os.path.exists(audio_path):
                logger.error(f"Invalid audio path: {audio_path}")
                return None
            
            # Get file info
            file_size = os.path.getsize(audio_path)
            file_extension = Path(audio_path).suffix.lower()
            logger.info(f"File: {Path(audio_path).name}, Size: {file_size} bytes, Format: {file_extension}")
                
            output_path = audio_path.replace(Path(audio_path).suffix, '_processed.wav')
            logger.info(f"Output path will be: {output_path}")
            
            # Try to load audio with librosa (handles most formats)
            logger.info("Loading audio with librosa...")
            try:
                audio, sr = librosa.load(
                    audio_path, 
                    sr=self.config['target_sample_rate'], 
                    mono=self.config['mono_channel']
                )
                logger.info(f"Audio loaded with librosa: {len(audio)/sr:.2f}s duration, {sr}Hz sample rate")
                
            except Exception as librosa_error:
                logger.warning(f"Librosa failed: {librosa_error}")
                
                # Try with pydub for M4A and other formats
                logger.info("Trying pydub conversion...")
                temp_wav = audio_path.replace(Path(audio_path).suffix, '_temp.wav')
                
                try:
                    from pydub import AudioSegment
                    from pydub.utils import which
                    
                    # Load audio with pydub
                    logger.info(f"Loading {file_extension} file with pydub...")
                    
                    if file_extension == '.m4a':
                        audio_segment = AudioSegment.from_file(audio_path, format="m4a")
                    elif file_extension == '.mp3':
                        audio_segment = AudioSegment.from_mp3(audio_path)
                    elif file_extension == '.wav':
                        audio_segment = AudioSegment.from_wav(audio_path)
                    elif file_extension == '.flac':
                        audio_segment = AudioSegment.from_file(audio_path, format="flac")
                    elif file_extension == '.ogg':
                        audio_segment = AudioSegment.from_ogg(audio_path)
                    else:
                        audio_segment = AudioSegment.from_file(audio_path)
                    
                    # Convert to mono and set sample rate
                    audio_segment = audio_segment.set_channels(1).set_frame_rate(self.config['target_sample_rate'])
                    
                    # Export as WAV
                    audio_segment.export(temp_wav, format="wav")
                    logger.info("Pydub conversion successful")
                    
                    if os.path.exists(temp_wav):
                        logger.info("Loading converted audio with librosa...")
                        audio, sr = librosa.load(temp_wav, sr=self.config['target_sample_rate'])
                        os.remove(temp_wav)  # Clean up temp file
                        logger.info(f"Audio loaded after pydub: {len(audio)/sr:.2f}s duration")
                    else:
                        raise Exception("Pydub conversion failed - no output file")
                        
                except ImportError:
                    logger.error("Pydub not available and librosa failed")
                    return None
                except Exception as pydub_error:
                    logger.error(f"Pydub conversion failed: {pydub_error}")
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                    
                    # Last resort: try ffmpeg if available  
                    logger.info("Trying ffmpeg as last resort...")
                    try:
                        import subprocess
                        cmd = [
                            'ffmpeg', '-i', audio_path,
                            '-ac', '1',  # mono
                            '-ar', str(self.config['target_sample_rate']),  # sample rate
                            '-y', temp_wav  # overwrite output
                        ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                        
                        if result.returncode == 0 and os.path.exists(temp_wav):
                            logger.info("FFmpeg conversion successful")
                            audio, sr = librosa.load(temp_wav, sr=self.config['target_sample_rate'])
                            os.remove(temp_wav)
                            logger.info(f"Audio loaded after ffmpeg: {len(audio)/sr:.2f}s duration")
                        else:
                            logger.error(f"FFmpeg failed: {result.stderr}")
                            return None
                            
                    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
                        logger.error(f"FFmpeg fallback failed: {e}")
                        return None
            
            if len(audio) == 0:
                logger.error("Audio file appears to be empty or corrupted")
                return None
            
            # Normalize audio if configured
            if self.config['normalize_audio']:
                audio = librosa.util.normalize(audio)
                logger.info("Audio normalized")
            
            # Save as optimized format
            logger.info(f"Saving processed audio to: {output_path}")
            sf.write(output_path, audio, self.config['target_sample_rate'])
            
            # Verify output file was created
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                logger.info(f"Audio preprocessed successfully: {audio_path} -> {output_path} ({output_size} bytes)")
                return output_path
            else:
                logger.error(f"Output file was not created: {output_path}")
                return None
            
        except Exception as e:
            logger.error(f"Audio preprocessing failed with exception: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            
            # Provide helpful error message for M4A files
            if file_extension == '.m4a':
                logger.error("M4A format requires FFmpeg system installation")
                logger.error("Please convert your M4A file to WAV/MP3 format or install FFmpeg")
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def transcribe_audio(self, audio_path: str, job_id: str = None) -> Dict[str, Any]:
        """Transcribe audio file using Canary model"""
        try:
            if self.model is None:
                await self.load_model()
            
            # Preprocess audio
            processed_path = await self.preprocess_audio(audio_path)
            if not processed_path:
                file_extension = Path(audio_path).suffix.lower()
                if file_extension == '.m4a':
                    raise Exception("M4A format is not supported without FFmpeg. Please convert to WAV or MP3 format.")
                else:
                    raise Exception(f"Audio preprocessing failed for {file_extension} file. Please try a different format (WAV, MP3 recommended).")
            
            # Choose transcription method based on loaded model
            if self.model == "canary":
                # Use real Canary-Qwen-2.5B model
                logger.info("Using Canary-Qwen-2.5B for transcription")
                return await self.canary_service.transcribe_audio(processed_path, job_id)
            elif self.model == "whisper":
                # Use Whisper for real transcription
                logger.info("Using Whisper for transcription")
                return await self.whisper_service.transcribe_audio(processed_path)
            else:
                # Mock transcription for development/testing
                logger.warning("Using mock transcription - no real model loaded")
                return await self._mock_transcription(processed_path, job_id)
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            return {
                "transcription": "",
                "error": str(e),
                "confidence": 0.0,
                "duration": 0.0
            }
        finally:
            # Cleanup processed file
            if 'processed_path' in locals() and processed_path and os.path.exists(processed_path):
                try:
                    os.remove(processed_path)
                    logger.info(f"Cleaned up processed file: {processed_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup processed file: {cleanup_error}")
            
            # Hardware memory cleanup
            if self.config.get('clear_cache_after_inference', False):
                hardware_optimizer.cleanup_memory()
            
            # Monitor memory pressure
            memory_pressure = hardware_optimizer.check_memory_pressure()
            if memory_pressure.get('system', False) or any(memory_pressure.get('gpus', {}).values()):
                logger.warning("System under memory pressure after transcription")
                hardware_optimizer.cleanup_memory()
    
    
    async def _mock_transcription(self, audio_path: str, job_id: str = None) -> Dict[str, Any]:
        """Mock transcription for development"""
        try:
            logger.info("Starting mock transcription...")
            audio, sr = librosa.load(audio_path, sr=16000, mono=True)
            duration = len(audio) / sr
            
            logger.info(f"Mock transcription: Processing {duration:.2f}s audio file")
            
            # Simulate processing time with progress logging
            processing_time = min(duration * 0.1, 3.0)
            steps = 5
            for i in range(steps):
                await asyncio.sleep(processing_time / steps)
                progress = ((i + 1) / steps) * 100
                logger.info(f"Mock transcription progress: {progress:.0f}%")
            
            logger.info("Mock transcription completed")
            
            return {
                "transcription": f"Mock transcription for {Path(audio_path).name} (duration: {duration:.2f}s). This is a placeholder transcription that would be replaced by actual Canary-Qwen-2.5B model output. The audio file has been successfully processed and would normally contain the speech-to-text conversion from the NVIDIA Canary-Qwen-2.5B model.",
                "confidence": 0.85,
                "duration": duration,
                "model": "mock-canary-qwen-2.5b"
            }
            
        except Exception as e:
            logger.error(f"Mock transcription failed: {str(e)}")
            return {
                "transcription": "Transcription failed",
                "error": str(e),
                "confidence": 0.0,
                "duration": 0.0
            }

# Global service instance
transcription_service = CanaryTranscriptionService()
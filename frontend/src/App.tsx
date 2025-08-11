import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

interface TranscriptionJob {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  filename: string;
  progress?: {
    stage: string;
    percent: number;
  };
  result?: {
    transcription: string;
    confidence: number;
    duration: number;
    model?: string;
  };
  error?: string;
}

interface UploadedFile {
  file: File;
  job: TranscriptionJob | null;
  uploading: boolean;
  error: string | null;
}

function App() {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  const SUPPORTED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.opus'];
  
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const validFiles: File[] = [];
    const invalidFiles: File[] = [];

    acceptedFiles.forEach(file => {
      const extension = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
      if (SUPPORTED_EXTENSIONS.includes(extension) || file.type.startsWith('audio/')) {
        validFiles.push(file);
      } else {
        invalidFiles.push(file);
      }
    });

    if (invalidFiles.length > 0) {
      const invalidNames = invalidFiles.map(f => f.name).join(', ');
      const supportedList = SUPPORTED_EXTENSIONS.join(', ');
      alert(`Unsupported files: ${invalidNames}\n\nSupported formats: ${supportedList}`);
    }

    if (validFiles.length === 0) {
      return;
    }

    const newFiles: UploadedFile[] = validFiles.map(file => ({
      file,
      job: null,
      uploading: false,
      error: null
    }));

    setUploadedFiles(prev => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': SUPPORTED_EXTENSIONS
    },
    multiple: true
  });

  const uploadFile = async (index: number) => {
    const fileData = uploadedFiles[index];
    if (!fileData || fileData.uploading) return;

    setUploadedFiles(prev => prev.map((item, i) => 
      i === index ? { ...item, uploading: true, error: null } : item
    ));

    try {
      const formData = new FormData();
      formData.append('file', fileData.file);

      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const job: TranscriptionJob = {
        job_id: response.data.job_id,
        status: response.data.status,
        filename: fileData.file.name
      };

      setUploadedFiles(prev => prev.map((item, i) => 
        i === index ? { ...item, job, uploading: false } : item
      ));

    } catch (error: any) {
      setUploadedFiles(prev => prev.map((item, i) => 
        i === index ? { 
          ...item, 
          uploading: false, 
          error: error.response?.data?.detail || 'Upload failed' 
        } : item
      ));
    }
  };

  const transcribeFile = async (index: number) => {
    const fileData = uploadedFiles[index];
    if (!fileData?.job || fileData.job.status !== 'pending') return;

    setIsProcessing(true);

    try {
      await axios.post(`${API_BASE_URL}/transcribe/${fileData.job.job_id}`);
      
      setUploadedFiles(prev => prev.map((item, i) => 
        i === index && item.job ? { 
          ...item, 
          job: { ...item.job, status: 'processing' }
        } : item
      ));

      // Poll for results
      pollForResult(index, fileData.job.job_id);

    } catch (error: any) {
      let errorMessage = error.response?.data?.detail || 'Transcription failed';
      
      // Provide helpful message for M4A files
      if (fileData.file.name.toLowerCase().endsWith('.m4a') && 
          errorMessage.includes('M4A format is not supported')) {
        errorMessage = 'M4A format requires additional system components. Please convert your file to WAV or MP3 format and try again.';
      }
      
      setUploadedFiles(prev => prev.map((item, i) => 
        i === index ? { 
          ...item, 
          error: errorMessage 
        } : item
      ));
      setIsProcessing(false);
    }
  };

  const pollForResult = async (index: number, jobId: string) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;

    const poll = async () => {
      attempts++;
      
      try {
        // First check status for progress updates
        const statusResponse = await axios.get(`${API_BASE_URL}/status/${jobId}`);
        const statusData = statusResponse.data;

        // Update progress if available
        if (statusData.progress) {
          setUploadedFiles(prev => prev.map((item, i) => 
            i === index && item.job ? { 
              ...item, 
              job: { ...item.job, progress: statusData.progress }
            } : item
          ));
        }

        // Check if completed
        if (statusData.status === 'completed') {
          const resultResponse = await axios.get(`${API_BASE_URL}/result/${jobId}`);
          const job = resultResponse.data;
          
          setUploadedFiles(prev => prev.map((item, i) => 
            i === index ? { ...item, job } : item
          ));
          setIsProcessing(false);
          return;
        }

        if (statusData.status === 'failed') {
          const resultResponse = await axios.get(`${API_BASE_URL}/result/${jobId}`);
          const job = resultResponse.data;
          
          setUploadedFiles(prev => prev.map((item, i) => 
            i === index ? { ...item, error: job.error || 'Transcription failed' } : item
          ));
          setIsProcessing(false);
          return;
        }

        if (attempts < maxAttempts) {
          setTimeout(poll, 2000); // Poll every 2 seconds for better progress updates
        } else {
          setUploadedFiles(prev => prev.map((item, i) => 
            i === index ? { ...item, error: 'Transcription timeout' } : item
          ));
          setIsProcessing(false);
        }

      } catch (error) {
        console.error('Polling error:', error);
        if (attempts < maxAttempts) {
          setTimeout(poll, 2000);
        } else {
          setUploadedFiles(prev => prev.map((item, i) => 
            i === index ? { ...item, error: 'Failed to get result' } : item
          ));
          setIsProcessing(false);
        }
      }
    };

    poll();
  };

  const downloadTranscription = async (index: number) => {
    const fileData = uploadedFiles[index];
    if (!fileData?.job?.job_id || fileData.job.status !== 'completed') return;

    try {
      const response = await axios.get(`${API_BASE_URL}/download/${fileData.job.job_id}`, {
        responseType: 'blob'
      });

      // Create download link
      const blob = new Blob([response.data], { type: 'text/plain' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      
      // Extract filename from content-disposition header or create default
      const contentDisposition = response.headers['content-disposition'];
      let filename = `${fileData.file.name}_transcription.txt`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
      
    } catch (error: any) {
      console.error('Download failed:', error);
      alert('Failed to download transcription: ' + (error.response?.data?.detail || error.message));
    }
  };

  const removeFile = (index: number) => {
    const fileData = uploadedFiles[index];
    if (fileData.job?.job_id) {
      axios.delete(`${API_BASE_URL}/job/${fileData.job.job_id}`).catch(console.error);
    }
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🎤 Canary STT Transcription</h1>
        <p>High-Performance Speech-to-Text Service</p>
      </header>

      <main className="main-content">
        <div className="upload-section">
          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
            <input {...getInputProps()} />
            <div className="upload-content">
              <div className="upload-icon">📁</div>
              {isDragActive ? (
                <p>Drop the audio files here...</p>
              ) : (
                <div>
                  <p>Drag & drop audio files here, or click to select</p>
                  <p className="supported-formats">
                    Supported: WAV, MP3, M4A, AAC, FLAC, OGG, WMA, OPUS
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="files-section">
          {uploadedFiles.map((fileData, index) => (
            <div key={index} className="file-card">
              <div className="file-header">
                <div className="file-info">
                  <h3>{fileData.file.name}</h3>
                  <p>{(fileData.file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
                <button 
                  className="remove-button"
                  onClick={() => removeFile(index)}
                  title="Remove file"
                >
                  ×
                </button>
              </div>

              <div className="file-actions">
                {!fileData.job && !fileData.uploading && (
                  <button 
                    className="action-button upload"
                    onClick={() => uploadFile(index)}
                  >
                    Upload
                  </button>
                )}

                {fileData.uploading && (
                  <div className="loading">Uploading...</div>
                )}

                {fileData.job?.status === 'pending' && (
                  <button 
                    className="action-button transcribe"
                    onClick={() => transcribeFile(index)}
                    disabled={isProcessing}
                  >
                    Transcribe
                  </button>
                )}

                {fileData.job?.status === 'processing' && (
                  <div className="processing-container">
                    <div className="loading">
                      Processing... 
                      {fileData.job.progress && (
                        <span className="progress-text">
                          ({fileData.job.progress.stage} - {fileData.job.progress.percent}%)
                        </span>
                      )}
                    </div>
                    {fileData.job.progress && (
                      <div className="progress-bar-container">
                        <div className="progress-bar">
                          <div 
                            className="progress-bar-fill" 
                            style={{ width: `${fileData.job.progress.percent}%` }}
                          ></div>
                        </div>
                        <div className="progress-percentage">
                          {fileData.job.progress.percent}%
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {fileData.error && (
                <div className="error-message">
                  Error: {fileData.error}
                </div>
              )}

              {fileData.job?.status === 'completed' && fileData.job.result && (
                <div className="transcription-result">
                  <div className="result-header">
                    <h4>Transcription Result</h4>
                    <div className="result-actions">
                      <button 
                        className="action-button save"
                        onClick={() => downloadTranscription(index)}
                        title="Save transcription to file"
                      >
                        💾 Save
                      </button>
                    </div>
                  </div>
                  <div className="result-meta">
                    {fileData.job.result.duration && (
                      <span>Duration: {formatDuration(fileData.job.result.duration)}</span>
                    )}
                    {fileData.job.result.confidence && (
                      <span>Confidence: {(fileData.job.result.confidence * 100).toFixed(1)}%</span>
                    )}
                  </div>
                  <div className="transcription-text">
                    {fileData.job.result.transcription}
                  </div>
                  {fileData.job.result.model && (
                    <div className="model-info">
                      Model: {fileData.job.result.model}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {uploadedFiles.length === 0 && (
          <div className="empty-state">
            <h3>No files uploaded yet</h3>
            <p>Upload audio files to get started with transcription</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
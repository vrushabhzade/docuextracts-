import React, { useState, useRef, useCallback } from "react";
import Webcam from "react-webcam";
import { Upload, Camera, FileText, Image as ImageIcon, RotateCcw } from "lucide-react";

export default function UploadCapture({ onFileSelect, isProcessing }) {
  const [activeTab, setActiveTab] = useState("upload"); // 'upload' or 'camera'
  const [imagePreview, setImagePreview] = useState(null);
  const [fileObject, setFileObject] = useState(null);
  const [docType, setDocType] = useState("ration_card");
  
  const webcamRef = useRef(null);
  const fileInputRef = useRef(null);

  // Drag and drop states
  const [isDragActive, setIsDragActive] = useState(false);

  // Handle Drag events
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  // Process selected file
  const processFile = (file) => {
    if (file && file.type.startsWith("image/")) {
      setFileObject(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  // Handle Webcam Capture
  const capturePhoto = useCallback(() => {
    const imageSrc = webcamRef.current.getScreenshot();
    if (imageSrc) {
      setImagePreview(imageSrc);
      
      // Convert base64 format back to a File object for multipart uploads
      fetch(imageSrc)
        .then((res) => res.blob())
        .then((blob) => {
          const file = new File([blob], "captured_document.png", { type: "image/png" });
          setFileObject(file);
        });
    }
  }, [webcamRef]);

  // Reset current selection
  const handleReset = () => {
    setImagePreview(null);
    setFileObject(null);
  };

  // Submit selected image to backend
  const handleSubmit = (e) => {
    e.preventDefault();
    if (!fileObject) return;
    onFileSelect(fileObject, docType);
  };

  return (
    <div className="glass-panel rounded-2xl p-6 glow-blue border-slate-800">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <FileText className="text-blue-500 w-5 h-5" />
        Input Document Source
      </h2>

      {!imagePreview ? (
        <div>
          {/* Tabs header */}
          <div className="flex border-b border-slate-800 mb-6">
            <button
              onClick={() => setActiveTab("upload")}
              className={`flex-1 pb-3 text-sm font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
                activeTab === "upload"
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Upload className="w-4 h-4" />
              Upload Image File
            </button>
            <button
              onClick={() => setActiveTab("camera")}
              className={`flex-1 pb-3 text-sm font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
                activeTab === "camera"
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Camera className="w-4 h-4" />
              Capture via Camera
            </button>
          </div>

          {/* Upload panel */}
          {activeTab === "upload" && (
            <div
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                isDragActive
                  ? "border-blue-500 bg-blue-500/5"
                  : "border-slate-800 bg-slate-900/30 hover:border-slate-700 hover:bg-slate-900/50"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept="image/*"
                onChange={handleFileChange}
              />
              <Upload className="w-10 h-10 mx-auto text-slate-500 mb-4" />
              <p className="font-semibold text-slate-300">Drag & drop your document here</p>
              <p className="text-xs text-slate-500 mt-1">Supports PNG, JPG, JPEG up to 10MB</p>
              <button
                type="button"
                className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg text-sm transition-all"
              >
                Browse File
              </button>
            </div>
          )}

          {/* Camera panel */}
          {activeTab === "camera" && (
            <div className="flex flex-col items-center">
              <div className="overflow-hidden rounded-xl bg-slate-900 border border-slate-800 w-full aspect-video flex items-center justify-center relative mb-4">
                <Webcam
                  audio={false}
                  ref={webcamRef}
                  screenshotFormat="image/png"
                  videoConstraints={{ facingMode: "environment" }}
                  className="w-full h-full object-cover"
                />
              </div>
              <button
                onClick={capturePhoto}
                type="button"
                className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl shadow-lg transition-all"
              >
                <Camera className="w-5 h-5" />
                Snapshot Photo
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Image Preview and Configuration */
        <form onSubmit={handleSubmit}>
          <div className="relative rounded-xl overflow-hidden border border-slate-800 aspect-video mb-6 group bg-slate-900 flex items-center justify-center">
            <img src={imagePreview} alt="Preview" className="max-h-full object-contain" />
            <button
              onClick={handleReset}
              type="button"
              className="absolute top-3 right-3 p-2 bg-slate-950/80 hover:bg-slate-900 text-slate-300 rounded-full transition-all border border-slate-800"
              title="Reset Image"
              disabled={isProcessing}
            >
              <RotateCcw className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
                Document Schema Definition
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                disabled={isProcessing}
                className="w-full bg-slate-900 border border-slate-800 text-slate-200 rounded-xl px-4 py-2.5 focus:outline-none focus:border-blue-500 transition-all font-semibold"
              >
                <option value="ration_card">Indian Ration Card (Purity details, Members)</option>
                <option value="admit_card">Exam Admit Card (Candidate, Roll, Venue, Subjects)</option>
                <option value="custom_form">Custom Key-Value Form (Generic schema fallback)</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={isProcessing || !fileObject}
              className={`w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${
                isProcessing
                  ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                  : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-indigo-900/30"
              }`}
            >
              <FileText className="w-5 h-5" />
              {isProcessing ? "Extracting Structured Data..." : "Run Extraction Pipeline"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

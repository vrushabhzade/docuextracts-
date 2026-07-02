import React, { useState, useEffect } from "react";
import UploadCapture from "./components/UploadCapture";
import ProcessingStages from "./components/ProcessingStages";
import ExtractedFieldsEditor from "./components/ExtractedFieldsEditor";
import apiClient from "./api/client";
import { 
  FileText, 
  History, 
  TrendingUp, 
  Layers, 
  CheckCircle, 
  UserCheck, 
  Clock, 
  ExternalLink 
} from "lucide-react";

export default function App() {
  // Pipeline processing states
  const [isProcessing, setIsProcessing] = useState(false);
  const [pipelineStage, setPipelineStage] = useState("idle"); // idle, preprocessing, ocr, extraction, validation, done, error
  const [pipelineError, setPipelineError] = useState(null);
  
  // App data states
  const [extractionData, setExtractionData] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState({
    total_documents_processed: 0,
    total_documents_reviewed: 0,
    overall_accuracy_percentage: 100.0,
    field_accuracies: []
  });

  // Initial fetch on mount
  useEffect(() => {
    fetchHistory();
    fetchStats();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await apiClient.get("/api/history");
      setHistory(res.data);
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await apiClient.get("/api/stats");
      setStats(res.data);
    } catch (err) {
      console.error("Failed to load statistics:", err);
    }
  };

  // Triggers the Multipart upload & API call
  const handleFileSelect = async (file, docType) => {
    setIsProcessing(true);
    setPipelineStage("preprocessing");
    setPipelineError(null);
    setExtractionData(null);

    // Simulate backend stage progressions during the HTTP request lifecycle
    const stageTimeline = [
      { stage: "ocr", delay: 800 },
      { stage: "extraction", delay: 2500 },
      { stage: "validation", delay: 5500 }
    ];
    
    const timers = stageTimeline.map(item => 
      setTimeout(() => {
        setPipelineStage(item.stage);
      }, item.delay)
    );

    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", docType);

    try {
      const response = await apiClient.post("/api/extract", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      // Clear timers
      timers.forEach(t => clearTimeout(t));

      setExtractionData(response.data);
      setPipelineStage("done");
      fetchHistory(); // Refresh logs
      fetchStats();   // Refresh accuracy stats
    } catch (err) {
      // Clear timers
      timers.forEach(t => clearTimeout(t));
      
      const errMsg = err.response?.data?.detail || "An unexpected error occurred during extraction.";
      setPipelineStage("error");
      setPipelineError(errMsg);
    } finally {
      setIsProcessing(false);
    }
  };

  // Load a historical document into the active editor
  const handleLoadHistoryItem = (item) => {
    setExtractionData({
      document_id: item.document_id,
      document_type: item.document_type,
      fields: item.fields,
      image_url: item.image_url,
      processed_image_preview: "", // Preview is not critical for past viewings
      raw_ocr_text: item.raw_ocr_text,
      processing_time_ms: item.processing_time_ms
    });
    // Scroll smoothly to editor
    const editorEl = document.getElementById("extraction-editor-panel");
    if (editorEl) {
      editorEl.scrollIntoView({ behavior: "smooth" });
    }
  };

  // Callback when human corrections are successfully saved
  const handleSaveSuccess = () => {
    fetchHistory();
    fetchStats();
  };

  return (
    <div className="min-h-screen bg-slate-950 pb-20">
      {/* Top Banner Header */}
      <header className="border-b border-slate-900 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-tr from-blue-600 to-indigo-600 p-2.5 rounded-xl shadow-lg shadow-blue-500/10">
              <Layers className="text-white w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                DocuExtract
                <span className="text-xs bg-slate-900 border border-slate-800 text-blue-400 px-2 py-0.5 rounded-md font-mono">
                  v1.0.0
                </span>
              </h1>
              <p className="text-xs text-slate-500">AWS-Native Structured Document Data Extraction</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-850">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            AWS ECS Fargate Connected
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-6 mt-8 space-y-8">
        
        {/* Statistics Row */}
        <section className="grid grid-cols-1 md:grid-cols-4 gap-5">
          <div className="glass-panel p-5 rounded-2xl border-slate-850 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-slate-500 font-semibold uppercase">Total Extractions</p>
              <p className="text-2xl font-bold text-slate-200 mt-0.5">
                {stats.total_documents_processed}
              </p>
            </div>
          </div>

          <div className="glass-panel p-5 rounded-2xl border-slate-850 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-slate-500 font-semibold uppercase">Reviewed (Corrections)</p>
              <p className="text-2xl font-bold text-slate-200 mt-0.5">
                {stats.total_documents_reviewed}
              </p>
            </div>
          </div>

          <div className="glass-panel p-5 rounded-2xl border-slate-850 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-slate-500 font-semibold uppercase">Extraction Accuracy</p>
              <p className="text-2xl font-bold text-slate-200 mt-0.5">
                {stats.overall_accuracy_percentage}%
              </p>
            </div>
          </div>

          {/* Mini field metrics scroll */}
          <div className="glass-panel p-4 rounded-2xl border-slate-850 flex flex-col justify-center">
            <p className="text-[10px] text-slate-400 font-bold uppercase mb-1.5 flex items-center gap-1">
              <CheckCircle className="w-3.5 h-3.5 text-blue-500" />
              Field-level accuracy
            </p>
            {stats.field_accuracies.length > 0 ? (
              <div className="h-[46px] overflow-y-auto space-y-1 pr-1">
                {stats.field_accuracies.map(f => (
                  <div key={f.field_name} className="flex justify-between items-center text-[11px]">
                    <span className="text-slate-500 truncate max-w-[120px]">{f.field_name}</span>
                    <span className="font-mono text-slate-300 font-semibold">{f.accuracy_percentage}%</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No correction data yet.</p>
            )}
          </div>
        </section>

        {/* Input & Stage Flow & History Log */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Inputs Column */}
          <div className="lg:col-span-8 space-y-6">
            <UploadCapture onFileSelect={handleFileSelect} isProcessing={isProcessing} />
            
            {/* Show processing stages only when active or completed with status */}
            {(isProcessing || pipelineStage !== "idle") && (
              <ProcessingStages stage={pipelineStage} error={pipelineError} />
            )}
          </div>

          {/* History Column */}
          <div className="lg:col-span-4 glass-panel rounded-2xl p-5 border-slate-800 self-stretch flex flex-col max-h-[580px]">
            <h3 className="text-md font-bold mb-4 flex items-center gap-2 text-slate-300">
              <History className="w-4 h-4 text-blue-500" />
              Recent Pipeline Logs
            </h3>
            
            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {history.length > 0 ? (
                history.map(item => (
                  <div
                    key={item.document_id}
                    onClick={() => handleLoadHistoryItem(item)}
                    className="p-3 bg-slate-900/40 border border-slate-850 hover:border-slate-850 hover:bg-slate-900/80 rounded-xl cursor-pointer transition-all flex flex-col gap-2 group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-300 capitalize">
                        {item.document_type.replace("_", " ")}
                      </span>
                      <span className="text-[10px] text-slate-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span className="font-mono truncate max-w-[150px]">{item.document_id}</span>
                      <span className="flex items-center gap-0.5 text-blue-500 group-hover:text-blue-400 transition-colors font-semibold">
                        Inspect
                        <ExternalLink className="w-2.5 h-2.5" />
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-600">
                  <FileText className="w-8 h-8 mb-2 stroke-1" />
                  <p className="text-xs">No documents processed in history.</p>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Extraction Editor Panel (Anchored) */}
        {extractionData && (
          <section id="extraction-editor-panel" className="scroll-mt-24 space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-900 pb-3">
              <span className="px-2.5 py-1 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-xs font-mono font-bold">
                ID: {extractionData.document_id}
              </span>
              <h2 className="text-lg font-bold text-slate-200">
                Extraction Pipeline Results
              </h2>
            </div>
            
            <ExtractedFieldsEditor 
              data={extractionData} 
              onSaveSuccess={handleSaveSuccess} 
            />
          </section>
        )}

      </main>
    </div>
  );
}

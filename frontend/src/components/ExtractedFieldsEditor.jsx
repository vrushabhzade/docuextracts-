import React, { useState, useRef, useEffect } from "react";
import ConfidenceBadge from "./ConfidenceBadge";
import apiClient from "../api/client";
import { Check, Edit3, Image as ImageIcon, Save, Loader2, AlertCircle } from "lucide-react";

export default function ExtractedFieldsEditor({ data, onSaveSuccess }) {
  const { document_id, document_type, fields, image_url, processed_image_preview } = data;
  
  // Track edited values
  const [formFields, setFormFields] = useState([]);
  const [hoveredField, setHoveredField] = useState(null);
  
  // Image sizing states for bounding box scaling
  const imgRef = useRef(null);
  const [imgScale, setImgScale] = useState({ scaleX: 1, scaleY: 1 });
  const [previewMode, setPreviewMode] = useState("original"); // 'original' or 'processed'
  
  // Save status states
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // 'success' or 'error'
  const [errorMessage, setErrorMessage] = useState("");

  // Initialize fields on data change
  useEffect(() => {
    if (fields) {
      setFormFields(fields.map(f => ({ ...f })));
    }
    setSaveStatus(null);
  }, [fields]);

  // Recalculate scaling ratio when image loads or window resizes
  const updateImageScale = () => {
    if (imgRef.current) {
      const { clientWidth, clientHeight, naturalWidth, naturalHeight } = imgRef.current;
      if (naturalWidth && naturalHeight) {
        setImgScale({
          scaleX: clientWidth / naturalWidth,
          scaleY: clientHeight / naturalHeight,
        });
      }
    }
  };

  useEffect(() => {
    window.addEventListener("resize", updateImageScale);
    return () => window.removeEventListener("resize", updateImageScale);
  }, [previewMode, data]);

  // Handle input changes
  const handleFieldChange = (name, newValue) => {
    setFormFields(prev =>
      prev.map(f => (f.name === name ? { ...f, value: newValue } : f))
    );
  };

  // Submit corrections to backend
  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      const payload = {
        document_id,
        corrected_fields: formFields.map(f => ({ name: f.name, value: f.value })),
      };
      
      await apiClient.post("/api/extract/correct", payload);
      setSaveStatus("success");
      setTimeout(() => {
        if (onSaveSuccess) onSaveSuccess();
      }, 1500);
    } catch (err) {
      logger.error("Failed to save corrections", err);
      setSaveStatus("error");
      setErrorMessage(err.response?.data?.detail || "Could not connect to API server.");
    } finally {
      setIsSaving(false);
    }
  };

  // Formats field keys nicely (e.g. member_1_name -> Member 1 Name)
  const formatFieldName = (name) => {
    return name
      .split("_")
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  // Find bounding box for hovered field
  const activeBboxField = formFields.find(f => f.name === hoveredField && f.bbox);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Left Column: Image Viewer with OCR Bounding Box overlays */}
      <div className="lg:col-span-6 glass-panel rounded-2xl p-5 border-slate-800 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <ImageIcon className="w-4 h-4 text-blue-500" />
            Document Viewer
          </h3>
          <div className="flex bg-slate-900 rounded-lg p-0.5 border border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setPreviewMode("original")}
              className={`px-3 py-1 rounded-md transition-colors ${
                previewMode === "original"
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Original
            </button>
            <button
              onClick={() => setPreviewMode("processed")}
              className={`px-3 py-1 rounded-md transition-colors ${
                previewMode === "processed"
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Preprocessed
            </button>
          </div>
        </div>

        {/* Scaled overlay container */}
        <div className="relative rounded-xl overflow-hidden border border-slate-850 bg-slate-950 flex items-center justify-center min-h-[300px]">
          <img
            ref={imgRef}
            src={previewMode === "original" ? image_url : processed_image_preview}
            alt="Source Document"
            onLoad={updateImageScale}
            className="w-full max-h-[600px] object-contain"
          />

          {/* Render bounding box highlight */}
          {activeBboxField && activeBboxField.bbox && (
            <div
              className="absolute border-2 border-dashed border-blue-500 bg-blue-500/10 pointer-events-none rounded transition-all duration-150 glow-blue"
              style={{
                left: `${activeBboxField.bbox[0] * imgScale.scaleX}px`,
                top: `${activeBboxField.bbox[1] * imgScale.scaleY}px`,
                width: `${activeBboxField.bbox[2] * imgScale.scaleX}px`,
                height: `${activeBboxField.bbox[3] * imgScale.scaleY}px`,
              }}
            />
          )}
        </div>
        <p className="text-[10px] text-slate-500 mt-2 italic text-center">
          *Hover over field cards on the right to locate text segments in the image above.
        </p>
      </div>

      {/* Right Column: Editable Fields */}
      <div className="lg:col-span-6 glass-panel rounded-2xl p-5 border-slate-800 flex flex-col">
        <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">
          Structured Extractions Editor
        </h3>

        {/* Scrollable list of fields */}
        <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
          {formFields.map(field => (
            <div
              key={field.name}
              onMouseEnter={() => setHoveredField(field.name)}
              onMouseLeave={() => setHoveredField(null)}
              className={`p-3.5 rounded-xl border transition-all ${
                hoveredField === field.name
                  ? "border-blue-500 bg-blue-500/5"
                  : "border-slate-850 bg-slate-900/30 hover:border-slate-800"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-slate-400">
                  {formatFieldName(field.name)}
                </span>
                <ConfidenceBadge confidence={field.confidence} />
              </div>
              <input
                type="text"
                value={field.value === null ? "" : field.value}
                onChange={(e) => handleFieldChange(field.name, e.target.value)}
                placeholder="Not found"
                className="w-full bg-slate-900 border border-slate-850 text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-all font-mono"
              />
            </div>
          ))}
        </div>

        {/* Control actions */}
        <div className="mt-6 pt-4 border-t border-slate-850">
          <button
            onClick={handleSave}
            disabled={isSaving || saveStatus === "success"}
            className={`w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${
              saveStatus === "success"
                ? "bg-emerald-600 text-white"
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20"
            }`}
          >
            {isSaving ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Saving Changes...
              </>
            ) : saveStatus === "success" ? (
              <>
                <Check className="w-5 h-5" />
                Saved Successfully
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                Confirm & Save Changes
              </>
            )}
          </button>

          {saveStatus === "error" && (
            <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center gap-2 text-xs text-rose-400">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

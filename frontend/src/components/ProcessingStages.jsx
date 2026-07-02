import React from "react";
import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";

export default function ProcessingStages({ stage, error }) {
  // Steps in the pipeline
  const steps = [
    {
      id: "preprocessing",
      label: "Image Preprocessing",
      description: "Grayscale conversion, deskewing, denoising, and adaptive contrast.",
    },
    {
      id: "ocr",
      label: "Multilingual OCR Engine",
      description: "Extracting raw word values and bounding boxes (Tesseract).",
    },
    {
      id: "extraction",
      label: "AI Schema Extraction",
      description: "Mapping fields to structured JSON output (Gemini 2.0 Flash).",
    },
    {
      id: "validation",
      label: "Validation & Confidence Check",
      description: "Applying Verhoeff checksums, formats, and rating accuracy.",
    },
  ];

  // Helper to determine status of a step
  const getStepStatus = (stepId, index) => {
    if (error && stage === stepId) return "failed";
    
    const stageOrder = ["preprocessing", "ocr", "extraction", "validation", "done"];
    const currentIdx = stageOrder.indexOf(stage);
    const stepIdx = stageOrder.indexOf(stepId);

    if (currentIdx > stepIdx) return "completed";
    if (currentIdx === stepIdx) return "active";
    return "pending";
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border-slate-800">
      <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
        {stage !== "done" && stage !== "idle" && (
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
        )}
        Pipeline Processing Stages
      </h3>

      <div className="relative border-l border-slate-850 pl-6 ml-3 space-y-8">
        {steps.map((step, index) => {
          const status = getStepStatus(step.id, index);

          let icon = <Circle className="w-5 h-5 text-slate-700 bg-slate-950" />;
          let textStyle = "text-slate-500";
          let borderStyle = "border-transparent";

          if (status === "completed") {
            icon = <CheckCircle2 className="w-5 h-5 text-emerald-500 bg-slate-950 fill-emerald-500/10" />;
            textStyle = "text-slate-300";
          } else if (status === "active") {
            icon = <Loader2 className="w-5 h-5 text-blue-500 bg-slate-950 animate-spin" />;
            textStyle = "text-blue-400 font-medium";
            borderStyle = "border-blue-500/10 bg-blue-500/5";
          } else if (status === "failed") {
            icon = <AlertCircle className="w-5 h-5 text-rose-500 bg-slate-950 fill-rose-500/10" />;
            textStyle = "text-rose-400 font-medium";
            borderStyle = "border-rose-500/10 bg-rose-500/5";
          }

          return (
            <div
              key={step.id}
              className={`relative flex gap-4 p-3.5 rounded-xl border transition-all ${borderStyle}`}
            >
              {/* Dot absolute placement overlap */}
              <div className="absolute -left-[37px] top-[18px] z-10">
                {icon}
              </div>

              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h4 className={`text-sm ${textStyle}`}>{step.label}</h4>
                  {status === "active" && (
                    <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-md font-semibold tracking-wide uppercase animate-pulse">
                      Running
                    </span>
                  )}
                  {status === "failed" && (
                    <span className="text-[10px] bg-rose-500/10 text-rose-400 px-2 py-0.5 rounded-md font-semibold tracking-wide uppercase">
                      Error
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">{step.description}</p>
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <div className="mt-6 p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 text-xs text-rose-400 leading-relaxed font-mono">
          <p className="font-semibold mb-1">Execution Error:</p>
          {error}
        </div>
      )}
    </div>
  );
}

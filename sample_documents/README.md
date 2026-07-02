# Sample Documents

This directory is a placeholder for sample document images that you can use to test the DocuExtract pipeline.

## Document Types Supported

The pipeline is configured with optimized Pydantic extraction schemas and OpenCV settings for three categories:

1. **Ration Cards** (`ration_card`):
   - Place photos of state-issued Ration Cards.
   - The pipeline will attempt to extract: `card_number`, `head_of_household`, `address`, `category` (e.g., APL, BPL, AAY), and family members (`name`, `aadhaar_number`, `relationship`, `age`).

2. **Exam Admit Cards** (`admit_card`):
   - Place photos of school or entrance exam admit cards.
   - The pipeline will attempt to extract: `candidate_name`, `roll_number`, `exam_name`, `exam_date`, `center_code`, and `subjects`.

3. **Custom Forms** (`custom_form`):
   - Place photos of any other structured documents, handwritten forms, or applications.
   - The pipeline will fall back to a generic key-value matching schema.

## Adding Test Images

1. Take clear, well-lit photos of your test documents.
2. Save them to this directory as JPG or PNG files.
3. Use the frontend interface to drag-and-drop or select these images for extraction.
4. Try using skewed, low-light, or shadow-heavy photos to see how the OpenCV deskew/contrast enhancement improves the OCR success rate!

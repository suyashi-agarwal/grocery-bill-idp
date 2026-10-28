# Grocery Bill IDP: 100% free & offline

Upload a bill (photo/PDF) -> OCR -> local AI -> items, prices, categories, totals -> save -> dashboard + Q&A.
No API key. No cost. Runs on your computer.

## One-time setup
1. Python 3.10-3.12 (onnxruntime may not support newer versions yet)
2. Install Ollama from https://ollama.com and download a model:
       ollama pull qwen2.5:7b        # ~4.7 GB, needs ~8 GB RAM, best accuracy
       ollama pull llama3.2:3b       # ~2 GB, for low-RAM machines (less accurate)
3. Install the Python packages:
       pip install -r requirements.txt

## Run
    streamlit run app.py
(Ollama must be running. On Windows/Mac it starts with the app; on Linux run `ollama serve`.)

To use the smaller model:
    Mac/Linux:  export OLLAMA_MODEL=llama3.2:3b
    Windows:    set OLLAMA_MODEL=llama3.2:3b

## Pipeline
1. extractor.py: RapidOCR reads the image/PDF, rows are re-assembled, local LLM returns JSON (schema.py)
2. validate.py : checks line maths, subtotal, total, missing fields
3. app.py      : you review/correct every cell before saving (important: local models make more mistakes)
4. storage.py  : SQLite (bills.db)
5. app.py      : dashboard, CSV export, Q&A (totals pre-computed with pandas)

## Tips for good results
- Photograph the bill flat, in good light, filling the frame
- Digital PDF bills are the most accurate (text is read directly, no OCR)
# grocery-bill-idp
